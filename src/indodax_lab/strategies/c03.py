"""Time series momentum strategy candidate (C03-01)."""

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


def load_c03_specification(
    config_path: str | Path = "configs/strategies/C03_v1.yaml",
) -> StrategySpecification:
    """Load and strictly validate canonical C03 time series momentum specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c03_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Pure, stateless decision function for C03 Time series momentum candidate.

    Invariants:
    - Positive lookback return required; negative momentum remains 100% cash.
    - Zero realized volatility rejects / abstains without division by zero.
    - Future return cannot leak into or alter sizing.
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_c03_specification()

    lookback_bars = int(spec.parameters.get("lookback_bars", 24))
    target_vol = float(spec.parameters.get("target_volatility", 0.15))
    base_qty = Decimal(str(spec.parameters.get("base_qty", "0.1")))
    atr_mult = float(spec.parameters.get("atr_multiplier", 2.0))
    if (
        lookback_bars <= 0
        or not math.isfinite(target_vol)
        or target_vol <= 0
        or not base_qty.is_finite()
        or base_qty <= 0
        or not math.isfinite(atr_mult)
        or atr_mult <= 0
    ):
        raise ValueError("INVALID_C03_PARAMETERS")

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        if len(p_df) < lookback_bars + 1:
            continue

        window = p_df.iloc[-lookback_bars - 1 :]
        curr_row = window.iloc[-1]
        timestamps = pd.to_datetime(window["decision_ts"], utc=True, errors="coerce")
        ready_times = pd.to_datetime(window["row_ready_at"], utc=True, errors="coerce")
        if (
            timestamps.isna().any()
            or ready_times.isna().any()
            or not timestamps.is_monotonic_increasing
            or timestamps.duplicated().any()
            or (ready_times > timestamps).any()
            or timestamps.iloc[-1] != pd.Timestamp(frame.as_of)
            or not timestamps.dt.as_unit("ns").astype("int64")
            .diff()
            .iloc[1:]
            .eq(3_600_000_000_000)
            .all()
        ):
            continue

        closes = [_finite_float(value) for value in window["close"]]
        highs = [_finite_float(value) for value in window["high"]]
        lows = [_finite_float(value) for value in window["low"]]
        if any(value is None or value <= 0 for value in (*closes, *highs, *lows)):
            continue
        if any(
            high < max(close, low) or low > min(close, high)
            for close, high, low in zip(closes, highs, lows, strict=True)
        ):
            continue
        curr_close = closes[-1]
        start_close = closes[0]

        # Lookback momentum return
        mom_return = (curr_close - start_close) / start_close
        if not math.isfinite(mom_return):
            continue

        # C03-01-AC1: Negative momentum remains cash
        if mom_return <= 0.0:
            continue

        # Realized volatility over past lookback window
        pct_changes = pd.Series(closes).pct_change(fill_method=None).dropna()
        if pct_changes.empty or not pct_changes.map(math.isfinite).all():
            continue
        realized_vol = float(pct_changes.std(ddof=1))

        # C03-01-AC2: Zero volatility gives reject
        if not math.isfinite(realized_vol) or realized_vol <= 0.0:
            continue

        # Volatility-targeted sizing: scale inversely to realized volatility
        vol_denominator = realized_vol * 10.0
        scale = max(
            0.1,
            min(2.0, target_vol / vol_denominator if vol_denominator > 0 else 2.0),
        )
        desired_qty = Decimal(str(round(float(base_qty) * scale, 4)))
        if not desired_qty.is_finite() or desired_qty <= Decimal("0"):
            continue

        atr_val = _finite_float(curr_row.get("atr_14", curr_row.get("atr")))
        if atr_val is None or atr_val <= 0:
            continue
        stop_loss = curr_close - atr_mult * atr_val
        if not math.isfinite(stop_loss) or not 0 < stop_loss < curr_close:
            continue

        intent = SignalIntent(
            intent_id=f"c03_{pair}_{int(frame.as_of.timestamp())}",
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
