"""CLI entrypoint for assembling verified training datasets (TRAIN-01)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence
import pandas as pd

from indodax_lab.labels.materializer import materialize_training_dataset
from indodax_lab.labels.splits import SplitManifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble verified training dataset combining features, labels, and split folds."
    )
    parser.add_argument("--features", type=Path, required=True, help="Path to features parquet/csv.")
    parser.add_argument("--labels", type=Path, required=True, help="Path to labels parquet/csv.")
    parser.add_argument("--splits", type=Path, required=True, help="Path to split manifest JSON.")
    parser.add_argument("--target-column", type=str, default="net_return", help="Target column name.")
    parser.add_argument(
        "--inference-features",
        type=str,
        nargs="+",
        required=True,
        help="List of feature column names for inference.",
    )
    parser.add_argument("--dataset-snapshot-id", type=str, required=True, help="Dataset snapshot ID.")
    parser.add_argument("--feature-registry-version", type=str, default="1.0.0", help="Feature registry version.")
    parser.add_argument("--cost-schedule-id", type=str, default="indodax_idr_v1", help="Cost schedule ID.")
    parser.add_argument("--output", type=Path, required=True, help="Output destination path.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and assemble without saving.")
    return parser.parse_args(argv)


def _load_df(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    features_df = _load_df(args.features)
    labels_df = _load_df(args.labels)

    split_manifest_data = json.loads(args.splits.read_text(encoding="utf-8"))
    split_manifest = SplitManifest.model_validate(split_manifest_data)

    artifact = materialize_training_dataset(
        features_df=features_df,
        labels_df=labels_df,
        split_manifest=split_manifest,
        target_column=args.target_column,
        inference_feature_columns=args.inference_features,
        dataset_snapshot_id=args.dataset_snapshot_id,
        feature_registry_version=args.feature_registry_version,
        cost_schedule_id=args.cost_schedule_id,
    )

    if args.dry_run:
        print(f"[DRY-RUN] Verified training dataset assembled: {artifact.manifest.dataset_id}")
        print(f"Role counts: {artifact.manifest.sample_counts_by_role}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output.parent / f"{args.output.stem}_manifest.json"
    manifest_path.write_text(artifact.manifest.model_dump_json(indent=2), encoding="utf-8")
    artifact.data.to_parquet(args.output)
    print(f"[SUCCESS] Wrote training dataset to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
