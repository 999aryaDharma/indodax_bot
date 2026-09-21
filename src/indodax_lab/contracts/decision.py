"""Shared decision contracts used by backtest, shadow, and production adapters."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from indodax_lab.backtest.costs import OrderRole, OrderSide


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class SignalIntent(BaseModel):
    """Strategy decision / order intent submitted to an execution adapter."""

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


__all__ = ["SignalIntent"]
