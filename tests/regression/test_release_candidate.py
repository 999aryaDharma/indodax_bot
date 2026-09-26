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


def _write_manifest(path: Path, statuses: dict[str, str]) -> Path:
    """Write a minimal sprint manifest with the given sprint -> status mapping."""
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "baseline_commit": "0" * 40,
                "generated_on": "2026-09-26",
                "status_basis": "test",
                "sprints": [
                    {"id": sprint_id, "status": status}
                    for sprint_id, status in statuses.items()
                ],
                "readiness_rule": "All dependencies DONE; external activation and review gates remain separate.",
            }
        ),
        encoding="utf-8",
    )
    return path


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
    # Software readiness is derived from real dependency evidence, never assumed. No
    # manifest evidence was supplied, so the package must not claim READY (REL-01-AC0).
    assert pkg.software_rc_status == "NOT_READY"
    assert pkg.champion_status == "PENDING_FORWARD_EVALUATION"
    assert pkg.rollback_target_tag == "v0.0.9"
    assert "model_bundle_v1.json" in pkg.artifacts_manifest


def test_rel_01_contract_1(tmp_path: Path) -> None:
    """AC1: Restore previous compatible artifact terbukti."""
    manager = ReleaseCandidateManager()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    active_dir = tmp_path / "active"
    active_dir.mkdir(parents=True, exist_ok=True)

    # 1. Prepare previous compatible artifact v1.0.0
    v1_file = artifacts_dir / "candidate_weights_v1.0.0.json"
    v1_content = b'{"version": "1.0.0", "params": [1.0, 2.0]}'
    v1_file.write_bytes(v1_content)
    v1_checksum = hashlib.sha256(v1_content).hexdigest()

    v1_manifest = {"candidate_weights_v1.0.0.json": v1_checksum}

    # The currently installed release is v1.1.0 and must be genuinely replaced.
    (active_dir / "candidate_weights_v1.0.0.json").write_bytes(
        b'{"version": "1.1.0", "params": [9.9, 9.9]}'
    )

    # Successful rollback to v1.0.0
    result = manager.verify_and_execute_rollback(
        current_version="v1.1.0",
        target_version="v1.0.0",
        target_manifest=v1_manifest,
        artifacts_dir=artifacts_dir,
        active_dir=active_dir,
    )
    assert result is True
    assert (active_dir / "candidate_weights_v1.0.0.json").read_bytes() == v1_content

    # 2. Corrupted rollback target fails closed with RollbackIntegrityError
    corrupted_manifest = {"candidate_weights_v1.0.0.json": "corrupted_checksum_value"}
    with pytest.raises(RollbackIntegrityError):
        manager.verify_and_execute_rollback(
            current_version="v1.1.0",
            target_version="v1.0.0",
            target_manifest=corrupted_manifest,
            artifacts_dir=artifacts_dir,
            active_dir=active_dir,
        )


# ---------------------------------------------------------------------------
# Sprint-review fix cycle. Actor for every line below:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
# ---------------------------------------------------------------------------


