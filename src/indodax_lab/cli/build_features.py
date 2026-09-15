"""CLI entrypoint to materialize immutable feature matrices (FEAT-04)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from io import StringIO
from pathlib import Path
from typing import Sequence

import pandas as pd

from indodax_lab.features.builder import build_feature_frame
from indodax_lab.features.registry import load_feature_registry


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize immutable feature matrices with verified causality and lineage."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to feature registry YAML.")
    parser.add_argument("--bars", type=Path, required=True, help="Path to input bars CSV, Parquet, or directory.")
    parser.add_argument("--dataset-snapshot-id", type=str, required=True, help="Dataset snapshot identifier.")
    parser.add_argument("--output", type=Path, required=True, help="Destination path for materialized features.")
    parser.add_argument("--universe", type=Path, default=None, help="Optional universe snapshot table.")
    parser.add_argument("--universe-snapshot-id", type=str, default=None, help="Optional universe snapshot ID.")
    parser.add_argument("--btc-bars", type=Path, default=None, help="Optional benchmark BTC bars table.")
    parser.add_argument(
        "--historical-availability",
        action="store_true",
        help="Use close_time as available_at for closed historical bars whose ingested_at reflects offline download time.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and build without persisting to disk.")
    return parser.parse_args(argv)


def _load_table(path: Path) -> pd.DataFrame:
    if path.is_dir():
        df = pd.read_parquet(path)
    elif path.suffix.lower() in (".parquet", ".pq"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    if "close_time" in df.columns:
        df = df.sort_values("close_time").reset_index(drop=True)
    return df


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None, stdout: StringIO | None = None) -> int:
    out = stdout if stdout is not None else sys.stdout
    args = parse_args(argv)

    loaded_registry = load_feature_registry(args.config)
    bars_df = _load_table(args.bars)

    if args.historical_availability:
        if "is_closed" in bars_df.columns and "close_time" in bars_df.columns:
            bars_df["available_at"] = bars_df["close_time"]

    universe_df = _load_table(args.universe) if args.universe is not None else None

    btc_df = None
    if args.btc_bars is not None:
        btc_df = _load_table(args.btc_bars)
        if args.historical_availability and "is_closed" in btc_df.columns and "close_time" in btc_df.columns:
            btc_df["available_at"] = btc_df["close_time"]

    features_df = build_feature_frame(
        bars_df,
        registry=loaded_registry,
        dataset_snapshot_id=args.dataset_snapshot_id,
        universe=universe_df,
        universe_snapshot_id=args.universe_snapshot_id,
        btc_bars=btc_df,
    )

    rows = len(features_df)
    eligible = int(features_df["eligible"].sum())

    if args.dry_run:
        out.write(f"rows={rows} eligible={eligible} dry_run=true\n")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix.lower() in (".parquet", ".pq"):
        features_df.to_parquet(args.output, index=False)
    else:
        features_df.to_csv(args.output, index=False)

    manifest_info = {
        "manifest_version": "1.0.0",
        "dataset_snapshot_id": args.dataset_snapshot_id,
        "feature_set_id": loaded_registry.registry.feature_set_id,
        "feature_set_version": loaded_registry.registry.version,
        "decision_interval": loaded_registry.registry.decision_interval,
        "output_file": args.output.name,
        "output_sha256": _sha256_file(args.output),
        "total_rows": rows,
        "eligible_rows": eligible,
        "feature_count": len(loaded_registry.registry.features),
        "features": [f.name for f in loaded_registry.registry.features],
    }
    manifest_path = args.output.parent / f"{args.output.stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest_info, indent=2), encoding="utf-8")

    out.write(f"rows={rows} eligible={eligible} output={args.output} manifest={manifest_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
