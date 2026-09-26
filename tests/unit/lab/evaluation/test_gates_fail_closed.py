"""Fail-closed regression tests for EVAL-02 hard gates and selection diagnostics.

Review findings covered:
- EVAL-02-F1 (Critical): ``metrics.get("cost_model_verified", True)`` defaulted the cost
  gate to *verified* whenever the flag was absent, so a run that never recorded cost
  evidence sailed through the gate that exists to stop exactly that. A stellar score
  silently concealed an unknown cost model (EVAL-02-AC1).
- EVAL-02-F2 (Critical): outcome classification treated any non-sample-size gate failure
  as a NEAR_MISS when Sharpe was positive and profit factor >= 1. A run breaching the
  maximum drawdown by 2.5x was therefore reported as a near miss rather than a hard fail,
  softening a risk breach into a promotable-looking verdict.
- EVAL-02-F3 (Important): ``compute_pbo`` drew its CSCV partitions from the unseeded
  global numpy RNG, so the same matrix produced a different PBO on every call. Selection
  diagnostics are recorded evidence, so they must be reproducible.

opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from indodax_lab.evaluation.gates import (
    EvaluationOutcome,
    EvaluationPolicy,
    evaluate_multi_seed_runs,
    evaluate_run,
)
from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus
from indodax_lab.evaluation.statistics import (
    compute_deflated_sharpe_ratio,
    compute_pbo,
)


def _run(**metric_overrides: Any) -> ExperimentRunRecord:
    """A strong, fully verified run; ``metric_overrides`` replaces individual metrics."""
    metrics: dict[str, Any] = {
        "sharpe_ratio": 1.8,
        "profit_factor": 1.5,
        "trade_count": 50,
        "max_drawdown": 0.10,
        "cost_model_verified": True,
    }
    metrics.update(metric_overrides)
    return ExperimentRunRecord(
        run_id="run_failclosed",
        candidate_id="c01_donchian",
        candidate_version="1.0.0",
        family="breakout",
        git_sha="0123456789abcdef0123456789abcdef01234567",
        is_dirty=False,
        environment_hash="env_hash_test",
        dataset_snapshot_id="snap_20250601",
        dataset_hash="dataset_hash_test",
        config_hash="config_hash_test",
        cost_schedule_hash="valid_cost_hash_123",
        execution_hash="exec_hash_test",
        status=ExperimentRunStatus.SUCCESS,
        metrics=metrics,
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        promotable=True,
    )


def test_eval_02_absent_cost_verification_fails_closed() -> None:
    """EVAL-02-F1: an unrecorded cost flag is unknown cost, not verified cost."""
    base = _run()
    metrics = {k: v for k, v in base.metrics.items() if k != "cost_model_verified"}
    stripped = base.model_copy(update={"metrics": metrics})

    result = evaluate_run(stripped, EvaluationPolicy())

    assert result.outcome == EvaluationOutcome.INVALID_RUN
    assert "COST_MODEL_UNKNOWN" in result.reasons
    assert result.outcome != EvaluationOutcome.PASS


@pytest.mark.parametrize("flag", [False, None, "unknown", 0])
def test_eval_02_only_an_explicit_true_verifies_costs(flag: Any) -> None:
    """EVAL-02-F1: only a literal verified flag satisfies the cost gate."""
    result = evaluate_run(_run(cost_model_verified=flag), EvaluationPolicy())
    assert result.outcome == EvaluationOutcome.INVALID_RUN
    assert "COST_MODEL_UNKNOWN" in result.reasons


def test_eval_02_risk_breach_is_never_softened_to_near_miss() -> None:
    """EVAL-02-F2: breaching max drawdown is a hard fail despite a positive score."""
    result = evaluate_run(_run(max_drawdown=0.50), EvaluationPolicy())

    assert "DRAWDOWN_EXCEEDS_THRESHOLD" in result.reasons
    assert result.outcome == EvaluationOutcome.HARD_FAIL
    assert result.outcome != EvaluationOutcome.NEAR_MISS
    assert result.outcome != EvaluationOutcome.PASS


def test_eval_02_risk_breach_stays_hard_fail_at_the_policy_limit() -> None:
    """EVAL-02-F2 guard: a breach combined with a thin sample is still a hard fail."""
    result = evaluate_run(
        _run(max_drawdown=0.50, trade_count=4), EvaluationPolicy(min_trade_count=30)
    )
    assert result.outcome == EvaluationOutcome.HARD_FAIL
    assert "DRAWDOWN_EXCEEDS_THRESHOLD" in result.reasons


_MATRIX = [
    [0.01, -0.02, 0.015, 0.005, -0.01],
    [0.02, 0.01, -0.005, 0.012, 0.003],
    [-0.01, 0.02, 0.01, -0.004, 0.008],
    [0.005, -0.008, 0.02, 0.01, -0.002],
    [0.012, 0.004, -0.01, 0.02, 0.006],
    [-0.005, 0.015, 0.008, -0.01, 0.012],
    [0.008, -0.003, 0.012, 0.006, -0.008],
    [0.015, 0.009, -0.006, 0.011, 0.004],
]


def test_eval_02_pbo_is_deterministic_for_identical_input() -> None:
    """EVAL-02-F3: repeated PBO evaluation of the same matrix must agree exactly."""
    first, first_status = compute_pbo(_MATRIX)
    second, second_status = compute_pbo(_MATRIX)

    assert first_status == "ESTIMATED"
    assert second_status == "ESTIMATED"
    assert first == second
    assert first is not None


def test_eval_02_pbo_ignores_global_numpy_rng_state() -> None:
    """EVAL-02-F3: PBO must not depend on (or consume) the process-wide numpy RNG."""
    import numpy as np

    np.random.seed(1234)
    first, _ = compute_pbo(_MATRIX)
    np.random.seed(9999)
    second, _ = compute_pbo(_MATRIX)

    assert first == second


def test_eval_02_pbo_is_stable_across_many_draws() -> None:
    """EVAL-02-F3: the estimate is reproducible, not merely stable on two samples."""
    values = {compute_pbo(_MATRIX)[0] for _ in range(25)}
    assert len(values) == 1


# --- EVAL-02-F4: non-finite / unusable metrics must never satisfy a quality gate ---

_NAN = float("nan")
_INF = float("inf")


@pytest.mark.parametrize("bad", [_NAN, _INF, -_INF])
@pytest.mark.parametrize("metric", ["sharpe_ratio", "profit_factor", "max_drawdown"])
def test_eval_02_non_finite_quality_metric_cannot_pass(metric: str, bad: float) -> None:
    """EVAL-02-F4: ``nan < x`` and ``nan > x`` are both False, so garbage passed every gate."""
    result = evaluate_run(_run(**{metric: bad}), EvaluationPolicy())

    assert result.outcome != EvaluationOutcome.PASS
    assert result.outcome == EvaluationOutcome.INVALID_RUN
    assert metric not in result.passed_gates
    assert any("METRIC" in reason for reason in result.reasons)


@pytest.mark.parametrize("metric", ["sharpe_ratio", "profit_factor", "max_drawdown", "trade_count"])
def test_eval_02_absent_quality_metric_does_not_pass(metric: str) -> None:
    """EVAL-02-F4: absent data keeps unknown semantics; it never defaults to a passing value."""
    base = _run()
    metrics = {k: v for k, v in base.metrics.items() if k != metric}
    result = evaluate_run(base.model_copy(update={"metrics": metrics}), EvaluationPolicy())

    assert result.outcome != EvaluationOutcome.PASS
    assert result.outcome == EvaluationOutcome.INVALID_RUN
    assert metric not in result.passed_gates


@pytest.mark.parametrize("bad_count", ["many", None, _NAN, _INF, [50]])
def test_eval_02_unusable_trade_count_is_invalid_run_not_a_crash(bad_count: object) -> None:
    """EVAL-02-F4: a malformed count is rejected as an invalid run, never raised at the caller."""
    result = evaluate_run(_run(trade_count=bad_count), EvaluationPolicy())

    assert result.outcome == EvaluationOutcome.INVALID_RUN
    assert "SAMPLE_SIZE_ADEQUATE" not in result.passed_gates


@pytest.mark.parametrize("bad_sharpe", [_NAN, _INF, -_INF])
def test_eval_02_dsr_is_not_estimated_from_a_non_finite_sharpe(bad_sharpe: float) -> None:
    """EVAL-02-F4: ``max(0.0, min(1.0, nan))`` is 1.0, so NaN reported maximum confidence."""
    dsr, status = compute_deflated_sharpe_ratio(
        sharpe_ratio=bad_sharpe,
        trial_count=5,
        returns=[0.01 * (1 if i % 2 == 0 else -1) for i in range(40)],
    )

    assert dsr is None
    assert status == "NOT_ESTIMABLE"


def test_eval_02_dsr_is_not_estimated_from_non_finite_returns() -> None:
    """EVAL-02-F4: non-finite return samples cannot support a selection-bias correction."""
    returns = [0.01 * (1 if i % 2 == 0 else -1) for i in range(40)]
    returns[7] = _NAN

    dsr, status = compute_deflated_sharpe_ratio(
        sharpe_ratio=1.2, trial_count=5, returns=returns
    )

    assert dsr is None
    assert status == "NOT_ESTIMABLE"


# --- EVAL-02-F5: the multi-seed aggregate must carry honest cost evidence ---

_MULTI_SEED_SHARPE = [2.5, 0.8, 1.2, 0.4, 1.1]


def _seed_runs() -> list[ExperimentRunRecord]:
    return [_run(sharpe_ratio=sr, run_id=f"run_seed_{i}")
            for i, sr in enumerate(_MULTI_SEED_SHARPE)]


def test_eval_02_multi_seed_aggregate_is_evaluable_when_every_seed_is_verified() -> None:
    """EVAL-02-F5: aggregating verified seeds must not manufacture an invalid run."""
    result = evaluate_multi_seed_runs(_seed_runs(), EvaluationPolicy())

    assert result.overall_outcome != EvaluationOutcome.INVALID_RUN
    assert result.finalist_metric["cost_model_verified"] is True


def test_eval_02_multi_seed_with_one_unverified_seed_is_invalid() -> None:
    """EVAL-02-F5: the aggregate is only as trustworthy as its least verified seed."""
    runs = _seed_runs()
    runs[2] = runs[2].model_copy(
        update={"metrics": {**runs[2].metrics, "cost_model_verified": False}}
    )

    result = evaluate_multi_seed_runs(runs, EvaluationPolicy())

    assert result.overall_outcome == EvaluationOutcome.INVALID_RUN
    assert result.finalist_metric["cost_model_verified"] is False


def test_eval_02_multi_seed_mixing_cost_schedules_is_invalid() -> None:
    """EVAL-02-F5: seeds priced with different cost schedules are not one candidate."""
    runs = _seed_runs()
    runs[3] = runs[3].model_copy(update={"cost_schedule_hash": "other_cost_hash"})

    result = evaluate_multi_seed_runs(runs, EvaluationPolicy())

    assert result.overall_outcome == EvaluationOutcome.INVALID_RUN


# Actor for every line this file contributes to review evidence:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
