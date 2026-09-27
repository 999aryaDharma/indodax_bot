from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from indodax_lab.evaluation.lifecycle import (
    CandidateLifecycleManager,
    CandidateRecord,
    CandidateStage,
)
from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus

EXPOSED_AT = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


def _manager(
    tmp_path, candidate_id: str = "candidate", split_id: str = "split-v1"
) -> CandidateLifecycleManager:
    manager = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    candidate = CandidateRecord(
        candidate_id=candidate_id,
        candidate_version="1.0.0",
        strategy_name="candidate-strategy",
        config_hash="config-hash",
        current_stage=CandidateStage.IDEA,
        created_at=EXPOSED_AT,
    )
    manager.register_candidate(candidate)
    for stage in (
        CandidateStage.IMPLEMENTED,
        CandidateStage.BACKTESTED,
        CandidateStage.VALIDATED,
    ):
        manager.transition_stage(candidate_id, stage)
    manager.unseal_gate(
        candidate_id,
        split_id,
        authorized_by="researcher",
        as_of=EXPOSED_AT,
    )
    return manager


def _run(
    metric: float,
    *,
    candidate_id: str = "candidate",
    run_id: str = "run",
    metric_name: str = "sharpe_ratio",
    status: ExperimentRunStatus = ExperimentRunStatus.SUCCESS,
    created_at: datetime = datetime(2025, 6, 1, 13, 0, tzinfo=UTC),
    config_hash: str = "config-hash",
    split_id: str | None = "split-v1",
) -> ExperimentRunRecord:
    return ExperimentRunRecord(
        run_id=run_id,
        candidate_id=candidate_id,
        candidate_version="1.0.0",
        family="momentum",
        git_sha="abc123",
        environment_hash="environment",
        dataset_snapshot_id="snapshot",
        dataset_split_id=split_id,
        dataset_hash="dataset-hash",
        config_hash=config_hash,
        cost_schedule_hash="costs",
        execution_hash="execution",
        status=status,
        metrics={metric_name: metric},
        created_at=created_at,
        promotable=status == ExperimentRunStatus.SUCCESS,
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_eval_04_eligible_non_finite_metric_is_audited_once(tmp_path, value: float) -> None:
    manager = _manager(tmp_path)
    run = _run(value)

    assert manager.compute_leaderboard([run]) == []
    first = manager.get_leaderboard_exclusions()
    assert len(first) == 1
    assert first[0].run_digest == run.content_digest()
    assert first[0].candidate_id == run.candidate_id
    assert first[0].candidate_version == run.candidate_version
    assert first[0].dataset_split_id == run.dataset_split_id
    assert first[0].metric_name == "sharpe_ratio"
    assert first[0].reason_code == "RANK_METRIC_NON_FINITE"

    manager.compute_leaderboard([run])
    assert manager.get_leaderboard_exclusions() == first


def test_eval_04_ineligible_runs_do_not_create_exclusions(tmp_path) -> None:
    manager = _manager(tmp_path)
    runs = [
        _run(float("nan"), run_id="failed", status=ExperimentRunStatus.FAILED),
        _run(float("nan"), run_id="pre-exposure", created_at=EXPOSED_AT - timedelta(seconds=1)),
        _run(float("nan"), run_id="config-mismatch", config_hash="other"),
        _run(float("nan"), run_id="split-mismatch", split_id="other"),
        _run(float("nan"), run_id="missing-split", split_id=None),
        _run(float("nan"), run_id="unregistered", candidate_id="missing-candidate"),
        _run(float("nan"), run_id="missing-metric", metric_name="other_metric"),
        _run("not-a-number", run_id="unconvertible"),
    ]

    assert manager.compute_leaderboard(runs) == []
    assert manager.get_leaderboard_exclusions() == []


def test_eval_04_legacy_database_adds_table_without_rewriting_rows(tmp_path) -> None:
    manager = _manager(tmp_path)
    db_path = manager.db_path
    with sqlite3.connect(db_path) as conn:
        candidates_before = conn.execute("SELECT * FROM candidates").fetchall()
        exposures_before = conn.execute("SELECT * FROM exposure_audits").fetchall()
        conn.execute("DROP TABLE IF EXISTS leaderboard_metric_exclusions")

    reopened = CandidateLifecycleManager(db_path)
    with sqlite3.connect(db_path) as conn:
        candidates_after = conn.execute("SELECT * FROM candidates").fetchall()
        exposures_after = conn.execute("SELECT * FROM exposure_audits").fetchall()
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            ("leaderboard_metric_exclusions",),
        ).fetchone()
    CandidateLifecycleManager(db_path)

    assert candidates_after == candidates_before
    assert exposures_after == exposures_before
    assert table is not None
    assert reopened.get_leaderboard_exclusions() == []


def test_eval_04_metric_name_is_part_of_exclusion_identity(tmp_path) -> None:
    manager = _manager(tmp_path)
    run = _run(float("nan"), metric_name="sharpe_ratio")
    run = run.model_copy(
        update={"metrics": {"sharpe_ratio": float("nan"), "sortino_ratio": float("inf")}}
    )

    manager.compute_leaderboard([run], sort_metric="sharpe_ratio")
    manager.compute_leaderboard([run], sort_metric="sortino_ratio")
    exclusions = manager.get_leaderboard_exclusions()

    assert {item.metric_name for item in exclusions} == {"sharpe_ratio", "sortino_ratio"}
    assert len({item.exclusion_id for item in exclusions}) == 2


def test_eval_04_identity_binds_exposure_candidate_and_split(tmp_path) -> None:
    cases = [
        ("candidate", "split-v1"),
        ("candidate", "split-v1"),  # distinct exposure audit
        ("candidate-b", "split-v1"),
        ("candidate", "split-v2"),
    ]
    exclusion_ids = []
    for index, (candidate_id, split_id) in enumerate(cases):
        manager = _manager(tmp_path / str(index), candidate_id, split_id)
        manager.compute_leaderboard(
            [_run(float("nan"), candidate_id=candidate_id, split_id=split_id)]
        )
        exclusion_ids.append(manager.get_leaderboard_exclusions()[0].exclusion_id)

    assert len(set(exclusion_ids)) == len(cases)
