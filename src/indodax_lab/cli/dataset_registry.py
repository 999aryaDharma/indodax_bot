"""CLI for the RW1-01 DatasetRegistry service: lookup, create, extend, validate.

Subcommands:
  find   -- Find datasets covering a time range (zero-fetch check)
  create -- Create a new dataset version via provider
  extend -- Extend an existing dataset version to cover additional intervals
  validate -- Validate partition integrity of a registered dataset

Legacy commands (pre-RW1-01) are preserved for backward compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from indodax_lab.cli.dataset_inventory import inventory
from indodax_lab.data.dataset_registry import (
    DatasetCoverageError,
    DatasetNotFoundError,
    DatasetQualityError,
    DatasetRegistry,
    DatasetRequest,
)

# ---------------------------------------------------------------------------
# Legacy helpers (pre-RW1-01, kept for backward compatibility)
# ---------------------------------------------------------------------------


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def build_registry(roots: list[Path]) -> dict[str, object]:
    entries = [inventory(root) for root in roots]
    content = {"registry_version": "dataset-registry-v1", "datasets": entries}
    digest = hashlib.sha256(_canonical(content)).hexdigest()
    return {**content, "registry_id": f"sha256:{digest}"}


def publish_no_clobber(path: Path, registry: dict[str, object]) -> None:
    payload = _canonical(registry) + b"\n"
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"IMMUTABLE_REGISTRY_CONFLICT: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    if partial.exists():
        raise RuntimeError(f"IMMUTABLE_REGISTRY_PARTIAL_EXISTS: {partial}")
    partial.write_bytes(payload)
    partial.replace(path)


# ---------------------------------------------------------------------------
# RW1-01 DatasetRegistry CLI subcommands
# ---------------------------------------------------------------------------


def _parse_utc(s: str) -> datetime:
    """Parse ISO-8601 UTC datetime string."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _registry_from_args(args: argparse.Namespace) -> DatasetRegistry:
    catalog = Path(args.catalog) if hasattr(args, "catalog") and args.catalog else None
    return DatasetRegistry(root=Path(args.root), catalog_path=catalog)


def cmd_find(args: argparse.Namespace) -> int:
    """Find registered datasets covering a time range."""
    registry = _registry_from_args(args)
    start = _parse_utc(args.start)
    end = _parse_utc(args.end)
    try:
        refs = registry.find(args.venue, args.pair, args.timeframe, start, end)
        result = {
            "status": "FOUND",
            "count": len(refs),
            "refs": [
                {"kind": r.kind, "id": r.id, "version": r.version, "sha256": r.sha256}
                for r in refs
            ],
        }
        print(json.dumps(result, indent=2))
        return 0
    except DatasetCoverageError as exc:
        print(json.dumps({"status": "COVERAGE_MISS", "reason": str(exc)}), file=sys.stderr)
        return 2


