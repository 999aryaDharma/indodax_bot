"""CLI entrypoint to materialize immutable feature matrices (FEAT-04)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Sequence
from io import StringIO
from pathlib import Path

import pandas as pd

from indodax_lab.data.publication import (
    best_effort_remove_entry,
    ensure_directory_tree,
    fsync_directory,
    publish_existing_partial,
    publish_immutable_bytes,
    remove_entry,
    rollback_or_raise_indeterminate,
)
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


def _publish_output(features_df: pd.DataFrame, path: Path) -> tuple[str, bool]:
    ensure_directory_tree(path.parent)
    partial_path = path.parent / f".{uuid.uuid4().hex}.partial"
    published_new = False
    try:
        if path.suffix.lower() in (".parquet", ".pq"):
            with partial_path.open("xb") as sink:
                features_df.to_parquet(sink, index=False)
                sink.flush()
                os.fsync(sink.fileno())
        else:
            with partial_path.open("x", encoding="utf-8", newline="") as sink:
                features_df.to_csv(sink, index=False)
                sink.flush()
                os.fsync(sink.fileno())

        checksum = _sha256_file(partial_path)
        published_new = publish_existing_partial(
            partial_path,
            path,
            same_content=lambda existing: _sha256_file(existing) == checksum,
            conflict_message=f"immutable feature output already differs: {path}",
            fsync_directory_fn=fsync_directory,
        )
        try:
            remove_entry(partial_path, fsync_directory_fn=fsync_directory)
        except OSError:
            if published_new:
                rollback_or_raise_indeterminate(
                    path, "feature output partial cleanup", fsync_directory_fn=fsync_directory
                )
            raise
        return checksum, published_new
    except Exception:
        best_effort_remove_entry(partial_path, fsync_directory_fn=fsync_directory)
        raise


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

    output_sha256, output_published_new = _publish_output(features_df, args.output)

    manifest_info = {
        "manifest_version": "1.0.0",
        "dataset_snapshot_id": args.dataset_snapshot_id,
        "feature_set_id": loaded_registry.registry.feature_set_id,
        "feature_set_version": loaded_registry.registry.version,
        "feature_registry_source_id": loaded_registry.source_id,
        "decision_interval": loaded_registry.registry.decision_interval,
        "output_file": args.output.name,
        "output_sha256": output_sha256,
        "total_rows": rows,
        "eligible_rows": eligible,
        "feature_count": len(loaded_registry.registry.features),
        "features": [f.name for f in loaded_registry.registry.features],
    }
    manifest_path = args.output.parent / f"{args.output.stem}_manifest.json"
    try:
        publish_immutable_bytes(
            manifest_path, json.dumps(manifest_info, indent=2).encode("utf-8")
        )
    except Exception:
        if output_published_new:
            rollback_or_raise_indeterminate(args.output, "feature manifest publication")
        raise

    out.write(f"rows={rows} eligible={eligible} output={args.output} manifest={manifest_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
