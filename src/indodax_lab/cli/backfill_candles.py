"""Idempotent monthly-window backfill for public Indodax candles."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from indodax_lab.data.checksums import sha256_bytes, sha256_file
from indodax_lab.data.indodax_candles import (
    HISTORY_V2_ENDPOINT,
    PAIR_TO_VENUE_SYMBOL,
    HttpResponse,
    HttpTransport,
    IndodaxCandleClient,
)
from indodax_lab.data.manifest import (
    ImmutableContentConflictError,
    canonical_json_bytes,
    read_manifest,
)
from indodax_lab.data.parquet_store import ParquetStore, WriteStatus
from indodax_lab.data.publication import fsync_directory, publish_immutable_bytes
from indodax_lab.data.wire_store import WireStore
from indodax_lab.paths import LabPaths


@dataclass(frozen=True)
class BackfillWindow:
    """One end-exclusive request window, split at UTC month boundaries."""

    start: datetime
    end: datetime

    def identity(self, *, pair: str, interval: str) -> dict[str, str]:
        return {
            "pair": pair,
            "interval": interval,
            "from": self.start.isoformat(),
            "to": self.end.isoformat(),
        }


@dataclass(frozen=True)
class BackfillSummary:
    """Observable request, resume, and parser totals for one invocation."""

    windows: int
    fetched_windows: int
    resumed_windows: int
    accepted_rows: int
    rejected_rows: int
    dataset_snapshot_ids: tuple[str, ...]


class BackfillStorageError(RuntimeError):
    """A bronze publication failed without producing an authoritative manifest."""


class UrllibTransport:
    """Minimal credential-free transport for the public history endpoint."""

    def get(self, url: str, *, params, timeout: float) -> HttpResponse:
        request_url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(request_url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    status_code=int(response.status),
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except urllib.error.HTTPError as error:
            return HttpResponse(
                status_code=int(error.code),
                headers=dict(error.headers.items()),
                body=error.read(),
            )


def plan_windows(start: datetime, end: datetime) -> tuple[BackfillWindow, ...]:
    """Split an end-exclusive UTC range at calendar-month boundaries."""
    _require_utc(start, "start")
    _require_utc(end, "end")
    if end <= start:
        raise ValueError("backfill end must be after start")
    windows: list[BackfillWindow] = []
    cursor = start
    while cursor < end:
        if cursor.month == 12:
            month_boundary = datetime(cursor.year + 1, 1, 1, tzinfo=UTC)
        else:
            month_boundary = datetime(cursor.year, cursor.month + 1, 1, tzinfo=UTC)
        next_cursor = min(end, month_boundary)
        windows.append(BackfillWindow(start=cursor, end=next_cursor))
        cursor = next_cursor
    return tuple(windows)


def run_backfill(
    *,
    data_root: Path,
    pair: str,
    interval: str,
    start: datetime,
    end: datetime,
    transport: HttpTransport,
    clock: Callable[[], datetime],
    sleeper: Callable[[float], object],
    rate_limit_seconds: float,
) -> BackfillSummary:
    """Fetch unfinished windows, publish bronze, and resume validated completions."""
    if rate_limit_seconds < 0:
        raise ValueError("rate_limit_seconds must be non-negative")
    root = Path(data_root)
    windows = plan_windows(start, end)
    client = IndodaxCandleClient(transport=transport, wire_store=WireStore(root))
    parquet_store = ParquetStore(root)
    fetched = 0
    resumed = 0
    accepted_rows = 0
    rejected_rows = 0
    snapshot_ids: list[str] = []
    made_request = False

    for window in windows:
        identity = window.identity(pair=pair, interval=interval)
        checkpoint_path = _checkpoint_path(root, identity)
        if checkpoint_path.exists():
            checkpoint = _read_checkpoint(root, checkpoint_path, identity)
            resumed += 1
            accepted_rows += int(checkpoint["accepted_rows"])
            rejected_rows += int(checkpoint["rejected_rows"])
            snapshot_ids.append(str(checkpoint["dataset_snapshot_id"]))
            continue

        if made_request and rate_limit_seconds:
            sleeper(rate_limit_seconds)
        received_at = clock()
        _require_utc(received_at, "clock result")
        fetched_result = client.fetch_window(
            pair=pair,
            interval=interval,
            start=window.start,
            end=window.end,
            received_at=received_at,
        )
        made_request = True
        fetched += 1
        if not fetched_result.batch.records:
            raise BackfillStorageError("window has no accepted candle rows")
        write_result = parquet_store.write_candles(fetched_result.batch.records)
        if write_result.status is not WriteStatus.SUCCESS:
            raise BackfillStorageError(write_result.error or "bronze publication failed")
        if write_result.manifest_path is None or write_result.dataset_snapshot_id is None:
            raise BackfillStorageError("bronze success did not return a manifest identity")

        checkpoint = _build_checkpoint(
            root=root,
            identity=identity,
            wire_body_path=fetched_result.wire.body_path,
            wire_body_sha256=fetched_result.wire.body_sha256,
            wire_metadata_path=fetched_result.wire.metadata_path,
            wire_metadata_sha256=fetched_result.wire.metadata_sha256,
            wire_request_id=fetched_result.wire.request_id,
            wire_status_code=fetched_result.wire.status_code,
            manifest_path=write_result.manifest_path,
            dataset_snapshot_id=write_result.dataset_snapshot_id,
            accepted_rows=len(fetched_result.batch.items),
            rejects=fetched_result.batch.rejects,
        )
        _publish_checkpoint(checkpoint_path, checkpoint)
        accepted_rows += len(fetched_result.batch.items)
        rejected_rows += len(fetched_result.batch.rejects)
        snapshot_ids.append(write_result.dataset_snapshot_id)

    return BackfillSummary(
        windows=len(windows),
        fetched_windows=fetched,
        resumed_windows=resumed,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        dataset_snapshot_ids=tuple(snapshot_ids),
    )


def _build_checkpoint(
    *,
    root: Path,
    identity: dict[str, str],
    wire_body_path: Path,
    wire_body_sha256: str,
    wire_metadata_path: Path,
    wire_metadata_sha256: str,
    wire_request_id: str,
    wire_status_code: int,
    manifest_path: Path,
    dataset_snapshot_id: str,
    accepted_rows: int,
    rejects,
) -> dict[str, object]:
    checkpoint: dict[str, object] = {
        "checkpoint_version": "1.0.0",
        "window": identity,
        "wire_body_path": wire_body_path.relative_to(root).as_posix(),
        "wire_body_sha256": wire_body_sha256,
        "wire_metadata_path": wire_metadata_path.relative_to(root).as_posix(),
        "wire_metadata_sha256": wire_metadata_sha256,
        "wire_request_id": wire_request_id,
        "wire_status_code": wire_status_code,
        "manifest_path": manifest_path.relative_to(root).as_posix(),
        "dataset_snapshot_id": dataset_snapshot_id,
        "accepted_rows": accepted_rows,
        "rejected_rows": len(rejects),
        "rejects": [
            {
                "row_index": reject.row_index,
                "reason": reject.reason,
                "source_event_id": reject.source_event_id,
            }
            for reject in rejects
        ],
    }
    checkpoint["checkpoint_sha256"] = _checkpoint_checksum(checkpoint)
    return checkpoint


def _checkpoint_path(root: Path, identity: dict[str, str]) -> Path:
    digest = sha256_bytes(canonical_json_bytes(identity))
    return root / "ops" / "backfills" / "candles" / f"window={digest}" / "completed.json"


def _checkpoint_checksum(checkpoint: dict[str, object]) -> str:
    content = {key: value for key, value in checkpoint.items() if key != "checkpoint_sha256"}
    return sha256_bytes(canonical_json_bytes(content))


def _read_checkpoint(
    root: Path, checkpoint_path: Path, expected_identity: dict[str, str]
) -> dict[str, object]:
    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ImmutableContentConflictError(
            f"cannot validate completed backfill checkpoint: {checkpoint_path}"
        ) from error
    if not isinstance(checkpoint, dict):
        raise ImmutableContentConflictError("completed backfill checkpoint must be an object")
    if checkpoint.get("window") != expected_identity:
        raise ImmutableContentConflictError("completed backfill checkpoint identity changed")
    if checkpoint.get("checkpoint_sha256") != _checkpoint_checksum(checkpoint):
        raise ImmutableContentConflictError("completed backfill checkpoint checksum changed")
    try:
        wire_path = _safe_relative_path(root, str(checkpoint["wire_body_path"]))
        wire_metadata_path = _safe_relative_path(root, str(checkpoint["wire_metadata_path"]))
        manifest_path = _safe_relative_path(root, str(checkpoint["manifest_path"]))
        if sha256_file(wire_path) != checkpoint["wire_body_sha256"]:
            raise ImmutableContentConflictError("completed wire body checksum changed")
        if sha256_file(wire_metadata_path) != checkpoint["wire_metadata_sha256"]:
            raise ImmutableContentConflictError("completed wire metadata checksum changed")
        wire_metadata = json.loads(wire_metadata_path.read_text(encoding="utf-8"))
        _validate_wire_metadata(
            wire_metadata,
            checkpoint=checkpoint,
            expected_identity=expected_identity,
            actual_body_size=wire_path.stat().st_size,
        )
        manifest = read_manifest(manifest_path)
        if manifest["dataset_snapshot_id"] != checkpoint["dataset_snapshot_id"]:
            raise ImmutableContentConflictError("completed manifest identity changed")
        if int(manifest["row_count"]) != int(checkpoint["accepted_rows"]):
            raise ImmutableContentConflictError("completed manifest row count changed")
        if int(checkpoint["rejected_rows"]) != len(checkpoint["rejects"]):
            raise ImmutableContentConflictError("completed reject count changed")
        for partition in manifest["partitions"]:
            partition_path = _safe_relative_path(root, str(partition["path"]))
            if sha256_file(partition_path) != partition["sha256"]:
                raise ImmutableContentConflictError("completed bronze partition checksum changed")
    except (KeyError, OSError, TypeError, ValueError) as error:
        if isinstance(error, ImmutableContentConflictError):
            raise
        raise ImmutableContentConflictError("completed artifacts cannot be validated") from error
    return checkpoint


def _validate_wire_metadata(
    wire_metadata: object,
    *,
    checkpoint: dict[str, object],
    expected_identity: dict[str, str],
    actual_body_size: int,
) -> None:
    if not isinstance(wire_metadata, dict) or not isinstance(wire_metadata.get("request"), dict):
        raise ImmutableContentConflictError("completed wire metadata shape changed")
    request = wire_metadata["request"]
    expected_start = int(datetime.fromisoformat(expected_identity["from"]).timestamp())
    expected_end = int(datetime.fromisoformat(expected_identity["to"]).timestamp())
    expected_request = {
        "endpoint": HISTORY_V2_ENDPOINT,
        "pair": expected_identity["pair"],
        "venue_symbol": PAIR_TO_VENUE_SYMBOL[expected_identity["pair"]],
        "interval": expected_identity["interval"],
        "start_epoch": expected_start,
        "end_epoch": expected_end,
        "epoch_unit": "seconds",
    }
    derived_request_id = f"sha256:{sha256_bytes(canonical_json_bytes(request))}"
    if request != expected_request:
        raise ImmutableContentConflictError("completed wire request identity changed")
    if wire_metadata.get("request_id") != checkpoint["wire_request_id"]:
        raise ImmutableContentConflictError("checkpoint wire request ID changed")
    if wire_metadata.get("request_id") != derived_request_id:
        raise ImmutableContentConflictError("wire request ID declaration changed")
    if wire_metadata.get("status_code") != checkpoint["wire_status_code"]:
        raise ImmutableContentConflictError("completed wire status declaration changed")
    if not 200 <= int(wire_metadata["status_code"]) < 300:
        raise ImmutableContentConflictError("completed wire status is not successful")
    if wire_metadata.get("body_sha256") != checkpoint["wire_body_sha256"]:
        raise ImmutableContentConflictError("wire body checksum declaration changed")
    if int(wire_metadata.get("size_bytes", -1)) != actual_body_size:
        raise ImmutableContentConflictError("wire body size declaration changed")


def _safe_relative_path(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ImmutableContentConflictError("checkpoint contains an unsafe artifact path")
    return root / path


def _publish_checkpoint(path: Path, checkpoint: dict[str, object]) -> None:
    content = canonical_json_bytes(checkpoint)
    publish_immutable_bytes(path, content, fsync_directory_fn=_fsync_directory)


def _fsync_directory(path: Path) -> None:
    fsync_directory(path)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    _require_utc(parsed, "timestamp")
    return parsed


def _require_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{name} must be timezone-aware UTC")


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill auditable Indodax public candles")
    parser.add_argument("--pair", required=True)
    parser.add_argument("--interval", required=True)
    parser.add_argument("--from", dest="start", required=True, type=_parse_utc)
    parser.add_argument("--to", dest="end", required=True, type=_parse_utc)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--rate-limit-seconds", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    transport_factory: Callable[[], HttpTransport] = UrllibTransport,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], object] = time.sleep,
    stdout: TextIO = sys.stdout,
) -> int:
    """Run CLI; dry-run returns before resolving paths or runtime dependencies."""
    args = _argument_parser().parse_args(argv)
    windows = plan_windows(args.start, args.end)
    if args.dry_run:
        print(f"windows={len(windows)} requests={len(windows)}", file=stdout)
        return 0

    project_root = Path(__file__).resolve().parents[3]
    data_root = args.data_root or LabPaths.from_env(project_root).data_root
    summary = run_backfill(
        data_root=data_root,
        pair=args.pair,
        interval=args.interval,
        start=args.start,
        end=args.end,
        transport=transport_factory(),
        clock=clock,
        sleeper=sleeper,
        rate_limit_seconds=args.rate_limit_seconds,
    )
    print(
        f"windows={summary.windows} fetched={summary.fetched_windows} "
        f"resumed={summary.resumed_windows} accepted={summary.accepted_rows} "
        f"rejected={summary.rejected_rows}",
        file=stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
