"""Donchian breakout strategy candidate (C01-01).

Contract:
Previous N-bar high breakout with volume gate; ATR stop -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.contracts.decision import SignalIntent
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
        if not math.isfinite(curr_close) or curr_close <= 0:
            continue

        # C01-01-AC1: Previous N completed bars EXCLUDING current decision bar (-1)
        prev_window = p_df.iloc[-lookback_bars - 1 : -1]
        try:
            prev_n_high = float(prev_window["high"].max())
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(prev_n_high) or prev_n_high <= 0:
            continue

        # Volume gate (fail-closed): unknown/zero average volume never passes.
        if "base_volume" in p_df.columns:
            vol_col = "base_volume"
        elif "volume" in p_df.columns:
            vol_col = "volume"
        else:
            continue
        curr_vol_raw = curr_row.get(vol_col)
        if curr_vol_raw is None or pd.isna(curr_vol_raw):
            continue
        try:
            curr_vol = float(curr_vol_raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(curr_vol):
            continue
        try:
            avg_vol = float(pd.to_numeric(prev_window[vol_col], errors="coerce").mean())
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(avg_vol) or avg_vol <= 0:
            continue

        # C01-01-AC2: Breakout confirmed if close > prev_n_high and curr_vol >= avg_vol * volume_mult
        if curr_close > prev_n_high and curr_vol >= (avg_vol * volume_mult):
            # Price-denominated ATR stop loss (fail-closed on unknown/nonpositive ATR).
            atr_raw = curr_row.get("atr_14", curr_row.get("atr"))
            if atr_raw is None or pd.isna(atr_raw):
                continue
            try:
                atr_val = float(atr_raw)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(atr_val) or atr_val <= 0:
                continue
            stop_loss = curr_close - atr_mult * atr_val
            if not math.isfinite(stop_loss) or stop_loss <= 0 or stop_loss >= curr_close:
                continue

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
