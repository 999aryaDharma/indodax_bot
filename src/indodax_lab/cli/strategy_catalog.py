"""Validate and list the declarative offline strategy catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from indodax_lab.strategies.registry import StrategyRegistry


def load_catalog(config_dir: Path) -> list[dict[str, object]]:
    registry = StrategyRegistry()
    result: list[dict[str, object]] = []
    for path in sorted(config_dir.glob("*.yaml")):
        spec = registry.load_specification_from_yaml(path)
        result.append({
            "config": path.as_posix(),
            "strategy_id": spec.strategy_id,
            "version": spec.version,
            "timeframes": spec.timeframes,
            "signal_timing": spec.signal_timing,
            "execution_timing": spec.execution_timing,
            "status": spec.status,
            "parameters_hash": spec.parameters_hash(),
        })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("configs/strategies"))
    args = parser.parse_args(argv)
    catalog = load_catalog(args.config_dir)
    print(json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
