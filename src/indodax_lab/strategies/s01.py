"""Liquidity screened breakout strategy candidate (S01-01).

Contract:
Breakout with spread/depth gate relative to simulated size -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.registry import StrategyRegistry


def load_s01_specification(config_path: str | Path = "configs/strategies/S01_v1.yaml") -> StrategySpecification:
    """Load and strictly validate the canonical S01 liquidity screened breakout specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def s01_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
    """Pure, stateless decision function for S01 Liquidity screened breakout candidate.

    Invariants:
    - Wide spread rejects entry.
    - Insufficient depth restricts order size to available depth.
    - Missing liquidity strictly blocks trade.
    - Breakout requires close > previous N-bar high and volume confirmation.
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_s01_specification()

    lookback_bars = int(spec.parameters.get("lookback_bars", 20))
    volume_mult = float(spec.parameters.get("volume_multiplier", 1.0))
    max_spread_bps = float(spec.parameters.get("max_spread_bps", 30.0))
    min_depth = float(spec.parameters.get("min_depth", 0.01))
    base_qty = Decimal(str(spec.parameters.get("base_qty", "0.1")))
    atr_mult = float(spec.parameters.get("atr_multiplier", 2.0))

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        if len(p_df) < lookback_bars + 1:
            continue

        curr_row = p_df.iloc[-1]

        # Incomplete / missing row values
        if pd.isna(curr_row.get("close")) or pd.isna(curr_row.get("high")) or pd.isna(curr_row.get("low")):
            continue
        if "eligible" in curr_row and not curr_row["eligible"]:
            continue

        # S01-01-AC3: Missing liquidity blocks trade
        spread_val = curr_row.get("spread_bps")
        depth_val = curr_row.get("depth_50bps")
        if depth_val is None:
            depth_val = curr_row.get("depth")

        if spread_val is None or depth_val is None:
            continue
        if pd.isna(spread_val) or pd.isna(depth_val):
            continue

        spread_bps = float(spread_val)
        avail_depth = float(depth_val)

        if spread_bps < 0 or avail_depth <= 0:
            continue

        # S01-01-AC1: Wide spread rejects entry
        if spread_bps > max_spread_bps:
            continue

        curr_close = float(curr_row["close"])

        # Previous N completed bars excluding current decision bar
        prev_window = p_df.iloc[-lookback_bars - 1 : -1]
        prev_n_high = float(prev_window["high"].max())

        # Volume gate
        vol_col = "base_volume" if "base_volume" in p_df.columns else "volume"
        curr_vol = float(curr_row.get(vol_col, 0.0))
        avg_vol = float(prev_window[vol_col].mean()) if vol_col in prev_window.columns else 0.0

        if curr_close <= prev_n_high or curr_vol < (avg_vol * volume_mult):
            continue

        # S01-01-AC2: Depth restricts size
        if avail_depth < float(base_qty):
            desired_qty = Decimal(str(round(avail_depth, 4)))
        else:
            desired_qty = base_qty

        if desired_qty < Decimal(str(min_depth)) or desired_qty <= Decimal("0"):
            continue

        # ATR stop loss
        atr_val = float(curr_row.get("atr_14", curr_row.get("atr", 0.0)))
        stop_loss = max(0.0, curr_close - atr_mult * atr_val)

        intent = SignalIntent(
            intent_id=f"s01_{pair}_{int(frame.as_of.timestamp())}",
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


# Alias for compatibility
c01_decide_s01 = s01_decide
