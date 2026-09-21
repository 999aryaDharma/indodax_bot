"""Behavioral tests for immutable candle Parquet partitions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from indodax_lab.contracts import CandleRecord, CanonicalPair, QualityStatus
from indodax_lab.data import parquet_store
from indodax_lab.data.manifest import ImmutableContentConflictError, snapshot_manifest_path
from indodax_lab.data.parquet_store import (
    CANDLE_SCHEMA_V1,
    IndeterminatePublicationError,
    ParquetStore,
    WriteStatus,
)


def _candle(*, pair: str, open_time: datetime, source: str = "indodax") -> CandleRecord:
    return CandleRecord(
        schema_version="1.0.0",
        pair=CanonicalPair(pair=pair),
        venue_symbol=pair.replace("_", "").upper(),
        interval="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=Decimal("100.123456789012"),
        high=Decimal("110.123456789012"),
        low=Decimal("90.123456789012"),
        close=Decimal("105.123456789012"),
        base_volume=Decimal("1.123456789012345678"),
        quote_volume=Decimal("105.123456789012"),
        trade_count=4,
        is_closed=True,
        available_at=open_time + timedelta(hours=1),
        source=source,
        ingested_at=open_time + timedelta(hours=1),
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )


def test_store_writes_sorted_zstd_utc_partitions_and_content_addressed_manifest(tmp_path):
    """Removing explicit ordering/schema or checksums changes audit-visible output."""
    start = datetime(2026, 8, 1, tzinfo=UTC)
    store = ParquetStore(tmp_path)

    result = store.write_candles(
        [
            _candle(pair="eth_idr", open_time=start),
            _candle(pair="btc_idr", open_time=start + timedelta(hours=1)),
            _candle(pair="btc_idr", open_time=start),
        ]
    )

    assert result.status is WriteStatus.SUCCESS
    assert len(result.partitions) == 2
    assert not list(tmp_path.rglob("*.partial"))
    assert result.manifest_path == snapshot_manifest_path(tmp_path, result.dataset_snapshot_id)
    assert result.manifest_path.is_file()
    manifest = result.manifest_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in manifest
    assert "created_at" not in manifest
    assert '"size_bytes"' in manifest
    assert '"schema_identity"' in manifest
    for partition in result.partitions:
        parquet_file = pq.ParquetFile(tmp_path / partition.path)
        assert parquet_file.schema_arrow == CANDLE_SCHEMA_V1
        assert parquet_file.metadata.row_group(0).column(0).compression == "ZSTD"
        assert partition.row_count == parquet_file.metadata.num_rows
        assert partition.sha256
        if "pair=btc_idr" in partition.path:
            open_times = parquet_file.read(columns=["open_time"])["open_time"].to_pylist()
            assert open_times == sorted(open_times)


def test_candle_schema_uses_documented_decimals_and_utc_timestamps():
    """Using inferred numerics or local timestamps would violate the source table contract."""
    assert CANDLE_SCHEMA_V1.field("open").type == pa.decimal128(38, 12)
    assert CANDLE_SCHEMA_V1.field("base_volume").type == pa.decimal128(38, 18)
    assert CANDLE_SCHEMA_V1.field("open_time").type == pa.timestamp("us", tz="UTC")


def test_store_reuses_identical_content_and_changes_snapshot_when_source_changes(tmp_path):
    """Replacing source bytes without a new checksum must create a distinct snapshot."""
    start = datetime(2026, 8, 1, tzinfo=UTC)
    store = ParquetStore(tmp_path)
    original = store.write_candles([_candle(pair="btc_idr", open_time=start, source="indodax")])
    retry = store.write_candles([_candle(pair="btc_idr", open_time=start, source="indodax")])
    changed = store.write_candles([_candle(pair="btc_idr", open_time=start, source="indoday")])

    assert retry.dataset_snapshot_id == original.dataset_snapshot_id
    assert changed.partitions[0].sha256 != original.partitions[0].sha256
    assert changed.dataset_snapshot_id != original.dataset_snapshot_id


def test_store_never_overwrites_a_tampered_content_addressed_partition(tmp_path):
    """Replacing an occupied content path would lose a concurrent writer's audit evidence."""
    start = datetime(2026, 8, 1, tzinfo=UTC)
    store = ParquetStore(tmp_path)
    original = store.write_candles([_candle(pair="btc_idr", open_time=start)])
    partition_path = tmp_path / original.partitions[0].path
    partition_path.write_bytes(b"tampered")

    with pytest.raises(ImmutableContentConflictError):
        store.write_candles([_candle(pair="btc_idr", open_time=start)])

    assert partition_path.read_bytes() == b"tampered"


def test_store_returns_retryable_failure_and_never_publishes_manifest_after_write_error(
    tmp_path, monkeypatch
):
    """Publishing a manifest after a failed close would advertise data that is not durable."""
    store = ParquetStore(tmp_path)

    def fail_validation(*_args, **_kwargs):
        raise OSError("simulated disk validation failure")

    monkeypatch.setattr(store, "_validate_partition", fail_validation)
    result = store.write_candles(
        [_candle(pair="btc_idr", open_time=datetime(2026, 8, 1, tzinfo=UTC))]
    )

    assert result.status is WriteStatus.FAILED_RETRYABLE
    assert result.dataset_snapshot_id is None
    snapshots = tmp_path / "snapshots"
    assert not snapshots.exists() or not list(snapshots.rglob("manifest.json"))
    assert not list(tmp_path.rglob("*.partial"))


