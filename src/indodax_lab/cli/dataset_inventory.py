"""Read-only inventory and integrity gate for immutable candle roots."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, object]:
    """Return manifest/checkpoint facts without modifying the root."""
    manifests = list(root.glob("snapshots/*/manifest.json"))
    checkpoints = list(root.glob("ops/backfills/candles/window=*/completed.json"))
    pairs: Counter[str] = Counter()
    intervals: Counter[str] = Counter()
    rows = 0
    rejected = 0
    integrity_errors: list[str] = []
    for path in manifests:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            for partition in manifest["partitions"]:
                rel = Path(str(partition["path"]))
                part_path = root / rel
                if not part_path.is_file() or _sha256(part_path) != partition["sha256"]:
                    integrity_errors.append(f"partition:{path}")
                rows += int(partition["row_count"])
                parts = dict(item.split("=", 1) for item in rel.parts if "=" in item)
                if "pair" in parts:
                    pairs[parts["pair"]] += int(partition["row_count"])
                if "interval" in parts:
                    intervals[parts["interval"]] += int(partition["row_count"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            integrity_errors.append(f"manifest:{path}")
    for path in checkpoints:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rejected += int(payload.get("rejected_rows", 0))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            integrity_errors.append(f"checkpoint:{path}")
    return {
        "root": str(root),
        "manifest_count": len(manifests),
        "checkpoint_count": len(checkpoints),
        "accepted_rows": rows,
        "rejected_rows": rejected,
        "pairs": dict(sorted(pairs.items())),
        "intervals": dict(sorted(intervals.items())),
        "status": "PASS" if not integrity_errors else "BLOCKED",
        "integrity_errors": integrity_errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args(argv)
    reports = [inventory(root) for root in args.roots]
    print(json.dumps(reports, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if all(report["status"] == "PASS" for report in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
