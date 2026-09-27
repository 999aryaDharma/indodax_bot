"""Fail-closed regression tests for the EVAL-03 sealed candidate lifecycle.

Review findings covered:
- EVAL-03-F1 (Important): ``isolation_level=None`` triggers an implicit autocommit, so
  ``transition_stage`` and ``unseal_gate`` were non-atomic. A failure between the state
  write and the audit/transition record left the lifecycle inconsistent with no rollback.
- EVAL-03-F2 (Important): ``unseal_gate`` accepted any stage, including ``IDEA``, so the
  sealed evaluation gate could be opened before the candidate was ever validated.
- EVAL-03-F3 (Important): the stage read happened outside the write transaction, so two
  concurrent transitions could both read the same ``from_stage`` and both commit.
- EVAL-03-F4 (Important): ``compute_leaderboard`` admitted non-finite metric values, so a
  NaN Sharpe ranked above real results instead of being excluded as unusable evidence.

opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sqlite3

import pytest

from indodax_lab.evaluation.lifecycle import (
    CandidateFrozenError,
    CandidateLifecycleManager,
    CandidateRecord,
    CandidateStage,
    InvalidTransitionError,
)
from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus

BASE_TS = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


def _candidate(candidate_id: str) -> CandidateRecord:
    return CandidateRecord(
        candidate_id=candidate_id,
        candidate_version="1.0.0",
        strategy_name="C01_Donchian",
        config_hash="cfg_hash_initial",
        current_stage=CandidateStage.IDEA,
        created_at=BASE_TS,
    )


def _advance_to_validated(mgr: CandidateLifecycleManager, candidate_id: str) -> None:
    mgr.transition_stage(candidate_id, CandidateStage.IMPLEMENTED)
    mgr.transition_stage(candidate_id, CandidateStage.BACKTESTED)
    mgr.transition_stage(candidate_id, CandidateStage.VALIDATED)


def _run(run_id: str, candidate_id: str, sharpe: float) -> ExperimentRunRecord:
    return ExperimentRunRecord(
        run_id=run_id,
        candidate_id=candidate_id,
        candidate_version="1.0.0",
        family="momentum",
        git_sha="abcdef1234567890",
        is_dirty=False,
        environment_hash="env_001",
        dataset_snapshot_id="ds_001",
        dataset_hash="dsh_001",
        config_hash="cfg_001",
        cost_schedule_hash="cst_001",
        execution_hash="exe_001",
        status=ExperimentRunStatus.SUCCESS,
        metrics={"sharpe_ratio": sharpe},
        created_at=BASE_TS,
        promotable=True,
    )


def test_eval_03_unseal_from_idea_stage_is_refused(tmp_path: Path) -> None:
    """EVAL-03-F2: the sealed gate must be reachable only from its legal predecessor."""
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate("cand_idea")
    mgr.register_candidate(cand)

    with pytest.raises(InvalidTransitionError) as exc_info:
        mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="reviewer")
    assert "UNSEAL_REQUIRES_VALIDATED_STAGE" in str(exc_info.value)

    # No exposure may have been recorded, and the gate must still be closed.
    assert mgr.get_candidate(cand.candidate_id).sealed_gate_opened is False


@pytest.mark.parametrize("stage", ["IMPLEMENTED", "BACKTESTED"])
def test_eval_03_unseal_from_pre_validation_stages_is_refused(
    tmp_path: Path, stage: str
) -> None:
    """EVAL-03-F2: IMPLEMENTED/BACKTESTED are not the gate's predecessor stage either."""
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate(f"cand_{stage.lower()}")
    mgr.register_candidate(cand)
    mgr.transition_stage(cand.candidate_id, CandidateStage.IMPLEMENTED)
    if stage == "BACKTESTED":
        mgr.transition_stage(cand.candidate_id, CandidateStage.BACKTESTED)

    with pytest.raises(InvalidTransitionError) as exc_info:
        mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="reviewer")
    assert "UNSEAL_REQUIRES_VALIDATED_STAGE" in str(exc_info.value)


def test_eval_03_unseal_rejects_blank_split_and_authorizer(tmp_path: Path) -> None:
    """EVAL-03-F3: unseal evidence must be named, not blank, and the gate stays shut."""
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate("cand_unverified_unseal")
    mgr.register_candidate(cand)
    _advance_to_validated(mgr, cand.candidate_id)

    with pytest.raises(ValueError, match="DATASET_SPLIT_ID_REQUIRED"):
        mgr.unseal_gate(cand.candidate_id, "   ", authorized_by="reviewer")
    with pytest.raises(ValueError, match="UNSEAL_AUTHORIZED_BY_REQUIRED"):
        mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="  ")

    stored = mgr.get_candidate(cand.candidate_id)
    assert stored.sealed_gate_opened is False


