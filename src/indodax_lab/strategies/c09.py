"""VWAP deviation reversion strategy candidate (C09-01)."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c09_specification(
    config_path: str | Path = "configs/strategies/C09_v1.yaml",
) -> StrategySpecification:
    """Load and validate the canonical C09 specification."""
    return StrategyRegistry().load_specification_from_yaml(config_path)


def c09_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit VWAP reversion intents only when required features and volume exist."""
    spec = spec or load_c09_specification()
    params = spec.parameters
    deviation_entry = float(params.get("vwap_deviation_entry", -0.02))
    max_adx = float(params.get("max_adx", 0.25))
    atr_multiplier = float(params.get("atr_multiplier", 1.5))
    desired_qty = Decimal(str(params.get("desired_qty", "0.1")))
    if not math.isfinite(deviation_entry) or deviation_entry >= 0:
        raise ValueError("C09_VWAP_ENTRY_MUST_BE_NEGATIVE")
    if not math.isfinite(max_adx) or not 0 <= max_adx <= 1:
        raise ValueError("C09_ADX_THRESHOLD_OUT_OF_RANGE")
    if not math.isfinite(atr_multiplier) or atr_multiplier <= 0 or desired_qty <= 0:
        raise ValueError("C09_INVALID_RISK_OR_SIZE_PARAMETER")

    intents: list[SignalIntent] = []
    names = (
        "close",
        "atr_14",
        "base_volume",
        "vwap_dev_24_1h",
        "ema20_slope_5_1h",
        "adx_14_1h",
    )
    for pair in frame.eligible_pairs:
        row = frame.latest_row(pair)
        if row is None:
            continue
        values = [row.get(name) for name in names]
        if any(value is None or pd.isna(value) for value in values):
            continue
        try:
            close, atr, volume, deviation, slope, adx = map(float, values)
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (close, atr, volume, deviation, slope, adx)):
            continue
        if close <= 0 or atr <= 0 or volume <= 0 or not 0 <= adx <= 1:
            continue
        if deviation > deviation_entry or slope < 0 or adx > max_adx:
            continue

        stop_loss = close - atr_multiplier * atr
        if stop_loss <= 0:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"c09_{pair}_{int(frame.as_of.timestamp())}",
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