def test_store_returns_retryable_failure_when_manifest_publish_link_fails(tmp_path, monkeypatch):
    """A failed atomic publish must not leave an authoritative success manifest behind."""
    store = ParquetStore(tmp_path)
    original_link = parquet_store.os.link

    def fail_manifest_link(source, destination, *args, **kwargs):
        if Path(destination).name == "manifest.json":
            raise OSError("simulated atomic publish failure")
        return original_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(parquet_store.os, "link", fail_manifest_link)
    result = store.write_candles(
        [_candle(pair="btc_idr", open_time=datetime(2026, 8, 1, tzinfo=UTC))]
    )

    assert result.status is WriteStatus.FAILED_RETRYABLE
    snapshots = tmp_path / "snapshots"
    assert not snapshots.exists() or not list(snapshots.rglob("manifest.json"))
    assert not list(tmp_path.rglob("*.partial"))


def test_partial_cleanup_failure_rolls_back_new_partition_and_never_reports_success(
    tmp_path, monkeypatch
):
    """A visible final plus an unconsumed partial is not an immutable successful write."""
    store = ParquetStore(tmp_path)
    remove_entry = parquet_store._remove_entry

    def fail_partial_removal(path):
        if Path(path).suffix == ".partial":
            raise OSError("simulated partial cleanup failure")
        return remove_entry(path)

    monkeypatch.setattr(parquet_store, "_remove_entry", fail_partial_removal)
    result = store.write_candles(
        [_candle(pair="btc_idr", open_time=datetime(2026, 8, 1, tzinfo=UTC))]
    )

    assert result.status is WriteStatus.FAILED_RETRYABLE
    assert not list(tmp_path.rglob("part-*.parquet"))
    assert not list((tmp_path / "snapshots").rglob("manifest.json"))


def test_failed_partition_rollback_reports_indeterminate_publication(tmp_path, monkeypatch):
    """A rollback that cannot be fsynced leaves an unknown state and must not become success."""
    store = ParquetStore(tmp_path)

    def fail_removal(_path):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(parquet_store, "_remove_entry", fail_removal)

    with pytest.raises(IndeterminatePublicationError):
        store.write_candles(
            [_candle(pair="btc_idr", open_time=datetime(2026, 8, 1, tzinfo=UTC))]
        )


def test_successful_new_and_idempotent_writes_fsync_partition_and_manifest_namespaces(
    tmp_path, monkeypatch
):
    """Omitting a namespace fsync can make a successful publish disappear after a crash."""
    store = ParquetStore(tmp_path)
    fsync_directory = parquet_store._fsync_directory
    calls: list[Path] = []

    def record_fsync(path):
        calls.append(Path(path))
        fsync_directory(path)

    monkeypatch.setattr(parquet_store, "_fsync_directory", record_fsync)
    candle = _candle(pair="btc_idr", open_time=datetime(2026, 8, 1, tzinfo=UTC))
    initial = store.write_candles([candle])
    initial_calls = set(calls)
    calls.clear()
    retry = store.write_candles([candle])

    assert initial.status is WriteStatus.SUCCESS
    assert retry.status is WriteStatus.SUCCESS
    assert tmp_path in initial_calls
    assert tmp_path / "snapshots" in initial_calls
    assert (tmp_path / retry.partitions[0].path).parent in calls
    assert retry.manifest_path.parent in calls


def test_corrupt_parquet_validation_maps_to_retryable_failure_without_manifest(
    tmp_path, monkeypatch
):
    """Leaking an Arrow validation exception makes a recoverable storage failure unsafe to retry."""
    store = ParquetStore(tmp_path)

    def reject_parquet(*_args, **_kwargs):
        raise pa.ArrowInvalid("simulated unreadable parquet")

    monkeypatch.setattr(parquet_store.pq, "ParquetFile", reject_parquet)
    result = store.write_candles(
        [_candle(pair="btc_idr", open_time=datetime(2026, 8, 1, tzinfo=UTC))]
    )

    assert result.status is WriteStatus.FAILED_RETRYABLE
    assert not list((tmp_path / "snapshots").rglob("manifest.json"))


def test_corrupt_existing_manifest_maps_to_retryable_failure(tmp_path):
    """A malformed existing manifest must not escape as an unclassified ValueError."""
    store = ParquetStore(tmp_path)
    candle = _candle(pair="btc_idr", open_time=datetime(2026, 8, 1, tzinfo=UTC))
    initial = store.write_candles([candle])
    initial.manifest_path.write_text("not json", encoding="utf-8")

    result = store.write_candles([candle])

    assert result.status is WriteStatus.FAILED_RETRYABLE
    assert result.dataset_snapshot_id is None