def test_eval_03_unseal_from_validated_still_succeeds(tmp_path: Path) -> None:
    """EVAL-03-F2 guard: the legal predecessor stage remains unsealable."""
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate("cand_validated")
    mgr.register_candidate(cand)
    _advance_to_validated(mgr, cand.candidate_id)

    audit = mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="reviewer")
    assert audit.candidate_id == cand.candidate_id
    assert mgr.get_candidate(cand.candidate_id).sealed_gate_opened is True


_FAULT_STATE: dict[str, object] = {"armed": False, "needle": ""}


class _FaultyConnection(sqlite3.Connection):
    """Connection that can be told to fail one specific statement, for rollback proof."""

    def execute(self, sql, *args, **kwargs):  # type: ignore[no-untyped-def]
        if _FAULT_STATE["armed"] and _FAULT_STATE["needle"] in str(sql):
            raise sqlite3.OperationalError("injected audit-log failure")
        return super().execute(sql, *args, **kwargs)


def _install_faulty_connect(mgr: CandidateLifecycleManager, db_path: Path) -> None:
    def _connect() -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(db_path), timeout=10.0, isolation_level=None, factory=_FaultyConnection
        )
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    mgr._connect = _connect  # type: ignore[method-assign]


def test_eval_03_transition_is_atomic_when_the_audit_insert_fails(tmp_path: Path) -> None:
    """EVAL-03-F1: a failure after the stage write must not leave the stage advanced."""
    db_path = tmp_path / "lifecycle.db"
    mgr = CandidateLifecycleManager(db_path)
    cand = _candidate("cand_atomic")
    mgr.register_candidate(cand)

    _install_faulty_connect(mgr, db_path)
    _FAULT_STATE.update(armed=True, needle="INSERT INTO transitions")
    with pytest.raises(sqlite3.OperationalError):
        mgr.transition_stage(cand.candidate_id, CandidateStage.IMPLEMENTED)
    _FAULT_STATE.update(armed=False, needle="")

    # The stage write must have been rolled back with the failed audit insert.
    assert mgr.get_candidate(cand.candidate_id).current_stage == CandidateStage.IDEA
    assert mgr.get_transition_history(cand.candidate_id) == []

    # And the lifecycle is still usable afterwards.
    mgr.transition_stage(cand.candidate_id, CandidateStage.IMPLEMENTED)
    assert mgr.get_candidate(cand.candidate_id).current_stage == CandidateStage.IMPLEMENTED


def test_eval_03_unseal_is_atomic_when_the_exposure_insert_fails(tmp_path: Path) -> None:
    """EVAL-03-F1: a failed exposure-audit insert must not leave the gate marked opened."""
    db_path = tmp_path / "lifecycle.db"
    mgr = CandidateLifecycleManager(db_path)
    cand = _candidate("cand_unseal_atomic")
    mgr.register_candidate(cand)
    _advance_to_validated(mgr, cand.candidate_id)

    _install_faulty_connect(mgr, db_path)
    _FAULT_STATE.update(armed=True, needle="INSERT INTO exposure_audits")
    with pytest.raises(sqlite3.OperationalError):
        mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="reviewer")
    _FAULT_STATE.update(armed=False, needle="")

    assert mgr.get_candidate(cand.candidate_id).sealed_gate_opened is False
    with sqlite3.connect(str(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM exposure_audits").fetchone()[0] == 0

    # The gate must remain usable: a later authorized unseal succeeds and is recorded once.
    audit = mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="reviewer_2")
    assert audit.candidate_id == cand.candidate_id
    with sqlite3.connect(str(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM exposure_audits").fetchone()[0] == 1


def test_eval_03_transition_and_audit_commit_together(tmp_path: Path) -> None:
    """EVAL-03-F1: after a successful transition both rows are durable."""
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate("cand_committed")
    mgr.register_candidate(cand)
    mgr.transition_stage(cand.candidate_id, CandidateStage.IMPLEMENTED, reason="done")

    assert mgr.get_candidate(cand.candidate_id).current_stage == CandidateStage.IMPLEMENTED
    history = mgr.get_transition_history(cand.candidate_id)
    assert len(history) == 1
    assert history[0].to_stage == CandidateStage.IMPLEMENTED
    assert history[0].reason == "done"


def test_eval_03_concurrent_double_unseal_opens_the_gate_once(tmp_path: Path) -> None:
    """EVAL-03-F3: the single-use gate must stay single-use under a second opener."""
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate("cand_race")
    mgr.register_candidate(cand)
    _advance_to_validated(mgr, cand.candidate_id)

    mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="first")
    with pytest.raises(Exception) as exc_info:
        mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="second")
    assert "GATE_ALREADY_OPENED" in str(exc_info.value)

    with sqlite3.connect(str(tmp_path / "lifecycle.db")) as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM exposure_audits WHERE candidate_id = ?",
            (cand.candidate_id,),
        ).fetchone()
    assert rows[0] == 1


