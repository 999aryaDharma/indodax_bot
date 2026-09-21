"""Canonical market health states and diagnostic reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MarketHealthState(StrEnum):
    """Explicit health classification for market data feeds."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    CLOCK_UNSAFE = "CLOCK_UNSAFE"


# Non-negotiable safety invariant: these states MUST halt new orders
UNSAFE_TRADING_STATES = frozenset(
    {
        MarketHealthState.STALE,
        MarketHealthState.UNAVAILABLE,
        MarketHealthState.CLOCK_UNSAFE,
    }
)


@dataclass(frozen=True)
class MarketHealthReport:
    """Immutable diagnostic report of market feed quality for a trading pair."""

    pair: str
    state: MarketHealthState
    as_of_utc: datetime
    last_event_time_utc: datetime | None = None
    age_seconds: float = 0.0
    clock_offset_ms: float = 0.0
    findings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def should_halt_new_orders(self) -> bool:
        """Fail-closed check: returns True if trading must be halted."""
        return self.state in UNSAFE_TRADING_STATES or not self.is_clean

    @property
    def is_clean(self) -> bool:
        """Feed is healthy without critical findings."""
        return self.state in (MarketHealthState.HEALTHY, MarketHealthState.DEGRADED) and not any(
            f.startswith("CRITICAL_")
            or f.startswith("HALT_")
            or f.startswith("INVALID_")
            or f.startswith("CROSSED_")
            for f in self.findings
        )
