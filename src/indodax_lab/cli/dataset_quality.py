"""Read-only candle quality gate for immutable Parquet manifests."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq


def validate_manifest(root: Path, manifest_path: Path, listing_start: datetime | None = None) -> dict[str, object]:
    errors: list[str] = []
    rows_checked = 0
    for partition in json.loads(manifest_path.read_text(encoding="utf-8"))["partitions"]:
        path = root / str(partition["path"])
        try:
            # ParquetFile avoids Hive partition inference colliding with the
            # physical ``pair``/``interval`` columns on Windows paths.
            parquet = pq.ParquetFile(path)
            seen: set[tuple[str, object]] = set()
            previous: dict[str, object] = {}
            any_rows = False
            for batch in parquet.iter_batches(batch_size=8192, columns=["pair", "interval", "open_time", "close_time", "open", "high", "low", "close", "base_volume", "available_at"]):
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
                        seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}.get(str(interval))
                        if delta <= 0:
                            errors.append(f"non_chronological:{pair}:{path}")
                        elif seconds is not None and delta % seconds != 0:
                            errors.append(f"invalid_interval_step:{pair}:{path}")
                    previous[str(pair)] = open_time
                    if high < max(open_, close, low) or low > min(open_, close, high):
                        errors.append(f"ohlc_inconsistent:{path}")
                    if volume < 0:
                        errors.append(f"negative_volume:{path}")
                    if available_at < close_time:
                        errors.append(f"availability_before_close:{path}")
                    if listing_start is not None and open_time.to_pydatetime().astimezone(UTC) < listing_start:
                        errors.append(f"before_listing_cutoff:{path}")
            if not any_rows:
                errors.append(f"empty:{path}")
        except Exception as exc:  # quality gate must report, never silently pass
            errors.append(f"read_error:{path}:{type(exc).__name__}:{exc}")
    return {"manifest": str(manifest_path), "rows_checked": rows_checked, "status": "PASS" if not errors else "BLOCKED", "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--listing-start", type=lambda value: datetime.fromisoformat(value).astimezone(UTC))
    args = parser.parse_args(argv)
    reports = [validate_manifest(args.root, path, args.listing_start) for path in sorted(args.root.glob("snapshots/*/manifest.json"))]
    print(json.dumps(reports, ensure_ascii=False, sort_keys=True, indent=2, default=str))
    return 0 if reports and all(report["status"] == "PASS" for report in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