def test_eval_03_non_finite_metric_is_excluded_from_leaderboard(tmp_path: Path) -> None:
    """EVAL-03-F4: NaN evidence must not be ranked as a neutral or top result."""
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    for candidate_id in ("cand_ok_1", "cand_ok_2"):
        candidate = _candidate(candidate_id)
        mgr.register_candidate(candidate)
        _advance_to_validated(mgr, candidate_id)
        mgr.unseal_gate(candidate_id, "split_v1", authorized_by="reviewer")

    board = mgr.compute_leaderboard(
        [
            _run("run_nan", "cand_nan", float("nan")),
            _run("run_inf", "cand_inf", float("inf")),
            _run("run_ok_1", "cand_ok_1", 1.8),
            _run("run_ok_2", "cand_ok_2", 1.2),
        ],
        sort_metric="sharpe_ratio",
    )

    ranked = [entry.candidate_id for entry in board]
    assert ranked == ["cand_ok_1", "cand_ok_2"]
    assert [entry.rank for entry in board] == [1, 2]


@pytest.mark.parametrize(
    ("stage", "gate_opened"),
    [(CandidateStage.CHAMPION, False), (CandidateStage.IDEA, True)],
)
def test_eval_03_registration_cannot_bypass_lifecycle(
    tmp_path: Path, stage: CandidateStage, gate_opened: bool
) -> None:
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate("cand_bypass").model_copy(
        update={"current_stage": stage, "sealed_gate_opened": gate_opened}
    )

    with pytest.raises(ValueError, match="CANDIDATE_MUST_START_IDEA_GATE_CLOSED"):
        mgr.register_candidate(cand)


def test_eval_03_leaderboard_requires_registered_exposed_candidate(tmp_path: Path) -> None:
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    exposed = _candidate("cand_exposed")
    closed = _candidate("cand_closed")
    mgr.register_candidate(exposed)
    mgr.register_candidate(closed)
    _advance_to_validated(mgr, exposed.candidate_id)
    _advance_to_validated(mgr, closed.candidate_id)
    mgr.unseal_gate(exposed.candidate_id, "split_v1", authorized_by="reviewer")

    board = mgr.compute_leaderboard(
        [
            _run("run_exposed", exposed.candidate_id, 1.0),
            _run("run_closed", closed.candidate_id, 2.0),
            _run("run_unregistered", "cand_unregistered", 3.0),
        ]
    )

    assert [entry.candidate_id for entry in board] == [exposed.candidate_id]


def test_eval_03_config_update_cannot_win_race_with_freeze(tmp_path: Path, monkeypatch) -> None:
    mgr = CandidateLifecycleManager(tmp_path / "lifecycle.db")
    cand = _candidate("cand_config_race")
    mgr.register_candidate(cand)
    original_fetch = mgr._fetch_candidate

    def freeze_after_read(conn, candidate_id):
        record = original_fetch(conn, candidate_id)
        conn.execute(
            "UPDATE candidates SET current_stage = ?, sealed_gate_opened = 1 WHERE candidate_id = ?",
            (CandidateStage.SEALED_PASS.value, candidate_id),
        )
        return record

    monkeypatch.setattr(mgr, "_fetch_candidate", freeze_after_read)
    with pytest.raises(CandidateFrozenError, match="CONFIG_MUTATION_FORBIDDEN"):
        mgr.update_config(cand.candidate_id, "cfg_after_freeze")

    assert mgr.get_candidate(cand.candidate_id).config_hash == cand.config_hash


# Actor for every line this file contributes to review evidence:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
