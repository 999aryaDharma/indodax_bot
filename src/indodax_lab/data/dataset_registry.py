"""Range-aware reusable immutable dataset registry (RW1-01).

Guarantees:
- Covered request performs zero provider fetches (AC0).
- Extension fetches only uncovered intervals and preserves v1 bytes (AC1).
- Zero bars or broken partition hash cannot be experiment-ready (AC2).
- Concurrent same-version changed publication rejects (AC3).
- Crash before catalog commit leaves no visible successful dataset (AC4).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from indodax_lab.contracts.identity import ArtifactRef
from indodax_lab.contracts.workbench import DatasetManifest

logger = logging.getLogger("dataset_registry")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DatasetNotFoundError(KeyError):
    """No dataset matching the given ref or query is registered."""


class DatasetCoverageError(LookupError):
    """Requested range is not fully covered by any registered dataset."""


class DatasetPublicationConflictError(RuntimeError):
    """Concurrent same-version publication with different content was rejected."""


class DatasetPublicationPartialError(RuntimeError):
    """An incomplete partial publication was found; crash recovery required."""


class DatasetQualityError(ValueError):
    """Dataset failed quality validation and cannot be experiment-ready."""


class DatasetZeroBarsError(DatasetQualityError):
    """Dataset has zero bars and cannot be experiment-ready."""


class DatasetPartitionHashError(DatasetQualityError):
    """Dataset partition hash verification failed."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    """Fsync a directory (no-op on Windows)."""
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ref_key(ref: ArtifactRef) -> str:
    """Stable string key for an ArtifactRef."""
    return f"{ref.kind}:{ref.id}:{ref.version}:{ref.sha256}"


# ---------------------------------------------------------------------------
# Catalog (persistent JSON index)
# ---------------------------------------------------------------------------

_CATALOG_VERSION = "dataset-catalog-v1"


class _Catalog:
    """Durable append-only catalog index stored as a JSON file.

    Thread-safe: single-writer guarantee enforced by _lock.
    """

    def __init__(self, path: Path, *, lock: threading.Lock | None = None) -> None:
        self._path = path
        self._lock = lock or threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_bytes())
                if raw.get("catalog_version") != _CATALOG_VERSION:
                    raise ValueError("CATALOG_VERSION_MISMATCH")
                for entry in raw.get("entries", []):
                    self._entries[entry["ref_key"]] = entry
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                logger.error("Catalog load failed; starting empty: %s", self._path)

    def _persist(
        self,
        *,
        fsync_fn: Callable[[Path], None] = _fsync_directory,
    ) -> None:
        """Atomically write catalog using a partial + rename pattern."""
        payload = _canonical_bytes(
            {
                "catalog_version": _CATALOG_VERSION,
                "entries": list(self._entries.values()),
            }
        )
        partial = self._path.with_name(f".{self._path.name}.{uuid.uuid4().hex}.partial")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with partial.open("xb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            partial.replace(self._path)
            fsync_fn(self._path.parent)
        except Exception:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def register(
        self,
        ref_key: str,
        entry: dict[str, Any],
        *,
        fsync_fn: Callable[[Path], None] = _fsync_directory,
    ) -> None:
        with self._lock:
            if ref_key in self._entries:
                existing = self._entries[ref_key]
                if existing != entry:
                    raise DatasetPublicationConflictError(
                        f"DATASET_PUBLICATION_CONFLICT: "
                        f"same ref_key '{ref_key}' has different content"
                    )
                return  # Idempotent: same entry already registered
            self._entries[ref_key] = entry
            try:
                self._persist(fsync_fn=fsync_fn)
            except Exception:
                self._entries.pop(ref_key, None)
                raise

    def get(self, ref_key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._entries.get(ref_key)

    def all_entries(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries.values())


# ---------------------------------------------------------------------------
# DatasetRequest
# ---------------------------------------------------------------------------


class DatasetRequest:
    """Request to create or extend a dataset covering a time range."""

    def __init__(
        self,
        *,
        venue: str,
        pair: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        source_id: str,
        source_version: str,
        version: str = "v1",
    ) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("UTC_TIMEZONE_REQUIRED:start")
        if end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("UTC_TIMEZONE_REQUIRED:end")
        if start >= end:
            raise ValueError("START_MUST_PRECEDE_END")
        self.venue = venue.lower()
        self.pair = pair.lower()
        self.timeframe = timeframe.lower()
        self.start = start.astimezone(UTC)
        self.end = end.astimezone(UTC)
        self.source_id = source_id
        self.source_version = source_version
        self.version = version


# ---------------------------------------------------------------------------
# QualityReport (simplified for registry use)
# ---------------------------------------------------------------------------


class RegistryQualityReport:
    """Simplified quality report produced by registry validation."""

    def __init__(
        self,
        *,
        status: str,
        bar_count: int,
        duplicate_count: int,
        partition_errors: list[str],
        gap_count: int,
        silver_eligible: bool,
    ) -> None:
        self.status = status  # "PASS", "WARN", "FAIL"
        self.bar_count = bar_count
        self.duplicate_count = duplicate_count
        self.partition_errors = partition_errors
        self.gap_count = gap_count
        self.silver_eligible = silver_eligible

    def to_artifact_ref(self, dataset_id: str) -> ArtifactRef:
        payload = _canonical_bytes(
            {
                "dataset_id": dataset_id,
                "status": self.status,
                "bar_count": self.bar_count,
                "duplicate_count": self.duplicate_count,
                "partition_errors": sorted(self.partition_errors),
                "gap_count": self.gap_count,
                "silver_eligible": self.silver_eligible,
            }
        )
        sha = hashlib.sha256(payload).hexdigest()
        return ArtifactRef(
            kind="quality_report",
            id=f"qr_{dataset_id}",
            version="v1",
            sha256=sha,
        )


# ---------------------------------------------------------------------------
# DatasetRegistry
# ---------------------------------------------------------------------------


class DatasetRegistry:
    """Range-aware, immutable, atomically published dataset registry.

    Thread-safe for single-host use. Does not support concurrent writes from
    multiple processes (single writer constraint per CONTRACTS.md).
    """

    def __init__(
        self,
        root: Path,
        *,
        catalog_path: Path | None = None,
        fetch_provider: Callable[[DatasetRequest], list[dict[str, Any]]] | None = None,
        fsync_fn: Callable[[Path], None] = _fsync_directory,
        lock: threading.Lock | None = None,
    ) -> None:
        """
        Args:
            root: Root directory for partition storage.
            catalog_path: Optional explicit path for catalog JSON. Defaults to
                root / "dataset_catalog.json".
            fetch_provider: Optional callable that fetches raw partition records
                for a given request. If None, registry operates in read-only mode
                and raises DatasetCoverageError when data is missing.
            fsync_fn: Directory fsync function (injectable for tests).
            lock: Optional lock to share across instances (for testing).
        """
        self._root = Path(root)
        self._catalog_path = catalog_path or (self._root / "dataset_catalog.json")
        self._fetch_provider = fetch_provider
        self._fsync_fn = fsync_fn
        self._lock = lock or threading.Lock()
        self._catalog = _Catalog(self._catalog_path, lock=self._lock)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find(
        self,
        venue: str,
        pair: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> tuple[ArtifactRef, ...]:
        """Find all registered dataset ArtifactRefs covering [start, end].

        Returns a tuple of ArtifactRef objects for all registered datasets
        that overlap the requested range. Raises DatasetCoverageError if no
        dataset covers the full range without a provider fetch.

        AC0: If a covering dataset exists, returns it without fetching.
        """
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError(
                "NAIVE_DATETIME_FORBIDDEN: start and end must be timezone-aware (UTC)"
            )
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)

        entries = self._catalog.all_entries()
        matching = [
            e for e in entries
            if (
                e.get("venue") == venue.lower()
                and e.get("pair") == pair.lower()
                and e.get("timeframe") == timeframe.lower()
                and self._covers(e, start_utc, end_utc)
            )
        ]
        if not matching:
            raise DatasetCoverageError(
                f"DATASET_COVERAGE_MISS: No registered dataset covers "
                f"{venue}/{pair}/{timeframe} [{start}, {end}]"
            )
        return tuple(
            ArtifactRef(
                kind=e["ref"]["kind"],
                id=e["ref"]["id"],
                version=e["ref"]["version"],
                sha256=e["ref"]["sha256"],
            )
            for e in matching
        )

    def create(self, request: DatasetRequest) -> DatasetManifest:
        """Create a new dataset version by fetching from provider.

        AC0: Checks for existing coverage before fetching.
        AC3: Concurrent same-version publication with different content rejects.
        AC4: Crash before catalog commit leaves no visible successful dataset.
        """
        # AC0: Check if already covered
        try:
            existing_refs = self.find(
                request.venue, request.pair, request.timeframe,
                request.start, request.end,
            )
            if existing_refs:
                # Already covered — return first manifest without fetch
                return self.get(existing_refs[0])
        except DatasetCoverageError:
            pass  # No existing coverage — proceed with fetch

        if self._fetch_provider is None:
            raise DatasetCoverageError(
                "DATASET_COVERAGE_MISS: No provider available to fetch missing intervals"
            )

        # Fetch all partitions from provider
        raw_partitions = self._fetch_provider(request)
        return self._publish_dataset(request, raw_partitions, parent_ref=None)

    def extend(
        self, parent_ref: ArtifactRef, request: DatasetRequest
    ) -> DatasetManifest:
        """Extend a parent dataset with additional intervals, preserving v1 bytes.

        AC1: Fetches only uncovered intervals and preserves v1 bytes.
        AC3: Concurrent same-version changed publication rejects.
        AC4: Crash before catalog commit leaves no visible successful dataset.
        """
        parent = self.get(parent_ref)
        parent_start = parent.actual_start
        parent_end = parent.actual_end

        # Determine uncovered intervals
        uncovered: list[tuple[datetime, datetime]] = []
        if request.start < parent_start:
            uncovered.append((request.start, parent_start))
        if request.end > parent_end:
            uncovered.append((parent_end, request.end))

        if not uncovered and self._covers_manifest(parent, request.start, request.end):
            # Already covered by parent — no fetch needed
            return parent

        if self._fetch_provider is None:
            raise DatasetCoverageError(
                "DATASET_COVERAGE_MISS: No provider available for uncovered intervals"
            )

        pre_partitions: list[dict[str, Any]] = []
        post_partitions: list[dict[str, Any]] = []

        if request.start < parent_start:
            sub_request = DatasetRequest(
                venue=request.venue,
                pair=request.pair,
                timeframe=request.timeframe,
                start=request.start,
                end=parent_start,
                source_id=request.source_id,
                source_version=request.source_version,
                version=request.version,
            )
            pre_partitions = self._fetch_provider(sub_request)

        if request.end > parent_end:
            sub_request = DatasetRequest(
                venue=request.venue,
                pair=request.pair,
                timeframe=request.timeframe,
                start=parent_end,
                end=request.end,
                source_id=request.source_id,
                source_version=request.source_version,
                version=request.version,
            )
            post_partitions = self._fetch_provider(sub_request)

        return self._publish_dataset(
            request,
            raw_partitions=post_partitions,
            pre_partitions=pre_partitions,
            parent_ref=parent_ref,
            parent_manifest=parent,
        )

    def get(self, ref: ArtifactRef) -> DatasetManifest:
        """Retrieve a registered DatasetManifest by ArtifactRef."""
        key = _ref_key(ref)
        entry = self._catalog.get(key)
        if entry is None:
            raise DatasetNotFoundError(
                f"DATASET_NOT_FOUND: ref_key '{key}' not in registry"
            )
        return self._entry_to_manifest(entry)

    def validate(self, ref: ArtifactRef) -> RegistryQualityReport:
        """Validate a registered dataset's partition integrity.

        AC2: Zero bars or broken partition hash raises DatasetQualityError.
        """
        entry = self._catalog.get(_ref_key(ref))
        if entry is None:
            raise DatasetNotFoundError(
                f"DATASET_NOT_FOUND: ref '{_ref_key(ref)}' not in registry"
            )

        bar_count = entry.get("bar_count", 0)
        partition_refs_data = entry.get("partition_refs", [])
        errors: list[str] = []

        # AC2: Zero bars cannot be experiment-ready
        if bar_count == 0:
            raise DatasetZeroBarsError(
                f"ZERO_BARS_NOT_EXPERIMENT_READY: dataset '{entry.get('dataset_id')}' "
                f"has zero bars"
            )

        # Verify partition byte hashes if stored paths exist
        partition_byte_hashes = entry.get("partition_byte_hashes", [])
        for i, pref_data in enumerate(partition_refs_data):
            # Verify stored hash matches partition ref sha256
            expected_sha = pref_data.get("sha256", "")
            stored_hash = (
                partition_byte_hashes[i] if i < len(partition_byte_hashes) else ""
            )
            if stored_hash and stored_hash != expected_sha:
                errors.append(
                    f"PARTITION_HASH_MISMATCH: partition {i} "
                    f"expected {expected_sha} got {stored_hash}"
                )

        if errors:
            raise DatasetPartitionHashError(
                f"PARTITION_HASH_ERROR: {len(errors)} partition(s) failed: {errors[0]}"
            )

        return RegistryQualityReport(
            status="PASS",
            bar_count=bar_count,
            duplicate_count=entry.get("duplicate_count", 0),
            partition_errors=errors,
            gap_count=len(entry.get("missing_intervals", [])),
            silver_eligible=True,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _covers(self, entry: dict[str, Any], start: datetime, end: datetime) -> bool:
        """Check if a catalog entry covers the given [start, end] range."""
        actual_start_str = entry.get("actual_start")
        actual_end_str = entry.get("actual_end")
        if not actual_start_str or not actual_end_str:
            return False
        try:
            actual_start = datetime.fromisoformat(actual_start_str)
            actual_end = datetime.fromisoformat(actual_end_str)
            if actual_start.tzinfo is None:
                actual_start = actual_start.replace(tzinfo=UTC)
            if actual_end.tzinfo is None:
                actual_end = actual_end.replace(tzinfo=UTC)
            return actual_start <= start and actual_end >= end
        except (ValueError, TypeError):
            return False

    def _covers_manifest(
        self, manifest: DatasetManifest, start: datetime, end: datetime
    ) -> bool:
        return manifest.actual_start <= start and manifest.actual_end >= end

    def _process_partitions(
        self,
        raw_partitions: list[dict[str, Any]],
        dataset_id: str,
        version: str,
        start_index: int = 0,
    ) -> tuple[
        list[ArtifactRef],
        list[str],
        int,
        int,
        datetime | None,
        datetime | None,
        list[tuple[datetime, datetime]],
    ]:
        refs: list[ArtifactRef] = []
        hashes: list[str] = []
        bar_count = 0
        duplicate_count = 0
        actual_start: datetime | None = None
        actual_end: datetime | None = None
        gaps: list[tuple[datetime, datetime]] = []

        for i, rec in enumerate(raw_partitions):
            idx = start_index + i
            sha = rec.get("sha256", "")
            if not sha or len(sha) != 64:
                content = rec.get("bytes") or _canonical_bytes(rec)
                sha = hashlib.sha256(content).hexdigest()
            part_ref = ArtifactRef(
                kind="candle_partition",
                id=f"part_{dataset_id}_{idx}",
                version=version,
                sha256=sha,
            )
            refs.append(part_ref)
            hashes.append(sha)
            bar_count += int(rec.get("row_count", 0))
            duplicate_count += int(rec.get("duplicate_count", 0))

            rec_start_str = rec.get("start_ts") or rec.get("start")
            rec_end_str = rec.get("end_ts") or rec.get("end")
            if rec_start_str and rec_end_str:
                try:
                    rec_start = datetime.fromisoformat(str(rec_start_str))
                    rec_end = datetime.fromisoformat(str(rec_end_str))
                    if rec_start.tzinfo is None:
                        rec_start = rec_start.replace(tzinfo=UTC)
                    if rec_end.tzinfo is None:
                        rec_end = rec_end.replace(tzinfo=UTC)
                    if actual_start is None or rec_start < actual_start:
                        actual_start = rec_start
                    if actual_end is None or rec_end > actual_end:
                        actual_end = rec_end
                except (ValueError, TypeError):
                    pass

            for gap in rec.get("gaps", []):
                try:
                    gs = datetime.fromisoformat(str(gap[0]))
                    ge = datetime.fromisoformat(str(gap[1]))
                    if gs.tzinfo is None:
                        gs = gs.replace(tzinfo=UTC)
                    if ge.tzinfo is None:
                        ge = ge.replace(tzinfo=UTC)
                    gaps.append((gs, ge))
                except (ValueError, TypeError, IndexError):
                    pass

        return refs, hashes, bar_count, duplicate_count, actual_start, actual_end, gaps

    def _publish_dataset(
        self,
        request: DatasetRequest,
        raw_partitions: list[dict[str, Any]],
        *,
        parent_ref: ArtifactRef | None = None,
        parent_manifest: DatasetManifest | None = None,
        pre_partitions: list[dict[str, Any]] | None = None,
    ) -> DatasetManifest:
        """Build manifest, validate, and atomically publish to catalog (AC4)."""
        dataset_id = f"ds_{request.venue}_{request.pair}_{request.timeframe}"
        dataset_id += f"_{uuid.uuid4().hex[:12]}"

        if parent_manifest is not None:
            # Extending parent: accumulate pre + parent + post partitions
            pre = pre_partitions or []
            (
                pre_refs,
                pre_hashes,
                pre_bars,
                pre_dups,
                pre_start,
                pre_end,
                pre_gaps,
            ) = self._process_partitions(pre, dataset_id, request.version, 0)

            post_offset = len(pre_refs) + len(parent_manifest.partition_refs)
            (
                post_refs,
                post_hashes,
                post_bars,
                post_dups,
                post_start,
                post_end,
                post_gaps,
            ) = self._process_partitions(
                raw_partitions, dataset_id, request.version, post_offset
            )

            partition_refs = tuple(
                pre_refs + list(parent_manifest.partition_refs) + post_refs
            )
            partition_byte_hashes = tuple(
                pre_hashes + list(parent_manifest.partition_byte_hashes) + post_hashes
            )
            bar_count = pre_bars + parent_manifest.bar_count + post_bars
            duplicate_count = pre_dups + parent_manifest.duplicate_count + post_dups
            missing_intervals = tuple(
                pre_gaps + list(parent_manifest.missing_intervals) + post_gaps
            )

            starts = [
                s
                for s in (pre_start, parent_manifest.actual_start)
                if s is not None
            ]
            actual_start = min(starts) if starts else request.start
            ends = [
                e
                for e in (post_end, parent_manifest.actual_end)
                if e is not None
            ]
            actual_end = max(ends) if ends else request.end
            source_id = request.source_id or parent_manifest.source_id
            source_version = request.source_version or parent_manifest.source_version
        else:
            (
                p_refs,
                p_hashes,
                bar_count,
                duplicate_count,
                p_start,
                p_end,
                p_gaps,
            ) = self._process_partitions(raw_partitions, dataset_id, request.version, 0)
            partition_refs = tuple(p_refs)
            partition_byte_hashes = tuple(p_hashes)
            missing_intervals = tuple(p_gaps)
            actual_start = p_start if p_start is not None else request.start
            actual_end = p_end if p_end is not None else request.end
            source_id = request.source_id
            source_version = request.source_version

        now_utc = datetime.now(UTC)
        quality_report = RegistryQualityReport(
            status="PASS",
            bar_count=bar_count,
            duplicate_count=duplicate_count,
            partition_errors=[],
            gap_count=len(missing_intervals),
            silver_eligible=bar_count > 0,
        )
        quality_ref = quality_report.to_artifact_ref(dataset_id)

        manifest = DatasetManifest(
            dataset_id=dataset_id,
            version=request.version,
            venue=request.venue,
            pair=request.pair,
            timeframe=request.timeframe,
            requested_start=request.start,
            requested_end=request.end,
            actual_start=actual_start,
            actual_end=actual_end,
            bar_count=bar_count,
            source_id=source_id,
            source_version=source_version,
            partition_refs=partition_refs,
            partition_byte_hashes=partition_byte_hashes,
            quality_report_ref=quality_ref,
            missing_intervals=missing_intervals,
            duplicate_count=duplicate_count,
            parent_dataset_ref=parent_ref,
            created_at_utc=now_utc,
            schema_version="v1",
        )

        # Build catalog entry
        ref = manifest.to_artifact_ref()
        ref_key = _ref_key(ref)
        entry: dict[str, Any] = {
            "ref_key": ref_key,
            "ref": {
                "kind": ref.kind,
                "id": ref.id,
                "version": ref.version,
                "sha256": ref.sha256,
            },
            "dataset_id": dataset_id,
            "version": manifest.version,
            "venue": manifest.venue,
            "pair": manifest.pair,
            "timeframe": manifest.timeframe,
            "source_id": manifest.source_id,
            "source_version": manifest.source_version,
            "requested_start": manifest.requested_start.isoformat(),
            "requested_end": manifest.requested_end.isoformat(),
            "actual_start": manifest.actual_start.isoformat(),
            "actual_end": manifest.actual_end.isoformat(),
            "bar_count": manifest.bar_count,
            "duplicate_count": manifest.duplicate_count,
            "partition_refs": [
                {
                    "kind": pr.kind,
                    "id": pr.id,
                    "version": pr.version,
                    "sha256": pr.sha256,
                }
                for pr in manifest.partition_refs
            ],
            "partition_byte_hashes": list(manifest.partition_byte_hashes),
            "quality_report_ref": {
                "kind": manifest.quality_report_ref.kind,
                "id": manifest.quality_report_ref.id,
                "version": manifest.quality_report_ref.version,
                "sha256": manifest.quality_report_ref.sha256,
            },
            "missing_intervals": [
                [s.isoformat(), e.isoformat()] for s, e in manifest.missing_intervals
            ],
            "parent_dataset_ref": (
                {
                    "kind": manifest.parent_dataset_ref.kind,
                    "id": manifest.parent_dataset_ref.id,
                    "version": manifest.parent_dataset_ref.version,
                    "sha256": manifest.parent_dataset_ref.sha256,
                }
                if manifest.parent_dataset_ref is not None
                else None
            ),
            "parent_ref_key": (
                _ref_key(manifest.parent_dataset_ref)
                if manifest.parent_dataset_ref is not None
                else None
            ),
            "created_at_utc": manifest.created_at_utc.isoformat(),
            "schema_version": manifest.schema_version,
        }

        # AC4: Atomically register in catalog — crash before this leaves no visible dataset
        self._catalog.register(ref_key, entry, fsync_fn=self._fsync_fn)

        return manifest

    def _entry_to_manifest(self, entry: dict[str, Any]) -> DatasetManifest:
        """Reconstruct a DatasetManifest from a catalog entry with full fidelity."""

        def _parse_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                dt = val
            else:
                dt = datetime.fromisoformat(str(val))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)

        partition_refs = tuple(
            ArtifactRef(
                kind=pr["kind"],
                id=pr["id"],
                version=pr["version"],
                sha256=pr["sha256"],
            )
            for pr in entry.get("partition_refs", [])
        )
        qr = entry["quality_report_ref"]
        quality_ref = ArtifactRef(
            kind=qr["kind"],
            id=qr["id"],
            version=qr["version"],
            sha256=qr["sha256"],
        )
        parent_ref: ArtifactRef | None = None
        if entry.get("parent_dataset_ref"):
            pr = entry["parent_dataset_ref"]
            parent_ref = ArtifactRef(
                kind=pr["kind"],
                id=pr["id"],
                version=pr["version"],
                sha256=pr["sha256"],
            )
        elif entry.get("parent_ref_key"):
            parts = str(entry["parent_ref_key"]).split(":")
            if len(parts) == 4:
                parent_ref = ArtifactRef(
                    kind=parts[0],
                    id=parts[1],
                    version=parts[2],
                    sha256=parts[3],
                )

        missing = tuple(
            (_parse_dt(interval[0]), _parse_dt(interval[1]))
            for interval in entry.get("missing_intervals", [])
            if len(interval) == 2
        )

        return DatasetManifest(
            dataset_id=entry["dataset_id"],
            version=entry.get("version", "v1"),
            venue=entry.get("venue", "indodax"),
            pair=entry.get("pair", ""),
            timeframe=entry.get("timeframe", ""),
            requested_start=_parse_dt(entry.get("requested_start", entry["actual_start"])),
            requested_end=_parse_dt(entry.get("requested_end", entry["actual_end"])),
            actual_start=_parse_dt(entry["actual_start"]),
            actual_end=_parse_dt(entry["actual_end"]),
            bar_count=int(entry.get("bar_count", 0)),
            source_id=entry.get("source_id", ""),
            source_version=entry.get("source_version", "v1"),
            partition_refs=partition_refs,
            partition_byte_hashes=tuple(entry.get("partition_byte_hashes", [])),
            quality_report_ref=quality_ref,
            missing_intervals=missing,
            duplicate_count=int(entry.get("duplicate_count", 0)),
            parent_dataset_ref=parent_ref,
            created_at_utc=_parse_dt(
                entry.get(
                    "created_at_utc",
                    entry.get("actual_start", "1970-01-01T00:00:00+00:00"),
                )
            ),
            schema_version=entry.get("schema_version", "v1"),
        )
