"""Behavioral tests for content-addressed dataset manifests."""

from __future__ import annotations

from indodax_lab.data.manifest import build_dataset_manifest, canonical_json_bytes


def test_manifest_id_is_stable_for_equivalent_partition_ordering():
    """Removing canonical ordering would make a snapshot depend on caller order."""
    first = {
        "path": "bronze/pair=btc_idr/part-a.parquet",
        "sha256": "a" * 64,
        "size_bytes": 101,
        "row_count": 1,
        "schema_identity": "sha256:schema",
    }
    second = {
        "path": "bronze/pair=eth_idr/part-b.parquet",
        "sha256": "b" * 64,
        "size_bytes": 202,
        "row_count": 2,
        "schema_identity": "sha256:schema",
    }

    forward = build_dataset_manifest([first, second])
    reverse = build_dataset_manifest([second, first])

    assert forward == reverse
    assert forward["dataset_snapshot_id"].startswith("sha256:")
    assert canonical_json_bytes(forward) == canonical_json_bytes(reverse)


def test_manifest_id_changes_when_a_partition_checksum_changes():
    """Ignoring content checksums would permit source changes under one snapshot ID."""
    partition = {
        "path": "bronze/pair=btc_idr/part-a.parquet",
        "sha256": "a" * 64,
        "size_bytes": 101,
        "row_count": 1,
        "schema_identity": "sha256:schema",
    }

    original = build_dataset_manifest([partition])
    changed = build_dataset_manifest([{**partition, "sha256": "b" * 64}])

    assert changed["dataset_snapshot_id"] != original["dataset_snapshot_id"]
