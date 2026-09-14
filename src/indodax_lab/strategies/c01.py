"""Donchian breakout strategy candidate (C01-01).

Contract:
Previous N-bar high breakout with volume gate; ATR stop -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c01_specification(config_path: str | Path = "configs/strategies/C01_v1.yaml") -> StrategySpecification:
    """Load and strictly validate the canonical C01 Donchian breakout specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c01_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
    """Pure, stateless decision function for C01 Donchian breakout candidate.

    Invariants:
    - Previous N-bar high strictly excludes the current decision bar.
    - Breakout confirmed by price and volume gate produces LONG intent.
    - Incomplete bar or insufficient lookback produces FLAT (empty intents).
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_c01_specification()

    lookback_bars = int(spec.parameters.get("lookback_bars", 20))
    volume_mult = float(spec.parameters.get("volume_multiplier", 1.0))
    atr_mult = float(spec.parameters.get("atr_multiplier", 2.0))
    desired_qty = Decimal(str(spec.parameters.get("desired_qty", "0.1")))

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        # C01-01-AC3: Must have at least lookback_bars completed prior bars + 1 current bar
        if len(p_df) < lookback_bars + 1:
            continue

        curr_row = p_df.iloc[-1]

        # Check for missing/incomplete bar values
        if pd.isna(curr_row.get("close")) or pd.isna(curr_row.get("high")) or pd.isna(curr_row.get("low")):
            continue
        if "eligible" in curr_row and not curr_row["eligible"]:
            continue

        curr_close = float(curr_row["close"])

        # C01-01-AC1: Previous N completed bars EXCLUDING current decision bar (-1)
        prev_window = p_df.iloc[-lookback_bars - 1 : -1]
        prev_n_high = float(prev_window["high"].max())

        # Volume gate
        vol_col = "base_volume" if "base_volume" in p_df.columns else "volume"
        curr_vol = float(curr_row.get(vol_col, 0.0))
        avg_vol = float(prev_window[vol_col].mean()) if vol_col in prev_window.columns else 0.0

        # C01-01-AC2: Breakout confirmed if close > prev_n_high and curr_vol >= avg_vol * volume_mult
        if curr_close > prev_n_high and curr_vol >= (avg_vol * volume_mult):
            # Price-denominated ATR stop loss
            atr_val = float(curr_row.get("atr_14", curr_row.get("atr", 0.0)))
            stop_loss = max(0.0, curr_close - atr_mult * atr_val)

            intent = SignalIntent(
                intent_id=f"c01_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=desired_qty,
                limit_price=Decimal(str(curr_close)),
                stop_loss=Decimal(str(stop_loss)) if stop_loss > 0 else None,
                strategy_id=spec.strategy_id,
            )
            intents.append(intent)

    return intents
