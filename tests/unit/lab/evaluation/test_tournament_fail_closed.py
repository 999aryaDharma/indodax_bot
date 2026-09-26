"""QA-01 fail-closed regression tests for the Wave 1 tournament checkpoint.

RED written against the reviewed QA-01 implementation to prove three defects:

- F1 (Critical): non-finite / impossible ``sharpe`` and ``max_drawdown`` metrics fall
  through every comparison (``nan < 0.0`` and ``nan > 0.30`` are both ``False``) and are
  classified ``PASS``, which maps to the ``ADVANCE_TO_SHADOW`` action. A corrupt or
  unestimable run is therefore promoted toward shadow trading.
- F2 (Important): the sprint contract is "identical snapshot/folds/**costs** comparison"
  (QA-01-AC0), but ``cost_basis`` is never read by the classifier and candidates evaluated
  under different cost assumptions are silently ranked side by side.
- F3 (Important): an empty candidate portfolio returns a well-formed
  ``TournamentReport`` with ``candidates_evaluated=0``, so a wave gate can be satisfied by a
  tournament that evaluated nothing.

These are behavioural assertions on classification and governance rejection, not
import/collection smoke tests.
"""

from __future__ import annotations

import math

import pytest

from indodax_lab.evaluation.gates import EvaluationOutcome
from indodax_lab.evaluation.tournament import (
    TournamentCandidate,
    run_wave1_tournament,
)


def _candidate(**overrides) -> TournamentCandidate:
    base = {
        "candidate_id": "cand",
        "candidate_type": "strategy",
        "sharpe": 1.5,
        "max_drawdown": 0.05,
        "cost_basis": 0.004,
        "is_valid_run": True,
    }
    base.update(overrides)
    return TournamentCandidate(**base)


