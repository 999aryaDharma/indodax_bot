"""Behavioral acceptance tests for RW2-02: model registry and offline training services.

Every test drives the public service boundary (``ModelRegistry`` /
``TrainingService``) inside a temporary namespace: no network, no Telegram, no
production database and no real market data.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from indodax_lab.contracts.identity import ArtifactRef
from indodax_lab.contracts.workbench import MetricValidity, ModelManifest
from indodax_lab.models import registry as registry_module
from indodax_lab.models.artifacts import PortableBundle
from indodax_lab.models.m01_logistic import M01Config, M01LogisticTrainer
from indodax_lab.models.registry import (
    ARCHITECTURE_LOADERS,
    LOADER_ALLOWLIST,
    ArtifactHashMismatchError,
    FeatureFrame,
    FeatureSchemaMismatchError,
    ImmutableVersionConflictError,
    LoaderNotAllowedError,
    ModelEntry,
    ModelRegistry,
    ProbabilityVector,
    RuntimeBlockedError,
)
from indodax_lab.models.training_service import (
    EvaluationArtifact,
    EvaluationStatus,
    TrainingConfig,
    TrainingService,
)
from indodax_lab.orchestration.jobs import JobStatus
from indodax_lab.orchestration.queue import SqliteJobQueue
from indodax_lab.orchestration.resources import StaticResourceProbe, SystemResourceReading

FEATURE_NAMES = ["feat_a", "feat_b", "feat_c", "feat_d", "feat_e"]
_BUNDLE_CACHE: dict[tuple[str, str, tuple[str, ...]], bytes] = {}


# ---------------------------------------------------------------------------
# Fixtures (synthetic, deterministic, local)
# ---------------------------------------------------------------------------


def _bundle_bytes(model_id: str, version: str, feature_names: list[str], seed: int = 42) -> bytes:
    """Train a small M01 model and serialize it as verified portable-bundle bytes."""
    key = (model_id, version, tuple(feature_names))
    cached = _BUNDLE_CACHE.get(key)
    if cached is not None:
        return cached

    row_count = 300
    rng = np.random.default_rng(seed)
    features = pd.DataFrame(
        rng.standard_normal((row_count, len(feature_names))), columns=feature_names
    )
    labels = pd.Series([index % 2 for index in range(row_count)])
    config = M01Config(model_id=model_id, version=version, max_iter=50, seed=seed)
    trainer = M01LogisticTrainer(config=config)
    fitted = trainer.train_and_calibrate(
        X_train=features.iloc[:240],
        y_train=labels.iloc[:240],
        X_val=features.iloc[240:],
        y_val=labels.iloc[240:],
        feature_names=feature_names,
    )
    payload = PortableBundle.from_m01(bundle=fitted, trainer=trainer).to_bytes()
    _BUNDLE_CACHE[key] = payload
    return payload


def _dataset_bytes(
    feature_names: list[str],
    row_count: int = 300,
    train_end: int = 240,
    seed: int = 7,
    declared_order: list[str] | None = None,
) -> bytes:
    rng = np.random.default_rng(seed)
    rows = np.round(rng.standard_normal((row_count, len(feature_names))), 6).tolist()
    payload = {
        "schema_version": "v1",
        "feature_names": list(declared_order or feature_names),
        "rows": rows,
        "labels": [index % 2 for index in range(row_count)],
        "train_end": train_end,
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _frame(feature_names: list[str], row_count: int = 4, seed: int = 99) -> FeatureFrame:
    rng = np.random.default_rng(seed)
    values = np.round(rng.standard_normal((row_count, len(feature_names))), 6)
    rows = [tuple(float(value) for value in row) for row in values]
    return FeatureFrame(feature_names=tuple(feature_names), rows=tuple(rows))


def _manifest(
    model_id: str,
    version: str,
    feature_names: list[str],
    bundle_ref: ArtifactRef,
    *,
    architecture: str = "m01_logistic",
    runtime_requirements: dict[str, str] | None = None,
    calibration_ref: ArtifactRef | None = None,
    preprocessing_ref: ArtifactRef | None = None,
) -> ModelManifest:
    return ModelManifest(
        model_id=model_id,
        architecture=architecture,
        version=version,
        artifact_refs=(bundle_ref,),
        ordered_feature_schema=tuple(feature_names),
        preprocessing_ref=preprocessing_ref,
        calibration_ref=calibration_ref,
        universe=("BTC-IDR",),
        runtime_requirements=dict(runtime_requirements or {}),
    )


def _register_model(
    registry: ModelRegistry,
    model_id: str,
    version: str = "1.0.0",
    *,
    architecture: str = "m01_logistic",
    runtime_requirements: dict[str, str] | None = None,
    calibration_ref: ArtifactRef | None = None,
    preprocessing_ref: ArtifactRef | None = None,
) -> tuple[ArtifactRef, ModelManifest]:
    bundle = _bundle_bytes(model_id, version, FEATURE_NAMES)
    bundle_ref = registry.put_bytes(
        bundle, kind="model", artifact_id=f"{model_id}_bundle", version=version
    )
    manifest = _manifest(
        model_id,
        version,
        FEATURE_NAMES,
        bundle_ref,
        architecture=architecture,
        runtime_requirements=runtime_requirements,
        calibration_ref=calibration_ref,
        preprocessing_ref=preprocessing_ref,
    )
    return registry.register(manifest), manifest


def _queue(tmp_path) -> SqliteJobQueue:
    return SqliteJobQueue(tmp_path / "jobs.sqlite")


# ---------------------------------------------------------------------------
# RW2-02-AC0: hash mismatch rejected before loader invocation
# ---------------------------------------------------------------------------


def test_rw2_02_0(tmp_path, monkeypatch) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    model_ref, _ = _register_model(registry, "rw2_02_hash")
    bundle_ref = ArtifactRef(
        kind="model",
        id="rw2_02_hash_bundle",
        version="1.0.0",
        sha256=registry.load_verified(model_ref).manifest.artifact_refs[0].sha256,
    )

    calls: list[bytes] = []
    real_resolve_loader = registry_module.resolve_loader

    def counting_resolve_loader(loader_id: str):
        loader = real_resolve_loader(loader_id)

        def counted(data: bytes):
            calls.append(data)
            return loader(data)

        return counted

    monkeypatch.setattr(registry_module, "resolve_loader", counting_resolve_loader)

    # 1. Tampered model bytes must be rejected before the loader sees them.
    bundle_path = registry.object_path(bundle_ref)
    original_bytes = bundle_path.read_bytes()
    bundle_path.write_bytes(b'{"tampered": true}')
    with pytest.raises(ArtifactHashMismatchError, match="ARTIFACT_HASH_MISMATCH"):
        registry.load_verified(model_ref)
    assert calls == [], "loader must not be invoked when artifact bytes fail hash verification"

    # 2. Tampered manifest identity bytes must be rejected before the loader too.
    bundle_path.write_bytes(original_bytes)
    manifest_path = registry.object_path(model_ref)
    manifest_bytes = manifest_path.read_bytes()
    manifest_path.write_bytes(b'{"tampered": true}')
    with pytest.raises(ArtifactHashMismatchError, match="ARTIFACT_HASH_MISMATCH"):
        registry.load_verified(model_ref)
    assert calls == [], "loader must not be invoked when manifest bytes fail hash verification"

    manifest_path.write_bytes(manifest_bytes)
    assert registry.load_verified(model_ref).model_id == "rw2_02_hash"


# ---------------------------------------------------------------------------
# RW2-02-AC1: arbitrary pickle and remote executable loaders reject
# ---------------------------------------------------------------------------


def test_rw2_02_1(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    bundle = _bundle_bytes("rw2_02_model", "1.0.0", FEATURE_NAMES)
    artifact_ref = registry.put_bytes(
        bundle, kind="model", artifact_id="rw2_02_model_bundle", version="1.0.0"
    )

    forbidden_architectures = (
        "pickle",
        "joblib",
        "torch_pickle",
        "cloud_remote_fetch",
        "http_url_loader",
        "python_eval",
    )
    for index, architecture in enumerate(forbidden_architectures):
        manifest = _manifest(
            f"rejected_{index}", "1.0.0", FEATURE_NAMES, artifact_ref, architecture=architecture
        )
        with pytest.raises(LoaderNotAllowedError, match="LOADER_NOT_ALLOWED"):
            registry.register(manifest)

    # The pinned allowlist contains no pickle/remote loader and no rejected model published.
    assert set(LOADER_ALLOWLIST) == {"portable_bundle_json_v2"}
    assert set(ARCHITECTURE_LOADERS) == {"m01_logistic"}
    assert all(not entry.registered for entry in registry.list_models())


# ---------------------------------------------------------------------------
# RW2-02-AC2: wrong feature order/schema cannot silently predict
# ---------------------------------------------------------------------------


def test_rw2_02_2(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    model_ref, _ = _register_model(registry, "rw2_02_model")
    predictor = registry.load_verified(model_ref)

    ordered = _frame(FEATURE_NAMES)
    result = predictor.predict_proba(ordered)
    assert isinstance(result, ProbabilityVector)
    assert result.model_id == "rw2_02_model"
    assert len(result.probabilities) == len(ordered.rows)
    assert all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in result.probabilities)

    permuted_names = list(reversed(FEATURE_NAMES))
    permuted = FeatureFrame(feature_names=tuple(permuted_names), rows=ordered.rows)
    with pytest.raises(FeatureSchemaMismatchError, match="FEATURE_SCHEMA_MISMATCH"):
        predictor.predict_proba(permuted)

    missing_names = FEATURE_NAMES[:-1]
    missing = FeatureFrame(
        feature_names=tuple(missing_names),
        rows=tuple(tuple(row[:-1]) for row in ordered.rows),
    )
    with pytest.raises(FeatureSchemaMismatchError, match="FEATURE_SCHEMA_MISMATCH"):
        predictor.predict_proba(missing)

    extra_names = [*FEATURE_NAMES, "feat_extra"]
    extra = FeatureFrame(
        feature_names=tuple(extra_names),
        rows=tuple(tuple(row) + (0.0,) for row in ordered.rows),
    )
    with pytest.raises(FeatureSchemaMismatchError, match="FEATURE_SCHEMA_MISMATCH"):
        predictor.predict_proba(extra)


# ---------------------------------------------------------------------------
# RW2-02-AC3: training creates a new model version and never mutates the
# running candidate
# ---------------------------------------------------------------------------


def test_rw2_02_3(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    queue = _queue(tmp_path)
    service = TrainingService(registry, queue, worker_id="rw2-02-test-worker")

    # The running candidate: an already registered, already used v1 identity.
    ref_v1, manifest_v1 = _register_model(registry, "rw2_02_candidate")
    v1_bytes_before = registry.read_object(ref_v1)
    frame = _frame(FEATURE_NAMES)
    v1_predictions_before = registry.load_verified(ref_v1).predict_proba(frame).probabilities

    dataset_ref = registry.put_bytes(
        _dataset_bytes(FEATURE_NAMES),
        kind="dataset",
        artifact_id="rw2_02_training_dataset",
        version="1",
    )
    config = TrainingConfig(
        model_id="rw2_02_candidate",
        version="2.0.0",
        ordered_feature_schema=tuple(FEATURE_NAMES),
        universe=("BTC-IDR",),
        trainer=M01Config(max_iter=50, seed=5),
    )
    record = service.create(config, (dataset_ref,))
    assert record.status is JobStatus.PENDING
    assert record.job_type == "train_model"

    ref_v2 = service.run(record.job_id)

    # A new immutable version was created.
    assert (ref_v2.id, ref_v2.version) == ("rw2_02_candidate", "2.0.0")
    assert ref_v2.sha256 != ref_v1.sha256
    assert queue.get_job(record.job_id).status is JobStatus.SUCCESS

    # The running candidate is untouched: same bytes, same loader output.
    assert registry.read_object(ref_v1) == v1_bytes_before
    predictor_v1 = registry.load_verified(ref_v1)
    assert predictor_v1.predict_proba(frame).probabilities == v1_predictions_before

    # Conflicting semantics under the running identity are refused, not merged.
    conflicting = manifest_v1.model_copy(
        update={"ordered_feature_schema": tuple(reversed(FEATURE_NAMES))}
    )
    with pytest.raises(ImmutableVersionConflictError, match="IMMUTABLE_VERSION_CONFLICT"):
        registry.register(conflicting)
    assert registry.read_object(ref_v1) == v1_bytes_before

    entries = {(entry.model_id, entry.version): entry for entry in registry.list_models()}
    assert entries[("rw2_02_candidate", "1.0.0")].registered is True
    assert entries[("rw2_02_candidate", "2.0.0")].registered is True
    assert entries[("rw2_02_candidate", "2.0.0")].runtime_eligible is True

    predictor_v2 = registry.load_verified(ref_v2)
    assert predictor_v2.manifest.calibration_ref is not None
    assert predictor_v2.manifest.preprocessing_ref is not None
    assert len(predictor_v2.predict_proba(frame).probabilities) == len(frame.rows)


# ---------------------------------------------------------------------------
# RW2-02-AC4: missing accelerator/runtime is BLOCKED_RESOURCE, not a model
# ---------------------------------------------------------------------------


def test_rw2_02_4(tmp_path) -> None:
    registry = ModelRegistry(
        tmp_path / "registry",
        probe=StaticResourceProbe(SystemResourceReading(gpu_available=False)),
    )
    queue = _queue(tmp_path)
    service = TrainingService(registry, queue, worker_id="rw2-02-test-worker")

    dataset_ref = registry.put_bytes(
        _dataset_bytes(FEATURE_NAMES),
        kind="dataset",
        artifact_id="rw2_02_dl_dataset",
        version="1",
    )
    config = TrainingConfig(
        model_id="rw2_02_dl",
        version="1.0.0",
        architecture="d01_mlp",
        ordered_feature_schema=tuple(FEATURE_NAMES),
        universe=("BTC-IDR",),
        runtime_requirements={"accelerator": "cuda"},
    )
    record = service.create(config, (dataset_ref,))
    assert record.status is JobStatus.PENDING

    with pytest.raises(RuntimeBlockedError) as blocked:
        service.run(record.job_id)
    assert "BLOCKED_RESOURCE" in str(blocked.value)
    assert "GPU_UNAVAILABLE" in str(blocked.value)

    job = queue.get_job(record.job_id)
    assert job.status is JobStatus.FAILED_FINAL
    assert job.error_message is not None and job.error_message.startswith("BLOCKED_RESOURCE")
    assert job.result_artifact_path is None

    # No successful model appeared, and nothing was substituted for it.
    assert all(entry.model_id != "rw2_02_dl" for entry in registry.list_models())


# ---------------------------------------------------------------------------
# RW2-02-AC5: listing distinguishes registered/verified/compatible/
# runtime-eligible without fallback substitution
# ---------------------------------------------------------------------------


def test_rw2_02_program_5(tmp_path, monkeypatch) -> None:
    registry = ModelRegistry(
        tmp_path / "registry",
        probe=StaticResourceProbe(SystemResourceReading(gpu_available=False)),
    )

    ref_a, _ = _register_model(registry, "rw2_02_a")
    ref_b, _ = _register_model(
        registry, "rw2_02_b", runtime_requirements={"accelerator": "cuda"}
    )
    # A raw model file dropped into the store: bytes without a published identity.
    registry.put_bytes(
        _bundle_bytes("rw2_02_a", "1.0.0", FEATURE_NAMES),
        kind="model",
        artifact_id="orphan_model",
        version="1",
    )

    entries = {(entry.model_id, entry.version): entry for entry in registry.list_models()}

    eligible = entries[("rw2_02_a", "1.0.0")]
    assert isinstance(eligible, ModelEntry)
    assert (
        eligible.registered,
        eligible.verified,
        eligible.compatible,
        eligible.runtime_eligible,
    ) == (True, True, True, True)
    assert eligible.reason is None

    blocked = entries[("rw2_02_b", "1.0.0")]
    assert (
        blocked.registered,
        blocked.verified,
        blocked.compatible,
        blocked.runtime_eligible,
    ) == (True, True, True, False)
    assert blocked.reason is not None and blocked.reason.startswith("BLOCKED_RESOURCE")

    raw = next(entry for entry in registry.list_models() if not entry.registered)
    assert raw.manifest_ref is None
    assert (raw.verified, raw.compatible, raw.runtime_eligible) == (False, False, False)
    assert raw.reason is not None and raw.reason.startswith("NOT_REGISTERED")

    # No fallback substitution: the blocked model refuses to load, the eligible
    # model stays its own identity, and an unsupported loader is never swapped in.
    with pytest.raises(RuntimeBlockedError, match="BLOCKED_RESOURCE"):
        registry.load_verified(ref_b)
    assert registry.load_verified(ref_a).model_id == "rw2_02_a"

    monkeypatch.setattr(registry_module, "ARCHITECTURE_LOADERS", {})
    relisted = {(entry.model_id, entry.version): entry for entry in registry.list_models()}
    unsupported = relisted[("rw2_02_a", "1.0.0")]
    assert (unsupported.registered, unsupported.verified) == (True, True)
    assert unsupported.compatible is False
    assert unsupported.reason is not None and "LOADER_NOT_ALLOWLISTED" in unsupported.reason
    with pytest.raises(LoaderNotAllowedError, match="LOADER_NOT_ALLOWED"):
        registry.load_verified(ref_a)


# ---------------------------------------------------------------------------
# Immutable publication: idempotent duplicate vs conflicting semantics
# ---------------------------------------------------------------------------


def test_register_is_idempotent_and_conflicting_semantics_reject(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    model_ref, manifest = _register_model(registry, "rw2_02_idempotent")

    assert registry.register(manifest) == model_ref
    assert registry.read_object(model_ref) == registry.read_object(model_ref)

    conflicting = manifest.model_copy(update={"universe": ("ETH-IDR",)})
    with pytest.raises(ImmutableVersionConflictError, match="IMMUTABLE_VERSION_CONFLICT"):
        registry.register(conflicting)
    assert registry.read_object(model_ref) == registry.read_object(model_ref)


# ---------------------------------------------------------------------------
# evaluate(): immutable evaluation evidence
# ---------------------------------------------------------------------------


def test_evaluate_returns_completed_evaluation_artifact(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    queue = _queue(tmp_path)
    service = TrainingService(registry, queue)

    calibration_ref = registry.put_bytes(
        b'{"a": 1.0, "b": 0.0, "method": "platt"}',
        kind="calibration",
        artifact_id="rw2_02_model_calibration",
        version="1.0.0",
    )
    preprocessing_ref = registry.put_bytes(
        b'{"feature_names": ["feat_a"], "mode": "identity"}',
        kind="preprocessing",
        artifact_id="rw2_02_model_preprocessing",
        version="1.0.0",
    )
    model_ref, _ = _register_model(
        registry,
        "rw2_02_model",
        calibration_ref=calibration_ref,
        preprocessing_ref=preprocessing_ref,
    )
    dataset_ref = registry.put_bytes(
        _dataset_bytes(FEATURE_NAMES),
        kind="dataset",
        artifact_id="rw2_02_eval_dataset",
        version="1",
    )

    artifact = service.evaluate(model_ref, dataset_ref)

    assert isinstance(artifact, EvaluationArtifact)
    assert artifact.status is EvaluationStatus.COMPLETED
    assert artifact.failure_reason is None
    assert artifact.model_ref == model_ref
    assert artifact.dataset_ref == dataset_ref
    assert artifact.split_ref is not None
    assert registry.read_object(artifact.split_ref)
    assert artifact.calibration_ref == calibration_ref
    assert artifact.train_transform_refs == (preprocessing_ref,)
    assert list(artifact.metrics) == ["brier_score", "accuracy"]
    for metric in artifact.metrics.values():
        assert metric.validity is MetricValidity.VALID
        assert metric.value is not None and math.isfinite(float(metric.value))


def test_evaluate_reports_failed_artifact_for_feature_schema_mismatch(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    service = TrainingService(registry, _queue(tmp_path))
    model_ref, _ = _register_model(registry, "rw2_02_model")
    dataset_ref = registry.put_bytes(
        _dataset_bytes(FEATURE_NAMES, declared_order=list(reversed(FEATURE_NAMES))),
        kind="dataset",
        artifact_id="rw2_02_reversed_dataset",
        version="1",
    )

    artifact = service.evaluate(model_ref, dataset_ref)

    assert artifact.status is EvaluationStatus.FAILED
    assert artifact.failure_reason is not None
    assert "FEATURE_SCHEMA_MISMATCH" in artifact.failure_reason
    assert artifact.metrics == {}


def test_evaluate_reports_invalid_artifact_for_empty_holdout(tmp_path) -> None:
    registry = ModelRegistry(tmp_path / "registry")
    service = TrainingService(registry, _queue(tmp_path))
    model_ref, _ = _register_model(registry, "rw2_02_model")
    dataset_ref = registry.put_bytes(
        _dataset_bytes(FEATURE_NAMES, row_count=60, train_end=60),
        kind="dataset",
        artifact_id="rw2_02_no_holdout_dataset",
        version="1",
    )

    artifact = service.evaluate(model_ref, dataset_ref)

    assert artifact.status is EvaluationStatus.INVALID
    assert artifact.failure_reason is not None
    assert "EVALUATION_SPLIT_EMPTY" in artifact.failure_reason
    assert artifact.metrics == {}, "missing evidence must never become a numeric default"
