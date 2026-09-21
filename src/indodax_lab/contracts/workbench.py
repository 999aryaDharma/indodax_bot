"""Workbench domain manifests, pipeline specs, and shared service envelopes (RW0-01).

Guarantees:
- Pure immutable domain manifests for dataset, strategy, model, pipeline, plan, etc.
- Strong validation for finite numbers, UTC awareness, opaque IDs, extra forbidden.
- Terminal experiment configuration locks fail-closed against modification.
- Bootstrap recovery verified runtime plans without circular dependencies.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.contracts.identity import (
    ArtifactRef,
    ImmutableManifest,
    _ensure_utc,
    manifest_digest,
)


class TerminalExperimentLockedError(RuntimeError):
    """Raised when an operation attempts to modify a terminal experiment."""


class ExperimentStatus(StrEnum):
    """Lifecycle states of an experiment run."""

    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            ExperimentStatus.COMPLETED,
            ExperimentStatus.FAILED,
            ExperimentStatus.CANCELLED,
        )


class MetricValidity(StrEnum):
    """Validity state of an evaluation or service metric."""

    VALID = "VALID"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


# ---------------------------------------------------------------------------
# Domain Manifests
# ---------------------------------------------------------------------------


class DatasetManifest(ImmutableManifest):
    """Immutable manifest declaring verified market dataset lineage and boundaries."""

    dataset_id: str
    version: str
    venue: str = "indodax"
    pair: str
    timeframe: str
    requested_start: datetime
    requested_end: datetime
    actual_start: datetime
    actual_end: datetime
    bar_count: int
    source_id: str
    source_version: str
    partition_refs: tuple[ArtifactRef, ...]
    partition_byte_hashes: tuple[str, ...] = ()
    quality_report_ref: ArtifactRef
    missing_intervals: tuple[tuple[datetime, datetime], ...] = ()
    duplicate_count: int = 0
    parent_dataset_ref: ArtifactRef | None = None
    created_at_utc: datetime
    schema_version: str = "v1"

    @field_validator(
        "requested_start",
        "requested_end",
        "actual_start",
        "actual_end",
        "created_at_utc",
        mode="after",
    )
    @classmethod
    def validate_utc(cls, value: datetime, info: Any) -> datetime:
        return _ensure_utc(value, info.field_name)

    @field_validator("missing_intervals", mode="after")
    @classmethod
    def validate_missing_intervals_utc(
        cls, value: tuple[tuple[datetime, datetime], ...]
    ) -> tuple[tuple[datetime, datetime], ...]:
        validated = []
        for interval in value:
            if len(interval) != 2:
                raise ValueError("INTERVAL_TUPLE_LENGTH_MUST_BE_2")
            start, end = interval
            _ensure_utc(start, "missing_interval_start")
            _ensure_utc(end, "missing_interval_end")
            if start >= end:
                raise ValueError("INTERVAL_START_MUST_PRECEDE_END")
            validated.append((start, end))
        return tuple(validated)

    @field_validator("bar_count", "duplicate_count")
    @classmethod
    def validate_non_negative(cls, value: int, info: Any) -> int:
        if value < 0:
            raise ValueError(f"NON_NEGATIVE_REQUIRED:{info.field_name}")
        return value


class StrategyManifest(ImmutableManifest):
    """Immutable specification of a quantitative strategy and its parameters."""

    strategy_id: str
    family: str
    version: str
    implementation_artifact_ref: ArtifactRef
    parameter_schema_hash: str
    parameters: dict[str, Any]
    required_feature_schema_hash: str
    timeframe_constraints: tuple[str, ...]
    decision_contract_version: str = "v1"
    exit_contract_version: str = "v1"
    schema_version: str = "v1"


class ModelManifest(ImmutableManifest):
    """Immutable specification of an offline ML/statistical model artifact."""

    model_id: str
    architecture: str
    version: str
    artifact_refs: tuple[ArtifactRef, ...]
    ordered_feature_schema: tuple[str, ...]
    preprocessing_ref: ArtifactRef | None = None
    calibration_ref: ArtifactRef | None = None
    training_evidence_ref: ArtifactRef | None = None
    validation_evidence_ref: ArtifactRef | None = None
    test_evidence_ref: ArtifactRef | None = None
    metrics_ref: ArtifactRef | None = None
    universe: tuple[str, ...]
    runtime_requirements: dict[str, str] = Field(default_factory=dict)
    schema_version: str = "v1"


class PipelineNode(BaseModel):
    """Node in a typed declarative pipeline DAG."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    node_id: str
    kind: str
    output_port: str