def test_package_release_is_ready_only_when_dependencies_are_done(tmp_path: Path) -> None:
    """REL-01: software readiness derives from real manifest evidence, not a constant."""
    manager = ReleaseCandidateManager()
    artifact = tmp_path / "model_bundle_v1.json"
    artifact.write_text('{"weights": [0.1, 0.2]}', encoding="utf-8")
    manifest = {"model_bundle_v1.json": hashlib.sha256(artifact.read_bytes()).hexdigest()}

    all_done = _write_manifest(
        tmp_path / "manifest-done.json",
        {"QA-01": "DONE", "QA-02": "DONE", "QA-03": "DONE", "REPORT-02": "DONE"},
    )
    ready = manager.package_release(
        tag="v0.1.0-rc1",
        git_sha="abcdef1234567890",
        core_sprints=["QA-01", "QA-02", "QA-03", "REPORT-02"],
        champion_id="m01_momentum_v1",
        forward_days=45,
        forward_trades=60,
        artifacts_manifest=manifest,
        rollback_target_tag="v0.0.9",
        manifest_path=all_done,
    )
    assert ready.software_rc_status == "READY"

    # Same call, but one dependency is still under review -> must NOT claim READY.
    unverified = _write_manifest(
        tmp_path / "manifest-review.json",
        {"QA-01": "DONE", "QA-02": "REVIEW", "QA-03": "DONE", "REPORT-02": "DONE"},
    )
    not_ready = manager.package_release(
        tag="v0.1.0-rc1",
        git_sha="abcdef1234567890",
        core_sprints=["QA-01", "QA-02", "QA-03", "REPORT-02"],
        champion_id="m01_momentum_v1",
        forward_days=45,
        forward_trades=60,
        artifacts_manifest=manifest,
        rollback_target_tag="v0.0.9",
        manifest_path=unverified,
    )
    assert not_ready.software_rc_status == "NOT_READY"


def test_package_release_fails_closed_without_verifiable_evidence(tmp_path: Path) -> None:
    """No manifest evidence, an unreadable manifest, or an unknown sprint -> NOT_READY."""
    manager = ReleaseCandidateManager()
    manifest = {"a.json": "0" * 64}

    def _package(manifest_path):
        return manager.package_release(
            tag="v0.1.0-rc1",
            git_sha="abcdef1234567890",
            core_sprints=["QA-01", "QA-02"],
            champion_id="c1",
            forward_days=95,
            forward_trades=120,
            artifacts_manifest=manifest,
            manifest_path=manifest_path,
        )

    # 1. No evidence at all.
    assert _package(None).software_rc_status == "NOT_READY"

    # 2. Manifest file does not exist.
    assert _package(tmp_path / "nope.json").software_rc_status == "NOT_READY"

    # 3. Malformed manifest must not crash the packager nor be read as ready.
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert _package(broken).software_rc_status == "NOT_READY"

    # 4. Sprint ids absent from the manifest cannot be assumed verified.
    partial = _write_manifest(tmp_path / "partial.json", {"QA-01": "DONE"})
    assert _package(partial).software_rc_status == "NOT_READY"


def test_package_release_ignores_narrative_evidence_claims(tmp_path: Path) -> None:
    """A prose evidence file claiming PASSED must not override the manifest authority."""
    manager = ReleaseCandidateManager()
    manifest = {"a.json": "0" * 64}

    # Narrative release evidence (docs/quality/release-evidence.md) claims QA-01..QA-03
    # PASSED. sprint-manifest.json is the only status authority and still says REVIEW,
    # so the package must follow the manifest.
    evidence_doc = tmp_path / "release-evidence.md"
    evidence_doc.write_text(
        "| Tournament Checkpoint (QA-01) | **PASSED** |\n"
        "| Boundary Security (QA-02) | **PASSED** |\n"
        "| Capacity & Recovery (QA-03) | **PASSED** |\n",
        encoding="utf-8",
    )
    authority = _write_manifest(
        tmp_path / "manifest.json",
        {"QA-01": "REVIEW", "QA-02": "REVIEW", "QA-03": "REVIEW"},
    )
    assert "PASSED" in evidence_doc.read_text(encoding="utf-8")

    pkg = manager.package_release(
        tag="v0.1.0-rc1",
        git_sha="abcdef1234567890",
        core_sprints=["QA-01", "QA-02", "QA-03"],
        champion_id="c1",
        forward_days=95,
        forward_trades=120,
        artifacts_manifest=manifest,
        manifest_path=authority,
    )
    assert pkg.software_rc_status == "NOT_READY"
    assert any("QA-01" in reason for reason in pkg.readiness_reasons)


