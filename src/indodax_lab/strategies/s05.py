"""Micro pullback continuation candidate (S05-01)."""

from __future__ import annotations

import math
from decimal import Decimal, DecimalException
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_s05_specification(
    config_path: str | Path = "configs/strategies/S05_v1.yaml",
) -> StrategySpecification:
    return StrategyRegistry().load_specification_from_yaml(config_path)


def s05_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit a maker-limit LONG intent after impulse, pullback and spread gates pass."""
    if spec is None:
        spec = load_s05_specification()

    params = spec.parameters
    try:
        min_impulse = float(params.get("min_impulse_log_return", 0.05))
        min_pullback = float(params.get("min_pullback_log_return", -0.015))
        max_pullback = float(params.get("max_pullback_log_return", -0.001))
        max_spread = float(params.get("max_spread_bps", 25.0))
        atr_multiplier = float(params.get("atr_multiplier", 2.0))
        target_notional = Decimal(str(params.get("target_notional_idr", "10000")))
    except (DecimalException, OverflowError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_S05_PARAMETERS") from exc
    if (
        not all(
            math.isfinite(v)
            for v in (min_impulse, min_pullback, max_pullback, max_spread, atr_multiplier)
        )
        or min_impulse <= 0
        or min_pullback >= max_pullback
        or max_pullback >= 0
        or max_spread <= 0
        or atr_multiplier <= 0
        or not target_notional.is_finite()
        or target_notional < Decimal("10000")
    ):
        raise ValueError("INVALID_S05_PARAMETERS")

    intents: list[SignalIntent] = []
    for pair in sorted(frame.eligible_pairs):
        row = frame.latest_row(pair)
        if row is None:
            continue
        fields = (
            row.get("close"),
            row.get("log_ret_12_1h"),
            row.get("log_ret_1_1h"),
            row.get("spread_bps"),
            row.get("atr_pct_14_1h"),
        )
        if any(value is None or pd.isna(value) for value in fields):
            continue
        try:
            close, impulse, pullback, spread_bps, atr_pct = map(float, fields)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (close, impulse, pullback, spread_bps, atr_pct)):
            continue
        if (
            close <= 0
            or impulse < min_impulse
            or not min_pullback <= pullback <= max_pullback
            or not 0 <= spread_bps <= max_spread
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
                intent_id=f"s05_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=quantity,
                limit_price=price,
                stop_loss=stop_loss,
                strategy_id=spec.strategy_id,
                role_preference=OrderRole.MAKER,
            )
        )
    return intents
