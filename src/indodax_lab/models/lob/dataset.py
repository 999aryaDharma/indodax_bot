"""Forward limit order book dataset eligibility and sequence window gating (LOB-01).

Guarantees:
1. LOB-01-AC0: LOB dataset only permits PASS sessions with >=90 day coverage and sufficient effective events.
2. LOB-01-AC1: Candle data cannot substitute for order book depth fixtures (CandleSubstitutionForbiddenError).
3. LOB-01-AC2: Gaps in book updates break sequence windows rather than bridging or interpolating.
4. LOB-01-AC3: High event row count across few days fails the >=90 day calendar coverage gate.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
import pandas as pd
from pydantic import BaseModel, ConfigDict, model_validator, field_validator


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CandleSubstitutionForbiddenError(ValueError):
    """Raised when candle / OHLCV data is provided instead of limit order book depth updates."""


class SessionGapBrokenWindowError(ValueError):
    """Raised when a sequence window crosses an unobserved or corrupted time gap."""


class InsufficientCoverageGateError(ValueError):
    """Raised when an order book dataset fails the 90-day coverage gate or event threshold."""


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------


class SessionStatus(StrEnum):
    """Quality and completeness status of an order book collection session."""

    PASS = "pass"
    FAIL = "fail"
    QUARANTINE = "quarantine"


class BookLevel(BaseModel):
    """Single price and volume level in the order book."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    price: Decimal
    volume: Decimal

    @field_validator("price", "volume")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("POSITIVE_DECIMAL_REQUIRED")
        return v


class BookSnapshot(BaseModel):
    """Point-in-time snapshot of limit order book depth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    pair: str
    session_id: str
    bids: list[BookLevel]
    asks: list[BookLevel]
    sequence_id: int | None = None

    @field_validator("timestamp")
    @classmethod
    def validate_utc(cls, dt: datetime) -> datetime:
        if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED")
        return dt

    @model_validator(mode="after")
    def validate_book(self) -> BookSnapshot:
        if not self.bids or not self.asks:
            raise ValueError("NON_EMPTY_BOOK_REQUIRED")
        if any(
            a.price <= b.price for a, b in zip(self.bids, self.bids[1:], strict=False)
        ):
            raise ValueError("BIDS_MUST_BE_DESCENDING")
        if any(
            a.price >= b.price for a, b in zip(self.asks, self.asks[1:], strict=False)
        ):
            raise ValueError("ASKS_MUST_BE_ASCENDING")
        if self.bids[0].price >= self.asks[0].price:
            raise ValueError("CROSSED_BOOK_FORBIDDEN")
        if not self.pair or not self.session_id:
            raise ValueError("PAIR_AND_SESSION_ID_REQUIRED")
        return self


class LOBSessionMetadata(BaseModel):
    """Metadata record for a recorded order book session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    pair: str
    start_ts: datetime
    end_ts: datetime
    event_count: int
    status: SessionStatus
    regime: str = "normal"

    @field_validator("start_ts", "end_ts")
    @classmethod
    def validate_utc(cls, dt: datetime) -> datetime:
        if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED")
        return dt

    @model_validator(mode="after")
    def validate_session(self) -> LOBSessionMetadata:
        if self.start_ts > self.end_ts:
            raise ValueError("SESSION_START_AFTER_END")
        if self.event_count < 0:
            raise ValueError("NEGATIVE_EVENT_COUNT")
        if not self.session_id or not self.pair:
            raise ValueError("PAIR_AND_SESSION_ID_REQUIRED")
        return self


