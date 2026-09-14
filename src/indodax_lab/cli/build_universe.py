"""Offline-input CLI for deterministic daily point-in-time universe snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from indodax_lab.universe.contracts import UniverseMetrics, load_universe_policy
from indodax_lab.universe.snapshot import build_daily_snapshot, prepare_daily_snapshot


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _parse_date(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("as-of date must use YYYY-MM-DD")
    return parsed


def _argument_parser() -> argparse.ArgumentParser:
    parser = _Parser(description="Build an immutable point-in-time universe snapshot")
    parser.add_argument("--as-of-date", required=True, type=_parse_date)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, *, stdout: TextIO = sys.stdout) -> int:
    """Classify explicit offline inputs; dry-run never creates the output root."""
    arguments = _argument_parser().parse_args(argv)
    loaded = load_universe_policy(arguments.config)
    raw_metrics = json.loads(
        arguments.metrics.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=int
    )
    if not isinstance(raw_metrics, list):
        raise ValueError("metrics JSON must contain one array")
    metrics = tuple(UniverseMetrics.model_validate(row) for row in raw_metrics)
    if any(record.as_of_date != arguments.as_of_date for record in metrics):
        raise ValueError("metrics as_of_date must match --as-of-date")
    prepared = prepare_daily_snapshot(
        metrics=metrics,
        policy=loaded.policy,
        policy_source_id=loaded.source_id,
    )
    eligible = sum(decision.eligible for decision in prepared.decisions)
    if arguments.dry_run:
        stdout.write(
            f"rows={len(prepared.decisions)} eligible={eligible} "
            f"snapshot_id={prepared.universe_snapshot_id} "
            f"policy_source_id={loaded.source_id}\n"
        )
        return 0
    artifact = build_daily_snapshot(
        data_root=arguments.data_root,
        metrics=metrics,
        policy=loaded.policy,
        policy_source_id=loaded.source_id,
    )
    stdout.write(
        f"rows={len(artifact.decisions)} eligible={eligible} "
        f"snapshot_id={artifact.universe_snapshot_id} "
        f"manifest={artifact.manifest_path}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
