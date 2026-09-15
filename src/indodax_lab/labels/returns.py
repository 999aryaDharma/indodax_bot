"""Execution-aligned net return labels with strict causality and cost integration (LABEL-01)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Mapping, Sequence, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.backtest.costs import (
    CostScheduleTable,
    OrderRole,
    OrderSide,
    UnknownCostScheduleError,
    lookup_cost,
)


class NetReturnConfig(BaseModel):
    """Configuration for execution-aligned net return labelling."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    label_set_id: str = "net_return"
    version: str = "2.0.0"
    horizon: timedelta = timedelta(hours=4)
    edge_margin: Decimal = Decimal("0.001")
    cost_schedule_table: CostScheduleTable | None = None
    execution_model_version: str = "open_price_proxy_v2"

    @field_validator("execution_model_version")
    @classmethod
    def require_proxy_model(cls, value: str) -> str:
        if value != "open_price_proxy_v2":
            raise ValueError("UNSUPPORTED_EXECUTION_MODEL: rebuild labels with open_price_proxy_v2; simulator fill alignment is not implemented")
        return value


class NetReturnLabel(BaseModel):
    """One immutable label measuring net proceeds relative to gross cash debit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    label_set_id: str
    label_version: str
    pair: str
    decision_ts: datetime
    entry_ts: datetime | None = None
    exit_ts: datetime | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    gross_return: Decimal | None = None
    buy_cost: Decimal | None = None
    sell_cost: Decimal | None = None
    slippage_cost: Decimal = Decimal("0")
    net_return: Decimal | None = None
    binary_label: int | None = None
    cost_schedule_id: str | None = None
    execution_model_version: Literal["open_price_proxy_v2"] = "open_price_proxy_v2"
    execution_fidelity: Literal["RESEARCH_PRICE_PROXY_ONLY"] = "RESEARCH_PRICE_PROXY_ONLY"
    promotion_eligible: Literal[False] = False
    label_available_at: datetime | None = None
    status: str = "VALID"
    exclusion_reason: str | None = None


def _get_val(bar: Any, key: str) -> Any:
    if isinstance(bar, Mapping):
        return bar[key]
    return getattr(bar, key)


def _require_utc(value: datetime) -> datetime:
    if pd.isna(value) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED")
    return value


def build_net_return_label(
    sample_id: str,
    pair: str,
    decision_ts: datetime,
    bars: Sequence[Any],
    config: NetReturnConfig,
) -> NetReturnLabel:
    """Build a single net return label enforcing execution causality and cost basis."""
    if not bars:
        raise ValueError("EMPTY_BARS")
    _require_utc(decision_ts)

    bars = [bar for bar in bars if _get_val(bar, "pair") == pair]
    if not bars:
        raise ValueError("NO_BARS_FOR_PAIR")
    for bar in bars:
        _require_utc(_get_val(bar, "open_time"))

    # Enforce strict causality: entry cannot occur before or at decision if decision is after all bars
    max_open = max(_get_val(b, "open_time") for b in bars)
    if decision_ts > max_open:
        raise ValueError("ENTRY_BEFORE_OR_AT_DECISION")

    # Find earliest eligible execution bar at next-open: open_time >= decision_ts
    eligible_bars = [b for b in bars if _get_val(b, "open_time") >= decision_ts]
    if not eligible_bars:
        raise ValueError("ENTRY_BEFORE_OR_AT_DECISION")

    sorted_bars = sorted(eligible_bars, key=lambda b: _get_val(b, "open_time"))
    entry_bar = sorted_bars[0]
    entry_ts = _get_val(entry_bar, "open_time")
    entry_price = Decimal(str(_get_val(entry_bar, "open")))

    target_exit_ts = entry_ts + config.horizon

    # Check horizon completeness
    exit_candidates = [b for b in bars if _get_val(b, "open_time") == target_exit_ts]
    if not exit_candidates:
        return NetReturnLabel(
            sample_id=sample_id,
            label_set_id=config.label_set_id,
            label_version=config.version,
            pair=pair,
            decision_ts=decision_ts,
            entry_ts=entry_ts,
            exit_ts=target_exit_ts,
            status="EXCLUDED",
            exclusion_reason="INCOMPLETE_HORIZON",
        )

    exit_bar = exit_candidates[0]
    exit_price = Decimal(str(_get_val(exit_bar, "open")))

    outcome_bars = [
        bar for bar in sorted_bars
        if _get_val(bar, "open_time") <= target_exit_ts
    ]
    open_times = [_get_val(bar, "open_time") for bar in outcome_bars]
    if len(set(open_times)) != len(open_times):
        raise ValueError("DUPLICATE_OUTCOME_BAR")
    for bar in outcome_bars:
        _require_utc(_get_val(bar, "close_time"))
        _require_utc(_get_val(bar, "available_at"))
        if (
            _get_val(bar, "is_closed")
            and _get_val(bar, "available_at") < _get_val(bar, "close_time")
        ):
            raise ValueError("OUTCOME_AVAILABILITY_BEFORE_CLOSE")
    if any(
        _get_val(left, "close_time") != _get_val(right, "open_time")
        for left, right in zip(outcome_bars, outcome_bars[1:])
    ):
        return NetReturnLabel(
            sample_id=sample_id, label_set_id=config.label_set_id,
            label_version=config.version, pair=pair, decision_ts=decision_ts,
            entry_ts=entry_ts, exit_ts=target_exit_ts, status="EXCLUDED",
            exclusion_reason="INCOMPLETE_HORIZON",
        )
    if any(not _get_val(bar, "is_closed") for bar in outcome_bars):
        return NetReturnLabel(
            sample_id=sample_id, label_set_id=config.label_set_id,
            label_version=config.version, pair=pair, decision_ts=decision_ts,
            entry_ts=entry_ts, exit_ts=target_exit_ts, status="EXCLUDED",
            exclusion_reason="UNCLOSED_OUTCOME_SOURCE",
        )

    # Check cost schedule availability
    if config.cost_schedule_table is None:
        return NetReturnLabel(
            sample_id=sample_id,
            label_set_id=config.label_set_id,
            label_version=config.version,
            pair=pair,
            decision_ts=decision_ts,
            entry_ts=entry_ts,
            exit_ts=target_exit_ts,
            status="EXCLUDED",
            exclusion_reason="COST_SCHEDULE_UNAVAILABLE",
        )

    try:
        buy_sched = lookup_cost(
            table=config.cost_schedule_table,
            market=pair,
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            event_ts=entry_ts,
        )
        sell_sched = lookup_cost(
            table=config.cost_schedule_table,
            market=pair,
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            event_ts=target_exit_ts,
        )
    except UnknownCostScheduleError:
        return NetReturnLabel(
            sample_id=sample_id,
            label_set_id=config.label_set_id,
            label_version=config.version,
            pair=pair,
            decision_ts=decision_ts,
            entry_ts=entry_ts,
            exit_ts=target_exit_ts,
            status="EXCLUDED",
            exclusion_reason="COST_SCHEDULE_UNAVAILABLE",
        )

    # Net-proceeds / gross-debit calculation
    buy_cost = entry_price * buy_sched.total_rate
    sell_cost = exit_price * sell_sched.total_rate

    total_buy_cash_debit = entry_price + buy_cost
    net_sell_proceeds = exit_price - sell_cost

    net_return = (net_sell_proceeds / total_buy_cash_debit) - Decimal("1")
    gross_return = (exit_price / entry_price) - Decimal("1")

    binary_label = 1 if net_return > config.edge_margin else 0
    label_avail = max(target_exit_ts, *(
        _get_val(bar, "available_at") for bar in outcome_bars
    ))

    return NetReturnLabel(
        sample_id=sample_id,
        label_set_id=config.label_set_id,
        label_version=config.version,
        pair=pair,
        decision_ts=decision_ts,
        entry_ts=entry_ts,
        exit_ts=target_exit_ts,
        entry_price=entry_price,
        exit_price=exit_price,
        gross_return=gross_return,
        buy_cost=buy_cost,
        sell_cost=sell_cost,
        slippage_cost=Decimal("0"),
        net_return=net_return,
        binary_label=binary_label,
        cost_schedule_id=buy_sched.schedule_id,
        execution_model_version=config.execution_model_version,
        label_available_at=label_avail,
        status="VALID",
        exclusion_reason=None,
    )


def build_net_return_labels_frame(
    samples: Sequence[Mapping[str, Any]],
    bars: Sequence[Any],
    config: NetReturnConfig,
) -> pd.DataFrame:
    """Build a DataFrame of net return labels for a collection of decision samples."""
    rows = []
    for s in samples:
        sample_id = s["sample_id"]
        pair = s["pair"]
        decision_ts = s["decision_ts"]
        lbl = build_net_return_label(
            sample_id=sample_id,
            pair=pair,
            decision_ts=decision_ts,
            bars=bars,
            config=config,
        )
        row = lbl.model_dump()
        # Net-return outcomes end at their configured exit event. Preserve the
        # source event name and expose the canonical split/training boundary.
        row["label_end_ts"] = lbl.exit_ts
        rows.append(row)
    return pd.DataFrame(rows)


__all__ = [
    "NetReturnConfig",
    "NetReturnLabel",
    "build_net_return_label",
    "build_net_return_labels_frame",
]
