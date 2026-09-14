"""Regression tests for QA-01: Wave 1 tournament checkpoint.

RED tests written before implementation.

Contract: tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

AC boundaries:
- AC0: Tiny tournament checkpoint unites baseline classical ML and rule-based strategies deterministically.
- AC1: Fixture produces and verifies all four lifecycle outcomes: INVALID_RUN, HARD_FAIL, NEAR_MISS, PASS.
- AC2: Follow-up actions correctly match evaluation outcomes per JOB-03 repeat policy.
- AC3: Tiny CI results explicitly forbid claims of real-market profitability (disclaimer and flag required).
"""

from __future__ import annotations

import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.evaluation.gates import EvaluationOutcome
from indodax_lab.evaluation.tournament import (
    LiveProfitabilityClaimForbiddenError,
    TournamentCandidate,
    TournamentReport,
    run_wave1_tournament,
)


# ---------------------------------------------------------------------------
# AC0: Tiny offline tournament runs deterministically on identical snapshot
# ---------------------------------------------------------------------------

def test_qa_01_valid_contract():
    """QA-01-AC0: Tournament evaluates candidate portfolio deterministically on common snapshot."""
    candidates = [
        TournamentCandidate(
            candidate_id="c01_donchian",
            candidate_type="strategy",
            sharpe=1.2,
            max_drawdown=0.08,
            cost_basis=0.004,
            is_valid_run=True,
        ),
        TournamentCandidate(
            candidate_id="m01_logistic",
            candidate_type="model",
            sharpe=1.1,
            max_drawdown=0.09,
            cost_basis=0.004,
            is_valid_run=True,
        ),
    ]

    report1 = run_wave1_tournament(candidates, snapshot_id="snap_20240601")
    report2 = run_wave1_tournament(candidates, snapshot_id="snap_20240601")

    assert isinstance(report1, TournamentReport)
    assert report1.snapshot_id == "snap_20240601"
    assert report1.candidates_evaluated == 2
    # Deterministic: identical input produces identical ranking/metrics
    assert report1.model_dump() == report2.model_dump()


# ---------------------------------------------------------------------------
# AC1: Fixture covers all four lifecycle outcomes
# ---------------------------------------------------------------------------

def test_qa_01_contract_1():
    """QA-01-AC1: Tournament fixture yields INVALID_RUN, HARD_FAIL, NEAR_MISS, and PASS outcomes."""
    portfolio = [
        TournamentCandidate(
            candidate_id="cand_pass",
            candidate_type="strategy",
            sharpe=1.5,
            max_drawdown=0.06,
            cost_basis=0.004,
            is_valid_run=True,
        ),
        TournamentCandidate(
            candidate_id="cand_near_miss",
            candidate_type="strategy",
            sharpe=0.95,  # Slightly below 1.0 threshold
            max_drawdown=0.12,
            cost_basis=0.004,
            is_valid_run=True,
        ),
        TournamentCandidate(
            candidate_id="cand_hard_fail",
            candidate_type="model",
            sharpe=-0.5,  # Catastrophic failure
            max_drawdown=0.45,
            cost_basis=0.004,
            is_valid_run=True,
        ),
        TournamentCandidate(
            candidate_id="cand_invalid_run",
            candidate_type="model",
            sharpe=0.0,
            max_drawdown=0.0,
            cost_basis=0.004,
            is_valid_run=False,  # Corrupted / interrupted run
        ),
    ]

    report = run_wave1_tournament(portfolio, snapshot_id="snap_all_outcomes")

    outcomes = {res.candidate_id: res.outcome for res in report.results}

    assert outcomes["cand_pass"] == EvaluationOutcome.PASS
    assert outcomes["cand_near_miss"] == EvaluationOutcome.NEAR_MISS
    assert outcomes["cand_hard_fail"] == EvaluationOutcome.HARD_FAIL
    assert outcomes["cand_invalid_run"] == EvaluationOutcome.INVALID_RUN


# ---------------------------------------------------------------------------
# AC2: Follow-up scheduling aligns with outcomes per JOB-03 repeat policy
# ---------------------------------------------------------------------------

def test_qa_01_contract_2():
    """QA-01-AC2: Follow-up actions map correctly to evaluation outcomes."""
    portfolio = [
        TournamentCandidate(candidate_id="c_pass", candidate_type="strategy", sharpe=1.5, max_drawdown=0.05, is_valid_run=True),
        TournamentCandidate(candidate_id="c_fail", candidate_type="model", sharpe=-0.8, max_drawdown=0.50, is_valid_run=True),
        TournamentCandidate(candidate_id="c_near", candidate_type="strategy", sharpe=0.92, max_drawdown=0.11, is_valid_run=True),
        TournamentCandidate(candidate_id="c_inv", candidate_type="model", sharpe=0.0, max_drawdown=0.0, is_valid_run=False),
    ]

    report = run_wave1_tournament(portfolio, snapshot_id="snap_follow_ups")
    follow_ups = {fu.candidate_id: fu for fu in report.follow_ups}

    # PASS -> advances to shadow trading
    assert follow_ups["c_pass"].action == "ADVANCE_TO_SHADOW"
    assert follow_ups["c_pass"].allowed_to_retry is False

    # HARD_FAIL -> retries blocked
    assert follow_ups["c_fail"].action == "BLOCK_RETRIES"
    assert follow_ups["c_fail"].allowed_to_retry is False

    # NEAR_MISS -> requires new version
    assert follow_ups["c_near"].action == "REQUIRE_NEW_VERSION"
    assert follow_ups["c_near"].allowed_to_retry is True

    # INVALID_RUN -> retry allowed under budget
    assert follow_ups["c_inv"].action == "RETRY_WITH_BACKOFF"
    assert follow_ups["c_inv"].allowed_to_retry is True


# ---------------------------------------------------------------------------
# AC3: Tiny CI is NOT real-market profitability evidence
# ---------------------------------------------------------------------------

def test_qa_01_contract_3():
    """QA-01-AC3: Tournament report contains strict disclaimer and rejects real-market profitability claims."""
    candidates = [
        TournamentCandidate(candidate_id="c1", candidate_type="strategy", sharpe=2.5, max_drawdown=0.02, is_valid_run=True),
    ]

    report = run_wave1_tournament(candidates, snapshot_id="snap_ci")

    assert report.is_real_market_evidence is False
    assert "TINY_CI_DOES_NOT_CONSTITUTE_REAL_MARKET_PROFITABILITY_EVIDENCE" in report.disclaimer

    # Attempting to claim live profitability raises LiveProfitabilityClaimForbiddenError
    with pytest.raises(LiveProfitabilityClaimForbiddenError):
        run_wave1_tournament(
            candidates,
            snapshot_id="snap_ci",
            claim_live_profitability=True,  # Forbidden!
        )
