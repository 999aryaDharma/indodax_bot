"""Behavioral unit tests for ``indodax_lab.cli.dataset_quality.validate_manifest``.

Each test builds a minimal Parquet file and a corresponding manifest.json,
then checks that the specific quality gate (duplicate, gap, OHLC, availability,
listing cutoff, checksum mismatch) fires correctly.

All fixtures use temp directories so no real dataset root is modified.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from indodax_lab.cli.dataset_quality import validate_manifest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

T0 = datetime(2024, 3, 1, tzinfo=UTC)
_5M = timedelta(minutes=5)


def _ts(dt: datetime):
    """Convert datetime to pandas Timestamp with tz."""
    return pd.Timestamp(dt)


def _make_row(
    open_time: datetime,
    interval: str = "5m",
    pair: str = "btc_idr",
    open_: float = 100.0,
    high: float = 110.0,
    low: float = 90.0,
    close: float = 105.0,
    volume: float = 1.0,
    available_at_offset: timedelta = timedelta(0),
) -> dict:
    close_time = open_time + _5M
    return {
        "pair": pair,
        "interval": interval,
        "open_time": _ts(open_time),
        "close_time": _ts(close_time),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "base_volume": volume,
        "available_at": _ts(close_time + available_at_offset),
    }


def _write_parquet_and_manifest(
    tmp: Path,
    rows: list[dict],
    corrupt_sha: bool = False,
) -> tuple[Path, Path]:
    """Write rows to a Parquet file, build a manifest.json, return (root, manifest_path)."""
    root = tmp / "root"
    snap_dir = root / "snapshots" / "test_snapshot"
    snap_dir.mkdir(parents=True)

    part_rel = "snapshots/test_snapshot/part-0.parquet"
    part_path = root / part_rel

    if rows:
        df = pd.DataFrame(rows)
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, part_path)
    else:
        # Write an empty parquet file with the right schema
        schema = pa.schema(
            [
                ("pair", pa.string()),
                ("interval", pa.string()),
                ("open_time", pa.timestamp("us", tz="UTC")),
                ("close_time", pa.timestamp("us", tz="UTC")),
                ("open", pa.float64()),
                ("high", pa.float64()),
                ("low", pa.float64()),
                ("close", pa.float64()),
                ("base_volume", pa.float64()),
                ("available_at", pa.timestamp("us", tz="UTC")),
            ]
        )
        pq.write_table(pa.table({name: [] for name in schema.names}, schema=schema), part_path)

    # Compute real sha256
    digest = hashlib.sha256()
    with part_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()
    if corrupt_sha:
        sha = "0" * 64  # intentionally wrong

    manifest = {
        "partitions": [
            {
                "path": part_rel,
                "sha256": sha,
                "row_count": len(rows),
            }
        ]
    }
    manifest_path = snap_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_validate_manifest_passes_clean_rows():
    """A well-formed manifest with valid rows must produce PASS with no errors."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0 + i * _5M) for i in range(3)]
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "PASS", report["errors"]
    assert report["errors"] == []
    assert report["rows_checked"] == 3


def test_validate_manifest_detects_duplicate_pair_open_time():
    """Two rows with the same (pair, open_time) must trigger a duplicate error."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0), _make_row(T0)]  # identical open_time
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("duplicate" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_detects_gap_in_interval():
    """A missing candle bar (gap larger than one interval) must be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        # T0, then skip T0+5m, then T0+10m  → gap of 10m instead of 5m
        rows = [_make_row(T0), _make_row(T0 + 2 * _5M)]
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("invalid_interval_step" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_detects_non_chronological():
    """Rows out of ascending time order must trigger non_chronological error."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0 + _5M), _make_row(T0)]  # reversed order
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("non_chronological" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_detects_ohlc_invalid_high_below_close():
    """A high price below the close price violates OHLC consistency."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0, high=103.0, close=105.0)]  # high < close
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("ohlc_inconsistent" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_detects_ohlc_invalid_low_above_open():
    """A low price above the open price violates OHLC consistency."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0, open_=95.0, low=98.0, high=110.0, close=100.0)]  # low > open
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("ohlc_inconsistent" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_detects_availability_before_close():
    """available_at earlier than close_time must be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        # available_at set 1 second BEFORE close_time
        rows = [_make_row(T0, available_at_offset=timedelta(seconds=-1))]
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("availability_before_close" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_detects_listing_cutoff_violation():
    """A candle whose open_time is before the listing start must be rejected."""
    listing_start = datetime(2024, 3, 2, tzinfo=UTC)  # after T0
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0)]  # T0 = 2024-03-01 < listing_start = 2024-03-02
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path, listing_start=listing_start)

    assert report["status"] == "BLOCKED"
    assert any("before_listing_cutoff" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_passes_rows_after_listing_cutoff():
    """Rows at or after the listing start must not trigger a cutoff error."""
    listing_start = T0
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0 + i * _5M) for i in range(2)]
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path, listing_start=listing_start)

    assert report["status"] == "PASS", report["errors"]
    assert not any("before_listing_cutoff" in e for e in report["errors"])


def test_validate_manifest_detects_checksum_mismatch():
    """A corrupted partition SHA-256 must be detected before row-level checks."""
    with tempfile.TemporaryDirectory() as tmp:
        rows = [_make_row(T0)]
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows, corrupt_sha=True)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("checksum_mismatch" in e for e in report["errors"]), report["errors"]


def test_validate_manifest_blocked_status_on_any_failure():
    """If any check fails the overall manifest status must be BLOCKED, not PASS."""
    with tempfile.TemporaryDirectory() as tmp:
        # negative volume is the only problem
        rows = [_make_row(T0, volume=-1.0)]
        root, manifest_path = _write_parquet_and_manifest(Path(tmp), rows)
        report = validate_manifest(root, manifest_path)

    assert report["status"] == "BLOCKED"
    assert any("negative_volume" in e for e in report["errors"]), report["errors"]