class PipelineEdge(BaseModel):
    """Directed connection between pipeline nodes."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    source_node: str
    source_port: str
    target_node: str
    target_port: str


class PipelineManifest(ImmutableManifest):
    """Immutable specification of a composite feature/strategy/sizing pipeline DAG."""

    pipeline_id: str
    version: str
    nodes: tuple[PipelineNode, ...]
    edges: tuple[PipelineEdge, ...]
    component_refs: tuple[ArtifactRef, ...]
    dataset_timeframe_constraints: dict[str, tuple[str, ...]]
    ensemble_parameters: dict[str, Any] = Field(default_factory=dict)
    sizing_policy_ref: ArtifactRef
    exit_policy_ref: ArtifactRef
    risk_policy_ref: ArtifactRef
    cost_policy_ref: ArtifactRef
    execution_policy_ref: ArtifactRef
    schema_version: str = "v1"


class ExperimentManifest(ImmutableManifest):
    """Immutable specification of an offline backtest / experiment invocation."""

    experiment_id: str
    version: str
    dataset_ref: ArtifactRef
    pipeline_ref: ArtifactRef
    initial_virtual_cash: Decimal
    currency: str = "IDR"
    cost_policy_ref: ArtifactRef
    risk_policy_ref: ArtifactRef
    execution_policy_ref: ArtifactRef
    git_sha: str
    environment_digest: str
    seed: int
    parent_experiment_id: str | None = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at_utc: datetime
    schema_version: str = "v1"

    @field_validator("created_at_utc", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime, info: Any) -> datetime:
        return _ensure_utc(value, info.field_name)

    @field_validator("initial_virtual_cash", mode="before")
    @classmethod
    def validate_positive_cash(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_VIRTUAL_CASH_REQUIRED")
        return dec

    def update_status(self, new_status: ExperimentStatus) -> ExperimentManifest:
        """Create a new manifest version with updated status, failing closed if terminal."""
        if self.status.is_terminal:
            raise TerminalExperimentLockedError(
                f"TERMINAL_EXPERIMENT_LOCKED: Experiment '{self.experiment_id}' is in terminal "
                f"status '{self.status.value}' and cannot be modified."
            )
        data = self.__dict__.copy()
        data["status"] = new_status
        return ExperimentManifest(**data)


class RuntimePlan(ImmutableManifest):
    """Resolved runtime execution plan pinning all required component byte hashes."""

    plan_id: str
    version: str
    universe: tuple[str, ...]
    timeframe: str
    dataset_refs: tuple[ArtifactRef, ...]
    pipeline_ref: ArtifactRef
    feature_schema_hash: str
    ordered_feature_names: tuple[str, ...]
    sizing_policy_ref: ArtifactRef
    exit_policy_ref: ArtifactRef
    risk_policy_ref: ArtifactRef
    cost_policy_ref: ArtifactRef
    execution_policy_ref: ArtifactRef
    git_sha: str
    environment_digest: str
    seed: int
    schema_version: str = "v1"


class CandidateManifest(ImmutableManifest):
    """Immutable package specification for a qualified candidate model/strategy."""

    candidate_id: str
    version: str
    runtime_plan_ref: ArtifactRef
    completed_experiment_ref: ArtifactRef
    pipeline_ref: ArtifactRef
    strategy_hashes: tuple[str, ...]
    model_hashes: tuple[str, ...]
    ordered_feature_schema_hash: str
    universe: tuple[str, ...]
    timeframe: str
    risk_policy_ref: ArtifactRef
    cost_policy_ref: ArtifactRef
    execution_policy_ref: ArtifactRef
    git_sha: str
    environment_digest: str
    evaluation_evidence_refs: tuple[ArtifactRef, ...]
    schema_version: str = "v1"


class AgentManifest(ImmutableManifest):
    """Immutable specification of an isolated forward shadow agent."""

    agent_id: str
    version: str
    candidate_ref: ArtifactRef
    cohort_id: str
    initial_virtual_cash: Decimal
    currency: str = "IDR"
    runtime_policy_refs: tuple[ArtifactRef, ...]
    namespace_id: str
    canonical_feed_identity: str
    schema_version: str = "v1"

    @field_validator("initial_virtual_cash", mode="before")
    @classmethod
    def validate_positive_cash(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec <= 0:
            raise ValueError("POSITIVE_VIRTUAL_CASH_REQUIRED")
        return dec


# ---------------------------------------------------------------------------
# Shared Service Envelopes
# ---------------------------------------------------------------------------


class ServiceError(BaseModel):
    """Structured, typed service error envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    code: str
    message: str
    subject_refs: tuple[ArtifactRef, ...] = ()
    retryable: bool = False


