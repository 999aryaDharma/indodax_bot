"""Tests for SHADOW-03: Champion replacement gate.

RED tests written before implementation.

Contract: sealed pass + >=90 days AND >=100 pooled closed forward trades + no policy breach -> versioned promotion.

AC boundaries:
- AC0: Challenger with sealed pass, >=90 days, >=100 trades replaces champion.
- AC1: 100 trades within only 10 days is rejected (InsufficientForwardDurationError).
- AC2: 90 days with fewer than 100 trades is rejected (InsufficientForwardTradesError).
- AC3: Training/evaluating a challenger does NOT change the active champion.
"""

from __future__ import annotations

import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.paper.promotion import (
    ChallengerEvidence,
    ChampionRegistry,
    InsufficientForwardDurationError,
    InsufficientForwardTradesError,
    PromotionDecision,
    UnsealedCandidatePromotionError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_evidence(
    candidate_id: str = "challenger_m02",
    candidate_version: str = "2.0.0",
    is_sealed_pass: bool = True,
    forward_days: int = 95,
    closed_trades_count: int = 120,
    has_policy_breach: bool = False,
    outperformance: bool = True,
) -> ChallengerEvidence:
    return ChallengerEvidence(
        candidate_id=candidate_id,
        candidate_version=candidate_version,
        is_sealed_pass=is_sealed_pass,
        forward_days=forward_days,
        closed_trades_count=closed_trades_count,
        has_policy_breach=has_policy_breach,
        outperformance=outperformance,
    )


# ---------------------------------------------------------------------------
# AC0: Valid evidence promotes challenger to champion
# ---------------------------------------------------------------------------

def test_shadow_03_valid_contract():
    """SHADOW-03-AC0: Challenger with >=90 forward days, >=100 trades, sealed pass replaces champion."""
    registry = ChampionRegistry(
        initial_champion_id="champion_m01",
        initial_champion_version="1.0.0",
    )

    evidence = _make_evidence(
        candidate_id="challenger_m02",
        candidate_version="2.0.0",
        forward_days=95,
        closed_trades_count=120,
        is_sealed_pass=True,
    )

    decision = registry.evaluate_promotion(evidence)

    assert isinstance(decision, PromotionDecision)
    assert decision.promoted is True
    assert registry.active_champion_id == "challenger_m02"
    assert registry.active_champion_version == "2.0.0"


# ---------------------------------------------------------------------------
# AC1: 100 trades in 10 days does not pass (duration gate)
# ---------------------------------------------------------------------------

def test_shadow_03_contract_1():
    """SHADOW-03-AC1: 100 trades within only 10 days fails duration gate (InsufficientForwardDurationError)."""
    registry = ChampionRegistry(initial_champion_id="champion_m01", initial_champion_version="1.0.0")

    fast_evidence = _make_evidence(
        forward_days=10,  # Only 10 days (< 90)
        closed_trades_count=100,  # But 100 trades
    )

    with pytest.raises(InsufficientForwardDurationError):
        registry.evaluate_promotion(fast_evidence)

    # Active champion must remain unchanged
    assert registry.active_champion_id == "champion_m01"


# ---------------------------------------------------------------------------
# AC2: 90 days without enough trades does not pass (sample size gate)
# ---------------------------------------------------------------------------

def test_shadow_03_contract_2():
    """SHADOW-03-AC2: 90 forward days with only 40 trades fails sample size gate (InsufficientForwardTradesError)."""
    registry = ChampionRegistry(initial_champion_id="champion_m01", initial_champion_version="1.0.0")

    sparse_evidence = _make_evidence(
        forward_days=95,  # Sufficient duration (> 90)
        closed_trades_count=40,  # Insufficient trades (< 100)
    )

    with pytest.raises(InsufficientForwardTradesError):
        registry.evaluate_promotion(sparse_evidence)

    # Active champion must remain unchanged
    assert registry.active_champion_id == "champion_m01"


# ---------------------------------------------------------------------------
# AC3: Training challenger does NOT alter active champion
# ---------------------------------------------------------------------------

def test_shadow_03_contract_3():
    """SHADOW-03-AC3: Training, registering, or tuning a challenger leaves active champion unaltered."""
    registry = ChampionRegistry(initial_champion_id="champion_m01", initial_champion_version="1.0.0")

    # Simulate challenger training activity
    registry.record_challenger_activity(candidate_id="challenger_m02", action="TRAIN_STEP")
    registry.record_challenger_activity(candidate_id="challenger_m02", action="FOLD_EVAL")

    # Champion pointer must remain strictly untouched
    assert registry.active_champion_id == "champion_m01"
    assert registry.active_champion_version == "1.0.0"
