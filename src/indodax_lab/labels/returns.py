"""Execution-aligned net return labels with strict causality and cost integration (LABEL-01)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from indodax_lab.backtest.costs import (
    CostScheduleTable,
    OrderRole,
    OrderSide,
    UnknownCostScheduleError,
    UnverifiedCostScheduleError,
    lookup_cost,
)
from indodax_lab.backtest.events import ExecutionStatus, MarketBar
from indodax_lab.backtest.execution import ConservativeExecutionSimulator
from indodax_lab.contracts.decision import SignalIntent


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


class CandidateSampleRegistration(BaseModel):
    """Resolved immutable association from the candidate/sample registry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    registration_id: str
    candidate_bundle_id: str
    strategy_id: str
    sample_id: str
    intent_id: str
    pair: str
    decision_ts: datetime

    @field_validator(
        "registration_id", "candidate_bundle_id", "strategy_id", "sample_id", "intent_id", "pair"
    )
    @classmethod
    def require_nonempty_registration_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("NONEMPTY_CANDIDATE_REGISTRATION_IDENTITY_REQUIRED")
        return value

    @field_validator("decision_ts")
    @classmethod
    def validate_registration_time_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


class CandidateHorizonSample(BaseModel):
    """Candidate-sized sample input paired with trusted registry evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    candidate_bundle_id: str
    strategy_id: str
    pair: str
    decision_ts: datetime
    signal_intent: SignalIntent

    @field_validator("sample_id", "candidate_bundle_id", "strategy_id", "pair")
    @classmethod
    def require_nonempty_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("NONEMPTY_CANDIDATE_SAMPLE_IDENTITY_REQUIRED")
        return value

    @field_validator("decision_ts")
    @classmethod
    def validate_sample_time_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


class CandidateHorizonLabel(BaseModel):
    """Actual shared-simulator outcome; never a full SL/TP strategy result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    candidate_bundle_id: str
    registration_id: str
    intent_id: str
    strategy_id: str
    label_set_id: Literal["net_return_candidate_horizon_v2"] = "net_return_candidate_horizon_v2"
    label_version: str
    pair: str
    decision_ts: datetime
    label_end_ts: datetime | None = None
    entry_fill_id: str | None = None
    exit_fill_id: str | None = None
    entry_ts: datetime | None = None
    exit_ts: datetime | None = None
    entry_qty: Decimal | None = None
    exit_qty: Decimal | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    gross_return: Decimal | None = None
    buy_cost: Decimal | None = None
    sell_cost: Decimal | None = None
    slippage_cost: Decimal | None = None
    net_return: Decimal | None = None
    binary_label: int | None = None
    cost_schedule_id: str | None = None
    cost_schedule_version: str | None = None
    entry_cost_schedule_id: str | None = None
    exit_cost_schedule_id: str | None = None
    execution_model_version: Literal["causal-bar-proxy-v2"] = "causal-bar-proxy-v2"
    label_available_at: datetime | None = None
    status: Literal["VALID", "EXCLUDED"]
    exclusion_reason: str | None = None


class CandidateHorizonConfig(BaseModel):
    """Versioned settings for candidate-sized horizon outcomes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label_version: str = "2.0.0"
    horizon: timedelta = timedelta(hours=4)
    edge_margin: Decimal = Decimal("0.001")
    execution_model_version: Literal["causal-bar-proxy-v2"] = "causal-bar-proxy-v2"

    @field_validator("horizon")
    @classmethod
    def require_positive_horizon(cls, value: timedelta) -> timedelta:
        if value <= timedelta(0):
            raise ValueError("POSITIVE_HORIZON_REQUIRED")
        return value


def load_candidate_horizon_config(path: Path) -> CandidateHorizonConfig:
    """Load the separate v2 config without changing the legacy v1 defaults."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or raw.get("label_set_id") != "net_return_candidate_horizon_v2":
        raise ValueError("INVALID_CANDIDATE_HORIZON_CONFIG")
    raw["horizon"] = timedelta(seconds=int(raw.pop("horizon_seconds")))
    raw["label_version"] = raw.pop("version")
    for key in (
        "sizing_source", "exit_policy", "partial_entry_policy",
        "incomplete_or_missing_fill", "legacy_materialization",
    ):
        raw.pop(key, None)
    raw.pop("label_set_id")
    return CandidateHorizonConfig.model_validate(raw)


