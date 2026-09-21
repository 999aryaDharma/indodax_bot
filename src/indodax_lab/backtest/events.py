"""Market events, bars, signals and execution outcome models (SIM-01)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.backtest.orders import Fill
from indodax_lab.contracts.decision import SignalIntent as SignalIntent


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class ExecutionStatus(StrEnum):
    """Conservative order execution statuses."""

    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"


class MarketBar(BaseModel):
    """Completed OHLCV observation; omission of availability declares close-time availability.

    Open liquidity is separate, already available evidence, never outcome volume.
    A prior closed volume is only a disclosed modeling proxy, not observed L2 depth.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    base_volume: Decimal
    quote_volume: Decimal
    available_at: datetime | None = None
    is_closed: bool = True
    open_liquidity_base_volume: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    open_liquidity_available_at: datetime | None = None

    @field_validator("open_time", "close_time", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime, info) -> datetime:
        return _ensure_utc(value, info.field_name or "time")

    @field_validator("open", "high", "low", "close", "base_volume", "quote_volume", mode="before")
    @classmethod
    def parse_decimal(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec < 0:
            raise ValueError("NON_NEGATIVE_FINITE_DECIMAL_REQUIRED")
        return dec

    @model_validator(mode="after")
    def validate_chronology_and_bounds(self) -> MarketBar:
        if not self.is_closed:
            raise ValueError("CLOSED_BAR_REQUIRED")
        if self.available_at is None:
            object.__setattr__(self, "available_at", self.close_time)
        _ensure_utc(self.available_at, "available_at")
        if self.available_at < self.close_time:
            raise ValueError("BAR_AVAILABLE_BEFORE_CLOSE")
        if (self.open_liquidity_base_volume is None) != (self.open_liquidity_available_at is None):
            raise ValueError("INCOMPLETE_LIQUIDITY_EVIDENCE")
        if self.open_liquidity_available_at is not None:
            _ensure_utc(self.open_liquidity_available_at, "open_liquidity_available_at")
            if self.open_liquidity_available_at > self.open_time:
                raise ValueError("FUTURE_OPEN_LIQUIDITY")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("POSITIVE_BAR_PRICE_REQUIRED")
        if self.close_time <= self.open_time:
            raise ValueError(f"INVALID_BAR_CHRONOLOGY:{self.open_time} >= {self.close_time}")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("HIGH_LESS_THAN_SUB_PRICES")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("LOW_GREATER_THAN_SUB_PRICES")
        return self


class ExecutionResult(BaseModel):
    """The outcome of an order intent processed by the execution simulator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_id: str
    status: ExecutionStatus
    fill: Fill | None = None
    filled_qty: Decimal = Decimal("0")
    remaining_qty: Decimal = Decimal("0")
    fill_price: Decimal | None = None
    reason_code: str | None = None
