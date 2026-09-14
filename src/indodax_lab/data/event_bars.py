"""Deterministic information-driven bar challengers over reliable public trades."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.contracts import QualityStatus, TradeEvent, UtcTimestamp

from .bars import BarType, SilverBar, _bar_from_trades, _require_utc, _validate_trade_runtime
from .checksums import sha256_bytes

_IDENTITY_PATTERN = r"^sha256:[0-9a-f]{64}$"
EventType = Literal[BarType.CUSUM, BarType.RANGE, BarType.VOLUME, BarType.DOLLAR]


def _exact_positive_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("threshold must not use bool or binary float")
    if isinstance(value, (str, int)):
        value = Decimal(str(value))
    if not isinstance(value, Decimal) or value <= 0:
        raise ValueError("threshold must be positive")
    return value


class ThresholdArtifact(BaseModel):
    """A threshold fitted exclusively from a declared historical training window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str = Field(pattern=_IDENTITY_PATTERN)
    artifact_version: str = Field(default="1.0.0", min_length=1)
    threshold: Decimal
    train_end: UtcTimestamp
    available_at: UtcTimestamp

    @field_validator("threshold", mode="before")
    @classmethod
    def validate_threshold(cls, value: object) -> Decimal:
        return _exact_positive_decimal(value)


class EventThresholdConfig(BaseModel):
    """One registered event representation and its fixed or fitted threshold."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    bar_type: EventType
    fixed_threshold: Decimal | None = None
    fit_artifact: ThresholdArtifact | None = None

    @field_validator("fixed_threshold", mode="before")
    @classmethod
    def validate_fixed_threshold(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        return _exact_positive_decimal(value)

    @model_validator(mode="after")
    def validate_threshold_source(self) -> EventThresholdConfig:
        if (self.fixed_threshold is None) == (self.fit_artifact is None):
            raise ValueError("event threshold requires exactly one fixed value or fit artifact")
        return self


class EventBarConfig(BaseModel):
    """Strict event-bar challenger registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    availability_lag_seconds: int = Field(ge=0)
    thresholds: tuple[EventThresholdConfig, ...]

    @model_validator(mode="after")
    def validate_registry(self) -> EventBarConfig:
        if not self.thresholds:
            raise ValueError("event-bar config requires at least one threshold")
        ids = [threshold.config_id for threshold in self.thresholds]
        if len(set(ids)) != len(ids):
            raise ValueError("event threshold config IDs must be unique")
        return self


class LoadedEventBarConfig(BaseModel):
    """Validated event config plus exact YAML byte identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: EventBarConfig
    source_id: str = Field(pattern=_IDENTITY_PATTERN)


class EventBarRemainder(BaseModel):
    """Auditable input events that did not reach a final event-bar boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    closed: Literal[False] = False
    pair: str = Field(pattern=r"^[a-z0-9]+_[a-z0-9]+$")
    bar_type: EventType
    threshold_config_id: str
    threshold_value: Decimal
    threshold_provenance: Literal["FIXED", "FITTED"]
    threshold_artifact_id: str | None
    threshold_artifact_version: str | None
    threshold_train_end: UtcTimestamp | None
    threshold_available_at: UtcTimestamp | None
    source_snapshot_id: str = Field(pattern=_IDENTITY_PATTERN)
    stream_session_id: str = Field(min_length=1)
    source_event_ids: tuple[str, ...]
    first_event_ts: UtcTimestamp
    last_event_ts: UtcTimestamp
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    reason: Literal["CONTINUITY_GAP", "SESSION_CHANGE"] | None = None

    @field_validator(
        "open",
        "high",
        "low",
        "close",
        "base_volume",
        "quote_volume",
        "threshold_value",
        mode="before",
    )
    @classmethod
    def validate_decimals(cls, value: object) -> Decimal:
        if not isinstance(value, Decimal):
            raise ValueError("remainder values must be Decimal")
        return value


