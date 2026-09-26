"""Donchian breakout strategy candidate (C01-01)."""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def _finite_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def load_c01_specification(
    config_path: str | Path = "configs/strategies/C01_v1.yaml",
) -> StrategySpecification:
    """Load and strictly validate the canonical C01 Donchian breakout specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c01_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
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

        # Only decide on the actual current row; an ineligible tail must not replay an old signal.
        curr_ts = pd.to_datetime(curr_row.get("decision_ts"), utc=True, errors="coerce")
        ready_ts = pd.to_datetime(curr_row.get("row_ready_at"), utc=True, errors="coerce")
        if pd.isna(curr_ts) or curr_ts != pd.Timestamp(frame.as_of):
            continue
        if pd.isna(ready_ts) or ready_ts > frame.as_of:
            continue

        curr_close = _finite_float(curr_row.get("close"))
        curr_high = _finite_float(curr_row.get("high"))
        curr_low = _finite_float(curr_row.get("low"))
        if (
            curr_close is None
            or curr_high is None
            or curr_low is None
            or curr_close <= 0
            or curr_low <= 0
            or curr_high < max(curr_close, curr_low)
            or curr_low > min(curr_close, curr_high)
        ):
            continue

        # C01-01-AC1: Previous N completed bars EXCLUDING current decision bar (-1)
        prev_window = p_df.iloc[-lookback_bars - 1 : -1]
        prev_highs = [_finite_float(value) for value in prev_window["high"]]
        if any(value is None or value <= 0 for value in prev_highs):
            continue
        prev_n_high = max(prev_highs)

        # Volume gate
        vol_col = "base_volume" if "base_volume" in p_df.columns else "volume"
        if vol_col not in prev_window.columns:
            continue
        curr_vol = _finite_float(curr_row.get(vol_col))
        prev_volumes = [_finite_float(value) for value in prev_window[vol_col]]
        if (
            curr_vol is None
            or curr_vol < 0
            or any(value is None or value < 0 for value in prev_volumes)
        ):
            continue
        avg_vol = math.fsum(prev_volumes) / len(prev_volumes)

        # C01-01-AC2: confirm breakout with price and volume gates.
        # Guard: abstain when avg_vol <= 0 (no volume history for confirmation)
        if avg_vol <= 0.0:
            continue
            
        if curr_close > prev_n_high and curr_vol >= (avg_vol * volume_mult):
            # Price-denominated ATR stop loss
            atr_val = _finite_float(curr_row.get("atr_14", curr_row.get("atr")))
            # Guard: abstain when ATR <= 0 (no valid stop loss)
            if atr_val is None or atr_val <= 0.0 or not math.isfinite(atr_mult):
                continue
            stop_loss = curr_close - atr_mult * atr_val
            if not math.isfinite(stop_loss) or not 0 < stop_loss < curr_close:
                continue

            intent = SignalIntent(
                intent_id=f"c01_{pair}_{int(frame.as_of.timestamp())}",
                decision_ts=frame.as_of,
                pair=pair,
                side=OrderSide.BUY,
                desired_qty=desired_qty,
                limit_price=Decimal(str(curr_close)),
                stop_loss=Decimal(str(stop_loss)),
                strategy_id=spec.strategy_id,
            )
            intents.append(intent)

    return intents
