"""Read-only candle quality gate for immutable Parquet manifests.

Processes one manifest at a time so memory usage is bounded regardless of
root size.  Reports are emitted incrementally; if a single manifest fails
the overall exit code is non-zero.

Usage
-----
  python -m indodax_lab.cli.dataset_quality <root> [--listing-start ISO8601]
                                                   [--report-dir <dir>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

_INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(
    root: Path,
    manifest_path: Path,
    listing_start: datetime | None = None,
) -> dict[str, object]:
    """Check one manifest, streaming Parquet row-groups.  Never loads the full
    file into memory.  Returns a dict with ``status`` PASS or BLOCKED."""
    errors: list[str] = []
    rows_checked = 0

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "manifest": str(manifest_path),
            "rows_checked": 0,
            "status": "BLOCKED",
            "errors": [f"manifest_read_error:{type(exc).__name__}:{exc}"],
        }

    for partition in manifest.get("partitions", []):
        part_rel = str(partition.get("path", ""))
        path = root / part_rel

        # --- checksum gate (integrity) ---
        expected_sha = partition.get("sha256", "")
        if expected_sha:
            try:
                actual_sha = _sha256_file(path)
                if actual_sha != expected_sha:
                    errors.append(
                        f"checksum_mismatch:{path}:expected={expected_sha}:actual={actual_sha}"
                    )
            except OSError as exc:
                errors.append(f"checksum_read_error:{path}:{exc}")
                continue  # cannot read → skip row-level checks for this partition

        # --- row-level checks (streaming) ---
        try:
            # ParquetFile avoids Hive partition inference colliding with the
            # physical ``pair``/``interval`` columns on Windows paths.
            parquet = pq.ParquetFile(path)
            seen: set[tuple[str, object]] = set()
            previous: dict[str, object] = {}
            any_rows = False
            for batch in parquet.iter_batches(
                batch_size=8192,
                columns=[
                    "pair",
                    "interval",
                    "open_time",
                    "close_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "base_volume",
                    "available_at",
                ],
            ):
                frame = batch.to_pandas()
                any_rows = any_rows or not frame.empty
                rows_checked += len(frame)
                for row in frame.itertuples(index=False):
                    pair, interval, open_time, close_time, open_, high, low, close, volume, available_at = row
                    key = (str(pair), open_time)
                    if key in seen:
                        errors.append(f"duplicate:{path}")
                    seen.add(key)
                    prior = previous.get(str(pair))
                    if prior is not None:
                        delta = (open_time - prior).total_seconds()
                        seconds = _INTERVAL_SECONDS.get(str(interval))
                        if delta <= 0:
                            errors.append(f"non_chronological:{pair}:{path}")
                        elif seconds is not None and delta % seconds != 0:
                            # Timestamp not aligned to any multiple of the interval
                            errors.append(f"invalid_interval_step:{pair}:{path}")
                        elif seconds is not None and delta > seconds:
                            # Aligned gap: delta is valid multiple but > 1 step → missing bars
                            errors.append(f"invalid_interval_step:{pair}:{path}")
                    previous[str(pair)] = open_time
                    if high < max(open_, close, low) or low > min(open_, close, high):
                        errors.append(f"ohlc_inconsistent:{path}")
                    if volume < 0:
                        errors.append(f"negative_volume:{path}")
                    if available_at < close_time:
                        errors.append(f"availability_before_close:{path}")
                    if listing_start is not None:
                        ot_utc = open_time.to_pydatetime().astimezone(UTC)
                        if ot_utc < listing_start:
                            errors.append(f"before_listing_cutoff:{path}")
            if not any_rows:
                errors.append(f"empty:{path}")
        except Exception as exc:  # quality gate must report, never silently pass
            errors.append(f"read_error:{path}:{type(exc).__name__}:{exc}")

    return {
        "manifest": str(manifest_path),
        "rows_checked": rows_checked,
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--listing-start",
        type=lambda value: datetime.fromisoformat(value).astimezone(UTC),
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory to write one JSON report per manifest (append-only; never overwritten).",
    )
    args = parser.parse_args(argv)

    manifest_paths = sorted(args.root.glob("snapshots/*/manifest.json"))
    if not manifest_paths:
        msg = {"root": str(args.root), "status": "BLOCKED", "errors": ["no_manifests_found"]}
        print(json.dumps(msg, ensure_ascii=False, sort_keys=True, indent=2, default=str))
        return 2

    overall_pass = True
    # Stream output as a JSON array, emitting each element after it is validated.
    # This avoids keeping all reports in memory simultaneously.
    print("[")
    for idx, manifest_path in enumerate(manifest_paths):
        report = validate_manifest(args.root, manifest_path, args.listing_start)

        # Per-manifest incremental file report (never overwrite existing files)
        if args.report_dir is not None:
            args.report_dir.mkdir(parents=True, exist_ok=True)
            slug = manifest_path.parent.name  # snapshot hash dir
            report_file = args.report_dir / f"quality-{slug}.json"
            if not report_file.exists():  # no-clobber: never overwrite earlier failure evidence
                report_file.write_text(
                    json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, default=str),
                    encoding="utf-8",
                )

        # Emit to stdout as part of the array
        line = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        # Indent array elements by 2 spaces
        indented = "\n".join("  " + l for l in line.splitlines())
        separator = "," if idx < len(manifest_paths) - 1 else ""
        print(f"{indented}{separator}")
        sys.stdout.flush()

        if report["status"] != "PASS":
            overall_pass = False

    print("]")
    sys.stdout.flush()
    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
