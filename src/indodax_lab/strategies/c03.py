"""Time series momentum strategy candidate (C03-01).

Contract:
Positive lookback return with volatility target and cash fallback -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c03_specification(config_path: str | Path = "configs/strategies/C03_v1.yaml") -> StrategySpecification:
    """Load and strictly validate canonical C03 time series momentum specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c03_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
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

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        if len(p_df) < lookback_bars + 1:
            continue

        window = p_df.iloc[-lookback_bars - 1 :]
        start_row = window.iloc[0]
        curr_row = window.iloc[-1]

        if pd.isna(curr_row.get("close")) or pd.isna(start_row.get("close")):
            continue
        if "eligible" in curr_row and not curr_row["eligible"]:
            continue

        curr_close = float(curr_row["close"])
        start_close = float(start_row["close"])

        # Lookback momentum return
        mom_return = (curr_close - start_close) / start_close

        # C03-01-AC1: Negative momentum remains cash
        if mom_return <= 0.0:
            continue

        # Realized volatility over past lookback window
        pct_changes = window["close"].pct_change().dropna()
        realized_vol = float(pct_changes.std(ddof=1))

        # C03-01-AC2: Zero volatility gives reject
        if realized_vol <= 0.0 or pd.isna(realized_vol):
            continue

        # Volatility-targeted sizing: scale inversely to realized volatility
        scale = max(0.1, min(2.0, target_vol / (realized_vol * 10.0)))
        desired_qty = Decimal(str(round(float(base_qty) * scale, 4)))
        if desired_qty <= Decimal("0"):
            continue

        atr_val = float(curr_row.get("atr_14", curr_row.get("atr", 0.0)))
        stop_loss = max(0.0, curr_close - atr_mult * atr_val)

        intent = SignalIntent(
            intent_id=f"c03_{pair}_{int(frame.as_of.timestamp())}",
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
