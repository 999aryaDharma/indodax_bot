"""Validated domain objects shared by research ingestion and storage."""

from .common import AggressorSide, CanonicalPair, QualityStatus, UtcTimestamp
from .market import CandleRecord, TradeEvent

__all__ = [
    "AggressorSide",
    "CandleRecord",
    "CanonicalPair",
    "QualityStatus",
    "TradeEvent",
    "UtcTimestamp",
]