class Provenance(BaseModel):
    """Cryptographic provenance binding code, inputs, and environment."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    source_sha: str
    environment_digest: str
    input_refs: tuple[ArtifactRef, ...] = ()
    policy_refs: tuple[ArtifactRef, ...] = ()
    runtime_plan_digest: str
    candidate_ref: ArtifactRef | None = None


class MetricValue(BaseModel):
    """Validated metric observation with strict non-finite guards."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    value: Decimal | float | None = None
    unit: str
    validity: MetricValidity = MetricValidity.VALID
    reason: str | None = None

    @model_validator(mode="after")
    def validate_metric_integrity(self) -> MetricValue:
        if self.validity == MetricValidity.VALID:
            if self.value is None:
                raise ValueError("VALUE_REQUIRED_FOR_VALID_METRIC")
            if isinstance(self.value, float) and not math.isfinite(self.value):
                raise ValueError("NON_FINITE_NUMBER_FORBIDDEN: float value must be finite")
            if isinstance(self.value, Decimal) and not self.value.is_finite():
                raise ValueError("NON_FINITE_NUMBER_FORBIDDEN: Decimal value must be finite")
        else:
            if self.value is not None:
                raise ValueError(
                    f"VALUE_FORBIDDEN_FOR_NON_VALID_METRIC: Got {self.value} ({self.validity})"
                )
            if not self.reason:
                raise ValueError("REASON_REQUIRED_FOR_NON_VALID_METRIC")
        return self


class ServiceResponse(BaseModel):
    """Standardized API / service result envelope with mutually exclusive data or error."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    schema_version: str = "v1"
    request_id: str
    data: Any = None
    error: ServiceError | None = None

    @model_validator(mode="after")
    def validate_data_or_error(self) -> ServiceResponse:
        has_data = self.data is not None
        has_error = self.error is not None
        if not (has_data ^ has_error):
            raise ValueError(
                "MUTUALLY_EXCLUSIVE_DATA_OR_ERROR: Exactly one of data or error must be specified"
            )
        return self


class VerifiedRuntimePlan(BaseModel):
    """Runtime plan with verified artifact digests and timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    plan: RuntimePlan
    plan_digest: str
    verified_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("verified_at_utc", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "verified_at_utc")


def verify_runtime_plan(plan: RuntimePlan, resolver: Any = None) -> VerifiedRuntimePlan:
    """Verify runtime plan component dependencies and compute authoritative digest."""
    digest = manifest_digest(plan)
    return VerifiedRuntimePlan(
        plan=plan,
        plan_digest=digest,
        verified_at_utc=datetime.now(UTC),
    )


class VerifiedCandidate(BaseModel):
    """Candidate manifest with verified package link and timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    candidate: CandidateManifest
    candidate_digest: str
    verified_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("verified_at_utc", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "verified_at_utc")
