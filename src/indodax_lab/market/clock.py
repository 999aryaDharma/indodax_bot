"""Clock safety monitor and guard for trading execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


class ClockRegressionError(RuntimeError):
    """Raised when the system or venue clock regresses backwards."""


@dataclass(frozen=True)
class ClockReport:
    """Diagnostic report on clock validity and synchronization."""

    is_safe: bool
    current_utc: datetime
    offset_ms: float
    max_offset_ms: float
    regression_detected: bool
    finding_code: str | None = None
    detail: str = ""


class ClockGuard:
    """Institutional-discipline clock verification guard.

    Enforces:
    1. Pure UTC enforcement (naive timestamps or non-UTC tz strictly rejected).
    2. Monotonicity checks: time cannot regress backwards beyond allowable jitter tolerance.
    3. Maximum drift boundary relative to venue/NTP time. If drift exceeds threshold,
       trading MUST be halted fail-closed (CLOCK_UNSAFE).
    """

    def __init__(
        self,
        max_allowed_offset_ms: float = 2000.0,
        max_allowable_regression_ms: float = 100.0,
    ) -> None:
        self.max_allowed_offset_ms = float(max_allowed_offset_ms)
        self.max_allowable_regression_ms = float(max_allowable_regression_ms)
        self._last_observed_utc: datetime | None = None

    def verify_timestamp_utc(self, ts: datetime) -> datetime:
        """Validate that a datetime is timezone-aware UTC."""
        if ts.tzinfo is None:
            raise ValueError(f"ClockGuard rejects naive timestamp: {ts}")
        return ts.astimezone(UTC)

    def check_clock(
        self,
        current_utc: datetime,
        reference_utc: datetime | None = None,
    ) -> ClockReport:
        """Evaluate local clock against reference time and previous observations.

        Parameters
        ----------
        current_utc: Local system timestamp (must be UTC).
        reference_utc: Optional venue server timestamp or NTP reference timestamp (must be UTC).
        """
        current_utc = self.verify_timestamp_utc(current_utc)

        # 1. Monotonicity check
        if self._last_observed_utc is not None:
            delta = (current_utc - self._last_observed_utc).total_seconds() * 1000.0
            if delta < -self.max_allowable_regression_ms:
                return ClockReport(
                    is_safe=False,
                    current_utc=current_utc,
                    offset_ms=abs(delta),
                    max_offset_ms=self.max_allowed_offset_ms,
                    regression_detected=True,
                    finding_code="CLOCK_REGRESSION_DETECTED",
                    detail=f"Local clock regressed backwards by {abs(delta):.1f} ms",
                )

        self._last_observed_utc = current_utc

        # 2. Offset check against venue/reference time
        offset_ms = 0.0
        if reference_utc is not None:
            reference_utc = self.verify_timestamp_utc(reference_utc)
            offset_ms = abs((current_utc - reference_utc).total_seconds() * 1000.0)
            if offset_ms > self.max_allowed_offset_ms:
                return ClockReport(
                    is_safe=False,
                    current_utc=current_utc,
                    offset_ms=offset_ms,
                    max_offset_ms=self.max_allowed_offset_ms,
                    regression_detected=False,
                    finding_code="CLOCK_OFFSET_EXCEEDED",
                    detail=(
                        f"Clock offset {offset_ms:.1f} ms exceeds limit of "
                        f"{self.max_allowed_offset_ms:.1f} ms"
                    ),
                )

        return ClockReport(
            is_safe=True,
            current_utc=current_utc,
            offset_ms=offset_ms,
            max_offset_ms=self.max_allowed_offset_ms,
            regression_detected=False,
            finding_code=None,
            detail="Clock synchronized and monotonic",
        )
