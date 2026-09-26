"""Volatility contraction and expansion breakout strategy candidate (C05-01)."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c05_specification(
    config_path: str | Path = "configs/strategies/C05_v1.yaml",
) -> StrategySpecification:
    """Load and validate the canonical C05 specification."""
    return StrategyRegistry().load_specification_from_yaml(config_path)


def c05_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Emit a long intent after prior range contraction and current expansion breakout."""
    spec = spec or load_c05_specification()
    params = spec.parameters
    baseline_bars = int(params.get("baseline_bars", 20))
    contraction_bars = int(params.get("contraction_bars", 5))
    contraction_ratio = float(params.get("contraction_ratio", 0.7))
    expansion_ratio = float(params.get("expansion_ratio", 1.5))
    atr_multiplier = float(params.get("atr_multiplier", 2.0))
    desired_qty = Decimal(str(params.get("desired_qty", "0.1")))
    if baseline_bars < 1 or contraction_bars < 1:
        raise ValueError("C05_LOOKBACKS_MUST_BE_POSITIVE")

    intents: list[SignalIntent] = []
    for pair in frame.eligible_pairs:
        rows = frame.get_pair_features(pair)
        required = baseline_bars + contraction_bars + 1
        if len(rows) < required:
            continue

        current = rows.iloc[-1]
        needed = ("high", "low", "close", "atr_14")
        if any(column not in rows or rows[column].isna().any() for column in needed):
            continue

        market = rows.loc[:, ("high", "low", "close")].apply(
            pd.to_numeric, errors="coerce"
        )
        market_values = market.to_numpy().ravel()
        if not all(math.isfinite(float(value)) and float(value) > 0 for value in market_values):
            continue
        if (
            market["high"].lt(market["low"]).any()
            or market["close"].lt(market["low"]).any()
            or market["close"].gt(market["high"]).any()
        ):
            continue

        baseline_market = market.iloc[-required:-contraction_bars - 1]
        contraction_market = market.iloc[-contraction_bars - 1:-1]
        current_market = market.iloc[-1]
        baseline_range = (baseline_market["high"] - baseline_market["low"]).mean()
        contraction_range = (
            contraction_market["high"] - contraction_market["low"]
        ).mean()
        current_range = float(current_market["high"] - current_market["low"])
        close = float(current_market["close"])
        atr = float(current["atr_14"])
        if (
            baseline_range <= 0
            or contraction_range <= 0
            or current_range <= 0
            or close <= 0
            or atr <= 0
            or not math.isfinite(atr)
        ):
            continue
        if contraction_range > baseline_range * contraction_ratio:
            continue
        if current_range < contraction_range * expansion_ratio:
            continue
        if close <= float(contraction_market["high"].max()):
            continue

        stop = close - atr_multiplier * atr
        if stop <= 0:
            continue
        intents.append(
            SignalIntent(
                intent_id=f"c05_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=desired_qty,
                limit_price=Decimal(str(close)),
                stop_loss=Decimal(str(stop)),
                strategy_id=spec.strategy_id,
            )
        )
    return intents