# ---------------------------------------------------------------------------
# F1 (Critical): non-finite / impossible metrics must not classify as PASS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "overrides"),
    [
        ("nan_sharpe", {"sharpe": math.nan}),
        ("nan_max_drawdown", {"max_drawdown": math.nan}),
        ("both_nan", {"sharpe": math.nan, "max_drawdown": math.nan}),
        ("posinf_sharpe", {"sharpe": math.inf}),
        ("neginf_max_drawdown", {"max_drawdown": -math.inf}),
        ("neg_inf_sharpe", {"sharpe": -math.inf}),
        ("negative_max_drawdown", {"max_drawdown": -0.05}),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_qa_01_non_finite_metrics_are_invalid_run_not_pass(label, overrides):
    """F1: unestimable metrics must classify INVALID_RUN, never PASS."""
    report = run_wave1_tournament([_candidate(**overrides)], snapshot_id="snap_f1")

    result = report.results[0]
    assert result.outcome is EvaluationOutcome.INVALID_RUN, (
        f"{label}: outcome {result.outcome!r} must be INVALID_RUN"
    )
    assert result.outcome is not EvaluationOutcome.PASS


def test_qa_01_non_finite_metrics_never_advance_to_shadow():
    """F1: the ADVANCE_TO_SHADOW action is the safety consequence and must not fire."""
    candidates = [
        _candidate(candidate_id="nan_sharpe", sharpe=math.nan),
        _candidate(candidate_id="nan_dd", max_drawdown=math.nan),
        _candidate(candidate_id="neg_dd", max_drawdown=-0.42),
    ]

    report = run_wave1_tournament(candidates, snapshot_id="snap_f1_actions")
    actions = {fu.candidate_id: fu.action for fu in report.follow_ups}

    assert "ADVANCE_TO_SHADOW" not in actions.values(), actions
    for candidate_id in ("nan_sharpe", "nan_dd", "neg_dd"):
        assert actions[candidate_id] == "RETRY_WITH_BACKOFF"


def test_qa_01_invalid_metric_records_machine_readable_reason():
    """F1: the excluded candidate must carry an auditable reason token."""
    report = run_wave1_tournament([_candidate(sharpe=math.nan)], snapshot_id="snap_f1_reason")

    result = report.results[0]
    assert hasattr(result, "exclusion_reason"), (
        "TournamentCandidate must expose an auditable exclusion_reason"
    )
    assert result.exclusion_reason == "NON_FINITE_SHARPE"


def test_qa_01_finite_genuine_results_are_unaffected():
    """F1 fix must not demote genuinely good candidates."""
    candidates = [
        _candidate(candidate_id="good", sharpe=1.5, max_drawdown=0.05),
        _candidate(candidate_id="near", sharpe=0.92, max_drawdown=0.11),
        _candidate(candidate_id="bad", sharpe=-0.8, max_drawdown=0.50),
    ]

    report = run_wave1_tournament(candidates, snapshot_id="snap_f1_control")
    outcomes = {r.candidate_id: r.outcome for r in report.results}

    assert outcomes == {
        "good": EvaluationOutcome.PASS,
        "near": EvaluationOutcome.NEAR_MISS,
        "bad": EvaluationOutcome.HARD_FAIL,
    }
    assert all(hasattr(r, "exclusion_reason") for r in report.results)
    assert all(r.exclusion_reason is None for r in report.results)


def test_qa_01_invalid_run_flag_still_short_circuits():
    """F1: the pre-existing ``is_valid_run=False`` path keeps its own reason."""
    report = run_wave1_tournament(
        [_candidate(is_valid_run=False)], snapshot_id="snap_f1_invalid"
    )

    assert report.results[0].outcome is EvaluationOutcome.INVALID_RUN
    assert report.results[0].exclusion_reason == "RUN_NOT_VALID"


# ---------------------------------------------------------------------------
# F2 (Important): identical cost basis is a contract requirement
# ---------------------------------------------------------------------------


def test_qa_01_mixed_cost_basis_is_rejected():
    """F2: comparing candidates across different cost bases is not a valid tournament."""
    candidates = [
        _candidate(candidate_id="cheap_costs", cost_basis=0.0001),
        _candidate(candidate_id="real_costs", cost_basis=0.004),
    ]

    with pytest.raises(ValueError) as excinfo:
        run_wave1_tournament(candidates, snapshot_id="snap_f2")

    assert "COST_BASIS_NOT_IDENTICAL" in str(excinfo.value)


def test_qa_01_portfolio_rejection_error_is_public_api():
    """F2/F3: the rejection must be a documented, catchable public error type."""
    import indodax_lab.evaluation as evaluation_pkg

    error_type = getattr(evaluation_pkg, "TournamentPortfolioInvalidError", None)
    assert error_type is not None, "TournamentPortfolioInvalidError must be exported"
    assert issubclass(error_type, ValueError)


def test_qa_01_identical_cost_basis_is_accepted():
    """F2 fix must not reject a portfolio that honours the identical-cost contract."""
    candidates = [
        _candidate(candidate_id="a", cost_basis=0.004),
        _candidate(candidate_id="b", cost_basis=0.004),
    ]

    report = run_wave1_tournament(candidates, snapshot_id="snap_f2_ok")

    assert report.candidates_evaluated == 2
    assert {r.cost_basis for r in report.results} == {0.004}


def test_qa_01_non_finite_cost_basis_is_invalid_run():
    """F2: an unestimable cost assumption must also fail closed."""
    report = run_wave1_tournament(
        [_candidate(cost_basis=math.nan)], snapshot_id="snap_f2_nan"
    )

    assert report.results[0].outcome is EvaluationOutcome.INVALID_RUN
    assert report.results[0].exclusion_reason == "NON_FINITE_COST_BASIS"


# ---------------------------------------------------------------------------
# F3 (Important): an empty portfolio must not produce a checkpoint report
# ---------------------------------------------------------------------------


def test_qa_01_empty_portfolio_is_rejected():
    """F3: zero evaluated candidates must not be reported as a completed tournament."""
    with pytest.raises(ValueError) as excinfo:
        run_wave1_tournament([], snapshot_id="snap_f3")

    assert "EMPTY_TOURNAMENT_PORTFOLIO" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC3 guard: the fix must not weaken the live-profitability prohibition
# ---------------------------------------------------------------------------


def test_qa_01_profitability_claim_still_forbidden():
    """AC3 regression guard while the classifier changes."""
    from indodax_lab.evaluation.tournament import LiveProfitabilityClaimForbiddenError

    with pytest.raises(LiveProfitabilityClaimForbiddenError):
        run_wave1_tournament(
            [_candidate()], snapshot_id="snap_ac3", claim_live_profitability=True
        )
