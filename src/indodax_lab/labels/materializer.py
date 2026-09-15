"""Verified training dataset assembly and role-restricted tables (TRAIN-01).

Contract:
dataset/feature/label/split/universe/cost IDs -> training manifest and role-restricted tables.
Duplicate sample join ditolak.
Target kolom tidak boleh berada dalam inference feature list.
Checksum atau availability mismatch memblokir output.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
from decimal import Decimal
from typing import Any, Sequence, Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.labels.splits import FoldAssignment, SampleRole, SplitManifest


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class DuplicateSampleError(ValueError):
    """Raised when duplicate sample IDs are detected in inputs."""


class TargetLeakageError(ValueError):
    """Raised when target or future label columns leak into the inference feature list."""


class ArtifactIntegrityError(ValueError):
    """Raised when input artifact checksums do not match expected cryptographic hashes."""


class AvailabilityMismatchError(ValueError):
    """Raised when row availability or label end timestamps violate temporal causality."""


def _content_digest(frame: pd.DataFrame) -> str:
    """Canonical logical rows, independent of physical row order/index and wall clock."""
    def scalar(value: Any) -> Any:
        if isinstance(value, (list, tuple, np.ndarray)):
            return [scalar(v) for v in value]
        if isinstance(value, dict):
            return {str(k): scalar(v) for k, v in sorted(value.items())}
        if value is None or value is pd.NA or value is pd.NaT:
            return None
        if isinstance(value, (datetime, pd.Timestamp)):
            return {"utc": pd.Timestamp(value).isoformat()}
        if isinstance(value, Decimal):
            return {"decimal": str(value)}
        if isinstance(value, (float, np.floating)):
            return None if math.isnan(value) else {"float": float(value).hex()}
        if isinstance(value, (np.integer, np.bool_)):
            return value.item()
        if isinstance(value, (str, int, bool)):
            return value
        raise ArtifactIntegrityError(f"UNSUPPORTED_CONTENT_VALUE:{type(value).__name__}")
    columns = sorted(frame.columns)
    rows = [[scalar(v) for v in row] for row in frame.sort_values("sample_id")[columns].itertuples(index=False, name=None)]
    payload = {"domain": "training-table-v2", "columns": columns, "rows": rows}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _validated_times(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column not in result:
            raise AvailabilityMismatchError(f"MISSING_TEMPORAL_COLUMN:{column}")
        timestamps = []
        for value in result[column]:
            try:
                timestamp = pd.Timestamp(value)
                if pd.isna(timestamp):
                    raise ValueError("MISSING_TIMESTAMP")
                _ensure_utc(timestamp, column)
            except (ValueError, TypeError) as exc:
                raise AvailabilityMismatchError(f"INVALID_UTC_TIMESTAMP:{column}") from exc
            timestamps.append(timestamp)
        result[column] = pd.to_datetime(timestamps, utc=True)
    return result


class TrainingDatasetManifest(BaseModel):
    """Metadata and lineage manifest for an immutable training dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    identity_version: Literal["training-dataset-v2"] = "training-dataset-v2"
    features_content_sha256: str
    labels_content_sha256: str
    split_content_sha256: str
    dataset_snapshot_id: str
    feature_registry_version: str
    features_manifest_id: str
    labels_manifest_id: str
    split_policy_id: str
    cost_schedule_id: str
    target_column: str
    inference_feature_columns: list[str]
    sample_counts_by_role: dict[str, int]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class TrainingDatasetArtifact:
    """Materialized training dataset containing manifest and role-restricted sample partitions."""

    def __init__(
        self,
        manifest: TrainingDatasetManifest,
        data: pd.DataFrame,
    ) -> None:
        self.manifest = manifest
        self._data = data

    @property
    def data(self) -> pd.DataFrame:
        return self._data.copy()

    def get_role_data(self, role: SampleRole | str) -> pd.DataFrame:
        """Return role-restricted subset of samples (e.g. TRAIN, VALIDATION, SEALED_TEST)."""
        role_str = role.value if isinstance(role, SampleRole) else str(role).upper()
        subset = self._data[self._data["role"] == role_str].copy()
        return subset