@pytest.mark.parametrize("tier", ["BETA", "", "   ", "production", "unknown", None])
def test_promote_candidate_rejects_unknown_tier(tier: str) -> None:
    """REL-01-AC2: an unrecognized tier must be rejected, never promoted.

    Every case below stays outside the allowlist even after ``.strip().upper()``
    normalization. Case/whitespace variants of a *known* tier (e.g. ``"core "``)
    are normalized and accepted — see
    ``test_promote_candidate_still_allows_the_three_known_tiers``.
    """
    manager = ReleaseCandidateManager()
    with pytest.raises(ExperimentalPromotionForbiddenError) as exc_info:
        manager.promote_candidate(candidate_id="mystery_candidate", tier=tier)
    message = str(exc_info.value)
    assert "UNKNOWN_CANDIDATE_TIER" in message
    assert "PROMOTED" not in message


def test_promote_candidate_still_allows_the_three_known_tiers() -> None:
    """Regression guard: the closed tier allowlist must not over-block known tiers."""
    manager = ReleaseCandidateManager()
    assert manager.promote_candidate("m01_logistic", tier="CORE") == "PROMOTED"
    assert manager.promote_candidate("m01_logistic", tier=" core ") == "PROMOTED"
    assert (
        manager.promote_candidate("r01_rl_allocator_spike", tier="EXPERIMENTAL", is_owner_approved=True)
        == "PROMOTED"
    )
    with pytest.raises(ExperimentalPromotionForbiddenError):
        manager.promote_candidate("r01_rl_allocator_spike", tier="EXPERIMENTAL", is_owner_approved=False)


def test_rollback_without_destination_fails_loudly(tmp_path: Path) -> None:
    """A rollback with no restore destination must not report success (REL-01-AC1)."""
    manager = ReleaseCandidateManager()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    content = b'{"version": "1.0.0"}'
    (artifacts_dir / "w.json").write_bytes(content)
    target_manifest = {"w.json": hashlib.sha256(content).hexdigest()}

    with pytest.raises(RollbackIntegrityError) as exc_info:
        manager.verify_and_execute_rollback(
            current_version="v1.1.0",
            target_version="v1.0.0",
            target_manifest=target_manifest,
            artifacts_dir=artifacts_dir,
        )
    assert "RESTORATION_NOT_PERFORMED" in str(exc_info.value)


def test_rollback_actually_restores_previous_state(tmp_path: Path) -> None:
    """verify_and_execute_rollback must perform the restore, not just verify it (REL-01-AC1)."""
    manager = ReleaseCandidateManager()
    artifacts_dir = tmp_path / "artifacts"
    active_dir = tmp_path / "active"
    artifacts_dir.mkdir()
    active_dir.mkdir()

    target_bytes = b'{"version": "1.0.0", "params": [1.0, 2.0]}'
    (artifacts_dir / "weights.json").write_bytes(target_bytes)
    (artifacts_dir / "thresholds.json").write_bytes(b'{"tp": 0.03}')
    target_manifest = {
        "weights.json": hashlib.sha256(target_bytes).hexdigest(),
        "thresholds.json": hashlib.sha256(b'{"tp": 0.03}').hexdigest(),
    }

    installed = b'{"version": "1.1.0", "params": [9.9]}'
    (active_dir / "weights.json").write_bytes(installed)
    (active_dir / "thresholds.json").write_bytes(b'{"tp": 0.99}')

    assert manager.verify_and_execute_rollback(
        current_version="v1.1.0",
        target_version="v1.0.0",
        target_manifest=target_manifest,
        artifacts_dir=artifacts_dir,
        active_dir=active_dir,
    ) is True

    # Independently confirm the previous state was genuinely restored on disk.
    assert (active_dir / "weights.json").read_bytes() == target_bytes
    assert (active_dir / "thresholds.json").read_bytes() == b'{"tp": 0.03}'
    for name, expected in target_manifest.items():
        assert hashlib.sha256((active_dir / name).read_bytes()).hexdigest() == expected


