"""Offline wire-to-bronze integration tests for candle history backfill."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from indodax_lab.cli import backfill_candles
from indodax_lab.cli.backfill_candles import main, run_backfill
from indodax_lab.data.indodax_candles import HttpResponse
from indodax_lab.data.manifest import ImmutableContentConflictError, read_manifest

FIXTURE = Path(__file__).parents[2] / "fixtures" / "indodax" / "history_v2_pascal.json"
START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2024, 2, 1, tzinfo=UTC)
RECEIVED_AT = datetime(2024, 2, 2, tzinfo=UTC)


class FixtureTransport:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls: list[tuple[str, dict[str, object], float]] = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        return HttpResponse(
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "X-Request-ID": "fixture-request",
                "Authorization": "must-not-persist",
            },
            body=self.body,
        )


def test_dry_run_reports_windows_without_clock_transport_or_filesystem(tmp_path):
    """Constructing runtime dependencies in dry-run would make planning cause side effects."""
    output = io.StringIO()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("dry-run called a runtime dependency")

    exit_code = main(
        [
            "--pair",
            "btc_idr",
            "--interval",
            "1h",
            "--from",
            "2024-01-01T00:00:00Z",
            "--to",
            "2024-03-01T00:00:00Z",
            "--data-root",
            str(tmp_path / "must-not-exist"),
            "--dry-run",
        ],
        transport_factory=forbidden,
        clock=forbidden,
        sleeper=forbidden,
        stdout=output,
    )

    assert exit_code == 0
    assert output.getvalue() == "windows=2 requests=2\n"
    assert not (tmp_path / "must-not-exist").exists()


def test_fake_transport_backfill_is_wire_first_bronze_published_and_resumable(tmp_path):
    """A completed rerun must neither call HTTP nor add another copy of a candle row."""
    transport = FixtureTransport(FIXTURE.read_bytes())
    sleeps: list[float] = []

    first = run_backfill(
        data_root=tmp_path,
        pair="btc_idr",
        interval="1h",
        start=START,
        end=END,
        transport=transport,
        clock=lambda: RECEIVED_AT,
        sleeper=sleeps.append,
        rate_limit_seconds=0.25,
    )
    replay = run_backfill(
        data_root=tmp_path,
        pair="btc_idr",
        interval="1h",
        start=START,
        end=END,
        transport=transport,
        clock=lambda: datetime(2025, 1, 1, tzinfo=UTC),
        sleeper=sleeps.append,
        rate_limit_seconds=0.25,
    )

    assert first.fetched_windows == 1
    assert first.resumed_windows == 0
    assert first.accepted_rows == 2
    assert first.rejected_rows == 1
    assert replay.fetched_windows == 0
    assert replay.resumed_windows == 1
    assert len(transport.calls) == 1
    assert transport.calls[0][1] == {
        "symbol": "BTCIDR",
        "tf": "60",
        "from": 1704067200,
        "to": 1706745600,
    }
    assert sleeps == []

    wire_bodies = list(tmp_path.rglob("wire/**/body.json"))
    wire_metadata = list(tmp_path.rglob("wire/**/metadata.json"))
    parquet_paths = list(tmp_path.rglob("part-*.parquet"))
    manifest_paths = list(tmp_path.rglob("snapshots/**/manifest.json"))
    checkpoints = list(tmp_path.rglob("ops/**/completed.json"))
    assert len(wire_bodies) == len(wire_metadata) == len(parquet_paths) == 1
    assert len(manifest_paths) == len(checkpoints) == 1
    assert wire_bodies[0].read_bytes() == FIXTURE.read_bytes()
    assert b"must-not-persist" not in wire_metadata[0].read_bytes()
    assert pq.ParquetFile(parquet_paths[0]).metadata.num_rows == 2
    assert read_manifest(manifest_paths[0])["row_count"] == 2


def test_backfill_rate_limits_between_actual_requests_only(tmp_path):
    """Sleeping before the first or after the last request wastes time without enforcing spacing."""

    class WindowTransport:
        def __init__(self):
            self.calls = 0

        def get(self, url, *, params, timeout):
            epoch = int(params["from"])
            self.calls += 1
            body = json.dumps(
                [
                    {
                        "Time": epoch,
                        "Open": "100",
                        "High": "102",
                        "Low": "99",
                        "Close": "101",
                        "Volume": "1",
                    }
                ]
            ).encode()
            return HttpResponse(200, {"Content-Type": "application/json"}, body)

    transport = WindowTransport()
    sleeps: list[float] = []

    result = run_backfill(
        data_root=tmp_path,
        pair="btc_idr",
        interval="1h",
        start=START,
        end=datetime(2024, 3, 1, tzinfo=UTC),
        transport=transport,
        clock=lambda: RECEIVED_AT,
        sleeper=sleeps.append,
        rate_limit_seconds=0.25,
    )

    assert result.fetched_windows == 2
    assert transport.calls == 2
    assert sleeps == [0.25]


def test_backfill_rejects_rows_outside_end_exclusive_window(tmp_path):
    """An inclusive endpoint row must not duplicate the next window's opening candle."""

    class BoundaryTransport:
        def get(self, url, *, params, timeout):
            rows = [
                {
                    "Time": epoch,
                    "Open": "100",
                    "High": "102",
                    "Low": "99",
                    "Close": "101",
                    "Volume": "1",
                }
                for epoch in (1704063600, 1704067200, 1706745600)
            ]
            return HttpResponse(
                200, {"Content-Type": "application/json"}, json.dumps(rows).encode()
            )

    result = run_backfill(
        data_root=tmp_path,
        pair="btc_idr",
        interval="1h",
        start=START,
        end=END,
        transport=BoundaryTransport(),
        clock=lambda: RECEIVED_AT,
        sleeper=lambda _seconds: None,
        rate_limit_seconds=0,
    )

    assert result.accepted_rows == 1
    assert result.rejected_rows == 2
    parquet_path = next(tmp_path.rglob("part-*.parquet"))
    assert pq.ParquetFile(parquet_path).read(columns=["open_time"])["open_time"].to_pylist() == [
        START
    ]
    checkpoint = json.loads(next(tmp_path.rglob("ops/**/completed.json")).read_text())
    assert [reject["reason"] for reject in checkpoint["rejects"]] == [
        "OUTSIDE_REQUEST_WINDOW",
        "OUTSIDE_REQUEST_WINDOW",
    ]