class EventBarBuildResult(BaseModel):
    """Only final bars plus the explicitly unclosed final input bucket."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bars: tuple[SilverBar, ...]
    remainder: EventBarRemainder | None
    quarantined_remainders: tuple[EventBarRemainder, ...]
    threshold_value: Decimal
    threshold_provenance: Literal["FIXED", "FITTED"]
    threshold_artifact_id: str | None
    threshold_artifact_version: str | None
    threshold_train_end: UtcTimestamp | None
    threshold_available_at: UtcTimestamp | None


class TradeContinuity(BaseModel):
    """Explicit stream session and adjacency fact for one source trade identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_event_id: str = Field(min_length=1)
    stream_session_id: str = Field(min_length=1)
    continuous_from_previous: bool


def load_event_bar_config(path: Path) -> LoadedEventBarConfig:
    """Load an event-bar registry without ignoring unknown YAML fields."""
    raw = Path(path).read_bytes()
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("event-bar config YAML must contain one mapping")
    return LoadedEventBarConfig(
        config=EventBarConfig.model_validate(parsed), source_id=f"sha256:{sha256_bytes(raw)}"
    )


def build_event_bars(
    trades: Iterable[TradeEvent],
    *,
    bar_type: EventType,
    threshold: Decimal | ThresholdArtifact,
    threshold_config_id: str,
    source_snapshot_id: str,
    build_as_of: datetime,
    availability_lag: timedelta,
    continuity: Iterable[TradeContinuity] | None = None,
    policy_id: str = "direct-event-v1",
    include_partial: bool = False,
) -> EventBarBuildResult:
    """Close event bars on deterministic thresholds, never using data after build_as_of."""
    if bar_type not in {BarType.CUSUM, BarType.RANGE, BarType.VOLUME, BarType.DOLLAR}:
        raise ValueError("event bars require CUSUM, RANGE, VOLUME, or DOLLAR bar_type")
    if include_partial:
        raise ValueError("partial event bars cannot be published as final")
    _require_utc(build_as_of, "build_as_of")
    if availability_lag < timedelta(0):
        raise ValueError("availability_lag must be non-negative")
    if not threshold_config_id:
        raise ValueError("threshold_config_id is required")

    ordered = _validate_event_trades(trades, build_as_of=build_as_of)
    segments = _continuity_segments(ordered, continuity)
    artifact_id: str | None = None
    artifact_version: str | None = None
    artifact_train_end: datetime | None = None
    artifact_available_at: datetime | None = None
    if isinstance(threshold, ThresholdArtifact):
        if not ordered:
            raise ValueError("fitted threshold requires at least one eligible event")
        first = ordered[0]
        if threshold.train_end >= first.event_ts:
            raise ValueError("threshold train_end must be strictly before first event")
        if threshold.available_at > first.available_at:
            raise ValueError("threshold available_at must be by first input availability")
        if threshold.available_at > build_as_of:
            raise ValueError("threshold available_at is in the future relative to build as-of")
        threshold_value = threshold.threshold
        artifact_id = threshold.artifact_id
        artifact_version = threshold.artifact_version
        artifact_train_end = threshold.train_end
        artifact_available_at = threshold.available_at
        provenance: Literal["FIXED", "FITTED"] = "FITTED"
    else:
        threshold_value = _exact_positive_decimal(threshold)
        provenance = "FIXED"

    bars: list[SilverBar] = []
    quarantined: list[EventBarRemainder] = []
    final_remainder: EventBarRemainder | None = None
    for index, segment in enumerate(segments):
        final_buckets, remainder_trades = _event_buckets(
            segment.trades, bar_type=bar_type, threshold=threshold_value
        )
        bars.extend(
            _bar_from_trades(
                bucket.trades,
                bar_type=bar_type,
                interval=None,
                threshold_config_id=threshold_config_id,
                threshold_value=threshold_value,
                threshold_provenance=provenance,
                threshold_artifact_id=artifact_id,
                threshold_artifact_version=artifact_version,
                threshold_train_end=artifact_train_end,
                threshold_available_at=artifact_available_at,
                policy_id=policy_id,
                open_time=bucket.trades[0].event_ts,
                close_time=bucket.trades[-1].event_ts,
                availability_lag=availability_lag,
                minimum_available_at=artifact_available_at,
                source_snapshot_id=source_snapshot_id,
                source=bucket.trades[0].source,
                source_session_id=segment.stream_session_id,
                boundary_direction=bucket.direction,
            )
            for bucket in final_buckets
        )
        if not remainder_trades:
            continue
        if index < len(segments) - 1:
            quarantined.append(
                _remainder(
                    remainder_trades,
                    bar_type=bar_type,
                    threshold_config_id=threshold_config_id,
                    threshold_value=threshold_value,
                    threshold_provenance=provenance,
                    threshold_artifact_id=artifact_id,
                    threshold_artifact_version=artifact_version,
                    threshold_train_end=artifact_train_end,
                    threshold_available_at=artifact_available_at,
                    source_snapshot_id=source_snapshot_id,
                    stream_session_id=segment.stream_session_id,
                    reason=segment.boundary_reason,
                )
            )
        else:
            final_remainder = _remainder(
                remainder_trades,
                bar_type=bar_type,
                threshold_config_id=threshold_config_id,
                threshold_value=threshold_value,
                threshold_provenance=provenance,
                threshold_artifact_id=artifact_id,
                threshold_artifact_version=artifact_version,
                threshold_train_end=artifact_train_end,
                threshold_available_at=artifact_available_at,
                source_snapshot_id=source_snapshot_id,
                stream_session_id=segment.stream_session_id,
                reason=None,
            )
    return EventBarBuildResult(
        bars=tuple(bars),
        remainder=final_remainder,
        quarantined_remainders=tuple(quarantined),
        threshold_value=threshold_value,
        threshold_provenance=provenance,
        threshold_artifact_id=artifact_id,
        threshold_artifact_version=artifact_version,
        threshold_train_end=artifact_train_end,
        threshold_available_at=artifact_available_at,
    )


