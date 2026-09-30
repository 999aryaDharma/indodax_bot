"""RW4-01 acceptance: immutable candidate packaging and lifecycle.

Fake artifact bytes, fake clocks, temporary state. No network, no
credentials, no live DB. Real contract types (CandidateManifest,
VerifiedCandidate, RuntimePlan) and real hash verification throughout.
"""
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.contracts.workbench import (
    PipelineManifest,
    RuntimePlan,
    VerifiedRuntimePlan,
)
from indodax_lab.evaluation.candidates import CandidateRecord, CandidateRegistry

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _aref(kind: str, ident: str, payload: bytes) -> ArtifactRef:
    return ArtifactRef(kind=kind, id=ident, version="v1", sha256=_sha(payload))


class _Store:
    """Content-addressed artifact bytes (dict-backed fake CAS)."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def put(self, payload: bytes) -> str:
        digest = _sha(payload)
        self.blobs[digest] = payload
        return digest

    def resolve(self, ref: ArtifactRef) -> bytes:
        try:
            return self.blobs[ref.sha256]
        except KeyError as exc:
            raise LookupError(f"EVIDENCE_MISSING:{ref.kind}:{ref.id}") from exc


def _pipeline_manifest(store: _Store, model_payload: bytes) -> PipelineManifest:
    model_ref = ArtifactRef(
        kind="model", id="m01", version="v1", sha256=store.put(model_payload)
    )
    policy = ArtifactRef(
        kind="policy", id="pol", version="v1", sha256=store.put(b"policy-bytes")
    )
    return PipelineManifest(
        pipeline_id="pipe_rw4",
        version="1.0.0",
        nodes=(),
        edges=(),
        component_refs=(model_ref,),
        dataset_timeframe_constraints={},
        sizing_policy_ref=policy,
        exit_policy_ref=policy,
        risk_policy_ref=policy,
        cost_policy_ref=policy,
        execution_policy_ref=policy,
    )


def _plan(store: _Store, model_payload: bytes = b"model-bytes-v1"):
    pipeline = _pipeline_manifest(store, model_payload)
    pipeline_ref = ArtifactRef(
        kind="pipeline",
        id="pipe_rw4",
        version="1.0.0",
        sha256=_sha(pipeline.model_dump_json().encode()),
    )
    store.blobs[pipeline_ref.sha256] = pipeline.model_dump_json().encode()
    policy = ArtifactRef(
        kind="policy", id="pol", version="v1", sha256=store.put(b"policy-bytes")
    )
    plan = RuntimePlan(
        plan_id="plan_rw4",
        version="1.0.0",
        universe=("btc_idr",),
        timeframe="1h",
        dataset_refs=(),
        pipeline_ref=pipeline_ref,
        feature_schema_hash=_sha(b"features"),
        ordered_feature_names=("ema_fast", "ema_slow", "atr_14"),
        sizing_policy_ref=policy,
        exit_policy_ref=policy,
        risk_policy_ref=policy,
        cost_policy_ref=policy,
        execution_policy_ref=policy,
        git_sha="aa" * 20,
        environment_digest="bb" * 32,
        seed=7,
    )
    return VerifiedRuntimePlan(
        plan=plan, plan_digest=manifest_digest(plan), verified_at_utc=NOW
    )


class _Experiment:
    """Minimal completed-experiment evidence (status + plan + result bytes)."""

    def __init__(self, tmp_path: Path, plan, status: str = "SUCCESS") -> None:
        self.experiment_id = "exp_rw4_001"
        self.status = status
        self.plan = plan
        self.artifact_path = tmp_path / "result.json"
        self.artifact_path.write_bytes(b'{"result_digest":"digest-1"}')
        self.result_digest = "digest-1"


def _registry(tmp_path: Path, store: _Store) -> CandidateRegistry:
    return CandidateRegistry(
        root=tmp_path / "candidates",
        clock=lambda: NOW,
        artifact_resolver=store.resolve,
    )


def test_rw4_01_bootstrap_recovery(tmp_path: Path) -> None:
    """RW4-01-AC5: package binds the executed plan; decision identity kept."""
    from indodax_lab.runtime.candidate import CandidateRuntime

    store = _Store()
    plan = _plan(store)
    registry = _registry(tmp_path, store)
    exp = _Experiment(tmp_path, plan)

    manifest = registry.package(exp.experiment_id, "review-pass-001", experiment=exp)
    assert manifest.runtime_plan_ref.sha256 == plan.plan_digest

    verified = registry.verify(manifest.to_artifact_ref())
    assert verified.candidate_digest == manifest_digest(manifest)
    # The verified candidate loads through the real runtime contract, so the
    # packaging step cannot have altered decision identity.
    runtime = CandidateRuntime.load(verified, plan=plan)
    assert runtime is not None


def test_rw4_01_0(tmp_path: Path) -> None:
    """RW4-01-AC0: changed model/policy bytes invalidate the package."""
    store = _Store()
    plan = _plan(store)
    registry = _registry(tmp_path, store)
    exp = _Experiment(tmp_path, plan)
    manifest = registry.package(exp.experiment_id, "review-pass-001", experiment=exp)
    ref = manifest.to_artifact_ref()

    # Corrupt the stored model bytes: re-verification must fail closed.
    store.blobs[_aref("model", "m01", b"model-bytes-v1").sha256] = b"tampered-bytes"
    with pytest.raises(ValueError, match="CANDIDATE_LINEAGE_MISMATCH"):
        registry.verify(ref)

    # Same (id, version) can never be re-published with different bytes.
    mutated = manifest.model_copy(update={"timeframe": "5m"})
    with pytest.raises(ValueError, match="CANDIDATE_VERSION_CONFLICT"):
        registry.publish_manifest(mutated)


def test_rw4_01_1(tmp_path: Path) -> None:
    """RW4-01-AC1: failed or unreviewed experiments never package as verified."""
    store = _Store()
    plan = _plan(store)
    registry = _registry(tmp_path, store)

    failed = _Experiment(tmp_path, plan, status="FAILED")
    with pytest.raises(ValueError, match="EXPERIMENT_NOT_COMPLETED"):
        registry.package(failed.experiment_id, "review-pass-001", experiment=failed)

    ok = _Experiment(tmp_path, plan)
    with pytest.raises(ValueError, match="REVIEW_REF_REQUIRED"):
        registry.package(ok.experiment_id, "  ", experiment=ok)
    assert registry.count() == 0


def test_rw4_01_2(tmp_path: Path) -> None:
    """RW4-01-AC2: missing evidence blocks; filename identity is never used."""
    store = _Store()
    plan = _plan(store)
    registry = _registry(tmp_path, store)
    exp = _Experiment(tmp_path, plan)

    exp.artifact_path.unlink()  # result bytes gone, name alone proves nothing
    with pytest.raises(ValueError, match="EVIDENCE_MISSING"):
        registry.package(exp.experiment_id, "review-pass-001", experiment=exp)
    assert registry.count() == 0

    exp2 = _Experiment(tmp_path, plan)
    exp2.artifact_path = tmp_path / "result.json"
    exp2.artifact_path.write_bytes(b'{"result_digest":"digest-1"}')
    manifest = registry.package(exp.experiment_id, "review-pass-001", experiment=exp2)
    assert manifest.candidate_id.startswith("cand_")


def test_rw4_01_3(tmp_path: Path) -> None:
    """RW4-01-AC3: retraining yields a new candidate version; v1 intact."""
    store = _Store()
    plan = _plan(store)
    registry = _registry(tmp_path, store)
    exp = _Experiment(tmp_path, plan)
    first = registry.package(exp.experiment_id, "review-pass-001", experiment=exp)
    assert first.version == "v1"

    second = registry.retrain(
        exp.experiment_id,
        "review-pass-002",
        experiment=exp,
        model_refs=(
            ArtifactRef(
                kind="model", id="m01", version="v2",
                sha256=store.put(b"model-bytes-v2"),
            ),
        ),
    )
    assert second.version == "v2"
    assert second.candidate_id == first.candidate_id
    assert second.to_artifact_ref().sha256 != first.to_artifact_ref().sha256
    # v1 remains addressable and valid.
    assert registry.get(first.to_artifact_ref()) == first


def test_rw4_01_4(tmp_path: Path) -> None:
    """RW4-01-AC4: lifecycle metadata cannot alter frozen configuration."""
    import pydantic

    store = _Store()
    plan = _plan(store)
    registry = _registry(tmp_path, store)
    exp = _Experiment(tmp_path, plan)
    manifest = registry.package(exp.experiment_id, "review-pass-001", experiment=exp)
    frozen = manifest_digest(manifest)

    with pytest.raises(pydantic.ValidationError):
        manifest.version = "v99"  # type: ignore[misc]

    record = registry.transition(
        manifest.candidate_id, "NOTE", evidence_refs=(), note="reviewer note"
    )
    assert isinstance(record, CandidateRecord)
    assert manifest_digest(registry.get(manifest.to_artifact_ref())) == frozen

    missing = ArtifactRef(kind="evidence", id="ghost", version="v1", sha256="ff" * 32)
    with pytest.raises(ValueError, match="EVIDENCE_MISSING"):
        registry.transition(manifest.candidate_id, "NOTE", evidence_refs=(missing,))


def test_rw4_01_program_6(tmp_path: Path) -> None:
    """RW4-01-AC6: freeze runtime+policy identity before shadow registration."""
    store = _Store()
    plan = _plan(store)
    registry = _registry(tmp_path, store)
    exp = _Experiment(tmp_path, plan)
    manifest = registry.package(exp.experiment_id, "review-pass-001", experiment=exp)

    record = registry.transition(
        manifest.candidate_id, "SHADOW_REGISTER", evidence_refs=()
    )
    frozen_event = record.events[-1]
    assert frozen_event["event"] == "SHADOW_REGISTER"
    assert frozen_event["runtime_plan_digest"] == plan.plan_digest
    assert frozen_event["config_digest"] == manifest_digest(manifest)

    # Same identity can never be re-published with different bytes.
    mutated = manifest.model_copy(update={"timeframe": "5m"})
    with pytest.raises(ValueError, match="CANDIDATE_VERSION_CONFLICT"):
        registry.publish_manifest(mutated)
