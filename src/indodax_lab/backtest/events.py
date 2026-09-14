"""Market events, bars, signals and execution outcome models (SIM-01)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.orders import Fill


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
    """Causal market bar for price execution and liquidity estimation."""

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
        if self.close_time <= self.open_time:
            raise ValueError(f"INVALID_BAR_CHRONOLOGY:{self.open_time} >= {self.close_time}")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("HIGH_LESS_THAN_SUB_PRICES")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("LOW_GREATER_THAN_SUB_PRICES")
        return self


class SignalIntent(BaseModel):
    """Strategy decision / order intent submitted to the execution simulator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_id: str
    decision_ts: datetime
    pair: str
    side: OrderSide
    desired_qty: Decimal
    limit_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    role_preference: OrderRole = OrderRole.TAKER
    strategy_id: str = "default_strat"
    time_in_force: str = "IOC"

    @field_validator("decision_ts", mode="after")
    @classmethod
    def validate_decision_ts_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "decision_ts")

    @field_validator("desired_qty", mode="before")
    @classmethod
    def parse_desired_qty(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_DESIRED_QTY_REQUIRED")
        return dec

    @field_validator("limit_price", "stop_loss", "take_profit", mode="before")
    @classmethod
    def parse_optional_price(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_PRICE_REQUIRED")
        return dec


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
