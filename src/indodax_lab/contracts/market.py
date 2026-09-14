"""Pydantic contracts for canonical candle and public-trade records."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import AggressorSide, CanonicalPair, QualityStatus, UtcTimestamp


def _require_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError("monetary and quantity values must be Decimal")
    return value


class CandleRecord(BaseModel):
    """A final or in-progress OHLCV candle with source lineage and quality state."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(min_length=1)
    pair: CanonicalPair
    venue_symbol: str = Field(min_length=1)
    interval: Literal["1m", "5m", "15m", "1h", "4h", "1d"]
    open_time: UtcTimestamp
    close_time: UtcTimestamp
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal | None = None
    trade_count: int | None = Field(default=None, ge=0)
    is_closed: bool
    available_at: UtcTimestamp
    source: str = Field(min_length=1)
    ingested_at: UtcTimestamp
    quality_status: QualityStatus
    quality_flags: list[str]

    @field_validator("open", "high", "low", "close", "base_volume", "quote_volume", mode="before")
    @classmethod
    def validate_decimal_values(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        return _require_decimal(value)

    @model_validator(mode="after")
    def validate_candle_invariants(self) -> "CandleRecord":
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")
        if self.available_at < self.close_time:
            raise ValueError("available_at must not be earlier than close_time")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC values must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC values violate high/low bounds")
        if self.high < self.low:
            raise ValueError("high must not be below low")
        if self.base_volume < 0:
            raise ValueError("base_volume must be non-negative")
        if self.quote_volume is not None and self.quote_volume < 0:
            raise ValueError("quote_volume must be non-negative")
        return self


class TradeEvent(BaseModel):
    """One executed public trade, retaining both canonical and venue identities."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(min_length=1)
    pair: CanonicalPair
    venue_symbol: str = Field(min_length=1)
    event_ts: UtcTimestamp
    ingested_at: UtcTimestamp
    available_at: UtcTimestamp
    price: Decimal
    base_qty: Decimal
    quote_qty: Decimal
    source_event_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    sequence: int | None = Field(default=None, ge=0)
    aggressor_side: AggressorSide | None = None
    quality_status: QualityStatus
    quality_flags: list[str]

    @field_validator("price", "base_qty", "quote_qty", mode="before")
    @classmethod
    def validate_decimal_values(cls, value: object) -> Decimal:
        return _require_decimal(value)

    @model_validator(mode="after")
    def validate_trade_invariants(self) -> "TradeEvent":
        if min(self.price, self.base_qty, self.quote_qty) <= 0:
            raise ValueError("price and quantities must be positive")
        if self.available_at < self.ingested_at:
            raise ValueError("available_at must not be earlier than ingested_at")
        if self.ingested_at < self.event_ts and "CLOCK_ANOMALY" not in self.quality_flags:
            raise ValueError("pre-event ingestion requires the CLOCK_ANOMALY quality flag")
        return self
