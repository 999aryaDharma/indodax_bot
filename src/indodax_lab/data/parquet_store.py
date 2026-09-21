"""Atomic immutable Parquet storage for canonical candle records."""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC
from enum import StrEnum
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from indodax_lab.contracts import CandleRecord

from .checksums import sha256_bytes, sha256_file
from .manifest import (
    ImmutableContentConflictError,
    build_dataset_manifest,
    canonical_json_bytes,
    read_manifest,
    snapshot_manifest_path,
)
from .publication import (
    IndeterminatePublicationError,
    best_effort_remove_entry,
    ensure_directory_tree,
    fsync_directory,
    publish_existing_partial,
    remove_entry,
)

CANDLE_SCHEMA_V1 = pa.schema(
    [
        pa.field("schema_version", pa.string(), nullable=False),
        pa.field("pair", pa.string(), nullable=False),
        pa.field("venue_symbol", pa.string(), nullable=False),
        pa.field("interval", pa.string(), nullable=False),
        pa.field("open_time", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("close_time", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("open", pa.decimal128(38, 12), nullable=False),
        pa.field("high", pa.decimal128(38, 12), nullable=False),
        pa.field("low", pa.decimal128(38, 12), nullable=False),
        pa.field("close", pa.decimal128(38, 12), nullable=False),
        pa.field("base_volume", pa.decimal128(38, 18), nullable=False),
        pa.field("quote_volume", pa.decimal128(38, 12), nullable=True),
        pa.field("trade_count", pa.int64(), nullable=True),
        pa.field("is_closed", pa.bool_(), nullable=False),
        pa.field("available_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("quality_status", pa.string(), nullable=False),
        pa.field("quality_flags", pa.list_(pa.string()), nullable=False),
    ]
)
"""Explicit bronze_candles_v1 Arrow schema; never inferred from pandas values."""

CANDLE_SCHEMA_IDENTITY = f"sha256:{sha256_bytes(CANDLE_SCHEMA_V1.serialize().to_pybytes())}"


class WriteStatus(StrEnum):
    """Observable write outcome, allowing callers to retry safe filesystem failures."""

    SUCCESS = "SUCCESS"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"


class StorageValidationError(RuntimeError):
    """A written or pre-existing storage artifact cannot be validated safely."""


@dataclass(frozen=True)
class PartitionAudit:
    """Relative partition facts included verbatim in a snapshot manifest."""

    path: str
    sha256: str
    size_bytes: int
    row_count: int
    schema_identity: str


@dataclass(frozen=True)
class WriteResult:
    """Result of attempting one immutable dataset write."""

    status: WriteStatus
    partitions: tuple[PartitionAudit, ...] = ()
    dataset_snapshot_id: str | None = None
    manifest_path: Path | None = None
    error: str | None = None


class ParquetStore:
    """Write canonical candle partitions and their manifest below one explicit data root."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)

    def write_candles(self, candles: Iterable[CandleRecord]) -> WriteResult:
        """Persist candles by UTC month, then atomically publish their audit manifest."""
        records = tuple(candles)
        self._validate_records(records)
        try:
            audits = tuple(
                self._write_partition(relative_directory, partition_records)
                for relative_directory, partition_records in self._group_partitions(records)
            )
            manifest = build_dataset_manifest(asdict(audit) for audit in audits)
            manifest_path = self._write_manifest(manifest)
        except (OSError, pa.ArrowException, StorageValidationError) as error:
            return WriteResult(status=WriteStatus.FAILED_RETRYABLE, error=str(error))
        return WriteResult(
            status=WriteStatus.SUCCESS,
            partitions=audits,
            dataset_snapshot_id=str(manifest["dataset_snapshot_id"]),
            manifest_path=manifest_path,
        )

    def _group_partitions(
        self, records: Sequence[CandleRecord]
    ) -> list[tuple[Path, tuple[CandleRecord, ...]]]:
        grouped: dict[Path, list[CandleRecord]] = defaultdict(list)
        for record in records:
            open_time = record.open_time.astimezone(UTC)
            grouped[
                Path("bronze")
                / "dataset=candles"
                / "schema=v1"
                / f"interval={record.interval}"
                / f"pair={record.pair.pair}"
                / f"year={open_time.year:04d}"
                / f"month={open_time.month:02d}"
            ].append(record)
        return [
            (relative_path, tuple(sorted(items, key=self._canonical_sort_key)))
            for relative_path, items in sorted(grouped.items(), key=lambda item: item[0].as_posix())
        ]

    @staticmethod
    def _canonical_sort_key(record: CandleRecord) -> tuple[str, str, object, str]:
        return (record.pair.pair, record.interval, record.open_time, record.source)

    @staticmethod
    def _validate_records(records: Sequence[CandleRecord]) -> None:
        keys: set[tuple[str, str, object, str]] = set()
        for record in records:
            if not isinstance(record, CandleRecord):
                raise TypeError("ParquetStore accepts validated CandleRecord values only")
            key = ParquetStore._canonical_sort_key(record)
            if key in keys:
                raise ValueError("duplicate candle primary key")
            keys.add(key)

    def _write_partition(
        self, relative_directory: Path, records: Sequence[CandleRecord]
    ) -> PartitionAudit:
        directory = self._data_root / relative_directory
        _ensure_directory_tree(directory)
        partial_path = directory / f".{uuid.uuid4().hex}.partial"
        published_new = False
        try:
            table = pa.Table.from_pylist(
                [self._row(record) for record in records], schema=CANDLE_SCHEMA_V1
            )
            with partial_path.open("wb") as sink:
                pq.write_table(table, sink, compression="zstd")
                sink.flush()
                os.fsync(sink.fileno())
            self._validate_partition(partial_path, expected_rows=len(records))
            checksum = sha256_file(partial_path)
            final_path = directory / f"part-{checksum}.parquet"
            published_new = self._publish_immutable(partial_path, final_path, checksum)
            try:
                _remove_entry(partial_path)
            except OSError:
                if published_new:
                    _rollback_or_raise_indeterminate(final_path, "partition partial cleanup")
                raise
            relative_path = final_path.relative_to(self._data_root).as_posix()
            return PartitionAudit(
                path=relative_path,
                sha256=checksum,
                size_bytes=final_path.stat().st_size,
                row_count=len(records),
                schema_identity=CANDLE_SCHEMA_IDENTITY,
            )
        except Exception:
            _best_effort_remove_entry(partial_path)
            raise

    @staticmethod
    def _row(record: CandleRecord) -> dict[str, object]:
        return {
            "schema_version": record.schema_version,
            "pair": record.pair.pair,
            "venue_symbol": record.venue_symbol,
            "interval": record.interval,
            "open_time": record.open_time,
            "close_time": record.close_time,
            "open": record.open,
            "high": record.high,
            "low": record.low,
            "close": record.close,
            "base_volume": record.base_volume,
            "quote_volume": record.quote_volume,
            "trade_count": record.trade_count,
            "is_closed": record.is_closed,
            "available_at": record.available_at,
            "source": record.source,
            "ingested_at": record.ingested_at,
            "quality_status": str(record.quality_status),
            "quality_flags": record.quality_flags,
        }

    @staticmethod
    def _validate_partition(path: Path, *, expected_rows: int) -> None:
        try:
            parquet_file = pq.ParquetFile(path)
        except (OSError, pa.ArrowException, ValueError) as error:
            raise StorageValidationError(
                f"cannot validate written Parquet partition: {path}"
            ) from error
        if parquet_file.schema_arrow != CANDLE_SCHEMA_V1:
            raise StorageValidationError("written Parquet schema does not match CANDLE_SCHEMA_V1")
        if parquet_file.metadata.num_rows != expected_rows:
            raise StorageValidationError("written Parquet row count does not match input")

    @staticmethod
    def _publish_immutable(partial_path: Path, final_path: Path, expected_checksum: str) -> bool:
        """Atomically publish without replacing a concurrent writer's different bytes."""
        return publish_existing_partial(
            partial_path,
            final_path,
            same_content=lambda existing: sha256_file(existing) == expected_checksum,
            conflict_message=f"immutable path already contains different content: {final_path}",
            fsync_directory_fn=_fsync_directory,
            rollback_fn=_rollback_or_raise_indeterminate,
        )

    def _write_manifest(self, manifest: dict[str, object]) -> Path:
        snapshot_id = str(manifest["dataset_snapshot_id"])
        manifest_path = snapshot_manifest_path(self._data_root, snapshot_id)
        _ensure_directory_tree(manifest_path.parent)
        expected_bytes = canonical_json_bytes(manifest)
        partial_path = manifest_path.parent / f".{uuid.uuid4().hex}.partial"
        published_new = False
        try:
            with partial_path.open("wb") as sink:
                sink.write(expected_bytes)
                sink.flush()
                os.fsync(sink.fileno())
            _read_storage_manifest(partial_path)
            try:
                os.link(partial_path, manifest_path)
                published_new = True
            except FileExistsError as error:
                _read_storage_manifest(manifest_path)
                if manifest_path.read_bytes() != expected_bytes:
                    raise ImmutableContentConflictError(
                        f"snapshot manifest already contains different content: {manifest_path}"
                    ) from error
            try:
                _fsync_directory(manifest_path.parent)
            except OSError:
                if published_new:
                    _rollback_or_raise_indeterminate(manifest_path, "manifest namespace fsync")
                raise
            try:
                _remove_entry(partial_path)
            except OSError:
                if published_new:
                    _rollback_or_raise_indeterminate(manifest_path, "manifest partial cleanup")
                raise
        finally:
            _best_effort_remove_entry(partial_path)
        return manifest_path


def _fsync_directory(path: Path) -> None:
    fsync_directory(path)


def _ensure_directory_tree(directory: Path) -> None:
    """Create missing namespace levels and durably record every parent entry."""
    ensure_directory_tree(directory, fsync_directory_fn=_fsync_directory)


def _remove_entry(path: Path) -> None:
    """Remove one namespace entry and durably record that removal."""
    remove_entry(path, fsync_directory_fn=_fsync_directory)


def _best_effort_remove_entry(path: Path) -> None:
    """Attempt cleanup while preserving the operation's original failure classification."""
    best_effort_remove_entry(path, fsync_directory_fn=_fsync_directory)


def _rollback_or_raise_indeterminate(path: Path, operation: str) -> None:
    """Remove a newly visible entry or signal that callers cannot know publication state."""
    try:
        _remove_entry(path)
    except OSError as error:
        raise IndeterminatePublicationError(
            f"cannot establish storage state after {operation} failed: {path}"
        ) from error


def _read_storage_manifest(path: Path) -> dict[str, object]:
    """Normalize malformed JSON or identity failures into a retryable storage validation error."""
    try:
        return read_manifest(path)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise StorageValidationError(f"cannot validate manifest: {path}") from error
