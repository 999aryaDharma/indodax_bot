"""Cross sectional momentum strategy candidate (C04-01).

Contract:
PIT rank return top-K with liquidity and stable tie break -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.registry import StrategyRegistry


def load_c04_specification(config_path: str | Path = "configs/strategies/C04_v1.yaml") -> StrategySpecification:
    """Load and strictly validate canonical C04 cross sectional momentum specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c04_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
    """Pure, stateless decision function for C04 Cross sectional momentum candidate.

    Invariants:
    - Future listing cannot enter rank (excluded by eligibility and point-in-time boundary).
    - Rank tie is consistent across runs using canonical pair order.
    - Cash is reserved once on rotation across top-K allocation.
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_c04_specification()

    lookback_bars = int(spec.parameters.get("lookback_bars", 24))
    top_k = int(spec.parameters.get("top_k", 2))
    min_volume = float(spec.parameters.get("min_volume", 100.0))
    cash_reserve_pct = Decimal(str(spec.parameters.get("cash_reserve_pct", 0.20)))
    base_qty = Decimal(str(spec.parameters.get("base_qty", "0.1")))
    atr_mult = float(spec.parameters.get("atr_multiplier", 2.0))

    candidates: list[dict[str, Any]] = []

    for pair in sorted(frame.eligible_pairs):
        p_df = frame.get_pair_features(pair)
        if len(p_df) < lookback_bars + 1:
            continue

        window = p_df.iloc[-lookback_bars - 1 :]
        start_row = window.iloc[0]
        curr_row = window.iloc[-1]

        # Invariant: Future listing date or explicit ineligibility cannot enter rank
        if "listing_date" in curr_row and pd.notna(curr_row["listing_date"]):
            listing_dt = pd.to_datetime(curr_row["listing_date"], utc=True)
            if listing_dt > frame.as_of:
                continue

        if "eligible" in curr_row and not curr_row["eligible"]:
            continue

        if pd.isna(curr_row.get("close")) or pd.isna(start_row.get("close")):
            continue

        curr_close = float(curr_row["close"])
        start_close = float(start_row["close"])
        if start_close <= 0:
            continue

        # Check liquidity filter
        vol = float(curr_row.get("volume", curr_row.get("base_volume", 0.0)))
        if vol < min_volume:
            continue

        # Point-in-time momentum return over lookback
        mom_return = (curr_close - start_close) / start_close

        # Must have positive momentum to qualify for LONG
        if mom_return <= 0.0:
            continue

        atr_val = float(curr_row.get("atr_14", curr_row.get("atr", 0.0)))
        stop_loss = max(0.0, curr_close - atr_mult * atr_val)

        candidates.append(
            {
                "pair": pair,
                "mom_return": mom_return,
                "curr_close": curr_close,
                "stop_loss": stop_loss,
            }
        )

    if not candidates:
        return []

    # C04-01-AC2: Deterministic, consistent tie-breaking across runs
    # Primary key: return descending (-mom_return)
    # Secondary key: canonical pair ascending
    candidates.sort(key=lambda x: (-x["mom_return"], x["pair"]))

    selected = candidates[:top_k]
    if not selected:
        return []

    # C04-01-AC3: Cash reserved once on rotation
    # Total deployed across the rotation is bounded by (1.0 - cash_reserve_pct) * base_qty
    # Each slot gets an equal fraction of the deployable pool based on top_k
    deployable_qty = base_qty * (Decimal("1") - cash_reserve_pct)
    per_slot_qty = deployable_qty / Decimal(str(top_k))
    per_slot_qty_rounded = Decimal(str(round(per_slot_qty, 4)))

    intents: list[SignalIntent] = []
    for cand in selected:
        pair = cand["pair"]
        curr_close = cand["curr_close"]
        stop_loss = cand["stop_loss"]

        intent = SignalIntent(
            intent_id=f"c04_{pair}_{int(frame.as_of.timestamp())}",
            decision_ts=frame.as_of,
            pair=pair,
            side=OrderSide.BUY,
            desired_qty=per_slot_qty_rounded,
            limit_price=Decimal(str(curr_close)),
            stop_loss=Decimal(str(stop_loss)) if stop_loss > 0 else None,
            strategy_id=spec.strategy_id,
        )
        intents.append(intent)

    return intents
