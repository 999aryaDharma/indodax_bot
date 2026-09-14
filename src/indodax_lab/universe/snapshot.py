"""Deterministic durable publication for immutable daily universe snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from indodax_lab.data.checksums import sha256_bytes
from indodax_lab.data.manifest import canonical_json_bytes
from indodax_lab.data.publication import publish_immutable_bytes, rollback_or_raise_indeterminate

from .contracts import UniverseDecision, UniverseMetrics, UniversePolicy
from .eligibility import classify_pair

DATASET = "silver_universe_v1"
SCHEMA_VERSION = "1.0.0"
MANIFEST_VERSION = "1.0.0"


@dataclass(frozen=True)
class PreparedUniverseSnapshot:
    """Canonical logical snapshot before any filesystem publication."""

    universe_snapshot_id: str
    decisions: tuple[UniverseDecision, ...]
    data_bytes: bytes
    manifest: dict[str, object]
    relative_data_path: Path


@dataclass(frozen=True)
class UniverseSnapshotArtifact:
    """Published paths and immutable decisions for one daily universe."""

    universe_snapshot_id: str
    decisions: tuple[UniverseDecision, ...]
    data_path: Path
    manifest_path: Path


def prepare_daily_snapshot(
    *,
    metrics: Iterable[UniverseMetrics],
    policy: UniversePolicy,
    policy_source_id: str,
) -> PreparedUniverseSnapshot:
    """Build canonical decisions and identity without touching storage."""
    records = tuple(metrics)
    if not records:
        raise ValueError("a daily universe snapshot requires at least one pair")
    pairs = [record.pair for record in records]
    if len(set(pairs)) != len(pairs):
        raise ValueError("duplicate universe primary key")
    as_of_dates = {record.as_of_date for record in records}
    if len(as_of_dates) != 1:
        raise ValueError("all universe inputs must use one as_of_date")
    decisions = tuple(
        sorted((classify_pair(record, policy) for record in records), key=lambda row: row.pair)
    )
    decision_rows = [decision.model_dump(mode="json") for decision in decisions]
    data_bytes = b"".join(canonical_json_bytes(row) + b"\n" for row in decision_rows)
    data_sha256 = sha256_bytes(data_bytes)
    source_input_ids = sorted(
        {source_id for decision in decisions for source_id in decision.source_input_ids}
    )
    identity = {
        "dataset": DATASET,
        "schema_version": SCHEMA_VERSION,
        "as_of_date": decisions[0].as_of_date.isoformat(),
        "policy": {
            "policy_version": policy.policy_version,
            "source_id": policy_source_id,
        },
        "source_input_ids": source_input_ids,
        "decisions": decision_rows,
    }
    digest = sha256_bytes(canonical_json_bytes(identity))
    snapshot_id = f"sha256:{digest}"
    relative_data_path = (
        Path("silver")
        / "dataset=universe"
        / "schema=v1"
        / f"as_of_date={decisions[0].as_of_date.isoformat()}"
        / f"snapshot={digest}"
        / "universe.jsonl"
    )
    manifest: dict[str, object] = {
        "dataset": DATASET,
        "manifest_version": MANIFEST_VERSION,
        "schema_version": SCHEMA_VERSION,
        "universe_snapshot_id": snapshot_id,
        "as_of_date": decisions[0].as_of_date.isoformat(),
        "policy": {
            "policy_version": policy.policy_version,
            "source_id": policy_source_id,
        },
        "source_input_ids": source_input_ids,
        "row_count": len(decisions),
        "partition": {
            "path": relative_data_path.as_posix(),
            "sha256": data_sha256,
            "size_bytes": len(data_bytes),
            "row_count": len(decisions),
        },
    }
    return PreparedUniverseSnapshot(
        universe_snapshot_id=snapshot_id,
        decisions=decisions,
        data_bytes=data_bytes,
        manifest=manifest,
        relative_data_path=relative_data_path,
    )


def build_daily_snapshot(
    *,
    data_root: Path,
    metrics: Iterable[UniverseMetrics],
    policy: UniversePolicy,
    policy_source_id: str,
) -> UniverseSnapshotArtifact:
    """Durably no-clobber publish a canonical daily data file and manifest."""
    prepared = prepare_daily_snapshot(
        metrics=metrics, policy=policy, policy_source_id=policy_source_id
    )
    root = Path(data_root)
    data_path = root / prepared.relative_data_path
    manifest_path = root / "snapshots" / prepared.universe_snapshot_id / "manifest.json"
    data_published = publish_immutable_bytes(data_path, prepared.data_bytes)
    try:
        publish_immutable_bytes(manifest_path, canonical_json_bytes(prepared.manifest))
    except Exception:
        if data_published:
            rollback_or_raise_indeterminate(data_path, "universe manifest publication")
        raise
    return UniverseSnapshotArtifact(
        universe_snapshot_id=prepared.universe_snapshot_id,
        decisions=prepared.decisions,
        data_path=data_path,
        manifest_path=manifest_path,
    )