def _get_val(bar: Any, key: str) -> Any:
    if isinstance(bar, Mapping):
        return bar[key]
    return getattr(bar, key)


def _require_utc(value: datetime) -> datetime:
    if pd.isna(value) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED")
    return value


def build_candidate_horizon_label(
    sample: CandidateHorizonSample | Mapping[str, Any],
    bars: Sequence[MarketBar],
    simulator: ConservativeExecutionSimulator,
    *,
    resolve_registration: Callable[[str, str], CandidateSampleRegistration | None],
    config: CandidateHorizonConfig | None = None,
) -> CandidateHorizonLabel:
    """Execute candidate-sized BUY and fixed-horizon SELL through SIM-01."""
    config = config or CandidateHorizonConfig()
    sample = CandidateHorizonSample.model_validate(sample)
    if simulator.execution_version != config.execution_model_version:
        raise ValueError("UNSUPPORTED_EXECUTION_MODEL")
    intent = sample.signal_intent
    registration = resolve_registration(sample.candidate_bundle_id, sample.sample_id)
    if registration is None:
        raise ValueError("CANDIDATE_SAMPLE_NOT_REGISTERED")
    if (
        registration.candidate_bundle_id,
        registration.strategy_id,
        registration.sample_id,
        registration.intent_id,
        registration.pair,
        registration.decision_ts,
    ) != (
        sample.candidate_bundle_id,
        sample.strategy_id,
        sample.sample_id,
        intent.intent_id,
        sample.pair,
        sample.decision_ts,
    ) or (intent.strategy_id, intent.pair, intent.decision_ts) != (
        sample.strategy_id, sample.pair, sample.decision_ts
    ):
        raise ValueError("CANDIDATE_INTENT_LINEAGE_MISMATCH")
    if intent.side != OrderSide.BUY:
        raise ValueError("CANDIDATE_HORIZON_REQUIRES_BUY_INTENT")
    _require_utc(sample.decision_ts)
    market_bars = sorted(
        (
            MarketBar.model_validate(bar)
            for bar in bars
            if _get_val(bar, "pair") == sample.pair
        ),
        key=lambda bar: bar.open_time,
    )

    def excluded(reason: str, *, entry=None, exit_at=None) -> CandidateHorizonLabel:
        return CandidateHorizonLabel(
            sample_id=sample.sample_id, candidate_bundle_id=sample.candidate_bundle_id,
            registration_id=registration.registration_id,
            intent_id=intent.intent_id, strategy_id=sample.strategy_id,
            label_version=config.label_version, pair=sample.pair,
            decision_ts=sample.decision_ts,
            entry_ts=entry.timestamp if entry else None, exit_ts=exit_at,
            entry_qty=entry.qty if entry else None, entry_price=entry.price if entry else None,
            cost_schedule_id=simulator.cost_schedule_table.schedule_set_id,
            cost_schedule_version=simulator.cost_schedule_table.version,
            status="EXCLUDED", exclusion_reason=reason,
        )

    if not intent.intent_id.strip():
        raise ValueError("CANDIDATE_INTENT_ID_REQUIRED")
    entry_bar = next((bar for bar in market_bars if bar.open_time >= sample.decision_ts), None)
    if entry_bar is None:
        return excluded("NO_ENTRY_FILL")
    try:
        entry_result = simulator.simulate_execution(
            intent,
            entry_bar,
            order_created_ts=(
                sample.decision_ts if intent.role_preference == OrderRole.MAKER else None
            ),
        )
    except (UnknownCostScheduleError, UnverifiedCostScheduleError):
        return excluded("COST_SCHEDULE_UNAVAILABLE")
    if entry_result.fill is None:
        return excluded("NO_ENTRY_FILL")

    entry = entry_result.fill
    entry_schedule = lookup_cost(
        simulator.cost_schedule_table,
        market=simulator.market,
        side=entry.side,
        role=entry.role,
        fee_basis_ts=(
            sample.decision_ts if entry.role == OrderRole.MAKER else entry.timestamp
        ),
    )
    target_exit = entry.timestamp + config.horizon
    exit_candidates = [bar for bar in market_bars if bar.open_time == target_exit]
    if not exit_candidates:
        return excluded("INCOMPLETE_HORIZON", entry=entry, exit_at=target_exit)
    interval_bars = [
        bar for bar in market_bars if entry_bar.open_time <= bar.open_time <= target_exit
    ]
    if not interval_bars or interval_bars[-1].open_time != target_exit or any(
        left.close_time != right.open_time
        for left, right in pairwise(interval_bars)
    ):
        return excluded("INCOMPLETE_HORIZON", entry=entry, exit_at=target_exit)
    exit_bar = exit_candidates[0]
    exit_intent = intent.model_copy(update={
        "intent_id": f"{intent.intent_id}:horizon-exit",
        "side": OrderSide.SELL,
        "desired_qty": entry.qty,
        "limit_price": None,
        "stop_loss": None,
        "take_profit": None,
        "role_preference": OrderRole.TAKER,
    })
    try:
        exit_result = simulator.simulate_execution(exit_intent, exit_bar)
    except (UnknownCostScheduleError, UnverifiedCostScheduleError):
        return excluded("COST_SCHEDULE_UNAVAILABLE", entry=entry, exit_at=target_exit)
    if exit_result.fill is None or exit_result.status != ExecutionStatus.FILLED:
        return excluded("INCOMPLETE_EXIT_FILL", entry=entry, exit_at=target_exit)

    exit_fill = exit_result.fill
    exit_schedule = lookup_cost(
        simulator.cost_schedule_table,
        market=simulator.market,
        side=exit_fill.side,
        role=exit_fill.role,
        fee_basis_ts=exit_fill.timestamp,
    )
    buy_debit = entry.gross + entry.fees
    sell_proceeds = exit_fill.gross - exit_fill.fees
    net_return = sell_proceeds / buy_debit - Decimal("1")
    gross_return = exit_fill.gross / entry.gross - Decimal("1")
    return CandidateHorizonLabel(
        sample_id=sample.sample_id, candidate_bundle_id=sample.candidate_bundle_id,
        registration_id=registration.registration_id,
        intent_id=intent.intent_id, strategy_id=sample.strategy_id,
        label_version=config.label_version, pair=sample.pair, decision_ts=sample.decision_ts,
        label_end_ts=exit_fill.timestamp,
        entry_fill_id=entry.fill_id, exit_fill_id=exit_fill.fill_id,
        entry_ts=entry.timestamp, exit_ts=exit_fill.timestamp,
        entry_qty=entry.qty, exit_qty=exit_fill.qty, entry_price=entry.price,
        exit_price=exit_fill.price, gross_return=gross_return,
        buy_cost=entry.fees, sell_cost=exit_fill.fees, slippage_cost=Decimal("0"),
        net_return=net_return,
        binary_label=int(net_return > config.edge_margin),
        cost_schedule_id=simulator.cost_schedule_table.schedule_set_id,
        cost_schedule_version=simulator.cost_schedule_table.version,
        entry_cost_schedule_id=entry_schedule.schedule_id,
        exit_cost_schedule_id=exit_schedule.schedule_id,
        label_available_at=max(bar.available_at for bar in interval_bars),
        status="VALID",
    )


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
        for left, right in pairwise(outcome_bars)
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
            fee_basis_ts=entry_ts,
        )
        sell_sched = lookup_cost(
            table=config.cost_schedule_table,
            market=pair,
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            fee_basis_ts=target_exit_ts,
        )
    except (UnknownCostScheduleError, UnverifiedCostScheduleError):
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


def build_candidate_horizon_labels_frame(
    samples: Sequence[CandidateHorizonSample | Mapping[str, Any]],
    bars: Sequence[MarketBar],
    simulator: ConservativeExecutionSimulator,
    *,
    resolve_registration: Callable[[str, str], CandidateSampleRegistration | None],
    config: CandidateHorizonConfig | None = None,
) -> pd.DataFrame:
    """Materialize v2 rows separately; does not read or rewrite v1 artifacts."""
    config = config or CandidateHorizonConfig()
    labels = [
        build_candidate_horizon_label(
            sample, bars, simulator,
            resolve_registration=resolve_registration, config=config,
        ).model_dump()
        for sample in samples
    ]
    return pd.DataFrame(labels)


__all__ = [
    "CandidateHorizonConfig",
    "CandidateHorizonLabel",
    "CandidateHorizonSample",
    "CandidateSampleRegistration",
    "NetReturnConfig",
    "NetReturnLabel",
    "build_candidate_horizon_label",
    "build_candidate_horizon_labels_frame",
    "load_candidate_horizon_config",
    "build_net_return_label",
    "build_net_return_labels_frame",
]
