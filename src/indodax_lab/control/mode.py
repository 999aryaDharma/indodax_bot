"""Execution mode definitions and autonomous trading constraints."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecutionMode(StrEnum):
    """Institutional execution operating modes.

    Progression path:
    DISABLED -> READ_ONLY -> SHADOW -> MANUAL_APPROVAL -> AUTONOMOUS_LIMITED
    """

    DISABLED = "DISABLED"
    READ_ONLY = "READ_ONLY"
    SHADOW = "SHADOW"
    MANUAL_APPROVAL = "MANUAL_APPROVAL"
    AUTONOMOUS_LIMITED = "AUTONOMOUS_LIMITED"

    @property
    def can_read_market(self) -> bool:
        return self != ExecutionMode.DISABLED

    @property
    def can_reconcile(self) -> bool:
        return self != ExecutionMode.DISABLED

    @property
    def can_write_venue(self) -> bool:
        return self in {ExecutionMode.MANUAL_APPROVAL, ExecutionMode.AUTONOMOUS_LIMITED}

    @property
    def is_shadow(self) -> bool:
        return self == ExecutionMode.SHADOW


class AutonomousLimits(BaseModel):
    """Hard capital, risk, and asset boundaries for AUTONOMOUS_LIMITED mode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_single_order_notional: Decimal = Field(default=Decimal("500000"))  # 500,000 IDR
    max_daily_loss_notional: Decimal = Field(default=Decimal("1000000"))  # 1,000,000 IDR
    allowed_pairs: tuple[str, ...] = Field(default=("btc_idr",))

    @field_validator("max_single_order_notional", "max_daily_loss_notional", mode="before")
    @classmethod
    def parse_positive_decimal(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_DECIMAL_REQUIRED")
        return dec

    @field_validator("allowed_pairs", mode="after")
    @classmethod
    def normalize_pairs(cls, pairs: tuple[str, ...]) -> tuple[str, ...]:
        if not pairs:
            raise ValueError("ALLOWED_PAIRS_REQUIRED")
        return tuple(p.strip().lower() for p in pairs)
