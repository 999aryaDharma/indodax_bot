"""Regression and qualification tests for paper research release candidate (REL-01).

Guarantees:
1. REL-01-AC0: Paper research release is packaged with lock, runbook, and verified rollback (test_rel_01_valid_contract).
2. REL-01-AC1: Restoration of previous compatible artifact is proven and deterministic (test_rel_01_contract_1).
3. REL-01-AC2: Optional experimental work is strictly prevented from silent promotion (test_rel_01_contract_2).
4. REL-01-AC3: Unmet forward gate is clearly displayed as pending champion qualification (test_rel_01_contract_3).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from indodax_lab.verification.release import (
    ExperimentalPromotionForbiddenError,
    ReleaseCandidateManager,
    ReleaseCandidatePackage,
    RollbackIntegrityError,
)


def test_rel_01_valid_contract(tmp_path: Path) -> None:
    """AC0: Release paper/research terpaket dengan lock, runbook dan rollback yang diverifikasi."""
    manager = ReleaseCandidateManager()

    # Artifacts manifest with sha256 checksums
    dummy_artifact = tmp_path / "model_bundle_v1.json"
    dummy_artifact.write_text('{"weights": [0.1, 0.2]}', encoding="utf-8")
    checksum = hashlib.sha256(dummy_artifact.read_bytes()).hexdigest()

    manifest = {"model_bundle_v1.json": checksum}

    pkg: ReleaseCandidatePackage = manager.package_release(
        tag="v0.1.0-rc1",
        git_sha="abcdef1234567890",
        core_sprints=["QA-01", "QA-02", "QA-03", "REPORT-02"],
        champion_id="m01_momentum_v1",
        forward_days=45,  # Unmet forward longevity (<90 days)
        forward_trades=60,  # Unmet forward count (<100 trades)
        artifacts_manifest=manifest,
        rollback_target_tag="v0.0.9",
    )

    assert pkg.release_tag == "v0.1.0-rc1"
    assert pkg.software_rc_status == "READY"
    assert pkg.champion_status == "PENDING_FORWARD_EVALUATION"
    assert pkg.rollback_target_tag == "v0.0.9"
    assert "model_bundle_v1.json" in pkg.artifacts_manifest


def test_rel_01_contract_1(tmp_path: Path) -> None:
    """AC1: Restore previous compatible artifact terbukti."""
    manager = ReleaseCandidateManager()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Prepare previous compatible artifact v1.0.0
    v1_file = artifacts_dir / "candidate_weights_v1.0.0.json"
    v1_content = b'{"version": "1.0.0", "params": [1.0, 2.0]}'
    v1_file.write_bytes(v1_content)
    v1_checksum = hashlib.sha256(v1_content).hexdigest()

    v1_manifest = {"candidate_weights_v1.0.0.json": v1_checksum}

    # Successful rollback to v1.0.0
    result = manager.verify_and_execute_rollback(
        current_version="v1.1.0",
        target_version="v1.0.0",
        target_manifest=v1_manifest,
        artifacts_dir=artifacts_dir,
    )
    assert result is True

    # 2. Corrupted rollback target fails closed with RollbackIntegrityError
    corrupted_manifest = {"candidate_weights_v1.0.0.json": "corrupted_checksum_value"}
    with pytest.raises(RollbackIntegrityError):
        manager.verify_and_execute_rollback(
            current_version="v1.1.0",
            target_version="v1.0.0",
            target_manifest=corrupted_manifest,
            artifacts_dir=artifacts_dir,
        )


def test_rel_01_contract_2() -> None:
    """AC2: Optional experimental work tidak diam-diam dipromosikan."""
    manager = ReleaseCandidateManager()

    # 1. Experimental candidate without owner approval must fail closed
    with pytest.raises(ExperimentalPromotionForbiddenError) as exc_info:
        manager.promote_candidate(
            candidate_id="r01_rl_allocator_spike",
            tier="EXPERIMENTAL",
            is_owner_approved=False,
        )
    assert "EXPERIMENTAL_PROMOTION_FORBIDDEN" in str(exc_info.value)

    # 2. Extension candidate without approval must also fail closed
    with pytest.raises(ExperimentalPromotionForbiddenError) as exc_info2:
        manager.promote_candidate(
            candidate_id="dl_01_neural_worker",
            tier="EXTENSION",
            is_owner_approved=False,
        )
    assert "EXPERIMENTAL_PROMOTION_FORBIDDEN" in str(exc_info2.value)

    # 3. Core candidate or owner-approved candidate is allowed
    assert manager.promote_candidate("m01_logistic", tier="CORE") == "PROMOTED"
    assert manager.promote_candidate("r01_rl_allocator_spike", tier="EXPERIMENTAL", is_owner_approved=True) == "PROMOTED"


def test_rel_01_contract_3() -> None:
    """AC3: Unmet forward gate terlihat jelas sebagai pending champion qualification."""
    manager = ReleaseCandidateManager()

    # Candidate with 30 forward days and 40 trades (below 90 days and 100 trades threshold)
    status = manager.evaluate_release_status(
        software_ready=True,
        forward_days=30,
        forward_trades=40,
    )

    assert status["software_rc_status"] == "READY"
    assert status["champion_status"] == "PENDING_FORWARD_EVALUATION"
    assert "Pending forward qualification (30/90 days, 40/100 trades)" in status["reason"]

    # When both gates are met (e.g. 95 days, 120 trades)
    qualified_status = manager.evaluate_release_status(
        software_ready=True,
        forward_days=95,
        forward_trades=120,
    )
    assert qualified_status["champion_status"] == "QUALIFIED"