def _make_provider(
    partitions_json: Path | None, mock_bars: int
) -> Callable[[DatasetRequest], list[dict[str, Any]]]:
    def provider(req: DatasetRequest) -> list[dict[str, Any]]:
        if partitions_json and partitions_json.exists():
            return json.loads(partitions_json.read_text(encoding="utf-8"))
        content = f"{mock_bars}:{req.start.isoformat()}:{req.end.isoformat()}".encode()
        return [
            {
                "row_count": mock_bars,
                "sha256": hashlib.sha256(content).hexdigest(),
                "start_ts": req.start.isoformat(),
                "end_ts": req.end.isoformat(),
                "bytes": content,
            }
        ]

    return provider


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new dataset version."""
    partitions_json = Path(args.partitions_json) if getattr(args, "partitions_json", None) else None
    mock_bars = int(getattr(args, "mock_bars", 100))
    provider = _make_provider(partitions_json, mock_bars)

    catalog = Path(args.catalog) if getattr(args, "catalog", None) else None
    registry = DatasetRegistry(root=Path(args.root), catalog_path=catalog, fetch_provider=provider)

    req = DatasetRequest(
        venue=args.venue,
        pair=args.pair,
        timeframe=args.timeframe,
        start=_parse_utc(args.start),
        end=_parse_utc(args.end),
        source_id=getattr(args, "source_id", "raw_provider"),
        source_version=getattr(args, "source_version", "v1"),
        version=getattr(args, "version", "v1"),
    )
    manifest = registry.create(req)
    ref = manifest.to_artifact_ref()
    result = {
        "status": "CREATED",
        "dataset_id": manifest.dataset_id,
        "bar_count": manifest.bar_count,
        "actual_start": manifest.actual_start.isoformat(),
        "actual_end": manifest.actual_end.isoformat(),
        "ref": {
            "kind": ref.kind,
            "id": ref.id,
            "version": ref.version,
            "sha256": ref.sha256,
        },
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_extend(args: argparse.Namespace) -> int:
    """Extend a registered dataset with additional intervals."""
    from indodax_lab.contracts.identity import ArtifactRef

    partitions_json = Path(args.partitions_json) if getattr(args, "partitions_json", None) else None
    mock_bars = int(getattr(args, "mock_bars", 50))
    provider = _make_provider(partitions_json, mock_bars)

    catalog = Path(args.catalog) if getattr(args, "catalog", None) else None
    registry = DatasetRegistry(root=Path(args.root), catalog_path=catalog, fetch_provider=provider)

    parent_ref = ArtifactRef(
        kind=getattr(args, "parent_kind", "dataset"),
        id=args.parent_id,
        version=getattr(args, "parent_version", "v1"),
        sha256=args.parent_sha256,
    )

    req = DatasetRequest(
        venue=args.venue,
        pair=args.pair,
        timeframe=args.timeframe,
        start=_parse_utc(args.start),
        end=_parse_utc(args.end),
        source_id=getattr(args, "source_id", "raw_provider"),
        source_version=getattr(args, "source_version", "v1"),
        version=getattr(args, "version", "v1"),
    )
    manifest = registry.extend(parent_ref, req)
    ref = manifest.to_artifact_ref()
    result = {
        "status": "EXTENDED",
        "dataset_id": manifest.dataset_id,
        "bar_count": manifest.bar_count,
        "actual_start": manifest.actual_start.isoformat(),
        "actual_end": manifest.actual_end.isoformat(),
        "ref": {
            "kind": ref.kind,
            "id": ref.id,
            "version": ref.version,
            "sha256": ref.sha256,
        },
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate partition integrity of a registered dataset ref."""
    registry = _registry_from_args(args)
    from indodax_lab.contracts.identity import ArtifactRef

    try:
        ref = ArtifactRef(
            kind=args.kind,
            id=args.id,
            version=args.version,
            sha256=args.sha256,
        )
        report = registry.validate(ref)
        result = {
            "status": report.status,
            "bar_count": report.bar_count,
            "duplicate_count": report.duplicate_count,
            "gap_count": report.gap_count,
            "silver_eligible": report.silver_eligible,
            "partition_errors": report.partition_errors,
        }
        print(json.dumps(result, indent=2))
        return 0 if report.status == "PASS" else 2
    except DatasetQualityError as exc:
        print(json.dumps({"status": "QUALITY_FAIL", "reason": str(exc)}), file=sys.stderr)
        return 2
    except DatasetNotFoundError as exc:
        print(json.dumps({"status": "NOT_FOUND", "reason": str(exc)}), file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # --- find ---
    p_find = sub.add_parser("find", help="Find datasets covering a time range")
    p_find.add_argument("--root", required=True, type=str, help="Registry root directory")
    p_find.add_argument("--catalog", type=str, default=None, help="Catalog JSON path")
    p_find.add_argument("--venue", required=True, help="Venue (e.g. indodax)")
    p_find.add_argument("--pair", required=True, help="Pair (e.g. btcidr)")
    p_find.add_argument("--timeframe", required=True, help="Timeframe (e.g. 1h)")
    p_find.add_argument("--start", required=True, help="Start datetime (ISO-8601 UTC)")
    p_find.add_argument("--end", required=True, help="End datetime (ISO-8601 UTC)")

    # --- create ---
    p_create = sub.add_parser("create", help="Create a new dataset version")
    p_create.add_argument("--root", required=True, type=str, help="Registry root directory")
    p_create.add_argument("--catalog", type=str, default=None, help="Catalog JSON path")
    p_create.add_argument("--venue", required=True, help="Venue (e.g. indodax)")
    p_create.add_argument("--pair", required=True, help="Pair (e.g. btcidr)")
    p_create.add_argument("--timeframe", required=True, help="Timeframe (e.g. 1h)")
    p_create.add_argument("--start", required=True, help="Start datetime (ISO-8601 UTC)")
    p_create.add_argument("--end", required=True, help="End datetime (ISO-8601 UTC)")
    p_create.add_argument("--source-id", type=str, default="raw_provider", help="Source ID")
    p_create.add_argument("--source-version", type=str, default="v1", help="Source version")
    p_create.add_argument("--version", type=str, default="v1", help="Dataset version")
    p_create.add_argument("--partitions-json", type=Path, default=None, help="Partitions JSON path")
    p_create.add_argument("--mock-bars", type=int, default=100, help="Mock bars count if no JSON")

    # --- extend ---
    p_extend = sub.add_parser("extend", help="Extend a registered dataset with intervals")
    p_extend.add_argument("--root", required=True, type=str, help="Registry root directory")
    p_extend.add_argument("--catalog", type=str, default=None, help="Catalog JSON path")
    p_extend.add_argument("--parent-kind", type=str, default="dataset", help="Parent ref kind")
    p_extend.add_argument("--parent-id", required=True, help="Parent dataset ID")
    p_extend.add_argument("--parent-version", type=str, default="v1", help="Parent dataset version")
    p_extend.add_argument("--parent-sha256", required=True, help="Parent SHA256 digest")
    p_extend.add_argument("--venue", required=True, help="Venue (e.g. indodax)")
    p_extend.add_argument("--pair", required=True, help="Pair (e.g. btcidr)")
    p_extend.add_argument("--timeframe", required=True, help="Timeframe (e.g. 1h)")
    p_extend.add_argument("--start", required=True, help="Start datetime (ISO-8601 UTC)")
    p_extend.add_argument("--end", required=True, help="End datetime (ISO-8601 UTC)")
    p_extend.add_argument("--source-id", type=str, default="raw_provider", help="Source ID")
    p_extend.add_argument("--source-version", type=str, default="v1", help="Source version")
    p_extend.add_argument("--version", type=str, default="v1", help="Dataset version")
    p_extend.add_argument("--partitions-json", type=Path, default=None, help="Partitions JSON path")
    p_extend.add_argument("--mock-bars", type=int, default=50, help="Mock bars count if no JSON")

    # --- validate ---
    p_val = sub.add_parser("validate", help="Validate partition integrity")
    p_val.add_argument("--root", required=True, type=str, help="Registry root directory")
    p_val.add_argument("--catalog", type=str, default=None, help="Catalog JSON path")
    p_val.add_argument("--kind", required=True, help="ArtifactRef kind")
    p_val.add_argument("--id", required=True, help="ArtifactRef id")
    p_val.add_argument("--version", required=True, help="ArtifactRef version")
    p_val.add_argument("--sha256", required=True, help="ArtifactRef sha256 (64 hex chars)")

    # --- legacy root-based ---
    p_legacy = sub.add_parser("legacy", help="Legacy root-inventory registry (pre-RW1-01)")
    p_legacy.add_argument("roots", nargs="+", type=Path)
    p_legacy.add_argument("--output", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "find":
        return cmd_find(args)
    if args.command == "create":
        return cmd_create(args)
    if args.command == "extend":
        return cmd_extend(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "legacy":
        registry = build_registry(args.roots)
        if args.output:
            publish_no_clobber(args.output, registry)
        print(json.dumps(registry, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if all(item["status"] == "PASS" for item in registry["datasets"]) else 2  # type: ignore[index]

    # Fallback: legacy positional roots mode (backward compat)
    if hasattr(args, "roots") and args.roots:
        registry_data = build_registry(args.roots)
        print(json.dumps(registry_data, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if all(item["status"] == "PASS" for item in registry_data["datasets"]) else 2  # type: ignore[index]

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