def materialize_training_dataset(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    split_manifest: SplitManifest,
    target_column: str,
    inference_feature_columns: Sequence[str],
    dataset_snapshot_id: str,
    feature_registry_version: str,
    cost_schedule_id: str,
    features_checksum: str | None = None,
    labels_checksum: str | None = None,
    features_manifest_id: str = "features_manifest_v1",
    labels_manifest_id: str = "labels_manifest_v1",
) -> TrainingDatasetArtifact:
    """Materialize verified training dataset with strict anti-leakage and causality checks.

    Guarantees:
    - Verifies cryptographic artifact checksums.
    - Rejects duplicate sample IDs fail-closed.
    - Prevents target or future columns from entering inference features.
    - Rejects causality/availability violations (row_ready_at > decision_ts).
    - Segregates data cleanly by split role.
    """
    # 1. Checksum verification (TRAIN-01-AC3)
    for name, frame in (("features", features_df), ("labels", labels_df)):
        if not frame.columns.is_unique:
            raise ArtifactIntegrityError(f"DUPLICATE_COLUMNS:{name}")
        if "sample_id" not in frame or not frame["sample_id"].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise ArtifactIntegrityError(f"MISSING_SAMPLE_ID:{name}")
    columns = list(inference_feature_columns)
    if not columns or len(columns) != len(set(columns)):
        raise ArtifactIntegrityError("INVALID_INFERENCE_COLUMNS")
    if target_column not in labels_df:
        raise ArtifactIntegrityError("MISSING_TARGET_COLUMN")
    if features_checksum is not None:
        feat_bytes = features_df.to_parquet()
        actual_feat_sha = hashlib.sha256(feat_bytes).hexdigest()
        if actual_feat_sha != features_checksum:
            raise ArtifactIntegrityError(
                f"CHECKSUM_MISMATCH:features expected {features_checksum}, got {actual_feat_sha}"
            )

    if labels_checksum is not None:
        label_bytes = labels_df.to_parquet()
        actual_label_sha = hashlib.sha256(label_bytes).hexdigest()
        if actual_label_sha != labels_checksum:
            raise ArtifactIntegrityError(
                f"CHECKSUM_MISMATCH:labels expected {labels_checksum}, got {actual_label_sha}"
            )

    # 2. Duplicate sample join rejection (TRAIN-01-AC1)
    if features_df["sample_id"].duplicated().any():
        dups = features_df.loc[features_df["sample_id"].duplicated(), "sample_id"].tolist()
        raise DuplicateSampleError(f"DUPLICATE_SAMPLE_ID_DETECTED: features dataframe contains duplicate sample_ids: {dups[:5]}")

    if labels_df["sample_id"].duplicated().any():
        dups = labels_df.loc[labels_df["sample_id"].duplicated(), "sample_id"].tolist()
        raise DuplicateSampleError(f"DUPLICATE_SAMPLE_ID_DETECTED: labels dataframe contains duplicate sample_ids: {dups[:5]}")

    # 3. Target leakage guard (TRAIN-01-AC2)
    inf_features_set = set(inference_feature_columns)
    prohibited_names = {target_column, "net_return", "binary_label"}
    for col in inf_features_set:
        if col.lower() in prohibited_names or col.lower().startswith(("label_", "future_", "exit_", "target_", "outcome_", "entry_")):
            raise TargetLeakageError(
                f"TARGET_COLUMN_IN_FEATURE_LIST: column '{col}' is a target or future outcome and cannot be in inference features"
            )

    # 4. Availability evidence is mandatory, never inferred from event time.
    if not set(columns).issubset(features_df.columns):
        raise ArtifactIntegrityError("INVALID_INFERENCE_COLUMNS")
    features_df = _validated_times(features_df, ("decision_ts", "row_ready_at"))
    labels_df = _validated_times(
        labels_df, ("decision_ts", "label_end_ts", "label_available_at")
    )
    for frame in (features_df, labels_df):
        if "pair" not in frame or frame["pair"].isna().any():
            raise ArtifactIntegrityError("MISSING_PAIR_IDENTITY")
    if set(features_df["sample_id"]) != set(labels_df["sample_id"]):
        raise ArtifactIntegrityError("SAMPLE_ID_SET_MISMATCH")
    feature_identity = features_df.set_index("sample_id")[["pair", "decision_ts"]]
    label_identity = labels_df.set_index("sample_id")[["pair", "decision_ts"]]
    if not feature_identity.sort_index().equals(label_identity.sort_index()):
        raise ArtifactIntegrityError("SAMPLE_IDENTITY_MISMATCH")
    if (labels_df["label_available_at"] < labels_df["label_end_ts"]).any():
        raise AvailabilityMismatchError("LABEL_AVAILABLE_BEFORE_OUTCOME_END")

    if "row_ready_at" in features_df.columns and "decision_ts" in features_df.columns:
        invalid = features_df["row_ready_at"] > features_df["decision_ts"]
        if invalid.any():
            violators = features_df.loc[invalid, "sample_id"].tolist()
            raise AvailabilityMismatchError(
                f"AVAILABILITY_MISMATCH: row_ready_at > decision_ts detected for samples: {violators[:5]}"
            )

    if "label_end_ts" in labels_df.columns and "decision_ts" in labels_df.columns:
        invalid = labels_df["label_end_ts"] < labels_df["decision_ts"]
        if invalid.any():
            violators = labels_df.loc[invalid, "sample_id"].tolist()
            raise AvailabilityMismatchError(
                f"AVAILABILITY_MISMATCH: label_end_ts < decision_ts detected for samples: {violators[:5]}"
            )

    # 5. Build split assignments table
    split_records = []
    assignments_iter = (
        split_manifest.assignments.values()
        if isinstance(split_manifest.assignments, dict)
        else split_manifest.assignments
    )
    for assignment in assignments_iter:
        split_records.append(
            {
                "sample_id": assignment.sample_id,
                "role": assignment.role.value if isinstance(assignment.role, SampleRole) else str(assignment.role),
                "fold_role": assignment.fold_role.value if assignment.fold_role else None,
                "split_reason": assignment.purge_reason,
                "fold_start_ts": assignment.fold_start_ts,
                "fold_end_ts": assignment.fold_end_ts,
            }
        )
    split_df = pd.DataFrame(split_records)

    if split_df.empty:
        raise ArtifactIntegrityError("EMPTY_SPLIT_ASSIGNMENTS")
    if any(key != value.sample_id for key, value in split_manifest.assignments.items()):
        raise ArtifactIntegrityError("SPLIT_ASSIGNMENT_KEY_MISMATCH")

    if split_df["sample_id"].duplicated().any():
        dups = split_df.loc[split_df["sample_id"].duplicated(), "sample_id"].tolist()
        raise DuplicateSampleError(f"DUPLICATE_SAMPLE_ID_DETECTED: split manifest contains duplicate sample_ids: {dups[:5]}")

    # Join features, labels, and splits on sample_id
    if set(split_df["sample_id"]) != set(features_df["sample_id"]):
        raise ArtifactIntegrityError("SPLIT_SAMPLE_ID_SET_MISMATCH")
    merged = pd.merge(features_df, labels_df[
        ["sample_id", target_column, "label_end_ts", "label_available_at"]
    ], on="sample_id", how="inner", validate="one_to_one")
    merged = pd.merge(merged, split_df, on="sample_id", how="inner")

    active = merged["role"].isin([
        SampleRole.TRAIN.value, SampleRole.VALIDATION.value,
        SampleRole.CALIBRATION.value, SampleRole.SEALED_TEST.value,
    ])
    if "eligible" not in merged or not merged["eligible"].isin([True, False]).all():
        raise ArtifactIntegrityError("FEATURE_ELIGIBILITY_REQUIRED")
    if (~merged.loc[active, "eligible"].astype(bool)).any():
        raise ArtifactIntegrityError("INELIGIBLE_ACTIVE_SAMPLE")
    try:
        finite = np.isfinite(merged.loc[active, columns + [target_column]].to_numpy(dtype=float)).all()
    except (TypeError, ValueError) as exc:
        raise ArtifactIntegrityError("INVALID_INFERENCE_VALUES") from exc
    if not finite:
        raise ArtifactIntegrityError("NONFINITE_ELIGIBLE_VALUES")
    for row in merged.loc[active].itertuples(index=False):
        if pd.isna(row.fold_start_ts) or pd.isna(row.fold_end_ts):
            raise AvailabilityMismatchError("FOLD_BOUNDARIES_REQUIRED")
        if not row.fold_start_ts <= row.decision_ts < row.fold_end_ts:
            raise AvailabilityMismatchError("DECISION_OUTSIDE_ASSIGNED_FOLD")
        if row.label_available_at >= row.fold_end_ts:
            raise AvailabilityMismatchError("LABEL_UNAVAILABLE_BEFORE_FOLD_CUTOFF")

    # Count samples per role
    sample_counts_by_role: dict[str, int] = {}
    for role_name in SampleRole:
        count = int((merged["role"] == role_name.value).sum())
        sample_counts_by_role[role_name.value] = count

    for field, role in (("train_count", "TRAIN"), ("validation_count", "VALIDATION"),
                        ("sealed_test_count", "SEALED_TEST"), ("purged_count", "PURGED"),
                        ("embargoed_count", "EMBARGOED")):
        if getattr(split_manifest, field) != sample_counts_by_role[role]:
            raise ArtifactIntegrityError(f"SPLIT_ROLE_COUNT_MISMATCH:{role}")
    if split_manifest.total_samples != len(merged):
        raise ArtifactIntegrityError("SPLIT_TOTAL_COUNT_MISMATCH")
    feature_digest = _content_digest(features_df)
    label_digest = _content_digest(labels_df)
    split_digest = _content_digest(split_df)
    id_source = json.dumps({
        "domain": "training-dataset-v2", "features": feature_digest, "labels": label_digest,
        "split": split_digest, "policy_id": split_manifest.policy_id,
        "split_parent": split_manifest.split_id,
        "policy_version": split_manifest.policy_version, "snapshot": dataset_snapshot_id,
        "policy_content": split_manifest.policy_content_sha256,
        "registry": feature_registry_version, "features_parent": features_manifest_id,
        "labels_parent": labels_manifest_id, "cost": cost_schedule_id,
        "target": target_column, "inference_features": columns,
    }, sort_keys=True, separators=(",", ":"))
    dataset_id = f"ds_train_v2_{hashlib.sha256(id_source.encode()).hexdigest()}"

    manifest = TrainingDatasetManifest(
        dataset_id=dataset_id,
        features_content_sha256=feature_digest,
        labels_content_sha256=label_digest,
        split_content_sha256=split_digest,
        dataset_snapshot_id=dataset_snapshot_id,
        feature_registry_version=feature_registry_version,
        features_manifest_id=features_manifest_id,
        labels_manifest_id=labels_manifest_id,
        split_policy_id=split_manifest.policy_id,
        cost_schedule_id=cost_schedule_id,
        target_column=target_column,
        inference_feature_columns=list(inference_feature_columns),
        sample_counts_by_role=sample_counts_by_role,
        created_at=datetime.now(UTC),
    )

    return TrainingDatasetArtifact(manifest=manifest, data=merged)
