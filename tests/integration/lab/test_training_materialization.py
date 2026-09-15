"""Integration tests for TRAIN-01 Verified training dataset assembly.

Acceptance Criteria:
- TRAIN-01-AC0 (test_train_01_valid_contract): Materializer menggabungkan fitur label dan fold hanya melalui ID yang telah diverifikasi.
- TRAIN-01-AC1 (test_train_01_contract_1): Duplicate sample join ditolak.
- TRAIN-01-AC2 (test_train_01_contract_2): Target kolom tidak boleh berada dalam inference feature list.
- TRAIN-01-AC3 (test_train_01_contract_3): Checksum atau availability mismatch memblokir output.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import pandas as pd
import pytest

from indodax_lab.labels.materializer import (
    ArtifactIntegrityError,
    AvailabilityMismatchError,
    DuplicateSampleError,
    TargetLeakageError,
    TrainingDatasetArtifact,
    TrainingDatasetManifest,
    materialize_training_dataset,
)
from indodax_lab.labels.splits import (
    FoldAssignment, FoldWindow, SampleRecord, SampleRole, SplitManifest, SplitPolicy, assign_folds,
)


def _build_test_data() -> tuple[pd.DataFrame, pd.DataFrame, SplitManifest, str, str]:
    """Generate minimal valid features, labels, and split manifest."""
    base_ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

    # 4 samples: 2 train, 1 validation, 1 sealed test
    sample_ids = [f"sample_{i:03d}" for i in range(4)]
    timestamps = [base_ts + timedelta(days=i * 30) for i in range(4)]

    # Features DataFrame
    features_df = pd.DataFrame(
        {
            "sample_id": sample_ids,
            "decision_ts": timestamps,
            "pair": ["btc_idr"] * 4,
            "ret_12": [0.01, -0.02, 0.03, 0.015],
            "rsi_14": [55.0, 42.0, 68.0, 50.0],
            "eligible": [True, True, True, True],
            "row_ready_at": timestamps,  # Available at decision time
        }
    )

    # Labels DataFrame
    labels_df = pd.DataFrame(
        {
            "sample_id": sample_ids,
            "decision_ts": timestamps,
            "pair": ["btc_idr"] * 4,
            "label_end_ts": [ts + timedelta(hours=24) for ts in timestamps],
            "net_return": [0.02, -0.01, 0.04, 0.005],
            "binary_label": [1, 0, 1, 1],
            "label_available_at": [ts + timedelta(hours=24) for ts in timestamps],
        }
    )

    # Split Manifest
    roles = [
        SampleRole.TRAIN,
        SampleRole.TRAIN,
        SampleRole.VALIDATION,
        SampleRole.SEALED_TEST,
    ]
    bounds = {
        SampleRole.TRAIN: (datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC)),
        SampleRole.VALIDATION: (datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 3, 31, tzinfo=UTC)),
        SampleRole.SEALED_TEST: (datetime(2024, 3, 31, tzinfo=UTC), datetime(2024, 5, 1, tzinfo=UTC)),
    }
    assignments = {
        sample_ids[i]: FoldAssignment(
            sample_id=sample_ids[i],
            role=roles[i],
            fold_role=roles[i],
            purge_reason=None,
            fold_start_ts=bounds[roles[i]][0],
            fold_end_ts=bounds[roles[i]][1],
        )
        for i in range(4)
    }

    split_manifest = SplitManifest(
        split_id="split_annual_2024",
        policy_id="annual_v1",
        policy_version="1.0.0",
        total_samples=4,
        train_count=2,
        validation_count=1,
        sealed_test_count=1,
        purged_count=0,
        embargoed_count=0,
        assignments=assignments,
        policy_content_sha256=hashlib.sha256(json.dumps({
            "policy_id": "annual_v1", "version": "1.0.0", "folds": {
                str(role): [start.isoformat(), end.isoformat()]
                for role, (start, end) in bounds.items()
            }, "embargo_hours": 24, "max_horizon_hours": 24,
        }, sort_keys=True).encode()).hexdigest(),
    )

    features_bytes = features_df.to_parquet()
    labels_bytes = labels_df.to_parquet()
    feat_sha = hashlib.sha256(features_bytes).hexdigest()
    label_sha = hashlib.sha256(labels_bytes).hexdigest()

    return features_df, labels_df, split_manifest, feat_sha, label_sha


def test_train_01_valid_contract() -> None:
    """TRAIN-01-AC0: Materializer menggabungkan fitur label dan fold hanya melalui ID yang telah diverifikasi."""
    features_df, labels_df, split_manifest, feat_sha, label_sha = _build_test_data()

    artifact = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest,
        features_checksum=feat_sha,
        labels_checksum=label_sha,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snapshot_btc_2024",
        feature_registry_version="1.0.0",
        cost_schedule_id="cost_schedule_v1",
    )

    assert isinstance(artifact, TrainingDatasetArtifact)
    assert artifact.manifest.target_column == "net_return"
    assert artifact.manifest.inference_feature_columns == ["ret_12", "rsi_14"]
    assert artifact.manifest.sample_counts_by_role["TRAIN"] == 2
    assert artifact.manifest.sample_counts_by_role["VALIDATION"] == 1
    assert artifact.manifest.sample_counts_by_role["SEALED_TEST"] == 1

    # Role-restricted tables exist and are properly segregated
    train_data = artifact.get_role_data(SampleRole.TRAIN)
    assert len(train_data) == 2
    assert set(train_data["sample_id"]) == {"sample_000", "sample_001"}

    val_data = artifact.get_role_data(SampleRole.VALIDATION)
    assert len(val_data) == 1
    assert list(val_data["sample_id"]) == ["sample_002"]

    sealed_data = artifact.get_role_data(SampleRole.SEALED_TEST)
    assert len(sealed_data) == 1
    assert list(sealed_data["sample_id"]) == ["sample_003"]


def test_train_01_contract_1() -> None:
    """TRAIN-01-AC1: Duplicate sample join ditolak."""
    features_df, labels_df, split_manifest, feat_sha, label_sha = _build_test_data()

    # Introduce duplicate sample_id in features
    dup_row = features_df.iloc[[0]].copy()
    corrupt_features_df = pd.concat([features_df, dup_row], ignore_index=True)
    new_feat_sha = hashlib.sha256(corrupt_features_df.to_parquet()).hexdigest()

    with pytest.raises(DuplicateSampleError) as exc_info:
        materialize_training_dataset(
            features_df=corrupt_features_df,
            labels_df=labels_df,
            split_manifest=split_manifest,
            features_checksum=new_feat_sha,
            labels_checksum=label_sha,
            target_column="net_return",
            inference_feature_columns=["ret_12", "rsi_14"],
            dataset_snapshot_id="snapshot_btc_2024",
            feature_registry_version="1.0.0",
            cost_schedule_id="cost_schedule_v1",
        )
    assert "DUPLICATE_SAMPLE_ID_DETECTED" in str(exc_info.value)


def test_train_01_contract_2() -> None:
    """TRAIN-01-AC2: Target kolom tidak boleh berada dalam inference feature list."""
    features_df, labels_df, split_manifest, feat_sha, label_sha = _build_test_data()

    # Attempting to include net_return (the target) into inference features
    with pytest.raises(TargetLeakageError) as exc_info:
        materialize_training_dataset(
            features_df=features_df,
            labels_df=labels_df,
            split_manifest=split_manifest,
            features_checksum=feat_sha,
            labels_checksum=label_sha,
            target_column="net_return",
            inference_feature_columns=["ret_12", "rsi_14", "net_return"],  # TARGET LEAKAGE!
            dataset_snapshot_id="snapshot_btc_2024",
            feature_registry_version="1.0.0",
            cost_schedule_id="cost_schedule_v1",
        )
    assert "TARGET_COLUMN_IN_FEATURE_LIST" in str(exc_info.value)


def test_train_01_contract_3() -> None:
    """TRAIN-01-AC3: Checksum atau availability mismatch memblokir output."""
    features_df, labels_df, split_manifest, feat_sha, label_sha = _build_test_data()

    # 1. Checksum mismatch
    with pytest.raises(ArtifactIntegrityError) as exc_info_chk:
        materialize_training_dataset(
            features_df=features_df,
            labels_df=labels_df,
            split_manifest=split_manifest,
            features_checksum="fabricated_wrong_checksum_12345",
            labels_checksum=label_sha,
            target_column="net_return",
            inference_feature_columns=["ret_12", "rsi_14"],
            dataset_snapshot_id="snapshot_btc_2024",
            feature_registry_version="1.0.0",
            cost_schedule_id="cost_schedule_v1",
        )
    assert "CHECKSUM_MISMATCH" in str(exc_info_chk.value)

    # 2. Availability mismatch: row_ready_at > decision_ts
    future_features_df = features_df.copy()
    future_features_df.loc[0, "row_ready_at"] = future_features_df.loc[0, "decision_ts"] + timedelta(hours=2)
    fut_feat_sha = hashlib.sha256(future_features_df.to_parquet()).hexdigest()

    with pytest.raises(AvailabilityMismatchError) as exc_info_avail:
        materialize_training_dataset(
            features_df=future_features_df,
            labels_df=labels_df,
            split_manifest=split_manifest,
            features_checksum=fut_feat_sha,
            labels_checksum=label_sha,
            target_column="net_return",
            inference_feature_columns=["ret_12", "rsi_14"],
            dataset_snapshot_id="snapshot_btc_2024",
            feature_registry_version="1.0.0",
            cost_schedule_id="cost_schedule_v1",
        )
    assert "AVAILABILITY_MISMATCH" in str(exc_info_avail.value)


def _temporal_inputs():
    features, labels, manifest, _, _ = _build_test_data()
    return features, labels, manifest


def _assemble_temporal(features, labels, manifest):
    return materialize_training_dataset(
        features, labels, manifest, "net_return", ["ret_12", "rsi_14"],
        "snapshot", "1", "cost",
    )


def test_training_preserves_label_availability():
    features, labels, manifest = _temporal_inputs()
    artifact = _assemble_temporal(features, labels, manifest)
    assert "label_available_at" in artifact.data.columns
    assert artifact.data["label_available_at"].tolist() == labels["label_available_at"].tolist()


def test_training_rejects_label_received_after_declared_cutoff():
    features, labels, manifest = _temporal_inputs()
    labels.loc[0, "label_available_at"] = datetime(2024, 5, 2, tzinfo=UTC)
    with pytest.raises(AvailabilityMismatchError):
        _assemble_temporal(features, labels, manifest)


@pytest.mark.parametrize("column", ["row_ready_at", "decision_ts"])
def test_training_rejects_missing_feature_temporal_evidence(column):
    features, labels, manifest = _temporal_inputs()
    with pytest.raises(AvailabilityMismatchError):
        _assemble_temporal(features.drop(columns=column), labels, manifest)


def test_training_rejects_missing_label_availability():
    features, labels, manifest = _temporal_inputs()
    with pytest.raises(AvailabilityMismatchError):
        _assemble_temporal(features, labels.drop(columns="label_available_at"), manifest)


@pytest.mark.parametrize("column,value", [
    ("pair", "eth_idr"), ("decision_ts", datetime(2024, 1, 2, tzinfo=UTC)),
])
def test_training_rejects_identity_disagreement(column, value):
    features, labels, manifest = _temporal_inputs()
    labels.loc[0, column] = value
    with pytest.raises(ArtifactIntegrityError):
        _assemble_temporal(features, labels, manifest)


def test_training_cannot_accept_unknown_fold_cutoff():
    features, labels, manifest, _, _ = _build_test_data()
    manifest = manifest.model_copy(update={"assignments": {
        key: assignment.model_copy(update={"fold_start_ts": None, "fold_end_ts": None})
        for key, assignment in manifest.assignments.items()
    }})
    with pytest.raises(AvailabilityMismatchError):
        _assemble_temporal(features, labels, manifest)


def test_generated_fold_cutoffs_exclude_delayed_labels_from_training():
    features, labels, _ = _temporal_inputs()
    labels.loc[1, "label_available_at"] = datetime(2024, 3, 2, tzinfo=UTC)
    policy = SplitPolicy(policy_id="chronological", version="2", folds=[
        FoldWindow(role=SampleRole.TRAIN, start_ts=datetime(2024, 1, 1, tzinfo=UTC),
                   end_ts=datetime(2024, 3, 1, tzinfo=UTC)),
        FoldWindow(role=SampleRole.VALIDATION, start_ts=datetime(2024, 3, 1, tzinfo=UTC),
                   end_ts=datetime(2024, 3, 31, tzinfo=UTC)),
        FoldWindow(role=SampleRole.SEALED_TEST, start_ts=datetime(2024, 3, 31, tzinfo=UTC),
                   end_ts=datetime(2024, 5, 1, tzinfo=UTC)),
    ])
    records = [SampleRecord(**row) for row in labels[
        ["sample_id", "pair", "decision_ts", "label_end_ts", "label_available_at"]
    ].to_dict("records")]
    manifest = assign_folds(records, policy)
    artifact = _assemble_temporal(features, labels, manifest)
    assert artifact.get_role_data("TRAIN")["sample_id"].tolist() == ["sample_000"]
    assert artifact.get_role_data("PURGED")["sample_id"].tolist() == ["sample_001"]
    assert artifact.get_role_data("VALIDATION")["sample_id"].tolist() == ["sample_002"]
    assert artifact.get_role_data("SEALED_TEST")["sample_id"].tolist() == ["sample_003"]


@pytest.mark.parametrize("change", ["label", "feature", "cost", "order", "role", "policy"])
def test_training_identity_binds_logical_content(change):
    features, labels, manifest = _temporal_inputs()
    original = _assemble_temporal(features, labels, manifest)
    kwargs = {}
    if change == "label":
        labels.loc[0, "net_return"] += .01
    elif change == "feature":
        features.loc[0, "ret_12"] += .01
    elif change == "cost":
        kwargs["cost_schedule_id"] = "other_cost"
    elif change == "order":
        kwargs["inference_feature_columns"] = ["rsi_14", "ret_12"]
    elif change == "policy":
        manifest = manifest.model_copy(update={"policy_version": "3"})
    else:
        assignments = dict(manifest.assignments)
        assignments["sample_000"] = assignments["sample_000"].model_copy(update={"role": SampleRole.EXCLUDED})
        manifest = manifest.model_copy(update={"assignments": assignments, "train_count": 1})
    args = dict(target_column="net_return", inference_feature_columns=["ret_12", "rsi_14"],
                dataset_snapshot_id="snapshot", feature_registry_version="1", cost_schedule_id="cost")
    args.update(kwargs)
    changed = materialize_training_dataset(features, labels, manifest, **args)
    assert original.manifest.dataset_id != changed.manifest.dataset_id


def test_training_identity_deterministic_for_reordered_rows_and_has_digests():
    features, labels, manifest = _temporal_inputs()
    a = _assemble_temporal(features, labels, manifest)
    b = _assemble_temporal(features.iloc[::-1], labels.iloc[::-1], manifest)
    assert a.manifest.dataset_id == b.manifest.dataset_id
    assert a.manifest.features_content_sha256
    assert a.manifest.labels_content_sha256


def test_legacy_split_without_policy_evidence_requires_rebuild():
    _, _, manifest = _temporal_inputs()
    legacy = manifest.model_dump()
    legacy.pop("policy_content_sha256", None)
    with pytest.raises(ValueError, match="policy_content_sha256"):
        SplitManifest.model_validate(legacy)


@pytest.mark.parametrize("defect", ["null_id", "missing_id", "infinite", "missing_feature", "duplicate_feature", "counts"])
def test_training_rejects_invalid_identity_or_inference_contract(defect):
    features, labels, manifest = _temporal_inputs()
    if defect == "null_id":
        features.loc[0, "sample_id"] = labels.loc[0, "sample_id"] = None
    elif defect == "missing_id":
        features = features.drop(columns="sample_id")
    elif defect == "infinite":
        features.loc[0, "ret_12"] = float("inf")
    elif defect == "missing_feature":
        features = features.drop(columns="ret_12")
    elif defect == "duplicate_feature":
        features = pd.concat([features, features[["ret_12"]]], axis=1)
    else:
        manifest = manifest.model_copy(update={"train_count": 999})
    with pytest.raises(ArtifactIntegrityError):
        _assemble_temporal(features, labels, manifest)
