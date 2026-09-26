"""Regression tests for TRAIN-01 checksum binding (CLI layer).

Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from indodax_lab.cli.build_training_dataset import _parquet_sha256, main
from indodax_lab.labels.materializer import (
    ArtifactIntegrityError,
    materialize_training_dataset,
)
from indodax_lab.labels.splits import FoldAssignment, SampleRole, SplitManifest


# Skip all tests in this module if pyarrow/fastparquet is not available
parquet = pytest.importorskip(
    "pyarrow",
    reason="pyarrow/fastparquet required for parquet-based checksum tests",
)


def _make_test_data(tmp_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, SplitManifest]:
    """Minimal test data matching the materializer expectations."""
    features_df = pd.DataFrame({
        "sample_id": ["sample_000", "sample_001", "sample_002", "sample_003"],
        "decision_ts": pd.to_datetime([
            "2024-01-15", "2024-02-15", "2024-03-10", "2024-04-05"
        ], utc=True),
        "pair": ["btc_idr"] * 4,
        "ret_12": [0.01, -0.02, 0.03, 0.015],
        "rsi_14": [55.0, 42.0, 68.0, 50.0],
        "eligible": [True, True, True, True],
        "row_ready_at": pd.to_datetime([
            "2024-01-15", "2024-02-15", "2024-03-10", "2024-04-05"
        ], utc=True),
    })

    labels_df = pd.DataFrame({
        "sample_id": ["sample_000", "sample_001", "sample_002", "sample_003"],
        "decision_ts": pd.to_datetime([
            "2024-01-15", "2024-02-15", "2024-03-10", "2024-04-05"
        ], utc=True),
        "pair": ["btc_idr"] * 4,
        "label_end_ts": pd.to_datetime([
            "2024-01-16", "2024-02-16", "2024-03-11", "2024-04-06"
        ], utc=True),
        "net_return": [0.02, -0.01, 0.04, 0.005],
        "binary_label": [1, 0, 1, 1],
        "label_available_at": pd.to_datetime([
            "2024-01-16", "2024-02-16", "2024-03-11", "2024-04-06"
        ], utc=True),
    })

    # Split manifest
    assignments = {
        "sample_000": FoldAssignment(
            sample_id="sample_000",
            role=SampleRole.TRAIN,
            fold_role=SampleRole.TRAIN,
            purge_reason=None,
            fold_start_ts=pd.Timestamp("2024-01-01", tz="UTC"),
            fold_end_ts=pd.Timestamp("2024-03-01", tz="UTC"),
        ),
        "sample_001": FoldAssignment(
            sample_id="sample_001",
            role=SampleRole.TRAIN,
            fold_role=SampleRole.TRAIN,
            purge_reason=None,
            fold_start_ts=pd.Timestamp("2024-01-01", tz="UTC"),
            fold_end_ts=pd.Timestamp("2024-03-01", tz="UTC"),
        ),
        "sample_002": FoldAssignment(
            sample_id="sample_002",
            role=SampleRole.VALIDATION,
            fold_role=SampleRole.VALIDATION,
            purge_reason=None,
            fold_start_ts=pd.Timestamp("2024-03-01", tz="UTC"),
            fold_end_ts=pd.Timestamp("2024-03-31", tz="UTC"),
        ),
        "sample_003": FoldAssignment(
            sample_id="sample_003",
            role=SampleRole.SEALED_TEST,
            fold_role=SampleRole.SEALED_TEST,
            purge_reason=None,
            fold_start_ts=pd.Timestamp("2024-03-31", tz="UTC"),
            fold_end_ts=pd.Timestamp("2024-05-01", tz="UTC"),
        ),
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
        policy_content_sha256="a" * 64,
    )

    return features_df, labels_df, split_manifest


def test_parquet_sha256_is_deterministic() -> None:
    """_parquet_sha256 produces the same hash for identical data."""
    df = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]})
    h1 = _parquet_sha256(df)
    h2 = _parquet_sha256(df)
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex


def test_parquet_sha256_changes_on_data_change() -> None:
    """_parquet_sha256 changes when data changes."""
    df1 = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]})
    df2 = pd.DataFrame({"a": [1, 2], "b": [3.0, 5.0]})
    assert _parquet_sha256(df1) != _parquet_sha256(df2)


def test_cli_passes_checksums_to_materializer(tmp_path: Path) -> None:
    """TRAIN-01: CLI computes and passes features/labels checksums to materializer."""
    features_df, labels_df, split_manifest = _make_test_data(tmp_path)

    features_path = tmp_path / "features.parquet"
    labels_path = tmp_path / "labels.parquet"
    splits_path = tmp_path / "splits.json"
    output_path = tmp_path / "dataset.parquet"

    features_df.to_parquet(features_path)
    labels_df.to_parquet(labels_path)
    splits_path.write_text(split_manifest.model_dump_json(), encoding="utf-8")

    # Run CLI with dry-run
    rc = main([
        "--features", str(features_path),
        "--labels", str(labels_path),
        "--splits", str(splits_path),
        "--target-column", "net_return",
        "--inference-features", "ret_12", "rsi_14",
        "--dataset-snapshot-id", "snap_001",
        "--feature-registry-version", "1.0.0",
        "--cost-schedule-id", "indodax_idr_v1",
        "--output", str(output_path),
        "--dry-run",
    ])
    assert rc == 0


def test_checksum_mismatch_rejected(tmp_path: Path) -> None:
    """Wrong checksum passed to materializer raises ArtifactIntegrityError."""
    features_df, labels_df, split_manifest = _make_test_data(tmp_path)

    # Compute correct checksums
    correct_feat = _parquet_sha256(features_df)
    correct_label = _parquet_sha256(labels_df)

    # Pass wrong checksums
    from indodax_lab.labels.materializer import ArtifactIntegrityError
    with pytest.raises(ArtifactIntegrityError, match="CHECKSUM_MISMATCH:features"):
        materialize_training_dataset(
            features_df=features_df,
            labels_df=labels_df,
            split_manifest=split_manifest,
            target_column="net_return",
            inference_feature_columns=["ret_12", "rsi_14"],
            dataset_snapshot_id="snap_001",
            feature_registry_version="1.0.0",
            cost_schedule_id="indodax_idr_v1",
            features_checksum="wrong_checksum",
            labels_checksum=correct_label,
        )

    with pytest.raises(ArtifactIntegrityError, match="CHECKSUM_MISMATCH:labels"):
        materialize_training_dataset(
            features_df=features_df,
            labels_df=labels_df,
            split_manifest=split_manifest,
            target_column="net_return",
            inference_feature_columns=["ret_12", "rsi_14"],
            dataset_snapshot_id="snap_001",
            feature_registry_version="1.0.0",
            cost_schedule_id="indodax_idr_v1",
            features_checksum=correct_feat,
            labels_checksum="wrong_checksum",
        )


def test_dataset_id_changes_when_features_change(tmp_path: Path) -> None:
    """Content-addressed dataset_id changes when features change."""
    features_df, labels_df, split_manifest = _make_test_data(tmp_path)

    # Original dataset
    artifact1 = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v1",
        features_checksum=_parquet_sha256(features_df),
        labels_checksum=_parquet_sha256(labels_df),
    )

    # Modify features
    features_df2 = features_df.copy()
    features_df2.loc[0, "ret_12"] = 999.0

    artifact2 = materialize_training_dataset(
        features_df=features_df2,
        labels_df=labels_df,
        split_manifest=split_manifest,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v1",
        features_checksum=_parquet_sha256(features_df2),
        labels_checksum=_parquet_sha256(labels_df),
    )

    assert artifact1.manifest.dataset_id != artifact2.manifest.dataset_id
    assert artifact1.manifest.features_content_sha256 != artifact2.manifest.features_content_sha256
    assert artifact1.manifest.labels_content_sha256 == artifact2.manifest.labels_content_sha256


def test_dataset_id_changes_when_labels_change(tmp_path: Path) -> None:
    """Content-addressed dataset_id changes when labels change."""
    features_df, labels_df, split_manifest = _make_test_data(tmp_path)

    artifact1 = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v1",
        features_checksum=_parquet_sha256(features_df),
        labels_checksum=_parquet_sha256(labels_df),
    )

    labels_df2 = labels_df.copy()
    labels_df2.loc[0, "net_return"] = 999.0

    artifact2 = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df2,
        split_manifest=split_manifest,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v1",
        features_checksum=_parquet_sha256(features_df),
        labels_checksum=_parquet_sha256(labels_df2),
    )

    assert artifact1.manifest.dataset_id != artifact2.manifest.dataset_id
    assert artifact1.manifest.labels_content_sha256 != artifact2.manifest.labels_content_sha256
    assert artifact1.manifest.features_content_sha256 == artifact2.manifest.features_content_sha256


def test_dataset_id_changes_when_split_policy_changes(tmp_path: Path) -> None:
    """Content-addressed dataset_id changes when split policy changes."""
    features_df, labels_df, split_manifest = _make_test_data(tmp_path)

    artifact1 = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v1",
        features_checksum=_parquet_sha256(features_df),
        labels_checksum=_parquet_sha256(labels_df),
    )

    # Change split policy
    split_manifest2 = split_manifest.model_copy(update={"policy_id": "annual_v2"})

    artifact2 = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest2,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v1",
        features_checksum=_parquet_sha256(features_df),
        labels_checksum=_parquet_sha256(labels_df),
    )

    assert artifact1.manifest.dataset_id != artifact2.manifest.dataset_id
    assert artifact1.manifest.split_content_sha256 != artifact2.manifest.split_content_sha256


def test_dataset_id_changes_when_cost_schedule_changes(tmp_path: Path) -> None:
    """Content-addressed dataset_id changes when cost schedule changes."""
    features_df, labels_df, split_manifest = _make_test_data(tmp_path)

    artifact1 = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v1",
        features_checksum=_parquet_sha256(features_df),
        labels_checksum=_parquet_sha256(labels_df),
    )

    artifact2 = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest,
        target_column="net_return",
        inference_feature_columns=["ret_12", "rsi_14"],
        dataset_snapshot_id="snap_001",
        feature_registry_version="1.0.0",
        cost_schedule_id="indodax_idr_v2",  # Different cost
        features_checksum=_parquet_sha256(features_df),
        labels_checksum=_parquet_sha256(labels_df),
    )

    assert artifact1.manifest.dataset_id != artifact2.manifest.dataset_id


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:cacheprovider"])