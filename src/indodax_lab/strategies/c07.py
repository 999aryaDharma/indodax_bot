"""Bollinger RSI reversion strategy candidate (C07-01).

Contract:
Extreme BB and RSI deviation only under available sideways regime -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c07_specification(config_path: str | Path = "configs/strategies/C07_v1.yaml") -> StrategySpecification:
    """Load and strictly validate canonical C07 Bollinger RSI reversion specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c07_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
    """Pure, stateless decision function for C07 Bollinger RSI reversion candidate.

    Invariants:
    - Strong downtrend strictly rejects entry (no knife-catching).
    - Sideways oversold produces bounded LONG intent with ATR stop/target.
    - Zero/degenerate band width gives abstain (FLAT / empty intents).
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_c07_specification()

    bb_std = float(spec.parameters.get("bb_std", 2.0))
    rsi_oversold = float(spec.parameters.get("rsi_oversold", 30.0))
    adx_trend_thresh = float(spec.parameters.get("adx_trend_threshold", 0.25))
    atr_mult = float(spec.parameters.get("atr_multiplier", 1.5))
    desired_qty = Decimal(str(spec.parameters.get("desired_qty", "0.1")))

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        if p_df.empty:
            continue

        curr_row = p_df.iloc[-1]

        if pd.isna(curr_row.get("close")):
            continue
        if "eligible" in curr_row and not curr_row["eligible"]:
            continue

        close = float(curr_row["close"])

        # C07-01-AC3: Zero or degenerate band width gives abstain
        bb_width_val = curr_row.get("bb_width")
        if bb_width_val is None or pd.isna(bb_width_val) or float(bb_width_val) <= 0.0:
            continue

        bb_z = float(curr_row.get("bb_z", 0.0)) if not pd.isna(curr_row.get("bb_z")) else 0.0
        rsi = float(curr_row.get("rsi_14", curr_row.get("rsi", 50.0)))
        adx = float(curr_row.get("adx_14", curr_row.get("adx", 0.0)))
        di_spread = float(curr_row.get("di_spread_14", curr_row.get("di_spread", 0.0)))
        regime = str(curr_row.get("regime", "sideways")).lower()

        # C07-01-AC1: Strong downtrend strictly rejects entry
        is_strong_downtrend = (
            regime in ("downtrend", "strong_downtrend")
            or (di_spread < -0.15 and adx > adx_trend_thresh)
        )
        if is_strong_downtrend:
            continue

        # C07-01-AC2: Sideways oversold gives bounded intent
        is_sideways = (regime in ("sideways", "ranging")) or (adx <= adx_trend_thresh)
        is_oversold = (bb_z <= -bb_std) and (rsi <= rsi_oversold)

        if is_sideways and is_oversold:
            atr_val = float(curr_row.get("atr_14", curr_row.get("atr", 0.0)))
            stop_loss = max(0.0, close - atr_mult * atr_val)
            take_profit = close + atr_mult * atr_val

            intent = SignalIntent(
                intent_id=f"c07_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=desired_qty,
                limit_price=Decimal(str(close)),
                stop_loss=Decimal(str(stop_loss)) if stop_loss > 0 else None,
                take_profit=Decimal(str(take_profit)),
                strategy_id=spec.strategy_id,
            )
            intents.append(intent)

    return intents
