"""Directional trend strength strategy candidate (C06-01)."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c06_specification(
    config_path: str | Path = "configs/strategies/C06_v1.yaml",
) -> StrategySpecification:
    """Load and validate the canonical C06 specification."""
    return StrategyRegistry().load_specification_from_yaml(config_path)


def c06_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Return BUY intents when normalized ADX and signed DI confirm direction."""
    spec = spec or load_c06_specification()
    params = spec.parameters
    adx_threshold = float(params.get("adx_threshold", 0.25))
    atr_multiplier = float(params.get("atr_multiplier", 2.0))
    desired_qty = Decimal(str(params.get("desired_qty", "0.1")))
    if not math.isfinite(adx_threshold) or not 0 <= adx_threshold <= 1:
        raise ValueError("C06_ADX_THRESHOLD_OUT_OF_RANGE")
    if not math.isfinite(atr_multiplier) or atr_multiplier <= 0 or desired_qty <= 0:
        raise ValueError("C06_INVALID_RISK_OR_SIZE_PARAMETER")

    intents: list[SignalIntent] = []
    for pair in frame.eligible_pairs:
        row = frame.latest_row(pair)
        if row is None:
            continue
        values = {key: row.get(key) for key in ("adx_14", "di_spread_14", "close", "atr_14")}
        if any(value is None or pd.isna(value) for value in values.values()):
            continue
        adx, di_spread, close, atr = (float(values[key]) for key in values)
        if not all(math.isfinite(value) for value in (adx, di_spread, close, atr)):
            continue
        if not 0 <= adx <= 1 or not -1 <= di_spread <= 1 or close <= 0 or atr <= 0:
            continue
        if adx < adx_threshold or di_spread <= 0:
            continue

        stop_loss = close - atr_multiplier * atr
        if stop_loss <= 0:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"c06_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=desired_qty,
                limit_price=Decimal(str(close)),
                stop_loss=Decimal(str(stop_loss)),
                strategy_id=spec.strategy_id,
            )
        )
    return intents
