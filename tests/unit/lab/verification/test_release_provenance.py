"""PM-05 candidate-bound release provenance (offline verification only).

No live orders, credentials, network, or production state. Fake clocks and
``tmp_path``-free in-memory bytes only.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from indodax_lab.verification.release import (
    DetachedSignature,
    TrustPolicy,
    VerifiedRelease,
    canonical_evidence_bytes,
    mark_deployed,
    verify_release,
)
from indodax_lab.verification.release_bundle import (
    ProductionReleaseManifest,
    ReleaseProvenanceError,
    create_production_release_manifest,
    create_release_bundle,
    verify_release_bundle,
)

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
ROOT_KEY = "offline-root-2026-01"


def _aggregate() -> dict:
    return {"shared_capital": {"report": "shadow-v1", "window": "90d", "trades": 240}}


def _make_manifest(
    *,
    release_id: str = "rel-pm05-001",
    candidates: dict[str, str] | None = None,
    pair_owner_map: dict[str, str] | None = None,
    artifacts: dict[str, bytes] | None = None,
    aggregate: dict | None = None,
) -> tuple[ProductionReleaseManifest, dict[str, bytes]]:
    candidates = candidates or {"BTC-C07": "a" * 64, "ETH-C02": "b" * 64}
    pair_owner_map = pair_owner_map or {"BTC/IDR": "BTC-C07", "ETH/IDR": "ETH-C02"}
    artifacts = artifacts if artifacts is not None else {"model.bin": b"model-bytes-v1"}
    aggregate = aggregate if aggregate is not None else _aggregate()
    manifest = create_production_release_manifest(
        release_id=release_id,
        candidate_digests=dict(candidates),
        model_payload=b"model-bytes-v1",
        features_payload=b"features-schema-v1",
        pipeline_payload=b"pipeline-graph-v1",
        risk_payload=b"risk-policy-v1",
        cost_payload=b"cost-policy-v1",
        execution_payload=b"execution-policy-v1",
        git_sha="f" * 40,
        dependency_payload=b"deps-lock-v1",
        environment_payload=b"env-fingerprint-v1",
        allocation_policy_payload=b"allocation-v1",
        aggregate_evidence_payload=canonical_evidence_bytes(aggregate),
        qualification_refs={cid: f"qual-{cid}-v1" for cid in candidates},
        pair_owner_map=dict(pair_owner_map),
        artifact_payloads=dict(artifacts),
        author="operator_test",
        packaged_at=NOW,
    )
    return manifest, dict(artifacts)


def _make_policy(
    manifest: ProductionReleaseManifest,
    *,
    aggregate: dict | None = None,
    source_clean: bool = True,
    known_deps: tuple[str, ...] | None = None,
    request_origin: str = "production",
    with_signature: bool = True,
) -> TrustPolicy:
    aggregate = aggregate if aggregate is not None else _aggregate()
    signatures = (
        {
            manifest.release_id: DetachedSignature(
                key_id=ROOT_KEY,
                covered_digest=manifest.manifest_digest,
                signature="signed-by-offline-root",
            )
        }
        if with_signature
        else {}
    )
    return TrustPolicy(
        trusted_key_ids=(ROOT_KEY,),
        signatures=signatures,
        gate_evidence={
            ref: {"qualified": True, "forward_days": 95, "forward_trades": 120}
            for ref in manifest.qualification_refs.values()
        },
        aggregate_evidence=aggregate,
        known_dependency_digests=(
            known_deps if known_deps is not None else (manifest.dependency_digest,)
        ),
        source_clean=source_clean,
        request_origin=request_origin,
    )


def test_pm_05_0() -> None:
    """Missing/mismatched policy/model/schema identity rejects."""
    base = {
        "release_id": "rel-pm05-000",
        "candidate_digests": {"BTC-C07": "a" * 64},
        "model_payload": b"m",
        "features_payload": b"f",
        "pipeline_payload": b"p",
        "risk_payload": b"r",
        "cost_payload": b"c",
        "execution_payload": b"e",
        "git_sha": "f" * 40,
        "dependency_payload": b"d",
        "environment_payload": b"env",
        "allocation_policy_payload": b"alloc",
        "aggregate_evidence_payload": canonical_evidence_bytes(_aggregate()),
        "qualification_refs": {"BTC-C07": "qual-BTC-C07-v1"},
        "pair_owner_map": {"BTC/IDR": "BTC-C07"},
        "author": "operator_test",
        "packaged_at": NOW,
    }
    with pytest.raises(ReleaseProvenanceError, match="POLICY_IDENTITY_MISSING"):
        create_production_release_manifest(**{**base, "risk_payload": b""})
    with pytest.raises(ReleaseProvenanceError, match="MODEL_IDENTITY_MISSING"):
        create_production_release_manifest(**{**base, "model_payload": None})
    with pytest.raises(ReleaseProvenanceError, match="SCHEMA_IDENTITY_MISSING"):
        create_production_release_manifest(**{**base, "features_payload": "  "})
    with pytest.raises(ReleaseProvenanceError, match="CANDIDATE_IDENTITY_MISMATCH"):
        create_production_release_manifest(
            **{**base, "qualification_refs": {"GHOST": "qual-ghost-v1"}}
        )
    with pytest.raises(ReleaseProvenanceError, match="CANDIDATE_IDENTITY_INVALID"):
        create_production_release_manifest(
            **{**base, "candidate_digests": {"BTC-C07": "not-a-digest"}}
        )


def test_pm_05_1() -> None:
    """Same filename with changed bytes fails."""
    manifest, _artifacts = _make_manifest()
    with pytest.raises(ReleaseProvenanceError, match="ARTIFACT_BYTES_MISMATCH"):
        verify_release(manifest, {"model.bin": b"tampered-bytes"}, _make_policy(manifest))


def test_pm_05_2() -> None:
    """Digest-only legacy bundle cannot claim authenticity."""
    legacy = create_release_bundle(
        bundle_id="legacy-v1",
        git_commit_sha="abc123",
        config_payload="cfg",
        schema_payload="schema",
        author="operator_test",
        packaged_at=NOW,
    )
    assert verify_release_bundle(
        legacy, expected_git_sha="abc123", config_payload="cfg", schema_payload="schema"
    ) is True
    with pytest.raises(ReleaseProvenanceError, match="LEGACY_BUNDLE_NOT_AUTHENTIC"):
        verify_release(legacy, {}, TrustPolicy(trusted_key_ids=(ROOT_KEY,)))
    manifest, artifacts = _make_manifest()
    unsigned = verify_release(manifest, artifacts, _make_policy(manifest, with_signature=False))
    assert unsigned.authenticity == "CHECKSUM_ONLY"
    assert unsigned.authenticity != "SIGNATURE_VERIFIED"


def test_pm_05_3() -> None:
    """Dirty source/unknown dependency identity cannot produce eligible release."""
    manifest, artifacts = _make_manifest()
    dirty = verify_release(manifest, artifacts, _make_policy(manifest, source_clean=False))
    assert dirty.eligible is False
    assert any("SOURCE_DIRTY" in reason for reason in dirty.reasons)
    unknown = verify_release(
        manifest, artifacts, _make_policy(manifest, known_deps=("0" * 64,))
    )
    assert unknown.eligible is False
    assert any("UNKNOWN_DEPENDENCY_IDENTITY" in reason for reason in unknown.reasons)
    with pytest.raises(ReleaseProvenanceError, match="ACTIVATION_NOT_ELIGIBLE"):
        mark_deployed(dirty, request_origin="production")


def test_pm_05_4() -> None:
    """Research request cannot mark deployed."""
    manifest, artifacts = _make_manifest()
    research_view = verify_release(
        manifest, artifacts, _make_policy(manifest, request_origin="research")
    )
    assert research_view.eligible is False
    assert any("RESEARCH_NEVER_ELIGIBLE" in reason for reason in research_view.reasons)
    production_view = verify_release(manifest, artifacts, _make_policy(manifest))
    assert production_view.eligible is True
    with pytest.raises(ReleaseProvenanceError, match="RESEARCH_CANNOT_DEPLOY"):
        mark_deployed(production_view, request_origin="research")
    assert production_view.deployed is False


def test_pm_05_program_5() -> None:
    """Release verifies each candidate policy and exclusive pair ownership."""
    manifest, artifacts = _make_manifest()
    verified = verify_release(manifest, artifacts, _make_policy(manifest))
    assert isinstance(verified, VerifiedRelease)
    assert verified.eligible is True
    assert verified.authenticity == "SIGNATURE_VERIFIED"
    assert verified.deployed is False
    deployed = mark_deployed(verified, request_origin="production")
    assert deployed.deployed is True
    assert deployed.release_id == manifest.release_id
    with pytest.raises(ReleaseProvenanceError, match="PAIR_OWNER_UNKNOWN"):
        _make_manifest(pair_owner_map={"BTC/IDR": "GHOST-C99", "ETH/IDR": "ETH-C02"})
    with pytest.raises(ReleaseProvenanceError, match="PAIR_OWNER_MISSING"):
        _make_manifest(pair_owner_map={"BTC/IDR": "BTC-C07"})
    legacy = create_release_bundle(
        bundle_id="legacy-readable",
        git_commit_sha="abc123",
        config_payload="cfg",
        schema_payload="schema",
        author="operator_test",
        packaged_at=NOW,
    )
    assert verify_release_bundle(
        legacy, expected_git_sha="abc123", config_payload="cfg", schema_payload="schema"
    ) is True


def test_pm_05_program_6() -> None:
    """No candidate or aggregate evidence mismatch can authorize activation."""
    manifest, artifacts = _make_manifest()
    tampered = manifest.model_copy(
        update={"candidate_digests": {"BTC-C07": "c" * 64, "ETH-C02": "b" * 64}}
    )
    with pytest.raises(ReleaseProvenanceError, match="MANIFEST_DIGEST_MISMATCH"):
        verify_release(tampered, artifacts, _make_policy(manifest))
    other_aggregate = {"shared_capital": {"report": "different-report"}}
    mismatched = verify_release(
        manifest, artifacts, _make_policy(manifest, aggregate=other_aggregate)
    )
    assert mismatched.eligible is False
    assert any("AGGREGATE_EVIDENCE_MISMATCH" in reason for reason in mismatched.reasons)
    with pytest.raises(ReleaseProvenanceError, match="ACTIVATION_NOT_ELIGIBLE"):
        mark_deployed(mismatched, request_origin="production")
    assert mismatched.deployed is False
    assert json.loads(json.dumps(mismatched.reasons))