class LOBEligibilityReport(BaseModel):
    """Summary report for order book dataset eligibility."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_eligible: bool
    distinct_pass_days: int
    total_events: int
    regimes: dict[str, int]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Eligibility Gate & Window Segmenter
# ---------------------------------------------------------------------------


class LOBDatasetEligibilityGate:
    """Eligibility gate enforcing >=90-day PASS coverage and contiguous sequence windows."""

    def __init__(
        self,
        min_coverage_days: int = 90,
        min_events_per_day: int = 100,
        max_gap_seconds: float = 60.0,
    ) -> None:
        self.min_coverage_days = min_coverage_days
        self.min_events_per_day = min_events_per_day
        self.max_gap_seconds = max_gap_seconds

    def validate_book_schema(self, data: Any) -> None:
        """Reject candle / OHLCV data or payloads missing order book depth levels."""
        candle_fields = {"open", "high", "low", "close", "ohlcv"}
        if isinstance(data, dict):
            keys_lower = {str(k).lower() for k in data.keys()}
            if keys_lower & candle_fields:
                raise CandleSubstitutionForbiddenError(
                    "CANDLE_SUBSTITUTION_FORBIDDEN: OHLCV candle data cannot substitute for LOB depth snapshots"
                )
            if "bids" not in keys_lower or "asks" not in keys_lower:
                raise CandleSubstitutionForbiddenError(
                    "CANDLE_SUBSTITUTION_FORBIDDEN: Order book payload must contain bids and asks depth levels"
                )
        elif isinstance(data, pd.DataFrame):
            cols_lower = {str(col).lower() for col in data.columns}
            if cols_lower & candle_fields:
                raise CandleSubstitutionForbiddenError(
                    "CANDLE_SUBSTITUTION_FORBIDDEN: OHLCV candle dataframe cannot substitute for LOB depth snapshots"
                )
            if not ("bids" in cols_lower and "asks" in cols_lower):
                raise CandleSubstitutionForbiddenError(
                    "CANDLE_SUBSTITUTION_FORBIDDEN: Order book dataframe must contain bids and asks columns"
                )

    def evaluate_coverage(self, sessions: list[LOBSessionMetadata]) -> LOBEligibilityReport:
        """Evaluate whether sessions satisfy the >=90 day PASS coverage gate."""
        pass_sessions = [s for s in sessions if s.status == SessionStatus.PASS]

        # Each pair must independently satisfy both coverage and the daily event floor.
        events_by_pair_day: dict[tuple[str, date], int] = {}
        for session in pass_sessions:
            key = (session.pair, session.start_ts.date())
            events_by_pair_day[key] = events_by_pair_day.get(key, 0) + session.event_count
        pairs = {pair for pair, _ in events_by_pair_day}
        days_by_pair = {
            pair: {
                day
                for (session_pair, day), count in events_by_pair_day.items()
                if session_pair == pair and count >= self.min_events_per_day
            }
            for pair in pairs
        }
        underfilled = any(
            count < self.min_events_per_day for count in events_by_pair_day.values()
        )
        num_days = min((len(days) for days in days_by_pair.values()), default=0)
        if not pairs:
            raise InsufficientCoverageGateError("COVERAGE_DAYS_INSUFFICIENT: No PASS sessions")
        if underfilled:
            raise InsufficientCoverageGateError(
                "INSUFFICIENT_EVENTS_PER_PAIR_DAY: Every PASS pair/day must meet "
                "the configured event floor"
            )
        if any(len(days) < self.min_coverage_days for days in days_by_pair.values()):
            raise InsufficientCoverageGateError(
                f"COVERAGE_DAYS_INSUFFICIENT: Each pair requires >= "
                f"{self.min_coverage_days} distinct PASS days"
            )

        total_events = sum(events_by_pair_day.values())

        # Regimes aggregation
        regime_counts: dict[str, int] = {}
        for s in pass_sessions:
            regime_counts[s.regime] = regime_counts.get(s.regime, 0) + 1

        return LOBEligibilityReport(
            is_eligible=True,
            distinct_pass_days=num_days,
            total_events=total_events,
            regimes=regime_counts,
            generated_at=datetime.now(UTC),
        )

    def validate_contiguous_window(
        self,
        snapshots: list[BookSnapshot],
        max_gap_seconds: float | None = None,
    ) -> None:
        """Validate that snapshots form a strictly contiguous time series without gaps."""
        gap_thresh = max_gap_seconds if max_gap_seconds is not None else self.max_gap_seconds
        for i in range(1, len(snapshots)):
            previous, current = snapshots[i - 1], snapshots[i]
            same_stream = (current.pair, current.session_id) == (
                previous.pair,
                previous.session_id,
            )
            if not same_stream:
                raise ValueError("LOB_WINDOW_CROSSES_PAIR_OR_SESSION")
            delta = (snapshots[i].timestamp - snapshots[i - 1].timestamp).total_seconds()
            if delta < 0:
                raise ValueError("NON_CHRONOLOGICAL_SNAPSHOTS_DETECTED")
            if (
                same_stream
                and previous.sequence_id is not None
                and current.sequence_id is not None
                and current.sequence_id <= previous.sequence_id
            ):
                raise ValueError("NON_MONOTONIC_SEQUENCE_ID")
            if (
                previous.sequence_id is not None
                and current.sequence_id is not None
                and current.sequence_id != previous.sequence_id + 1
            ):
                raise SessionGapBrokenWindowError("LOB_SEQUENCE_GAP_DETECTED")
            if delta > gap_thresh:
                raise SessionGapBrokenWindowError(
                    f"LOB_WINDOW_GAP_DETECTED: Gap of {delta:.1f}s between index {i-1} and {i} "
                    f"exceeds max allowable threshold {gap_thresh:.1f}s"
                )

    def segment_continuous_windows(
        self,
        snapshots: list[BookSnapshot],
        window_len: int,
        stride: int = 1,
        max_gap_seconds: float | None = None,
    ) -> list[list[BookSnapshot]]:
        """Segment raw snapshots into continuous sequence windows without bridging gaps."""
        gap_thresh = max_gap_seconds if max_gap_seconds is not None else self.max_gap_seconds
        if len(snapshots) < window_len:
            return []

        # Partition into contiguous runs
        contiguous_runs: list[list[BookSnapshot]] = []
        current_run: list[BookSnapshot] = [snapshots[0]]

        for i in range(1, len(snapshots)):
            previous, current = snapshots[i - 1], snapshots[i]
            delta = (current.timestamp - previous.timestamp).total_seconds()
            if delta < 0:
                raise ValueError("NON_CHRONOLOGICAL_SNAPSHOTS_DETECTED")
            boundary_changed = (current.pair, current.session_id) != (
                previous.pair,
                previous.session_id,
            )
            if (
                not boundary_changed
                and previous.sequence_id is not None
                and current.sequence_id is not None
                and current.sequence_id <= previous.sequence_id
            ):
                raise ValueError("NON_MONOTONIC_SEQUENCE_ID")
            sequence_gap = (
                not boundary_changed
                and previous.sequence_id is not None
                and current.sequence_id is not None
                and current.sequence_id != previous.sequence_id + 1
            )
            if delta > gap_thresh or boundary_changed or sequence_gap:
                contiguous_runs.append(current_run)
                current_run = [current]
            else:
                current_run.append(current)
        contiguous_runs.append(current_run)

        # From each contiguous run, slice rolling windows of size window_len
        valid_windows: list[list[BookSnapshot]] = []
        step = max(1, stride)
        for run in contiguous_runs:
            if len(run) >= window_len:
                for start_idx in range(0, len(run) - window_len + 1, step):
                    valid_windows.append(run[start_idx : start_idx + window_len])

        return valid_windows
