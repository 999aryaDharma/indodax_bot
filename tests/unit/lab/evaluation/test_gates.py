"""Unit tests for EVAL-02 Hard gates and selection diagnostics."""

from datetime import UTC, datetime
import pytest

from indodax_lab.evaluation.gates import (
    EvaluationOutcome,
    EvaluationPolicy,
    evaluate_multi_seed_runs,
    evaluate_run,
)
from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus


def _build_test_run(
    run_id: str = "run_001",
    sharpe: float = 1.8,
    profit_factor: float = 1.5,
    trade_count: int = 50,
    max_drawdown: float = 0.10,
    cost_schedule_hash: str = "valid_cost_hash_123",
    cost_model_verified: bool = True,
    is_dirty: bool = False,
    returns: list[float] | None = None,
) -> ExperimentRunRecord:
    """Helper to construct ExperimentRunRecord for evaluator tests."""
    return ExperimentRunRecord(
        run_id=run_id,
        candidate_id="c01_donchian",
        candidate_version="1.0.0",
        family="breakout",
        git_sha="0123456789abcdef0123456789abcdef01234567",
        is_dirty=is_dirty,
        environment_hash="env_hash_test",
        dataset_snapshot_id="snap_20250601",
        dataset_hash="dataset_hash_test",
        config_hash="config_hash_test",
        cost_schedule_hash=cost_schedule_hash,
        execution_hash="exec_hash_test",
        status=ExperimentRunStatus.SUCCESS,
        metrics={
            "sharpe_ratio": sharpe,
            "profit_factor": profit_factor,
            "trade_count": trade_count,
            "max_drawdown": max_drawdown,
            "cost_model_verified": cost_model_verified,
            "returns": returns or [0.01 * (1 if i % 2 == 0 else -0.5) for i in range(trade_count)],
        },
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        promotable=True,
    )


def test_eval_02_valid_contract() -> None:
    """EVAL-02-AC0: Evaluator separates run validity from strategy quality with versioned gates."""
    policy = EvaluationPolicy()
    run = _build_test_run(
        sharpe=1.8,
        profit_factor=1.5,
        trade_count=50,
        max_drawdown=0.10,
        cost_model_verified=True,
    )

    result = evaluate_run(run, policy)
    assert result.outcome == EvaluationOutcome.PASS
    assert "COST_MODEL_VERIFIED" in result.passed_gates
    assert "SAMPLE_SIZE_ADEQUATE" in result.passed_gates
    assert "SHARPE_GATE" in result.passed_gates
    assert "PROFIT_FACTOR_GATE" in result.passed_gates
    assert len(result.failed_gates) == 0


def test_eval_02_contract_1() -> None:
    """EVAL-02-AC1: High score does not conceal unknown costs."""
    policy = EvaluationPolicy()

    # Case A: Explicit cost_model_verified = False
    run_unverified = _build_test_run(
        sharpe=5.0,  # stellar score
        profit_factor=3.5,
        cost_model_verified=False,
    )
    result_a = evaluate_run(run_unverified, policy)
    assert result_a.outcome == EvaluationOutcome.INVALID_RUN
    assert "COST_MODEL_UNKNOWN" in result_a.reasons
    assert result_a.outcome != EvaluationOutcome.PASS

    # Case B: cost_schedule_hash is "unknown"
    run_unknown_hash = _build_test_run(
        sharpe=5.0,
        profit_factor=3.5,
        cost_schedule_hash="unknown",
    )
    result_b = evaluate_run(run_unknown_hash, policy)
    assert result_b.outcome == EvaluationOutcome.INVALID_RUN
    assert "COST_MODEL_UNKNOWN" in result_b.reasons


def test_eval_02_contract_2() -> None:
    """EVAL-02-AC2: Small sample produces insufficient evidence."""
    policy = EvaluationPolicy(min_trade_count=30)

    # Only 4 trades: insufficient evidence
    small_sample_run = _build_test_run(
        sharpe=2.5,
        profit_factor=2.0,
        trade_count=4,
    )

    result = evaluate_run(small_sample_run, policy)
    assert result.outcome == EvaluationOutcome.HARD_FAIL
    assert "INSUFFICIENT_SAMPLE_SIZE" in result.reasons
    assert result.dsr_status == "NOT_ESTIMABLE"
    assert result.pbo_status == "NOT_ESTIMABLE"
    assert result.outcome != EvaluationOutcome.PASS


def test_eval_02_contract_3() -> None:
    """EVAL-02-AC3: Best seed cannot be selected as finalist result."""
    policy = EvaluationPolicy()

    # Multi-seed runs with varying performance
    seeds = [42, 43, 44, 45, 46]
    sharpe_ratios = [2.5, 0.8, 1.2, 0.4, 1.1]  # best is 2.5, median is 1.1
    runs = [
        _build_test_run(
            run_id=f"run_seed_{s}",
            sharpe=sr,
            trade_count=40,
        )
        for s, sr in zip(seeds, sharpe_ratios)
    ]

    # Rejecting cherry-picked "best" seed selection
    with pytest.raises(ValueError, match="BEST_SEED_SELECTION_FORBIDDEN"):
        evaluate_multi_seed_runs(runs, policy, seed_selection="best")

    # Honest evaluation uses median/worst
    multi_result = evaluate_multi_seed_runs(runs, policy, seed_selection="median")
    assert multi_result.finalist_metric["sharpe_ratio"] == 1.1
    assert multi_result.finalist_metric["sharpe_ratio"] != 2.5
