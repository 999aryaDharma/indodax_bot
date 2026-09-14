"""Canonical, content-addressed manifests for immutable datasets."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .checksums import sha256_bytes

MANIFEST_VERSION = "1.0.0"
DATASET_NAME = "bronze_candles_v1"


class ImmutableContentConflictError(RuntimeError):
    """A content-addressed destination exists but does not contain the claimed bytes."""


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize a manifest reproducibly, excluding whitespace and key-order variation."""
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return serialized.encode("utf-8")


def canonical_manifest_bytes_without_id(manifest: Mapping[str, Any]) -> bytes:
    """Return the exact bytes used to derive a dataset snapshot ID."""
    without_id = {key: value for key, value in manifest.items() if key != "dataset_snapshot_id"}
    return canonical_json_bytes(without_id)


def dataset_snapshot_id(manifest: Mapping[str, Any]) -> str:
    """Return the content-addressed ID of a canonical manifest."""
    return f"sha256:{sha256_bytes(canonical_manifest_bytes_without_id(manifest))}"


def build_dataset_manifest(partitions: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a deterministic manifest from relative partition audit records only."""
    ordered_partitions = sorted(
        (dict(partition) for partition in partitions), key=lambda partition: str(partition["path"])
    )
    schema_identities = {str(partition["schema_identity"]) for partition in ordered_partitions}
    if len(schema_identities) != 1:
        raise ValueError("all manifest partitions must have one schema identity")
    manifest: dict[str, Any] = {
        "dataset": DATASET_NAME,
        "manifest_version": MANIFEST_VERSION,
        "partitions": ordered_partitions,
        "row_count": sum(int(partition["row_count"]) for partition in ordered_partitions),
        "schema_identity": schema_identities.pop(),
    }
    manifest["dataset_snapshot_id"] = dataset_snapshot_id(manifest)
    return manifest


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Reject a manifest whose claimed ID is not derived from its own immutable content."""
    expected = dataset_snapshot_id(manifest)
    if manifest.get("dataset_snapshot_id") != expected:
        raise ValueError("manifest dataset_snapshot_id does not match canonical content")


def read_manifest(path: Path) -> dict[str, Any]:
    """Read and validate a manifest already published by the store."""
    with path.open("rb") as source:
        manifest = json.load(source)
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    validate_manifest(manifest)
    return manifest