class _ClosedBucket(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    trades: tuple[TradeEvent, ...]
    direction: Literal["POSITIVE", "NEGATIVE"] | None


class _ContinuitySegment(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    trades: tuple[TradeEvent, ...]
    stream_session_id: str
    boundary_reason: Literal["CONTINUITY_GAP", "SESSION_CHANGE"] | None


def _event_buckets(
    trades: Sequence[TradeEvent], *, bar_type: EventType, threshold: Decimal
) -> tuple[tuple[_ClosedBucket, ...], tuple[TradeEvent, ...]]:
    closed: list[_ClosedBucket] = []
    bucket: list[TradeEvent] = []
    positive = Decimal(0)
    negative = Decimal(0)
    previous_price: Decimal | None = None

    for trade in trades:
        bucket.append(trade)
        direction: Literal["POSITIVE", "NEGATIVE"] | None = None
        reached = False
        if bar_type is BarType.CUSUM:
            if previous_price is not None:
                change = trade.price - previous_price
                positive = max(Decimal(0), positive + change)
                negative = min(Decimal(0), negative + change)
                if positive >= threshold:
                    reached = True
                    direction = "POSITIVE"
                elif negative <= -threshold:
                    reached = True
                    direction = "NEGATIVE"
            previous_price = trade.price
        elif bar_type is BarType.RANGE:
            reached = (
                max(row.price for row in bucket) - min(row.price for row in bucket) >= threshold
            )
        elif bar_type is BarType.VOLUME:
            reached = sum((row.base_qty for row in bucket), Decimal(0)) >= threshold
        else:
            reached = sum((row.quote_qty for row in bucket), Decimal(0)) >= threshold

        if reached:
            closed.append(_ClosedBucket(trades=tuple(bucket), direction=direction))
            bucket = []
            positive = Decimal(0)
            negative = Decimal(0)

    return tuple(closed), tuple(bucket)


def _validate_event_trades(
    trades: Iterable[TradeEvent],
    *,
    build_as_of: datetime,
) -> tuple[TradeEvent, ...]:
    rows = tuple(trades)
    if any(trade.quality_status is not QualityStatus.PASS for trade in rows):
        raise ValueError("event bars require a reliable PASS trade session")
    pairs = {trade.pair.pair for trade in rows}
    if len(pairs) > 1:
        raise ValueError("all event-bar trades must use one canonical pair")
    if len({trade.source for trade in rows}) > 1:
        raise ValueError("all event-bar trades must use one source provider")
    seen: dict[str, TradeEvent] = {}
    for trade in rows:
        _validate_trade_runtime(trade)
        if trade.event_ts > build_as_of or trade.available_at > build_as_of:
            raise ValueError("future trade is unavailable at build as-of")
        existing = seen.get(trade.source_event_id)
        if existing is not None:
            raise ValueError(f"duplicate source_event_id: {trade.source_event_id}")
        seen[trade.source_event_id] = trade
    return tuple(sorted(seen.values(), key=lambda trade: (trade.event_ts, trade.source_event_id)))


def _remainder(
    trades: Sequence[TradeEvent],
    *,
    bar_type: EventType,
    threshold_config_id: str,
    threshold_value: Decimal,
    threshold_provenance: Literal["FIXED", "FITTED"],
    threshold_artifact_id: str | None,
    threshold_artifact_version: str | None,
    threshold_train_end: datetime | None,
    threshold_available_at: datetime | None,
    source_snapshot_id: str,
    stream_session_id: str,
    reason: Literal["CONTINUITY_GAP", "SESSION_CHANGE"] | None,
) -> EventBarRemainder:
    return EventBarRemainder(
        pair=trades[0].pair.pair,
        bar_type=bar_type,
        threshold_config_id=threshold_config_id,
        threshold_value=threshold_value,
        threshold_provenance=threshold_provenance,
        threshold_artifact_id=threshold_artifact_id,
        threshold_artifact_version=threshold_artifact_version,
        threshold_train_end=threshold_train_end,
        threshold_available_at=threshold_available_at,
        source_snapshot_id=source_snapshot_id,
        stream_session_id=stream_session_id,
        source_event_ids=tuple(trade.source_event_id for trade in trades),
        first_event_ts=trades[0].event_ts,
        last_event_ts=trades[-1].event_ts,
        open=trades[0].price,
        high=max(trade.price for trade in trades),
        low=min(trade.price for trade in trades),
        close=trades[-1].price,
        base_volume=sum((trade.base_qty for trade in trades), Decimal(0)),
        quote_volume=sum((trade.quote_qty for trade in trades), Decimal(0)),
        reason=reason,
    )


def _continuity_segments(
    trades: Sequence[TradeEvent], continuity: Iterable[TradeContinuity] | None
) -> tuple[_ContinuitySegment, ...]:
    if continuity is None:
        raise ValueError("event bars require explicit reliable stream continuity and session")
    records = tuple(continuity)
    by_id = {record.source_event_id: record for record in records}
    if len(by_id) != len(records):
        raise ValueError("duplicate continuity source_event_id")
    event_ids = {trade.source_event_id for trade in trades}
    if set(by_id) != event_ids:
        raise ValueError("continuity identities must exactly match event identities")
    if not trades:
        return ()
    segments: list[_ContinuitySegment] = []
    current: list[TradeEvent] = []
    current_session = by_id[trades[0].source_event_id].stream_session_id
    first = by_id[trades[0].source_event_id]
    if first.continuous_from_previous:
        raise ValueError("first event cannot claim continuity from unavailable history")
    for index, trade in enumerate(trades):
        record = by_id[trade.source_event_id]
        if index == 0:
            current.append(trade)
            continue
        changed_session = record.stream_session_id != current_session
        if changed_session and record.continuous_from_previous:
            raise ValueError("an event cannot be continuous across stream sessions")
        if changed_session or not record.continuous_from_previous:
            reason: Literal["CONTINUITY_GAP", "SESSION_CHANGE"] = (
                "SESSION_CHANGE" if changed_session else "CONTINUITY_GAP"
            )
            segments.append(
                _ContinuitySegment(
                    trades=tuple(current),
                    stream_session_id=current_session,
                    boundary_reason=reason,
                )
            )
            current = [trade]
            current_session = record.stream_session_id
        else:
            current.append(trade)
    segments.append(
        _ContinuitySegment(
            trades=tuple(current), stream_session_id=current_session, boundary_reason=None
        )
    )
    return tuple(segments)
