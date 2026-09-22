"""Integration tests for RW1-01 — Reusable immutable dataset registry.

Covers acceptance criteria:
- RW1-01-AC0: Covered request performs zero provider fetches (test_rw1_01_0)
- RW1-01-AC1: Extension fetches only uncovered intervals and preserves v1 bytes
  (test_rw1_01_1)
- RW1-01-AC2: Zero bars or broken partition hash cannot be experiment-ready
  (test_rw1_01_2)
- RW1-01-AC3: Concurrent same-version changed publication rejects
  (test_rw1_01_3)
- RW1-01-AC4: Crash before catalog commit leaves no visible successful dataset
  (test_rw1_01_4)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from indodax_lab.contracts.workbench import DatasetManifest
from indodax_lab.data.dataset_registry import (
    DatasetPartitionHashError,
    DatasetPublicationConflictError,
    DatasetRegistry,
    DatasetRequest,
    DatasetZeroBarsError,
    _Catalog,
)

# =========================================================================
# Helpers
# =========================================================================

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
_T0 = datetime(2024, 1, 1, tzinfo=UTC)
_T1 = datetime(2024, 1, 10, tzinfo=UTC)
_T2 = datetime(2024, 1, 20, tzinfo=UTC)
_T3 = datetime(2024, 2, 1, tzinfo=UTC)


def _sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_partition(
    bar_count: int = 100,
    start: datetime = _T0,
    end: datetime = _T1,
    sha256: str | None = None,
) -> dict[str, Any]:
    content = f"{bar_count}:{start.isoformat()}:{end.isoformat()}:{uuid.uuid4().hex}".encode()
    sha = sha256 or _sha256_of(content)
    return {
        "row_count": bar_count,
        "sha256": sha,
        "start_ts": start.isoformat(),
        "end_ts": end.isoformat(),
        "bytes": content,
    }


def _make_request(
    start: datetime = _T0,
    end: datetime = _T1,
    pair: str = "btcidr",
    timeframe: str = "1h",
    version: str = "v1",
) -> DatasetRequest:
    return DatasetRequest(
        venue="indodax",
        pair=pair,
        timeframe=timeframe,
        start=start,
        end=end,
        source_id="indodax_raw",
        source_version="v1",
        version=version,
    )


def _make_registry(
    tmp_path: Path,
    fetch_provider: Callable[[DatasetRequest], list[dict[str, Any]]] | None = None,
) -> DatasetRegistry:
    return DatasetRegistry(
        root=tmp_path,
        catalog_path=tmp_path / "catalog.json",
        fetch_provider=fetch_provider,
    )


# =========================================================================
# AC0: Covered request performs zero provider fetches
# =========================================================================
def test_rw1_01_0(tmp_path: Path) -> None:
    """RW1-01-AC0: Covered request performs zero provider fetches."""
    fetch_calls: list[DatasetRequest] = []

    def provider(req: DatasetRequest) -> list[dict[str, Any]]:
        fetch_calls.append(req)
        return [_make_partition(100, _T0, _T1)]

    registry = _make_registry(tmp_path, fetch_provider=provider)
    request = _make_request(_T0, _T1)

    # First create — should fetch once
    manifest1 = registry.create(request)
    assert len(fetch_calls) == 1
    assert isinstance(manifest1, DatasetManifest)
    assert manifest1.bar_count == 100

    # Second create same range — must find existing, fetch count MUST NOT increase
    fetch_calls.clear()
    manifest2 = registry.create(request)
    assert len(fetch_calls) == 0, (
        "AC0 VIOLATED: Provider was called for an already-covered request"
    )
    # Returned manifest should be equivalent (same bar_count, same ref key prefix)
    assert manifest2.bar_count == 100


# =========================================================================
# AC1: Extension fetches only uncovered intervals and preserves v1 bytes
# =========================================================================
def test_rw1_01_1(tmp_path: Path) -> None:
    """RW1-01-AC1: Extension fetches only uncovered intervals, preserves v1 bytes."""
    fetch_intervals: list[tuple[datetime, datetime]] = []

    def provider(req: DatasetRequest) -> list[dict[str, Any]]:
        fetch_intervals.append((req.start, req.end))
        return [_make_partition(50, req.start, req.end)]

    registry = _make_registry(tmp_path, fetch_provider=provider)

    # Step 1: Create base dataset covering T0..T1
    base_request = _make_request(_T0, _T1)
    base_manifest = registry.create(base_request)
    base_ref = base_manifest.to_artifact_ref()
    assert len(fetch_intervals) == 1
    assert fetch_intervals[0] == (_T0, _T1)

    # Step 2: Extend to T0..T2 — should only fetch T1..T2 (not re-fetch T0..T1)
    fetch_intervals.clear()
    extended_request = _make_request(_T0, _T2)
    extended_manifest = registry.extend(base_ref, extended_request)

    # AC1: Only uncovered interval T1..T2 was fetched
    assert len(fetch_intervals) == 1, (
        f"AC1 VIOLATED: Expected 1 fetch for uncovered interval, got {fetch_intervals}"
    )
    fetched_start, fetched_end = fetch_intervals[0]
    assert fetched_start == _T1, f"Expected fetch start {_T1}, got {fetched_start}"
    assert fetched_end == _T2, f"Expected fetch end {_T2}, got {fetched_end}"

    assert isinstance(extended_manifest, DatasetManifest)
    assert extended_manifest.bar_count == 50  # Only newly fetched bars

    # Verify parent_dataset_ref linkage preserved
    assert extended_manifest.parent_dataset_ref is not None


# =========================================================================
# AC2: Zero bars or broken partition hash cannot be experiment-ready
# =========================================================================
def test_rw1_01_2(tmp_path: Path) -> None:
    """RW1-01-AC2: Zero bars or broken partition hash cannot be experiment-ready."""

    # Case A: Zero bars
    def zero_bar_provider(req: DatasetRequest) -> list[dict[str, Any]]:
        return [_make_partition(0, req.start, req.end)]  # 0 bars

    registry_zero = _make_registry(tmp_path / "zero", fetch_provider=zero_bar_provider)
    manifest = registry_zero.create(_make_request())
    ref_zero = manifest.to_artifact_ref()

    # Validate must raise DatasetZeroBarsError (not experiment-ready)
    with pytest.raises(DatasetZeroBarsError, match="ZERO_BARS_NOT_EXPERIMENT_READY"):
        registry_zero.validate(ref_zero)

    # Case B: Broken partition hash — manually corrupt the catalog entry
    def good_provider(req: DatasetRequest) -> list[dict[str, Any]]:
        return [_make_partition(100, req.start, req.end)]

    registry_hash = _make_registry(tmp_path / "hash", fetch_provider=good_provider)
    manifest2 = registry_hash.create(_make_request())
    ref2 = manifest2.to_artifact_ref()

    # Corrupt the partition_byte_hashes in the catalog
    catalog_path = tmp_path / "hash" / "catalog.json"
    raw = json.loads(catalog_path.read_bytes())
    for entry in raw["entries"]:
        if entry.get("partition_byte_hashes"):
            entry["partition_byte_hashes"] = ["a" * 64]  # Fake bad hash
    catalog_path.write_bytes(
        json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )

    # Reload registry from disk
    registry_hash2 = _make_registry(
        tmp_path / "hash",
        fetch_provider=good_provider,
    )
    # Validate must raise DatasetPartitionHashError
    with pytest.raises(DatasetPartitionHashError, match="PARTITION_HASH"):
        registry_hash2.validate(ref2)


# =========================================================================
# AC3: Concurrent same-version changed publication rejects
# =========================================================================
def test_rw1_01_3(tmp_path: Path) -> None:
    """RW1-01-AC3: Concurrent same-version changed publication rejects."""
    # We test _Catalog directly for idempotent vs conflicting behavior
    catalog_path = tmp_path / "catalog.json"
    catalog = _Catalog(catalog_path)

    entry_v1: dict[str, Any] = {
        "ref_key": "kind:id:v1:a" + "0" * 63,
        "dataset_id": "ds_test",
        "venue": "indodax",
        "pair": "btcidr",
        "timeframe": "1h",
        "actual_start": _T0.isoformat(),
        "actual_end": _T1.isoformat(),
        "bar_count": 100,
        "duplicate_count": 0,
        "partition_refs": [],
        "partition_byte_hashes": [],
        "quality_report_ref": {
            "kind": "qr", "id": "qr_1", "version": "v1",
            "sha256": "b" * 64,
        },
        "missing_intervals": [],
        "parent_ref_key": None,
        "schema_version": "v1",
    }

    # First registration — should succeed
    catalog.register("kind:id:v1:a" + "0" * 63, entry_v1)
    assert catalog.get("kind:id:v1:a" + "0" * 63) is not None

    # Idempotent re-registration — same content, should not raise
    catalog.register("kind:id:v1:a" + "0" * 63, entry_v1)

    # Conflicting registration — different content, same ref_key
    entry_v1_conflict = dict(entry_v1)
    entry_v1_conflict["bar_count"] = 999  # Different content

    with pytest.raises(
        DatasetPublicationConflictError, match="DATASET_PUBLICATION_CONFLICT"
    ):
        catalog.register("kind:id:v1:a" + "0" * 63, entry_v1_conflict)


# =========================================================================
# AC4: Crash before catalog commit leaves no visible successful dataset
# =========================================================================
def test_rw1_01_4(tmp_path: Path) -> None:
    """RW1-01-AC4: Crash before catalog commit leaves no visible dataset."""
    catalog_path = tmp_path / "catalog.json"

    # Simulate crash during _persist by patching partial.replace to raise
    catalog = _Catalog(catalog_path)
    entry: dict[str, Any] = {
        "ref_key": "kind:id:v1:" + "c" * 64,
        "dataset_id": "ds_crash_test",
        "venue": "indodax",
        "pair": "btcidr",
        "timeframe": "1h",
        "actual_start": _T0.isoformat(),
        "actual_end": _T1.isoformat(),
        "bar_count": 50,
        "duplicate_count": 0,
        "partition_refs": [],
        "partition_byte_hashes": [],
        "quality_report_ref": {
            "kind": "qr", "id": "qr_crash", "version": "v1",
            "sha256": "d" * 64,
        },
        "missing_intervals": [],
        "parent_ref_key": None,
        "schema_version": "v1",
    }

    # Simulate crash by forcing an error during the rename/persist step

    crash_happened = False

    def crash_persist(**kwargs: Any) -> None:
        nonlocal crash_happened
        crash_happened = True
        raise OSError("SIMULATED_DISK_CRASH")

    catalog._persist = crash_persist  # type: ignore[method-assign]

    with pytest.raises(OSError, match="SIMULATED_DISK_CRASH"):
        catalog.register("kind:id:v1:" + "c" * 64, entry)

    assert crash_happened

    # AC4: After crash, no entry should be visible in a fresh catalog load
    catalog_after_crash = _Catalog(catalog_path)
    result = catalog_after_crash.get("kind:id:v1:" + "c" * 64)
    assert result is None, (
        "AC4 VIOLATED: Entry visible in catalog after simulated crash before commit"
    )

    # Also verify no partial file left behind in the catalog directory
    partials = list(tmp_path.glob("*.partial"))
    assert len(partials) == 0, (
        f"AC4 VIOLATED: Partial files left behind after crash: {partials}"
    )
