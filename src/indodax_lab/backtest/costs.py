"""Time-valid exchange cost schedules and fee resolution (COST-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class OrderSide(StrEnum):
    """Execution side for cost schedule lookup."""

    BUY = "buy"
    SELL = "sell"


class OrderRole(StrEnum):
    """Execution liquidity role."""

    MAKER = "maker"
    TAKER = "taker"


class UnknownCostScheduleError(ValueError):
    """Raised when looking up fees for an uncovered timestamp or market."""


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class CostScheduleInterval(BaseModel):
    """One valid cost schedule interval [valid_from, valid_to) for a given market/side/role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schedule_id: str
    market: str
    side: OrderSide
    role: OrderRole
    valid_from: datetime
    valid_to: datetime | None = None
    service_fee_rate: Decimal
    tax_rate: Decimal
    exchange_fee_rate: Decimal
    min_notional: Decimal
    precision: int = 0
    sources: tuple[str, ...]

    @field_validator("valid_from", mode="after")
    @classmethod
    def validate_valid_from_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "valid_from")

    @field_validator("valid_to", mode="after")
    @classmethod
    def validate_valid_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            return _ensure_utc(value, "valid_to")
        return None

    @field_validator("service_fee_rate", "tax_rate", "exchange_fee_rate", "min_notional", mode="before")
    @classmethod
    def parse_decimal_rate(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec < 0:
            raise ValueError("NON_NEGATIVE_RATE_REQUIRED")
        return dec

    @field_validator("sources", mode="before")
    @classmethod
    def require_sources(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, (list, tuple)):
            clean = tuple(str(v).strip() for v in value if str(v).strip())
            if clean:
                return clean
        raise ValueError("SOURCES_REQUIRED")

    @model_validator(mode="after")
    def validate_interval_bounds(self) -> Self:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError(f"INVALID_INTERVAL_BOUNDS:{self.valid_from} >= {self.valid_to}")
        return self


class CostScheduleTable(BaseModel):
    """Collection of time-valid cost schedule intervals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schedule_set_id: str
    version: str
    intervals: tuple[CostScheduleInterval, ...]

    @model_validator(mode="after")
    def validate_no_overlapping_intervals(self) -> Self:
        # Group by (market, side, role)
        grouped: dict[tuple[str, OrderSide, OrderRole], list[CostScheduleInterval]] = {}
        for interval in self.intervals:
            key = (interval.market, interval.side, interval.role)
            grouped.setdefault(key, []).append(interval)

        for key, group in grouped.items():
            sorted_group = sorted(group, key=lambda item: item.valid_from)
            for i in range(len(sorted_group) - 1):
                cur = sorted_group[i]
                nxt = sorted_group[i + 1]
                # If cur is open-ended (valid_to is None), any subsequent interval overlaps
                if cur.valid_to is None:
                    raise ValueError(f"OVERLAPPING_COST_SCHEDULE:{key}:{cur.schedule_id}:{nxt.schedule_id}")
                # If nxt starts before cur ends, intervals overlap
                if nxt.valid_from < cur.valid_to:
                    raise ValueError(f"OVERLAPPING_COST_SCHEDULE:{key}:{cur.schedule_id}:{nxt.schedule_id}")
        return self


class CostScheduleResolution(BaseModel):
    """The resolved point-in-time cost schedule components."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schedule_id: str
    market: str
    side: OrderSide
    role: OrderRole
    valid_from: datetime
    valid_to: datetime | None
    service_fee_rate: Decimal
    tax_rate: Decimal
    exchange_fee_rate: Decimal
    total_rate: Decimal
    min_notional: Decimal
    precision: int
    sources: tuple[str, ...]


def load_cost_schedule_table(path: Path) -> CostScheduleTable:
    """Load and validate an immutable cost schedule YAML file."""
    raw = Path(path).read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("COST_SCHEDULE_YAML_MUST_BE_MAPPING")
    return CostScheduleTable.model_validate(parsed)


def lookup_cost(
    table: CostScheduleTable,
    *,
    market: str,
    side: OrderSide | str,
    role: OrderRole | str,
    event_ts: datetime,
) -> CostScheduleResolution:
    """Resolve the active cost schedule for (market, side, role) at event_ts."""
    _ensure_utc(event_ts, "event_ts")

    clean_side = OrderSide(str(side).lower())
    clean_role = OrderRole(str(role).lower())

    for interval in table.intervals:
        if (
            interval.market == market
            and interval.side is clean_side
            and interval.role is clean_role
        ):
            # [valid_from, valid_to): valid_from <= event_ts < valid_to
            if interval.valid_from <= event_ts and (
                interval.valid_to is None or event_ts < interval.valid_to
            ):
                total_rate = (
                    interval.service_fee_rate + interval.tax_rate + interval.exchange_fee_rate
                )
                return CostScheduleResolution(
                    schedule_id=interval.schedule_id,
                    market=interval.market,
                    side=interval.side,
                    role=interval.role,
                    valid_from=interval.valid_from,
                    valid_to=interval.valid_to,
                    service_fee_rate=interval.service_fee_rate,
                    tax_rate=interval.tax_rate,
                    exchange_fee_rate=interval.exchange_fee_rate,
                    total_rate=total_rate,
                    min_notional=interval.min_notional,
                    precision=interval.precision,
                    sources=interval.sources,
                )

    raise UnknownCostScheduleError(
        f"UNKNOWN_COST_SCHEDULE: no cost schedule for market={market}, side={clean_side}, "
        f"role={clean_role} at event_ts={event_ts.isoformat()}"
    )


__all__ = [
    "CostScheduleInterval",
    "CostScheduleResolution",
    "CostScheduleTable",
    "OrderRole",
    "OrderSide",
    "UnknownCostScheduleError",
    "load_cost_schedule_table",
    "lookup_cost",
]