def test_semantically_inconsistent_completion_marker_fails_closed_before_http(tmp_path):
    """A valid marker checksum must not excuse a row count that disagrees with its manifest."""
    transport = FixtureTransport(FIXTURE.read_bytes())
    run_backfill(
        data_root=tmp_path,
        pair="btc_idr",
        interval="1h",
        start=START,
        end=END,
        transport=transport,
        clock=lambda: RECEIVED_AT,
        sleeper=lambda _seconds: None,
        rate_limit_seconds=0,
    )
    marker = next(tmp_path.rglob("ops/**/completed.json"))
    checkpoint = json.loads(marker.read_text(encoding="utf-8"))
    checkpoint["accepted_rows"] = 999
    unsigned = {key: value for key, value in checkpoint.items() if key != "checkpoint_sha256"}
    canonical = json.dumps(unsigned, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    checkpoint["checkpoint_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    changed_bytes = json.dumps(
        checkpoint, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    marker.write_text(changed_bytes, encoding="utf-8")

    with pytest.raises(ImmutableContentConflictError):
        run_backfill(
            data_root=tmp_path,
            pair="btc_idr",
            interval="1h",
            start=START,
            end=END,
            transport=transport,
            clock=lambda: RECEIVED_AT,
            sleeper=lambda _seconds: None,
            rate_limit_seconds=0,
        )

    assert transport.calls and len(transport.calls) == 1
    assert marker.read_text(encoding="utf-8") == changed_bytes


def test_resume_fails_closed_when_wire_metadata_is_corrupt(tmp_path):
    """A valid raw body alone cannot prove request identity, HTTP status, or declared checksum."""
    transport = FixtureTransport(FIXTURE.read_bytes())
    run_backfill(
        data_root=tmp_path,
        pair="btc_idr",
        interval="1h",
        start=START,
        end=END,
        transport=transport,
        clock=lambda: RECEIVED_AT,
        sleeper=lambda _seconds: None,
        rate_limit_seconds=0,
    )
    metadata_path = next(tmp_path.rglob("wire/**/metadata.json"))
    metadata = json.loads(metadata_path.read_text())
    metadata["status_code"] = 500
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(ImmutableContentConflictError):
        run_backfill(
            data_root=tmp_path,
            pair="btc_idr",
            interval="1h",
            start=START,
            end=END,
            transport=transport,
            clock=lambda: RECEIVED_AT,
            sleeper=lambda _seconds: None,
            rate_limit_seconds=0,
        )

    assert len(transport.calls) == 1


def test_checkpoint_namespace_fsync_failure_rolls_back_visible_marker(tmp_path, monkeypatch):
    """A failed checkpoint namespace sync must not report failure with a marker still visible."""
    marker = tmp_path / "ops" / "backfills" / "completed.json"
    marker.parent.mkdir(parents=True)
    fsync_directory = backfill_candles._fsync_directory
    calls = 0

    def fail_first_fsync(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated checkpoint namespace failure")
        fsync_directory(path)

    monkeypatch.setattr(backfill_candles, "_fsync_directory", fail_first_fsync)

    with pytest.raises(OSError, match="checkpoint namespace"):
        backfill_candles._publish_checkpoint(marker, {"checkpoint": "fixture"})

    assert not marker.exists()
