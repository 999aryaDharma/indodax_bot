"""Regime ensemble strategy candidate (C10-01).

Contract:
Deterministic trend/reversion switch using available regime and frozen members -> versioned LONG/FLAT intent, never direct orders.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification
from indodax_lab.strategies.c01 import c01_decide, load_c01_specification
from indodax_lab.strategies.c07 import c07_decide, load_c07_specification
from indodax_lab.strategies.registry import StrategyRegistry


def load_c10_specification(config_path: str | Path = "configs/strategies/C10_v1.yaml") -> StrategySpecification:
    """Load and strictly validate the canonical C10 regime ensemble specification."""
    registry = StrategyRegistry()
    return registry.load_specification_from_yaml(config_path)


def c10_decide(frame: DecisionFrame, spec: StrategySpecification | None = None) -> list[SignalIntent]:
    """Pure, stateless decision function for C10 Regime ensemble candidate.

    Invariants:
    - Unknown regime produces cash (empty intents).
    - Future regime changes cannot alter decision at as_of.
    - Member version is explicitly recorded in each intent.
    - Strategies only produce SignalIntent, zero ledger or fill authority.
    """
    if spec is None:
        spec = load_c10_specification()

    trend_id = str(spec.parameters.get("trend_member_id", "C01"))
    trend_ver = str(spec.parameters.get("trend_member_version", "1.0.0"))
    rev_id = str(spec.parameters.get("reversion_member_id", "C07"))
    rev_ver = str(spec.parameters.get("reversion_member_version", "1.0.0"))

    regime_feature = str(spec.parameters.get("regime_feature", "regime"))
    trend_regimes = [str(r).strip().lower() for r in spec.parameters.get("trend_regimes", ["trending", "trend_up", "bull"])]
    rev_regimes = [str(r).strip().lower() for r in spec.parameters.get("reversion_regimes", ["sideways", "range", "neutral"])]

    # Load frozen member specifications
    c01_spec = load_c01_specification()
    c07_spec = load_c07_specification()

    intents: list[SignalIntent] = []

    for pair in frame.eligible_pairs:
        curr_row = frame.latest_row(pair)
        if curr_row is None:
            continue

        # C10-01-AC1: Unknown regime produces cash
        regime_val = curr_row.get(regime_feature)
        if regime_val is None or pd.isna(regime_val):
            continue

        regime_str = str(regime_val).strip().lower()

        pair_frame = DecisionFrame(
            as_of=frame.as_of,
            features=frame.get_pair_features(pair),
            eligible_pairs=(pair,),
            universe_snapshot_id=frame.universe_snapshot_id,
            feature_set_id=frame.feature_set_id,
            feature_set_version=frame.feature_set_version,
        )

        member_intents: list[SignalIntent] = []
        member_id: str | None = None
        member_ver: str | None = None

        if regime_str in trend_regimes:
            member_id = trend_id
            member_ver = trend_ver
            member_intents = c01_decide(pair_frame, c01_spec)
        elif regime_str in rev_regimes:
            member_id = rev_id
            member_ver = rev_ver
            member_intents = c07_decide(pair_frame, c07_spec)
        else:
            # C10-01-AC1: Unrecognized regime strictly produces cash (abstain)
            continue

        for m_intent in member_intents:
            # C10-01-AC3: Member version is recorded in intent
            c10_intent = SignalIntent(
                intent_id=f"c10_{pair}_{int(frame.as_of.timestamp())}_{member_id}_v{member_ver}",
                decision_ts=m_intent.decision_ts,
                pair=m_intent.pair,
                side=m_intent.side,
                desired_qty=m_intent.desired_qty,
                limit_price=m_intent.limit_price,
                stop_loss=m_intent.stop_loss,
                strategy_id=spec.strategy_id,
            )
            intents.append(c10_intent)

    return intents
