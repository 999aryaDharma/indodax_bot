"""Measure historical positive 1-hour close-to-close returns from verified Indodax bronze snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def _load_snapshot_manifest(path: Path) -> dict[str, Any]:
    source_root = Path(__file__).resolve().parents[2] / "src"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    from indodax_lab.data.manifest import content_id_path_component, read_manifest

    manifest = read_manifest(path)
    expected_directory = content_id_path_component(manifest["dataset_snapshot_id"])
    if path.parent.name != expected_directory:
        raise ValueError("SNAPSHOT_MANIFEST_DIRECTORY_ID_MISMATCH")
    return manifest


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def measure(dataset_root: Path) -> dict[str, Any]:
    rows: dict[str, dict[datetime, dict[str, Any]]] = defaultdict(dict)
    source_hash = hashlib.sha256()
    partitions = 0

    for manifest_path in sorted((dataset_root / "snapshots").glob("sha256_*/manifest.json")):
        manifest = _load_snapshot_manifest(manifest_path)
        for part in manifest["partitions"]:
            if "/interval=1h/" not in f"/{part['path']}" or not any(
                f"/pair={pair}/" in f"/{part['path']}" for pair in ("btc_idr", "eth_idr")
            ):
                continue
            path = dataset_root / part["path"]
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != part["sha256"] or len(data) != part["size_bytes"]:
                raise ValueError(f"SNAPSHOT_PARTITION_CHECKSUM_MISMATCH:{part['path']}")
            table = pq.ParquetFile(path).read()
            if table.num_rows != part["row_count"]:
                raise ValueError(f"SNAPSHOT_PARTITION_ROW_COUNT_MISMATCH:{part['path']}")
            source_hash.update(part["path"].encode() + b"\0" + bytes.fromhex(digest))
            partitions += 1
            for row in table.to_pylist():
                if (
                    row["interval"] != "1h"
                    or f"/pair={row['pair']}/" not in f"/{part['path']}"
                ):
                    raise ValueError(f"SNAPSHOT_PARTITION_IDENTITY_MISMATCH:{part['path']}")
                if row["quality_status"] != "PASS" or not row["is_closed"]:
                    raise ValueError(f"NON_PASS_CANDLE:{part['path']}")
                if row["source"] != "indodax-history-v2":
                    raise ValueError(f"UNEXPECTED_CANDLE_SOURCE:{row['source']}")
                if row["open_time"] in rows[row["pair"]]:
                    raise ValueError(f"DUPLICATE_CANDLE:{row['pair']}:{row['open_time'].isoformat()}")
                rows[row["pair"]][row["open_time"]] = row

    if partitions != 120 or set(rows) != {"btc_idr", "eth_idr"}:
        raise ValueError("EXPECTED_COMPLETE_BTC_ETH_2021_2025_ARCHIVE")

    result: dict[str, Any] = {
        "source": "lab-data-fetch2/bronze, snapshots verified by partition SHA-256 and row count",
        "partition_count": partitions,
        "partition_tree_sha256": source_hash.hexdigest(),
        "pairs": {},
    }
    for pair, by_time in sorted(rows.items()):
        candles = sorted(by_time.values(), key=lambda row: row["open_time"])
        returns: list[tuple[int, float]] = []
        availability_lags = [
            (row["available_at"] - row["close_time"]).total_seconds()
            for row in candles
        ]
        if any(lag < 0 for lag in availability_lags):
            raise ValueError(f"NONCAUSAL_CANDLE_AVAILABILITY:{pair}")
        gaps = 0
        for previous, current in zip(candles, candles[1:]):
            if previous["close_time"] != current["open_time"]:
                gaps += 1
                continue
            pct = (float(current["close"]) / float(previous["close"]) - 1.0) * 100.0
            returns.append((current["open_time"].year, pct))
        if (
            len(candles) != 43_824
            or candles[0]["open_time"].isoformat() != "2021-01-01T00:00:00+00:00"
            or candles[-1]["close_time"].isoformat() != "2026-01-01T00:00:00+00:00"
            or gaps != 0
            or len(returns) != 43_823
        ):
            raise ValueError(f"EXPECTED_COMPLETE_CONTIGUOUS_2021_2025_CANDLES:{pair}")

        def summarize(values: list[float]) -> dict[str, float | int]:
            positive = [value for value in values if value > 0]
            return {
                "return_count": len(values),
                "positive_count": len(positive),
                "positive_share": len(positive) / len(values) if values else 0.0,
                "positive_return_pct": {
                    f"p{int(q * 100):02d}": _quantile(positive, q)
                    for q in (0.50, 0.90, 0.95, 0.99)
                }
                | ({"max": max(positive)} if positive else {}),
            }

        all_returns = [value for _, value in returns]
        result["pairs"][pair] = {
            "row_count": len(candles),
            "quality_pass_closed_count": len(candles),
            "start_open_time": candles[0]["open_time"].isoformat(),
            "end_close_time": candles[-1]["close_time"].isoformat(),
            "continuity_break_count": gaps,
            "historical_available_at_minus_close_time_seconds": {
                "median": _quantile(availability_lags, 0.50),
                "p95": _quantile(availability_lags, 0.95),
                "max": max(availability_lags),
            },
            "all_years": summarize(all_returns),
            "by_year": {
                str(year): summarize([value for y, value in returns if y == year])
                for year in range(2021, 2026)
                if any(y == year for y, _ in returns)
            },
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=Path("lab-data-fetch2"))
    parser.add_argument("--output", type=Path, help="Write JSON here; stdout by default")
    args = parser.parse_args()
    rendered = json.dumps(measure(args.dataset_root), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
