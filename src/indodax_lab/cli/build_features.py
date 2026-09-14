"""CLI entrypoint to materialize immutable feature matrices (FEAT-04)."""

from __future__ import annotations

import argparse
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
    parser.add_argument("--bars", type=Path, required=True, help="Path to input bars CSV or Parquet.")
    parser.add_argument("--dataset-snapshot-id", type=str, required=True, help="Dataset snapshot identifier.")
    parser.add_argument("--output", type=Path, required=True, help="Destination path for materialized features.")
    parser.add_argument("--universe", type=Path, default=None, help="Optional universe snapshot table.")
    parser.add_argument("--universe-snapshot-id", type=str, default=None, help="Optional universe snapshot ID.")
    parser.add_argument("--btc-bars", type=Path, default=None, help="Optional benchmark BTC bars table.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and build without persisting to disk.")
    return parser.parse_args(argv)


def _load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main(argv: Sequence[str] | None = None, stdout: StringIO | None = None) -> int:
    out = stdout if stdout is not None else sys.stdout
    args = parse_args(argv)

    loaded_registry = load_feature_registry(args.config)
    bars_df = _load_table(args.bars)

    universe_df = _load_table(args.universe) if args.universe is not None else None
    btc_df = _load_table(args.btc_bars) if args.btc_bars is not None else None

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

    out.write(f"rows={rows} eligible={eligible} output={args.output}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
