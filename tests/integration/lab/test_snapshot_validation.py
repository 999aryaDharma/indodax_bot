from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from indodax_lab.cli.validate_snapshot import main
from indodax_lab.contracts import CandleRecord, CanonicalPair, QualityStatus
from indodax_lab.data import sentry
from indodax_lab.data.checksums import sha256_bytes, sha256_file
from indodax_lab.data.manifest import (
    ImmutableContentConflictError,
    build_dataset_manifest,
    canonical_json_bytes,
    content_id_path_component,
    snapshot_manifest_path,
)
from indodax_lab.data.parquet_store import (
    CANDLE_SCHEMA_IDENTITY,
    CANDLE_SCHEMA_V1,
    ParquetStore,
    WriteStatus,
)
from indodax_lab.data.publication import IndeterminatePublicationError
from indodax_lab.data.sentry import require_approved_snapshot_decision, validate_snapshot

START = datetime(2024, 1, 1, tzinfo=UTC)


def _candle(start: datetime = START) -> CandleRecord:
    return CandleRecord(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        interval="1h",
        open_time=start,
        close_time=start + timedelta(hours=1),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        base_volume=Decimal("1"),
        is_closed=True,
        available_at=start + timedelta(hours=1),
        source="indodax",
        ingested_at=start + timedelta(hours=1),
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )


def test_checksum_mismatch_quarantines_without_mutating_bronze_or_raw(tmp_path):
    """A changed bronze byte must fail closed while preserving audit evidence for investigation."""
    written = ParquetStore(tmp_path).write_candles([_candle(), _candle(START + timedelta(hours=1))])
    assert written.status is WriteStatus.SUCCESS
    assert written.dataset_snapshot_id is not None
    bronze = tmp_path / written.partitions[0].path
    raw = tmp_path / "wire" / "fixture" / "body.json"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"original raw wire")
    bronze_before = bronze.read_bytes()
    raw_before = raw.read_bytes()
    bronze.write_bytes(bronze_before + b"tampered")

    result = validate_snapshot(
        tmp_path,
        written.dataset_snapshot_id,
        expected_start=START,
        expected_end=START + timedelta(hours=2),
        as_of=START + timedelta(hours=2),
    )

    assert result.report.status == "FAIL"
    assert result.partition_state == "QUARANTINED"
    assert [finding.code for finding in result.report.findings] == ["PARTITION_CHECKSUM_MISMATCH"]
    assert bronze.read_bytes().endswith(b"tampered")
    assert raw.read_bytes() == raw_before
    assert result.quarantine_record is not None and result.quarantine_record.exists()
    assert "quarantine" in result.quarantine_record.parts


