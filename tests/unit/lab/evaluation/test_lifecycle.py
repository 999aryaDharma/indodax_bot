"""Unit tests for EVAL-03 Sealed candidate lifecycle.

Acceptance Criteria:
- EVAL-03-AC0 (test_eval_03_valid_contract): Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.
- EVAL-03-AC1 (test_eval_03_contract_1): Config berubah setelah sealed menjadi challenger baru.
- EVAL-03-AC2 (test_eval_03_contract_2): Gate dibuka sekali dan dicatat.
- EVAL-03-AC3 (test_eval_03_contract_3): Invalid run tidak masuk ranking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import pytest

from indodax_lab.evaluation.gates import EvaluationOutcome, EvaluationResult
from indodax_lab.evaluation.lifecycle import (
    CandidateFrozenError,
    CandidateLifecycleManager,
    CandidateRecord,
    CandidateStage,
    GateAlreadyOpenedError,
    InvalidTransitionError,
    LeaderboardEntry,
)
from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus


def _build_test_candidate(candidate_id: str = "cand_alpha_v1") -> CandidateRecord:
    return CandidateRecord(
        candidate_id=candidate_id,
        candidate_version="1.0.0",
        strategy_name="C01_Donchian",
        config_hash="cfg_hash_initial_123",
        current_stage=CandidateStage.IDEA,
        parent_candidate_id=None,
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )


def test_eval_03_valid_contract(tmp_path: Path) -> None:
    """EVAL-03-AC0: Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka."""
    db_path = tmp_path / "lifecycle.db"
    mgr = CandidateLifecycleManager(db_path)

    cand = _build_test_candidate("cand_c01_v1")
    mgr.register_candidate(cand)

    # Progression: IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED
    mgr.transition_stage(cand.candidate_id, CandidateStage.IMPLEMENTED, reason="Implementation complete")
    mgr.transition_stage(cand.candidate_id, CandidateStage.BACKTESTED, reason="Backtest finished")
    mgr.transition_stage(cand.candidate_id, CandidateStage.VALIDATED, reason="In-sample validation pass")

    # Unseal gate with authorization and audit logging
    audit = mgr.unseal_gate(
        candidate_id=cand.candidate_id,
        dataset_split_id="split_2024_annual",
        authorized_by="lead_researcher",
        as_of=datetime(2025, 6, 1, 14, 0, tzinfo=UTC),
    )
    assert audit.candidate_id == cand.candidate_id
    assert audit.authorized_by == "lead_researcher"

    # Transition to SEALED_PASS after successful evaluation
    mgr.transition_stage(cand.candidate_id, CandidateStage.SEALED_PASS, reason="Passed sealed out-of-sample gate")

    # Further promotion: SHADOW -> CHAMPION
    mgr.transition_stage(cand.candidate_id, CandidateStage.SHADOW, reason="Deployed to paper shadow")
    mgr.transition_stage(cand.candidate_id, CandidateStage.CHAMPION, reason="Promoted to paper champion")

    final_cand = mgr.get_candidate(cand.candidate_id)
    assert final_cand.current_stage == CandidateStage.CHAMPION

    # Audit history is complete and strictly chronological
    history = mgr.get_transition_history(cand.candidate_id)
    stages = [h.to_stage for h in history]
    assert stages == [
        CandidateStage.IMPLEMENTED,
        CandidateStage.BACKTESTED,
        CandidateStage.VALIDATED,
        CandidateStage.SEALED_PASS,
        CandidateStage.SHADOW,
        CandidateStage.CHAMPION,
    ]


def test_eval_03_contract_1(tmp_path: Path) -> None:
    """EVAL-03-AC1: Config berubah setelah sealed menjadi challenger baru."""
    db_path = tmp_path / "lifecycle.db"
    mgr = CandidateLifecycleManager(db_path)

    cand = _build_test_candidate("cand_sealed_v1")
    mgr.register_candidate(cand)
    mgr.transition_stage(cand.candidate_id, CandidateStage.IMPLEMENTED)
    mgr.transition_stage(cand.candidate_id, CandidateStage.BACKTESTED)
    mgr.transition_stage(cand.candidate_id, CandidateStage.VALIDATED)
    mgr.unseal_gate(cand.candidate_id, "split_v1", authorized_by="reviewer_1")
    mgr.transition_stage(cand.candidate_id, CandidateStage.SEALED_PASS)

    # In-place config mutation on sealed candidate is strictly forbidden
    with pytest.raises(CandidateFrozenError) as exc_info:
        mgr.update_config(cand.candidate_id, new_config_hash="cfg_modified_456")
    assert "CONFIG_MUTATION_FORBIDDEN" in str(exc_info.value)

    # Instead, must branch into a new challenger candidate
    challenger = mgr.fork_challenger(
        parent_candidate_id=cand.candidate_id,
        new_candidate_id="cand_sealed_v2_challenger",
        new_candidate_version="2.0.0",
        new_config_hash="cfg_modified_456",
        created_at=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
    )

    assert challenger.candidate_id == "cand_sealed_v2_challenger"
    assert challenger.parent_candidate_id == cand.candidate_id
    assert challenger.config_hash == "cfg_modified_456"
    assert challenger.current_stage == CandidateStage.IDEA  # Lifecycle reset for new challenger

    # Original sealed candidate remains completely intact at SEALED_PASS
    original = mgr.get_candidate(cand.candidate_id)
    assert original.current_stage == CandidateStage.SEALED_PASS
    assert original.config_hash == "cfg_hash_initial_123"


def test_eval_03_contract_2(tmp_path: Path) -> None:
    """EVAL-03-AC2: Gate dibuka sekali dan dicatat."""
    db_path = tmp_path / "lifecycle.db"
    mgr = CandidateLifecycleManager(db_path)

    cand = _build_test_candidate("cand_single_gate_v1")
    mgr.register_candidate(cand)
    mgr.transition_stage(cand.candidate_id, CandidateStage.IMPLEMENTED)
    mgr.transition_stage(cand.candidate_id, CandidateStage.BACKTESTED)
    mgr.transition_stage(cand.candidate_id, CandidateStage.VALIDATED)

    # First unseal succeeds and is recorded
    first_audit = mgr.unseal_gate(
        cand.candidate_id,
        dataset_split_id="split_annual_2024",
        authorized_by="auditor_alpha",
    )
    assert first_audit.exposure_id is not None

    # Second unseal attempt on the same candidate version is strictly blocked fail-closed
    with pytest.raises(GateAlreadyOpenedError) as exc_info:
        mgr.unseal_gate(
            cand.candidate_id,
            dataset_split_id="split_annual_2024",
            authorized_by="auditor_beta",
        )
    assert "GATE_ALREADY_OPENED" in str(exc_info.value)


def test_eval_03_contract_3(tmp_path: Path) -> None:
    """EVAL-03-AC3: Invalid run tidak masuk ranking."""
    db_path = tmp_path / "lifecycle.db"
    mgr = CandidateLifecycleManager(db_path)

    base_time = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)

    # Run 1: Valid run with Sharpe 1.8
    run_valid_1 = ExperimentRunRecord(
        run_id="run_001",
        candidate_id="cand_strat_A",
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
        metrics={"sharpe_ratio": 1.8, "profit_factor": 1.5, "trade_count": 45},
        created_at=base_time,
        promotable=True,
    )

    # Run 2: Invalid run (e.g. unknown costs, corrupt data)
    run_invalid = ExperimentRunRecord(
        run_id="run_002",
        candidate_id="cand_strat_B",
        candidate_version="1.0.0",
        family="reversion",
        git_sha="abcdef1234567890",
        is_dirty=False,
        environment_hash="env_001",
        dataset_snapshot_id="ds_001",
        dataset_hash="dsh_001",
        config_hash="cfg_002",
        cost_schedule_hash="cst_001",
        execution_hash="exe_002",
        status=ExperimentRunStatus.INVALID_RUN,
        metrics={"sharpe_ratio": 99.0, "profit_factor": 10.0},  # Fabricated or untrustworthy metrics
        created_at=base_time,
        promotable=False,
    )

    # Run 3: Valid run with Sharpe 1.2
    run_valid_2 = ExperimentRunRecord(
        run_id="run_003",
        candidate_id="cand_strat_C",
        candidate_version="1.0.0",
        family="breakout",
        git_sha="abcdef1234567890",
        is_dirty=False,
        environment_hash="env_001",
        dataset_snapshot_id="ds_001",
        dataset_hash="dsh_001",
        config_hash="cfg_003",
        cost_schedule_hash="cst_001",
        execution_hash="exe_003",
        status=ExperimentRunStatus.SUCCESS,
        metrics={"sharpe_ratio": 1.2, "profit_factor": 1.3, "trade_count": 50},
        created_at=base_time,
        promotable=True,
    )

    leaderboard = mgr.compute_leaderboard([run_valid_1, run_invalid, run_valid_2], sort_metric="sharpe_ratio")

    # Verify run_invalid is strictly omitted from leaderboard
    ranked_candidates = [entry.candidate_id for entry in leaderboard]
    assert "cand_strat_B" not in ranked_candidates
    assert ranked_candidates == ["cand_strat_A", "cand_strat_C"]
    assert leaderboard[0].rank == 1
    assert leaderboard[1].rank == 2
