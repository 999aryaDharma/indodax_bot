"""EMA pullback strategy candidate (C02-01)."""

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


def load_c02_specification(
    config_path: str | Path = "configs/strategies/C02_v1.yaml",
) -> StrategySpecification:
    """Load and strictly validate canonical C02 EMA pullback specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c02_decide(
    frame: DecisionFrame, spec: StrategySpecification | None = None
) -> list[SignalIntent]:
    """Pure, stateless decision function for C02 EMA pullback candidate.

    Invariants:
    - Long EMA regime filter: downtrend strictly rejects buy intents.
    - Pullback must have dipped below fast EMA.
    - Unrecovered pullback does not enter; closed bar recovery is mandatory.
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_c02_specification()

    atr_mult = float(spec.parameters.get("atr_multiplier", 1.5))
    desired_qty = Decimal(str(spec.parameters.get("desired_qty", "0.1")))
    if (
        not math.isfinite(atr_mult)
        or atr_mult <= 0
        or not desired_qty.is_finite()
        or desired_qty <= 0
    ):
        raise ValueError("INVALID_C02_PARAMETERS")

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        if len(p_df) < 2:
            continue

        prev_row = p_df.iloc[-2]
        curr_row = p_df.iloc[-1]

        prev_ts = pd.to_datetime(prev_row.get("decision_ts"), utc=True, errors="coerce")
        curr_ts = pd.to_datetime(curr_row.get("decision_ts"), utc=True, errors="coerce")
        prev_ready = pd.to_datetime(prev_row.get("row_ready_at"), utc=True, errors="coerce")
        curr_ready = pd.to_datetime(curr_row.get("row_ready_at"), utc=True, errors="coerce")
        if (
            pd.isna(prev_ts)
            or pd.isna(curr_ts)
            or pd.isna(prev_ready)
            or pd.isna(curr_ready)
            or not prev_ts < curr_ts
            or curr_ts != pd.Timestamp(frame.as_of)
            or prev_ready > prev_ts
            or curr_ready > curr_ts
        ):
            continue

        curr_close = _finite_float(curr_row.get("close"))
        curr_high = _finite_float(curr_row.get("high"))
        curr_low = _finite_float(curr_row.get("low"))
        prev_close = _finite_float(prev_row.get("close"))
        prev_high = _finite_float(prev_row.get("high"))
        prev_low = _finite_float(prev_row.get("low"))
        if any(
            value is None or value <= 0
            for value in (curr_close, curr_high, curr_low, prev_close, prev_high, prev_low)
        ):
            continue
        if (
            curr_high < max(curr_close, curr_low)
            or curr_low > min(curr_close, curr_high)
            or prev_high < max(prev_close, prev_low)
            or prev_low > min(prev_close, prev_high)
        ):
            continue

        fast_ema = _finite_float(curr_row.get("ema_fast"))
        slow_ema = _finite_float(curr_row.get("ema_slow"))
        prev_fast_ema = _finite_float(prev_row.get("ema_fast"))
        if any(
            value is None or value <= 0
            for value in (fast_ema, slow_ema, prev_fast_ema)
        ):
            continue

        # C02-01-AC1: Downtrend menolak buy
        is_uptrend = (curr_close > slow_ema) and (fast_ema > slow_ema)
        if not is_uptrend:
            continue

        # C02-01-AC2 & AC3: Pullback and recovery
        had_pullback = prev_low <= prev_fast_ema
        is_recovered = curr_close > fast_ema

        # Pullback belum recovered tidak entry
        if had_pullback and is_recovered:
            atr_val = _finite_float(curr_row.get("atr_14", curr_row.get("atr")))
            # Guard: abstain when ATR <= 0 (no valid stop loss)
            if atr_val is None or atr_val <= 0.0:
                continue
            stop_loss = curr_close - atr_mult * atr_val
            if not math.isfinite(stop_loss) or not 0 < stop_loss < curr_close:
                continue

            intent = SignalIntent(
                intent_id=f"c02_{pair}_{int(frame.as_of.timestamp())}",
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
