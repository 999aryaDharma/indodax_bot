"""Offline training and evaluation services for registered models (RW2-02).

Guarantees:
- Training is queue-backed (JOB-01): ``create`` submits a durable PENDING job,
  ``run`` claims, executes and publishes exactly one new immutable model
  version. Registered versions are never mutated in place.
- ``evaluate`` emits immutable evaluation evidence (COMPLETED/FAILED/INVALID)
  and never turns missing evidence into a numeric default.
- Failures are fail-closed: the job ends FAILED_FINAL with a specific reason
  and no successful model identity appears in the registry.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.contracts.identity import ArtifactRef, canonical_bytes, manifest_digest
from indodax_lab.contracts.workbench import MetricValidity, MetricValue, ModelManifest
from indodax_lab.models.artifacts import PortableBundle
from indodax_lab.models.m01_logistic import M01Config, M01LogisticTrainer
from indodax_lab.models.registry import (
    FeatureFrame,
    ModelRegistry,
    ModelRegistryError,
    RuntimeBlockedError,
    unmet_runtime_requirements,
)
from indodax_lab.orchestration.jobs import (
    JobDefinition,
    JobRecord,
    JobStatus,
    LeaseFencingError,
)
from indodax_lab.orchestration.queue import SqliteJobQueue

# ---------------------------------------------------------------------------
# Errors — fail-closed, ``<CODE>: <detail>`` messages
# ---------------------------------------------------------------------------


class TrainingServiceError(Exception):
    """Base error for training service operations."""

    code: ClassVar[str] = "TRAINING_SERVICE_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(f"{self.code}: {detail}")


class TrainingJobNotFoundError(TrainingServiceError):
    code: ClassVar[str] = "TRAINING_JOB_NOT_FOUND"


class TrainingJobStateError(TrainingServiceError):
    code: ClassVar[str] = "TRAINING_JOB_STATE"


class TrainingNotClaimableError(TrainingServiceError):
    code: ClassVar[str] = "TRAINING_JOB_NOT_CLAIMABLE"


class TrainingArchitectureError(TrainingServiceError):
    code: ClassVar[str] = "TRAINING_ARCHITECTURE_UNSUPPORTED"


class DatasetSchemaError(TrainingServiceError):
    code: ClassVar[str] = "DATASET_SCHEMA_INVALID"


# ---------------------------------------------------------------------------
# Evaluation evidence contract
# ---------------------------------------------------------------------------


class EvaluationStatus(StrEnum):
    """Lifecycle status of one evaluation artifact."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INVALID = "INVALID"


class EvaluationArtifact(BaseModel):
    """Immutable evaluation evidence for one model/dataset pair (RW2-02)."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    evaluation_id: str
    model_ref: ArtifactRef
    dataset_ref: ArtifactRef
    split_ref: ArtifactRef
    metrics: dict[str, MetricValue] = Field(default_factory=dict)
    calibration_ref: ArtifactRef | None = None
    train_transform_refs: tuple[ArtifactRef, ...] = ()
    status: EvaluationStatus
    failure_reason: str | None = None
    created_at_utc: datetime
    schema_version: str = "v1"

    @field_validator("evaluation_id")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("NON_EMPTY_REQUIRED:evaluation_id")
        return value

    @field_validator("created_at_utc", mode="after")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED:created_at_utc")
        return value

    @model_validator(mode="after")
    def _validate_status_evidence(self) -> EvaluationArtifact:
        if self.status is EvaluationStatus.COMPLETED:
            if self.failure_reason is not None:
                raise ValueError("EVALUATION_FAILURE_REASON_FORBIDDEN_FOR_COMPLETED")
            if not self.metrics:
                raise ValueError("EVALUATION_METRICS_REQUIRED_FOR_COMPLETED")
            for name, metric in self.metrics.items():
                if metric.validity is not MetricValidity.VALID:
                    raise ValueError(f"EVALUATION_METRIC_INVALID:{name}")
        else:
            if not self.failure_reason:
                raise ValueError("EVALUATION_FAILURE_REASON_REQUIRED")
            for name, metric in self.metrics.items():
                if metric.validity is MetricValidity.VALID:
                    raise ValueError(f"EVALUATION_METRIC_MUST_NOT_BE_VALID:{name}")
        return self


class TrainingConfig(BaseModel):
    """Declared inputs for one offline training job (immutable)."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str
    version: str = "1.0.0"
    architecture: str = "m01_logistic"
    ordered_feature_schema: tuple[str, ...]
    universe: tuple[str, ...]
    runtime_requirements: dict[str, str] = Field(default_factory=dict)
    trainer: M01Config = Field(default_factory=M01Config)

    @field_validator("model_id", "version", "architecture")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("NON_EMPTY_REQUIRED")
        return value

    @field_validator("ordered_feature_schema", mode="after")
    @classmethod
    def _require_valid_schema(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not name for name in value):
            raise ValueError("FEATURE_SCHEMA_INVALID: schema must be non-empty strings")
        if len(set(value)) != len(value):
            raise ValueError("FEATURE_SCHEMA_INVALID: schema names must be unique")
        return value


