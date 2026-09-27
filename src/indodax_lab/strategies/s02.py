"""Squeeze expansion strategy candidate (S02-01).

Contract:
BB/Keltner squeeze followed by volume expansion and no-chase cap -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

import math
from decimal import Decimal
from pathlib import Path

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
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
        try:
            interval_ns = pd.tseries.frequencies.to_offset(spec.timeframes[0]).nanos
            bar_interval = pd.Timedelta(interval_ns, unit="ns")
        except (IndexError, ValueError):
            continue
        decision_times = pd.to_datetime(p_df["decision_ts"], utc=True)
        window_times = decision_times.iloc[-lookback_bars - 1 :]
        if (
            bar_interval <= pd.Timedelta(0)
            or window_times.iloc[-1] != pd.Timestamp(frame.as_of)
            or not window_times.diff().iloc[1:].eq(bar_interval).all()
        ):
            continue

        # Lookback window for prior bar indicators (excluding current bar to establish squeeze regime)
        prior_window = p_df.iloc[-lookback_bars - 1 : -1]
        try:
            prior_closes = [float(value) for value in prior_window["close"]]
            prev_close = float(prev_row["close"])
            curr_close = float(curr_row["close"])
            prev_atr = float(prev_row.get("atr_14", prev_row.get("atr")))
            curr_atr = float(curr_row.get("atr_14", curr_row.get("atr")))
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in (*prior_closes, prev_close, curr_close, prev_atr, curr_atr)):
            continue
        if prev_close <= 0.0 or curr_close <= 0.0 or prev_atr <= 0.0 or curr_atr <= 0.0:
            continue

        prev_mean = float(prior_window["close"].mean())
        prev_std = float(prior_window["close"].std(ddof=1)) if len(prior_window) > 1 else 0.0
        if not math.isfinite(prev_mean) or not math.isfinite(prev_std):
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

        # S02-01-AC3: Gap above chase cap is rejected
        gap_pct = (curr_close - prev_close) / prev_close
        if not math.isfinite(gap_pct) or gap_pct > max_chase_pct:
            continue

        # S02-01-AC2: Expansion without volume is rejected
        vol_col = "base_volume" if "base_volume" in p_df.columns else "volume"
        if vol_col not in p_df.columns:
            continue
        try:
            volumes = [float(value) for value in prior_window[vol_col]]
            curr_vol = float(curr_row[vol_col])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) and value >= 0.0 for value in (*volumes, curr_vol)):
            continue
        avg_vol = sum(volumes) / len(volumes)
        if avg_vol <= 0.0 or curr_vol < (avg_vol * volume_mult):
            continue

        # Expansion detection using PRIOR window bands only (no self-reference)
        is_expansion = curr_close > prev_bb_upper
        if not is_expansion:
            continue

        # Valid expansion confirmed
        stop_loss = curr_close - atr_mult * curr_atr
        if not (math.isfinite(stop_loss) and 0.0 < stop_loss < curr_close):
            continue

        intent = SignalIntent(
            intent_id=f"s02_{pair}_{int(frame.as_of.timestamp())}",
            decision_ts=frame.as_of,
            pair=pair,
            side=OrderSide.BUY,
            desired_qty=base_qty,
            limit_price=Decimal(str(curr_close)),
            stop_loss=Decimal(str(stop_loss)),
            strategy_id=spec.strategy_id,
        )
        intents.append(intent)

    return intents
