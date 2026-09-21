"""Squeeze expansion strategy candidate (S02-01).

Contract:
BB/Keltner squeeze followed by volume expansion and no-chase cap -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.registry import StrategyRegistry


def load_s02_specification(config_path: str | Path = "configs/strategies/S02_v1.yaml") -> StrategySpecification:
    """Load and strictly validate the canonical S02 squeeze expansion specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def s02_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
    """Pure, stateless decision function for S02 Squeeze expansion candidate.

    Invariants:
    - Squeeze alone does not enter (requires confirmed expansion).
    - Expansion without volume confirmation is rejected.
    - Gap above chase cap is rejected.
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_s02_specification()

    lookback_bars = int(spec.parameters.get("lookback_bars", 20))
    bb_std_mult = float(spec.parameters.get("bb_std", 2.0))
    kc_atr_mult = float(spec.parameters.get("kc_atr_mult", 1.5))
    volume_mult = float(spec.parameters.get("volume_multiplier", 1.5))
    max_chase_pct = float(spec.parameters.get("max_chase_pct", 0.03))
    base_qty = Decimal(str(spec.parameters.get("base_qty", "0.1")))
    atr_mult = float(spec.parameters.get("atr_multiplier", 2.0))

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        if len(p_df) < lookback_bars + 1:
            continue

        curr_row = p_df.iloc[-1]
        prev_row = p_df.iloc[-2]

        if pd.isna(curr_row.get("close")) or pd.isna(curr_row.get("high")) or pd.isna(curr_row.get("low")):
            continue
        if "eligible" in curr_row and not curr_row["eligible"]:
            continue

        # Lookback window for prior bar indicators (excluding current bar to establish squeeze regime)
        prior_window = p_df.iloc[-lookback_bars - 1 : -1]
        prev_mean = float(prior_window["close"].mean())
        prev_std = float(prior_window["close"].std(ddof=1)) if len(prior_window) > 1 else 0.0
        prev_atr = float(prev_row.get("atr_14", prev_row.get("atr", 0.0)))
        if prev_atr <= 0:
            continue

        prev_bb_upper = prev_mean + bb_std_mult * prev_std
        prev_bb_lower = prev_mean - bb_std_mult * prev_std
        prev_kc_upper = prev_mean + kc_atr_mult * prev_atr
        prev_kc_lower = prev_mean - kc_atr_mult * prev_atr

        prev_bb_width = prev_bb_upper - prev_bb_lower
        prev_kc_width = prev_kc_upper - prev_kc_lower

        # Prior bar must have been in squeeze (BB width < KC width or BB inside KC)
        was_in_squeeze = (prev_bb_width < prev_kc_width) or (
            prev_bb_upper <= prev_kc_upper and prev_bb_lower >= prev_kc_lower
        )
        if not was_in_squeeze:
            continue

        curr_close = float(curr_row["close"])
        prev_close = float(prev_row["close"])
        if prev_close <= 0:
            continue

        # Check current bar squeeze status
        curr_window = p_df.iloc[-lookback_bars:]
        curr_mean = float(curr_window["close"].mean())
        curr_std = float(curr_window["close"].std(ddof=1)) if len(curr_window) > 1 else 0.0
        curr_atr = float(curr_row.get("atr_14", curr_row.get("atr", 0.0)))
        if curr_atr <= 0:
            continue

        curr_bb_upper = curr_mean + bb_std_mult * curr_std
        curr_bb_lower = curr_mean - bb_std_mult * curr_std
        curr_kc_upper = curr_mean + kc_atr_mult * curr_atr
        curr_kc_lower = curr_mean - kc_atr_mult * curr_atr

        # S02-01-AC1: Squeeze saja belum entry (still inside squeeze, no expansion)
        curr_in_squeeze = (curr_bb_upper <= curr_kc_upper) and (curr_bb_lower >= curr_kc_lower)
        is_expansion = (curr_close > prev_bb_upper) or (curr_bb_upper > curr_kc_upper)
        if curr_in_squeeze and not is_expansion:
            continue

        if curr_close <= prev_bb_upper and not (curr_close > curr_bb_upper):
            continue

        # S02-01-AC3: Gap above chase cap is rejected
        gap_pct = (curr_close - prev_close) / prev_close
        if gap_pct > max_chase_pct:
            continue

        # S02-01-AC2: Expansion without volume is rejected
        vol_col = "base_volume" if "base_volume" in p_df.columns else "volume"
        curr_vol = float(curr_row.get(vol_col, 0.0))
        avg_vol = float(prior_window[vol_col].mean()) if vol_col in prior_window.columns else 0.0
        if curr_vol < (avg_vol * volume_mult):
            continue

        # Valid expansion confirmed
        stop_loss = max(0.0, curr_close - atr_mult * curr_atr)

        intent = SignalIntent(
            intent_id=f"s02_{pair}_{int(frame.as_of.timestamp())}",
            decision_ts=frame.as_of,
            pair=pair,
            side=OrderSide.BUY,
            desired_qty=base_qty,
            limit_price=Decimal(str(curr_close)),
            stop_loss=Decimal(str(stop_loss)) if stop_loss > 0 else None,
            strategy_id=spec.strategy_id,
        )
        intents.append(intent)

    return intents