def test_rollback_restores_previous_state_when_restore_fails(tmp_path: Path, monkeypatch) -> None:
    """A mid-restore failure must be undone, not left half applied (REL-01-AC1)."""
    manager = ReleaseCandidateManager()
    artifacts_dir = tmp_path / "artifacts"
    active_dir = tmp_path / "active"
    artifacts_dir.mkdir()
    active_dir.mkdir()

    payloads = {
        "a.json": b'{"v": "1.0.0", "n": 1}',
        "b.json": b'{"v": "1.0.0", "n": 2}',
    }
    for name, data in payloads.items():
        (artifacts_dir / name).write_bytes(data)
    target_manifest = {n: hashlib.sha256(d).hexdigest() for n, d in payloads.items()}

    original_installed = {n: b'{"v": "1.1.0"}' for n in payloads}
    for name, data in original_installed.items():
        (active_dir / name).write_bytes(data)

    import os

    real_replace = os.replace
    call_count = {"n": 0}

    def _flaky_replace(src, dst, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("injected restore failure on second artifact")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", _flaky_replace)

    with pytest.raises(RollbackIntegrityError) as exc_info:
        manager.verify_and_execute_rollback(
            current_version="v1.1.0",
            target_version="v1.0.0",
            target_manifest=target_manifest,
            artifacts_dir=artifacts_dir,
            active_dir=active_dir,
        )
    assert "ROLLBACK_RESTORE_FAILED" in str(exc_info.value)

    # The first artifact must have been put back to its pre-rollback content.
    for name, data in original_installed.items():
        assert (active_dir / name).read_bytes() == data, (
            f"{name} left half-restored after a failed rollback"
        )


def test_rollback_does_not_touch_active_state_when_target_is_corrupt(tmp_path: Path) -> None:
    """A checksum failure must abort before any restore writes occur (REL-01-AC1)."""
    manager = ReleaseCandidateManager()
    artifacts_dir = tmp_path / "artifacts"
    active_dir = tmp_path / "active"
    artifacts_dir.mkdir()
    active_dir.mkdir()

    good = b'{"v": "1.0.0", "n": 1}'
    (artifacts_dir / "a.json").write_bytes(good)
    (artifacts_dir / "b.json").write_bytes(b'{"v": "1.0.0", "n": 2}')

    installed = b'{"v": "1.1.0"}'
    (active_dir / "a.json").write_bytes(installed)
    (active_dir / "b.json").write_bytes(installed)

    target_manifest = {
        "a.json": hashlib.sha256(good).hexdigest(),
        "b.json": "0" * 64,  # corrupt checksum for the second artifact
    }

    with pytest.raises(RollbackIntegrityError):
        manager.verify_and_execute_rollback(
            current_version="v1.1.0",
            target_version="v1.0.0",
            target_manifest=target_manifest,
            artifacts_dir=artifacts_dir,
            active_dir=active_dir,
        )

    assert (active_dir / "a.json").read_bytes() == installed
    assert (active_dir / "b.json").read_bytes() == installed


def test_rollback_rejects_empty_target_manifest(tmp_path: Path) -> None:
    """An empty rollback manifest restores nothing and must not report success."""
    manager = ReleaseCandidateManager()
    artifacts_dir = tmp_path / "artifacts"
    active_dir = tmp_path / "active"
    artifacts_dir.mkdir()
    active_dir.mkdir()
    (active_dir / "weights.json").write_bytes(b'{"v": "1.1.0"}')

    with pytest.raises(RollbackIntegrityError) as exc_info:
        manager.verify_and_execute_rollback(
            current_version="v1.1.0",
            target_version="v1.0.0",
            target_manifest={},
            artifacts_dir=artifacts_dir,
            active_dir=active_dir,
        )
    assert "ROLLBACK_MANIFEST_EMPTY" in str(exc_info.value)
    assert (active_dir / "weights.json").read_bytes() == b'{"v": "1.1.0"}'


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
