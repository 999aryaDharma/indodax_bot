"""CLI entry point for running deterministic backtest replays (SIM-03)."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from indodax_lab.backtest.costs import load_cost_schedule_table
from indodax_lab.backtest.engine import ReplayBacktestEngine
from indodax_lab.backtest.events import MarketBar
from indodax_lab.backtest.risk import RiskPolicy


def main(argv: Sequence[str] | None = None, stdout=None) -> int:
    out = stdout or sys.stdout
    parser = argparse.ArgumentParser(description="Deterministic replay backtest runner")
    parser.add_argument("--config", required=True, help="Path to cost schedule YAML config")
    parser.add_argument("--output", required=False, help="Path to write output result JSON")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without publishing artifacts")

    args = parser.parse_args(argv)

    table = load_cost_schedule_table(Path(args.config))
    policy = RiskPolicy(
        policy_id="cli_risk_v1",
        version="1.0.0",
    )
    engine = ReplayBacktestEngine(cost_schedule_table=table, risk_policy=policy)

    out.write(f"backtest initialized config={args.config} dry_run={args.dry_run}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
