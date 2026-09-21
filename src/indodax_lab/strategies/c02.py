"""EMA pullback strategy candidate (C02-01).

Contract:
Long EMA regime plus short EMA pullback and recovery -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.registry import StrategyRegistry


def load_c02_specification(config_path: str | Path = "configs/strategies/C02_v1.yaml") -> StrategySpecification:
    """Load and strictly validate canonical C02 EMA pullback specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c02_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
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

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        p_df = frame.get_pair_features(pair)
        if len(p_df) < 2:
            continue

        prev_row = p_df.iloc[-2]
        curr_row = p_df.iloc[-1]

        if pd.isna(curr_row.get("close")):
            continue
        if "eligible" in curr_row and not curr_row["eligible"]:
            continue

        curr_close = float(curr_row["close"])
        fast_ema = float(curr_row.get("ema_fast", 0.0))
        slow_ema = float(curr_row.get("ema_slow", 0.0))

        # C02-01-AC1: Downtrend menolak buy
        is_uptrend = (curr_close > slow_ema) and (fast_ema > slow_ema)
        if not is_uptrend:
            continue

        # C02-01-AC2 & AC3: Pullback and recovery
        prev_low = float(prev_row.get("low", prev_row.get("close")))
        prev_fast_ema = float(prev_row.get("ema_fast", fast_ema))

        had_pullback = prev_low <= prev_fast_ema
        is_recovered = curr_close > fast_ema

        # Pullback belum recovered tidak entry
        if had_pullback and is_recovered:
            atr_val = float(curr_row.get("atr_14", curr_row.get("atr", 0.0)))
            stop_loss = max(0.0, curr_close - atr_mult * atr_val)

            intent = SignalIntent(
                intent_id=f"c02_{pair}_{int(frame.as_of.timestamp())}",
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