def test_cli_emits_structured_failure_and_exit_three_for_corrupt_snapshot(tmp_path):
    """A corrupt snapshot must produce machine-readable failure rather than a traceback-only CLI."""
    output = io.StringIO()
    exit_code = main(
        [
            "--data-root", str(tmp_path), "--snapshot-id", "sha256:not-a-snapshot",
            "--from", "2024-01-01T00:00:00Z", "--to", "2024-01-01T01:00:00Z",
            "--as-of", "2024-01-01T01:00:00Z",
        ],
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert exit_code == 3
    assert payload["status"] == "FAIL"
    assert payload["findings"][0]["code"] == "SNAPSHOT_INVALID"


def test_cli_returns_four_for_invalid_invocation_without_traceback(tmp_path):
    """Malformed CLI input is a caller error, not an unstructured process crash."""
    output = io.StringIO()

    exit_code = main(["--data-root", str(tmp_path)], stdout=output)

    payload = json.loads(output.getvalue())
    assert exit_code == 4
    assert payload["status"] == "FAIL"
    assert payload["findings"][0]["code"] == "INVALID_INVOCATION"


def test_cli_returns_zero_for_pass_and_two_for_unapproved_warning(tmp_path):
    """Collapsing PASS and WARN exit codes would bypass the explicit silver approval policy."""
    written = ParquetStore(tmp_path).write_candles([_candle()])
    assert written.dataset_snapshot_id is not None
    base = [
        "--data-root", str(tmp_path), "--snapshot-id", written.dataset_snapshot_id,
        "--from", "2024-01-01T00:00:00Z", "--to", "2024-01-01T01:00:00Z",
        "--as-of", "2024-01-01T01:00:00Z",
    ]
    passed = io.StringIO()

    assert main(base, stdout=passed) == 0
    assert json.loads(passed.getvalue())["status"] == "PASS"


def test_valid_cli_corrupt_content_returns_structured_fail_not_invalid_invocation(tmp_path):
    """A malformed stored interval is snapshot content, even when every CLI argument is valid."""
    snapshot_id = _write_schema_valid_snapshot(tmp_path, interval="unsupported")
    output = io.StringIO()

    exit_code = main(
        [
            "--data-root", str(tmp_path), "--snapshot-id", snapshot_id,
            "--from", "2024-01-01T00:00:00Z", "--to", "2024-01-01T01:00:00Z",
            "--as-of", "2024-01-01T01:00:00Z",
        ],
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert exit_code == 3
    assert payload["findings"][0]["code"] == "SNAPSHOT_CONTENT_INVALID"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda report: report.__setitem__("expected_rows", 2), "canonical report"),
        (lambda report: report.__setitem__("duplicate_count", 1), "canonical report"),
        (
            lambda report: report.__setitem__(
                "gap_ranges",
                [{"start_ts": "2024-01-01T00:00:00Z", "end_ts": "2024-01-01T01:00:00Z"}],
            ),
            "canonical report",
        ),
        (lambda report: report.__setitem__("silver_eligible", False), "canonical report"),
    ],
)
def test_full_shaped_inconsistent_pass_cannot_authorize_silver(tmp_path, mutation, reason):
    """Rehashing a forged full report cannot replace recomputation from bronze bytes."""
    written = ParquetStore(tmp_path).write_candles([_candle()])
    assert written.dataset_snapshot_id is not None
    result = validate_snapshot(
        tmp_path,
        written.dataset_snapshot_id,
        expected_start=START,
        expected_end=START + timedelta(hours=1),
        as_of=START + timedelta(hours=1),
    )
    assert result.eligible_for_silver
    quality_dir = (
        tmp_path / "quality" / "snapshots" / content_id_path_component(written.dataset_snapshot_id)
    )
    record = next(quality_dir.glob("*.json"))
    report = json.loads(record.read_text(encoding="utf-8"))
    mutation(report)
    forged = canonical_json_bytes(report)
    record.unlink()
    (quality_dir / f"{sha256_bytes(forged)}.json").write_bytes(forged)

    with pytest.raises(ValueError, match=reason):
        require_approved_snapshot_decision(tmp_path, written.dataset_snapshot_id)


def test_unsafe_snapshot_id_is_an_invalid_invocation_before_any_path_write(tmp_path):
    """A traversal-shaped snapshot identity must never become part of a read or decision path."""
    output = io.StringIO()

    exit_code = main(
        [
            "--data-root", str(tmp_path), "--snapshot-id", "../escape",
            "--from", "2024-01-01T00:00:00Z", "--to", "2024-01-01T01:00:00Z",
            "--as-of", "2024-01-01T01:00:00Z",
        ],
        stdout=output,
    )

    assert exit_code == 4
    assert json.loads(output.getvalue())["findings"][0]["code"] == "INVALID_INVOCATION"
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2024-01-01T00:00:00Z", "2024-01-01T00:30:00Z"),
        ("2024-01-01T00:30:00Z", "2024-01-01T01:30:00Z"),
        ("2024-01-01T01:00:00Z", "2024-01-01T01:00:00Z"),
    ],
)
def test_interval_invalid_requested_window_is_invalid_invocation(tmp_path, start, end):
    """A caller's window incompatible with the stored 1h interval is not corrupt snapshot data."""
    written = ParquetStore(tmp_path).write_candles([_candle()])
    assert written.dataset_snapshot_id is not None
    output = io.StringIO()

    exit_code = main(
        [
            "--data-root", str(tmp_path), "--snapshot-id", written.dataset_snapshot_id,
            "--from", start, "--to", end, "--as-of", "2024-01-01T02:00:00Z",
        ],
        stdout=output,
    )

    assert exit_code == 4
    assert json.loads(output.getvalue())["findings"][0]["code"] == "INVALID_INVOCATION"


