"""Unit tests for immutable experiment registry (EVAL-01)."""

from datetime import UTC, datetime
from typing import Any
import pytest

from indodax_lab.evaluation.registry import (
    ExperimentRegistry,
    ExperimentRunRecord,
    ExperimentRunStatus,
)


def _make_run(
    run_id: str,
    parent_run_id: str | None = None,
    candidate_id: str = "C01_donchian",
    candidate_version: str = "1.0.0",
    family: str = "breakout",
    is_dirty: bool = False,
    status: ExperimentRunStatus = ExperimentRunStatus.SUCCESS,
    promotable: bool | None = None,
    metrics: dict[str, Any] | None = None,
) -> ExperimentRunRecord:
    """Helper to build a valid ExperimentRunRecord."""
    if promotable is None:
        promotable = (not is_dirty) and (status == ExperimentRunStatus.SUCCESS)

    return ExperimentRunRecord(
        run_id=run_id,
        parent_run_id=parent_run_id,
        candidate_id=candidate_id,
        candidate_version=candidate_version,
        family=family,
        git_sha="5687c100782c6b62de53d643d855df232f6ff7ba",
        is_dirty=is_dirty,
        environment_hash="env_hash_123",
        dataset_snapshot_id="snap_2024_06",
        dataset_hash="dataset_sha256_abc",
        config_hash="cfg_sha256_def",
        cost_schedule_hash="cost_sha256_ghi",
        execution_hash="exec_sha256_jkl",
        status=status,
        metrics=metrics or {"net_profit": 150000.0, "sharpe": 1.5},
        created_at=datetime(2024, 6, 1, 12, 0, tzinfo=UTC),
        promotable=promotable,
    )


def test_eval_01_valid_contract():
    """EVAL-01-AC0: Setiap percobaan termasuk gagal tersimpan dengan konfigurasi dan ancestry yang dapat diaudit."""
    registry = ExperimentRegistry()

    # 1. Record parent run (failed baseline)
    parent_run = _make_run(
        run_id="run-001",
        status=ExperimentRunStatus.FAILED,
        metrics={"net_profit": -50000.0},
    )
    registry.record_run(parent_run)

    # 2. Record child run (successful tuned hypothesis)
    child_run = _make_run(
        run_id="run-002",
        parent_run_id="run-001",
        candidate_version="1.1.0",
        status=ExperimentRunStatus.SUCCESS,
        metrics={"net_profit": 200000.0},
    )
    registry.record_run(child_run)

    # Assert retrieval
    retrieved_child = registry.get_run("run-002")
    assert retrieved_child is not None
    assert retrieved_child.run_id == "run-002"
    assert retrieved_child.parent_run_id == "run-001"
    assert retrieved_child.candidate_version == "1.1.0"
    assert retrieved_child.status == ExperimentRunStatus.SUCCESS

    # Assert ancestry chain can be traced back to parent
    ancestry = registry.get_ancestry("run-002")
    assert len(ancestry) == 2
    assert ancestry[0].run_id == "run-002"
    assert ancestry[1].run_id == "run-001"
    assert ancestry[1].status == ExperimentRunStatus.FAILED


def test_eval_01_contract_1():
    """EVAL-01-AC1: Dirty worktree tidak memenuhi promotable run."""
    registry = ExperimentRegistry()

    # Attempting to declare a dirty run as promotable must be rejected
    with pytest.raises(ValueError, match="DIRTY_WORKTREE_CANNOT_BE_PROMOTABLE"):
        _make_run(
            run_id="run-dirty-01",
            is_dirty=True,
            promotable=True,
        )

    # A dirty run with promotable=False is stored, but excluded from promotable query
    dirty_run = _make_run(
        run_id="run-dirty-01",
        is_dirty=True,
        promotable=False,
    )
    registry.record_run(dirty_run)

    clean_run = _make_run(
        run_id="run-clean-01",
        is_dirty=False,
        promotable=True,
    )
    registry.record_run(clean_run)

    promotable_runs = registry.list_runs(promotable_only=True)
    promotable_ids = [r.run_id for r in promotable_runs]
    assert "run-clean-01" in promotable_ids
    assert "run-dirty-01" not in promotable_ids


def test_eval_01_contract_2():
    """EVAL-01-AC2: Failed trial ikut trial count."""
    registry = ExperimentRegistry()

    # Record 2 successful runs and 3 failed/invalid runs
    registry.record_run(_make_run("run-s1", status=ExperimentRunStatus.SUCCESS))
    registry.record_run(_make_run("run-s2", status=ExperimentRunStatus.SUCCESS))
    registry.record_run(_make_run("run-f1", status=ExperimentRunStatus.FAILED))
    registry.record_run(_make_run("run-f2", status=ExperimentRunStatus.FAILED))
    registry.record_run(_make_run("run-f3", status=ExperimentRunStatus.INVALID_RUN))

    # Total trial count must include failed runs
    total_trials = registry.get_trial_count(family="breakout")
    assert total_trials == 5, f"Expected 5 total trials including failed ones, got {total_trials}"

    # Also check per candidate
    candidate_trials = registry.get_trial_count(candidate_id="C01_donchian")
    assert candidate_trials == 5


def test_eval_01_contract_3():
    """EVAL-01-AC3: Duplicate run key tidak menimpa hasil berbeda."""
    registry = ExperimentRegistry()

    original_run = _make_run(
        run_id="run-fixed-01",
        metrics={"net_profit": 100000.0},
    )
    registry.record_run(original_run)

    # 1. Idempotent re-recording of identical run succeeds without error
    registry.record_run(original_run)

    # 2. Re-recording same run_id with different metrics/config must fail
    conflicting_run = _make_run(
        run_id="run-fixed-01",
        metrics={"net_profit": 999999.0},  # Tampered or conflicting outcome
    )
    with pytest.raises(ValueError, match="DUPLICATE_RUN_KEY_CANNOT_OVERWRITE_DIFFERENT_RESULT"):
        registry.record_run(conflicting_run)

    # Ensure original run was preserved and not mutated
    saved = registry.get_run("run-fixed-01")
    assert saved is not None
    assert saved.metrics["net_profit"] == 100000.0