# ---------------------------------------------------------------------------
# Dataset contract (RW2-02 local JSON, schema v1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Dataset:
    """Validated dataset split: rows[:train_end] train, tail is holdout."""

    feature_names: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]
    labels: tuple[int, ...]
    train_end: int

    @property
    def holdout_rows(self) -> tuple[tuple[float, ...], ...]:
        return self.rows[self.train_end :]

    @property
    def holdout_labels(self) -> tuple[int, ...]:
        return self.labels[self.train_end :]


def _parse_dataset(payload: bytes) -> _Dataset:
    """Parse and strictly validate one dataset JSON payload."""
    try:
        document = json.loads(payload)
    except ValueError as exc:
        raise DatasetSchemaError(f"dataset bytes are not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise DatasetSchemaError("dataset payload must be a JSON object")
    if document.get("schema_version") != "v1":
        raise DatasetSchemaError(
            f"unsupported dataset schema_version {document.get('schema_version')!r}"
        )
    feature_names = document.get("feature_names")
    if not isinstance(feature_names, list) or not feature_names:
        raise DatasetSchemaError("feature_names must be a non-empty list")
    if any(not isinstance(name, str) or not name for name in feature_names):
        raise DatasetSchemaError("feature_names entries must be non-empty strings")
    if len(set(feature_names)) != len(feature_names):
        raise DatasetSchemaError("feature_names must be unique")
    rows_raw = document.get("rows")
    labels_raw = document.get("labels")
    if not isinstance(rows_raw, list) or not rows_raw:
        raise DatasetSchemaError("rows must be a non-empty list")
    if not isinstance(labels_raw, list) or len(labels_raw) != len(rows_raw):
        raise DatasetSchemaError("labels must align with rows")
    width = len(feature_names)
    rows: list[tuple[float, ...]] = []
    for index, row in enumerate(rows_raw):
        if not isinstance(row, list) or len(row) != width:
            got = len(row) if isinstance(row, list) else type(row).__name__
            raise DatasetSchemaError(f"row {index} must contain {width} values (got {got})")
        values: list[float] = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DatasetSchemaError(f"row {index} value {value!r} is not numeric")
            number = float(value)
            if not math.isfinite(number):
                raise DatasetSchemaError(f"row {index} value {value!r} is not finite")
            values.append(number)
        rows.append(tuple(values))
    labels: list[int] = []
    for index, label in enumerate(labels_raw):
        if isinstance(label, bool) or not isinstance(label, int) or label not in (0, 1):
            raise DatasetSchemaError(f"label {index} must be 0 or 1 (got {label!r})")
        labels.append(label)
    train_end = document.get("train_end")
    if isinstance(train_end, bool) or not isinstance(train_end, int):
        raise DatasetSchemaError(f"train_end must be an integer (got {train_end!r})")
    if not 0 < train_end <= len(rows):
        raise DatasetSchemaError(
            f"train_end must be within (0, {len(rows)}] (got {train_end!r})"
        )
    return _Dataset(
        feature_names=tuple(feature_names),
        rows=tuple(rows),
        labels=tuple(labels),
        train_end=train_end,
    )


def _combine_datasets(parts: Sequence[_Dataset]) -> _Dataset:
    """Merge ordered partitions: all train blocks first, then all holdouts."""
    if len(parts) == 1:
        return parts[0]
    first = parts[0]
    train_rows: list[tuple[float, ...]] = []
    train_labels: list[int] = []
    holdout_rows: list[tuple[float, ...]] = []
    holdout_labels: list[int] = []
    for part in parts:
        if part.feature_names != first.feature_names:
            raise DatasetSchemaError(
                f"partition feature schema {part.feature_names} does not match "
                f"{first.feature_names}"
            )
        train_rows.extend(part.rows[: part.train_end])
        train_labels.extend(part.labels[: part.train_end])
        holdout_rows.extend(part.rows[part.train_end :])
        holdout_labels.extend(part.labels[part.train_end :])
    return _Dataset(
        feature_names=first.feature_names,
        rows=tuple(train_rows) + tuple(holdout_rows),
        labels=tuple(train_labels) + tuple(holdout_labels),
        train_end=len(train_rows),
    )


# ---------------------------------------------------------------------------
# TrainingService
# ---------------------------------------------------------------------------


class TrainingService:
    """Queue-backed offline training and evaluation service (RW2-02)."""

    def __init__(
        self,
        registry: ModelRegistry,
        queue: SqliteJobQueue,
        *,
        worker_id: str = "rw2-02-training-service",
    ) -> None:
        self.registry = registry
        self.queue = queue
        self.worker_id = worker_id

    # -- job lifecycle -----------------------------------------------------

    def create(
        self,
        config: TrainingConfig,
        dataset_refs: Sequence[ArtifactRef],
    ) -> JobRecord:
        """Submit one durable PENDING training job (inputs hash-verified)."""
        refs = tuple(dataset_refs)
        if not refs:
            raise DatasetSchemaError("at least one dataset reference is required")
        for ref in refs:
            self.registry.read_object(ref)
        requirements = config.runtime_requirements
        needs_accelerator = any(
            key.strip().lower() in ("accelerator", "device") for key in requirements
        )
        job_def = JobDefinition(
            job_id=f"train_{uuid.uuid4().hex}",
            job_type="train_model",
            recipe_hash=manifest_digest(config),
            input_ids=[f"{ref.kind}:{ref.id}:{ref.version}:{ref.sha256}" for ref in refs],
            parameters={
                "resource_class": "GPU" if needs_accelerator else "HIGH",
                "model_id": config.model_id,
                "version": config.version,
                "architecture": config.architecture,
                "config": config.model_dump(mode="json"),
                "dataset_refs": [ref.model_dump(mode="json") for ref in refs],
            },
            lease_duration_seconds=600,
            created_at=datetime.now(UTC),
        )
        return self.queue.submit_job(job_def)

    def run(self, job_id: str) -> ArtifactRef:
        """Claim, execute and publish one training job; returns the new model ref."""
        try:
            record = self.queue.get_job(job_id)
        except KeyError as exc:
            raise TrainingJobNotFoundError(f"job {job_id} does not exist") from exc
        if record.status is not JobStatus.PENDING:
            raise TrainingJobStateError(
                f"job {job_id} is {record.status}, expected {JobStatus.PENDING}"
            )
        claimed = self.queue.claim_job(self.worker_id)
        if claimed is None:
            raise TrainingNotClaimableError(f"no claimable job while running {job_id}")
        if claimed.job_id != job_id:
            self._release(claimed)
            raise TrainingNotClaimableError(
                f"claimed {claimed.job_id} instead of requested {job_id}"
            )
        try:
            return self._execute(claimed)
        except Exception as exc:
            self._fail_final(claimed, str(exc)[:480])
            raise

    @contextmanager
    def _ignore_fenced(self):
        try:
            yield
        except LeaseFencingError:
            pass

    def _release(self, record: JobRecord) -> None:
        """Hand a mistakenly claimed job back to the queue."""
        with self._ignore_fenced():
            self.queue.fail_job(
                record.job_id,
                self.worker_id,
                record.generation,
                "TRAINING_JOB_NOT_CLAIMABLE: claimed by an identity-bound run",
                retryable=True,
            )

    def _fail_final(self, record: JobRecord, error_message: str) -> None:
        """Record a terminal failure without retry loops."""
        with self._ignore_fenced():
            self.queue.fail_job(
                record.job_id,
                self.worker_id,
                record.generation,
                error_message,
                retryable=False,
            )

    # -- execution ---------------------------------------------------------

    def _decode(self, record: JobRecord) -> tuple[TrainingConfig, tuple[ArtifactRef, ...]]:
        raw_config = record.parameters.get("config")
        raw_refs = record.parameters.get("dataset_refs")
        if not isinstance(raw_config, dict) or not isinstance(raw_refs, list):
            raise TrainingJobStateError(
                f"job {record.job_id} is missing training parameters"
            )
        config = TrainingConfig.model_validate(raw_config)
        refs = tuple(ArtifactRef.model_validate(item) for item in raw_refs)
        if not refs:
            raise DatasetSchemaError("at least one dataset reference is required")
        return config, refs

    def _execute(self, record: JobRecord) -> ArtifactRef:
        config, refs = self._decode(record)
        parts = tuple(_parse_dataset(self.registry.read_object(ref)) for ref in refs)
        dataset = _combine_datasets(parts)
        if dataset.feature_names != tuple(config.ordered_feature_schema):
            raise DatasetSchemaError(
                f"dataset feature schema {dataset.feature_names} does not match configured "
                f"{tuple(config.ordered_feature_schema)}"
            )
        if dataset.train_end >= len(dataset.rows):
            raise DatasetSchemaError(
                "DATASET_HOLDOUT_REQUIRED: training requires a non-empty holdout segment"
            )
        unmet = unmet_runtime_requirements(
            config.runtime_requirements, probe=self.registry.probe
        )
        if unmet:
            raise RuntimeBlockedError(
                f"{'; '.join(unmet)}: training job {record.job_id} for model "
                f"{config.model_id}:{config.version} cannot run"
            )
        trainer = _TRAINERS.get(config.architecture)
        if trainer is None:
            raise TrainingArchitectureError(
                f"no offline trainer is registered for architecture {config.architecture!r}"
            )
        return trainer(self, config, dataset, record)

    def _train_m01(
        self,
        config: TrainingConfig,
        dataset: _Dataset,
        record: JobRecord,
    ) -> ArtifactRef:
        """Train, package and register one new M01 model version."""
        feature_names = list(config.ordered_feature_schema)
        frame = pd.DataFrame(dataset.rows, columns=feature_names)
        labels = pd.Series(dataset.labels, dtype="int64")
        trainer_config = config.trainer.model_copy(
            update={"model_id": config.model_id, "version": config.version}
        )
        trainer = M01LogisticTrainer(config=trainer_config)
        fitted = trainer.train_and_calibrate(
            X_train=frame.iloc[: dataset.train_end],
            y_train=labels.iloc[: dataset.train_end],
            X_val=frame.iloc[dataset.train_end :],
            y_val=labels.iloc[dataset.train_end :],
            feature_names=feature_names,
        )
        bundle = PortableBundle.from_m01(bundle=fitted, trainer=trainer)
        bundle_ref = self.registry.put_bytes(
            bundle.to_bytes(),
            kind="model",
            artifact_id=f"{config.model_id}_bundle",
            version=config.version,
        )
        calibration_ref = self.registry.put_bytes(
            json.dumps(bundle.calibration, sort_keys=True).encode("utf-8"),
            kind="calibration",
            artifact_id=f"{config.model_id}_calibration",
            version=config.version,
        )
        preprocessing_ref = self.registry.put_bytes(
            json.dumps(
                {"mode": "identity", "feature_names": feature_names}, sort_keys=True
            ).encode("utf-8"),
            kind="preprocessing",
            artifact_id=f"{config.model_id}_preprocessing",
            version=config.version,
        )
        manifest = ModelManifest(
            model_id=config.model_id,
            architecture=config.architecture,
            version=config.version,
            artifact_refs=(bundle_ref,),
            ordered_feature_schema=tuple(feature_names),
            preprocessing_ref=preprocessing_ref,
            calibration_ref=calibration_ref,
            universe=tuple(config.universe),
            runtime_requirements=dict(config.runtime_requirements),
        )
        manifest_bytes = canonical_bytes(manifest)
        staging = self._staging_path(record.job_id)
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_bytes(manifest_bytes)
        manifest_ref = self.registry.register(manifest)
        self.queue.complete_job(
            record.job_id,
            self.worker_id,
            record.generation,
            artifact_path=staging,
            expected_hash=manifest_ref.sha256,
        )
        return manifest_ref

    def _staging_path(self, job_id: str) -> Path:
        return self.registry.root / "jobs" / f"{job_id}.bundle.json"

    # -- evaluation --------------------------------------------------------

    def evaluate(
        self,
        model_ref: ArtifactRef,
        dataset_ref: ArtifactRef,
    ) -> EvaluationArtifact:
        """Evaluate one registered model on one dataset split (immutable evidence)."""
        dataset = _parse_dataset(self.registry.read_object(dataset_ref))
        split_ref = self.registry.put_bytes(
            json.dumps(
                {
                    "schema_version": "v1",
                    "dataset_id": dataset_ref.id,
                    "dataset_version": dataset_ref.version,
                    "split": "holdout",
                    "feature_names": list(dataset.feature_names),
                    "row_count": len(dataset.holdout_rows),
                },
                sort_keys=True,
            ).encode("utf-8"),
            kind="split",
            artifact_id=f"{dataset_ref.id}_holdout",
            version=dataset_ref.version,
        )
        evaluation_id = f"eval_{uuid.uuid4().hex}"
        if not dataset.holdout_rows:
            return EvaluationArtifact(
                evaluation_id=evaluation_id,
                model_ref=model_ref,
                dataset_ref=dataset_ref,
                split_ref=split_ref,
                metrics={},
                status=EvaluationStatus.INVALID,
                failure_reason=(
                    f"EVALUATION_SPLIT_EMPTY: dataset {dataset_ref.id}:{dataset_ref.version} "
                    "declares no holdout rows"
                ),
                created_at_utc=datetime.now(UTC),
            )
        predictor = self.registry.load_verified(model_ref)
        frame = FeatureFrame(
            feature_names=dataset.feature_names,
            rows=dataset.holdout_rows,
        )
        try:
            result = predictor.predict_proba(frame)
        except ModelRegistryError as exc:
            return EvaluationArtifact(
                evaluation_id=evaluation_id,
                model_ref=model_ref,
                dataset_ref=dataset_ref,
                split_ref=split_ref,
                metrics={},
                calibration_ref=predictor.manifest.calibration_ref,
                train_transform_refs=_transform_refs(predictor.manifest),
                status=EvaluationStatus.FAILED,
                failure_reason=str(exc),
                created_at_utc=datetime.now(UTC),
            )
        brier = sum(
            (probability - label) ** 2
            for probability, label in zip(
                result.probabilities, dataset.holdout_labels, strict=True
            )
        ) / len(dataset.holdout_labels)
        accuracy = sum(
            1
            for probability, label in zip(
                result.probabilities, dataset.holdout_labels, strict=True
            )
            if (probability >= 0.5) == (label == 1)
        ) / len(dataset.holdout_labels)
        return EvaluationArtifact(
            evaluation_id=evaluation_id,
            model_ref=model_ref,
            dataset_ref=dataset_ref,
            split_ref=split_ref,
            metrics={
                "brier_score": MetricValue(value=brier, unit="probability_squared"),
                "accuracy": MetricValue(value=accuracy, unit="ratio"),
            },
            calibration_ref=predictor.manifest.calibration_ref,
            train_transform_refs=_transform_refs(predictor.manifest),
            status=EvaluationStatus.COMPLETED,
            created_at_utc=datetime.now(UTC),
        )


def _transform_refs(manifest: ModelManifest) -> tuple[ArtifactRef, ...]:
    """Collect train-only transform refs declared by a model manifest."""
    return tuple(
        ref for ref in (manifest.preprocessing_ref,) if ref is not None
    )


# Pinned offline trainers: architectures outside this map fail closed with
# TRAINING_ARCHITECTURE_UNSUPPORTED instead of being substituted by a default.
_TRAINERS: Mapping[str, Callable[..., ArtifactRef]] = MappingProxyType(
    {"m01_logistic": TrainingService._train_m01}
)
