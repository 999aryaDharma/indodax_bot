"""Post-listing maturation momentum candidate (S06-01)."""

from __future__ import annotations

import math
from decimal import Decimal, DecimalException
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_s06_specification(
    config_path: str | Path = "configs/strategies/S06_v1.yaml",
) -> StrategySpecification:
    return StrategyRegistry().load_specification_from_yaml(config_path)


def s06_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit minimum-notional LONG intents only after listing/history gates pass."""
    if spec is None:
        spec = load_s06_specification()

    params = spec.parameters
    try:
        minimum_age_value = float(params.get("minimum_listing_age_days", 180))
        max_log_return = float(params.get("max_24h_log_return", 0.25))
        min_completeness = float(params.get("min_history_completeness", 0.95))
        atr_multiplier = float(params.get("atr_multiplier", 2.0))
        target_notional = Decimal(str(params.get("target_notional_idr", "10000")))
    except (DecimalException, OverflowError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_S06_PARAMETERS") from exc
    if (
        not math.isfinite(minimum_age_value)
        or not minimum_age_value.is_integer()
        or minimum_age_value < 0
        or not all(
            math.isfinite(v) for v in (max_log_return, min_completeness, atr_multiplier)
        )
        or max_log_return <= 0
        or not 0 < min_completeness <= 1
        or atr_multiplier <= 0
        or not target_notional.is_finite()
        or target_notional < Decimal("10000")
    ):
        raise ValueError("INVALID_S06_PARAMETERS")

    minimum_age = int(minimum_age_value)
    intents: list[SignalIntent] = []
    minimum_age_log = math.log1p(minimum_age)
    for pair in sorted(frame.eligible_pairs):
        row = frame.latest_row(pair)
        if row is None:
            continue
        fields = (
            row.get("close"),
            row.get("log_listing_age_days"),
            row.get("log_ret_24_1h"),
            row.get("bar_completeness_24_1h"),
            row.get("atr_pct_14_1h"),
        )
        if any(value is None or pd.isna(value) for value in fields):
            continue
        try:
            close, age_log, log_return, completeness, atr_pct = map(float, fields)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (close, age_log, log_return, completeness, atr_pct)):
            continue
        # Registered listing age is float64 log1p(days); allow 1e-12 rounding tolerance.
        if (
            close <= 0
            or age_log < minimum_age_log - 1e-12
            or not 0 < log_return <= max_log_return
            or not min_completeness <= completeness <= 1
            or atr_pct <= 0
            or atr_pct * atr_multiplier >= 1
        ):
            continue

        try:
            price = Decimal(str(close))
            quantity = target_notional / price
            while quantity * price < target_notional:
                quantity = quantity.next_plus()
            stop_loss = price * (Decimal(1) - Decimal(str(atr_pct * atr_multiplier)))
        except DecimalException:
            continue
        if stop_loss <= 0:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"s06_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=quantity,
                limit_price=price,
                stop_loss=stop_loss,
                strategy_id=spec.strategy_id,
            )
        )
    return intents
