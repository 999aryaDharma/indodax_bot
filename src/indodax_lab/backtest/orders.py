"""Order and fill execution models for backtesting and ledger accounting."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.backtest.costs import OrderRole, OrderSide


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class Fill(BaseModel):
    """An executed order fill to be journaled in the research ledger."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fill_id: str
    order_id: str
    event_id: str
    pair: str
    side: OrderSide
    role: OrderRole = OrderRole.TAKER
    qty: Decimal
    price: Decimal
    fees: Decimal = Decimal("0")
    timestamp: datetime
    fee_components: Mapping[str, Decimal] = Field(default_factory=dict)

    @field_validator("timestamp", mode="after")
    @classmethod
    def validate_timestamp_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "timestamp")

    @field_validator("qty", "price", mode="before")
    @classmethod
    def parse_positive_decimal(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_DECIMAL_REQUIRED")
        return dec

    @field_validator("fees", mode="before")
    @classmethod
    def parse_non_negative_fee(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec < 0:
            raise ValueError("NON_NEGATIVE_FEE_REQUIRED")
        return dec

    @property
    def gross(self) -> Decimal:
        """Gross trade notional in valuation currency (qty * price)."""
        return self.qty * self.price