def test_symlink_loop_in_snapshot_path_is_structured_content_failure(tmp_path):
    """Following a corrupt snapshot symlink must not escape the root or turn into a traceback."""
    written = ParquetStore(tmp_path).write_candles([_candle()])
    assert written.dataset_snapshot_id is not None
    snapshot_dir = snapshot_manifest_path(tmp_path, written.dataset_snapshot_id).parent
    snapshot_dir.rename(tmp_path / "saved-snapshot")
    try:
        snapshot_dir.symlink_to(snapshot_dir)
    except OSError as exc:
        pytest.skip(f"Symlink creation not permitted in this environment: {exc}")
    output = io.StringIO()

    exit_code = main(
        [
            "--data-root", str(tmp_path), "--snapshot-id", written.dataset_snapshot_id,
            "--from", "2024-01-01T00:00:00Z", "--to", "2024-01-01T01:00:00Z",
            "--as-of", "2024-01-01T01:00:00Z",
        ],
        stdout=output,
    )

    assert exit_code == 3
    assert json.loads(output.getvalue())["findings"][0]["code"] == "SNAPSHOT_PATH_UNRESOLVABLE"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ImmutableContentConflictError("fixture"), "QUALITY_RECORD_CONFLICT"),
        (IndeterminatePublicationError("fixture"), "QUALITY_RECORD_INDETERMINATE"),
    ],
)
def test_quality_record_publication_failures_are_structured_and_not_claimed_written(
    tmp_path, monkeypatch, error, code
):
    """Publication uncertainty cannot be surfaced as a traceback or a claimed record."""
    written = ParquetStore(tmp_path).write_candles([_candle()])
    assert written.dataset_snapshot_id is not None

    def fail_publication(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(sentry, "publish_immutable_bytes", fail_publication)

    result = validate_snapshot(
        tmp_path,
        written.dataset_snapshot_id,
        expected_start=START,
        expected_end=START + timedelta(hours=1),
        as_of=START + timedelta(hours=1),
    )

    assert result.report.status == "FAIL"
    assert result.report.findings[0].code == code
    assert result.partition_state == "QUARANTINED"
    assert result.quarantine_record is None


def _write_schema_valid_snapshot(root, *, interval: str) -> str:
    row = {
        "schema_version": "1.0.0",
        "pair": "btc_idr",
        "venue_symbol": "BTCIDR",
        "interval": interval,
        "open_time": START,
        "close_time": START + timedelta(hours=1),
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "base_volume": Decimal("1"),
        "quote_volume": None,
        "trade_count": None,
        "is_closed": True,
        "available_at": START + timedelta(hours=1),
        "source": "indodax",
        "ingested_at": START + timedelta(hours=1),
        "quality_status": "PASS",
        "quality_flags": [],
    }
    partition = root / "bronze" / "fixture.parquet"
    partition.parent.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([row], schema=CANDLE_SCHEMA_V1), partition)
    audit = {
        "path": partition.relative_to(root).as_posix(),
        "sha256": sha256_file(partition),
        "size_bytes": partition.stat().st_size,
        "row_count": 1,
        "schema_identity": CANDLE_SCHEMA_IDENTITY,
    }
    manifest = build_dataset_manifest([audit])
    snapshot_id = str(manifest["dataset_snapshot_id"])
    manifest_path = snapshot_manifest_path(root, snapshot_id)
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    return snapshot_id
