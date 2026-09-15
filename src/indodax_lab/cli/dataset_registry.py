"""Build a content-addressed, no-clobber registry for local dataset roots."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from indodax_lab.cli.dataset_inventory import inventory


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    registry = build_registry(args.roots)
    if args.output:
        publish_no_clobber(args.output, registry)
    print(json.dumps(registry, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if all(item["status"] == "PASS" for item in registry["datasets"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
