"""Canonical market data gateway, clock safety, and feed quality package."""

from indodax_lab.market.clock import ClockGuard, ClockRegressionError, ClockReport
from indodax_lab.market.gateway import MarketGateway, MarketSnapshot
from indodax_lab.market.health import (
    UNSAFE_TRADING_STATES,
    MarketHealthReport,
    MarketHealthState,
)
from indodax_lab.market.quality import (
    DataQualityGuard,
    QualityValidationResult,
    TickerSnapshot,
)

__all__ = [
    "ClockGuard",
    "ClockReport",
    "ClockRegressionError",
    "DataQualityGuard",
    "MarketGateway",
    "MarketHealthReport",
    "MarketHealthState",
    "MarketSnapshot",
    "QualityValidationResult",
    "TickerSnapshot",
    "UNSAFE_TRADING_STATES",
]
