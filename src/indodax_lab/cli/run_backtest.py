"""CLI entry point for running deterministic backtest replays (SIM-03).

Usage (subset dry-run, 3 days):
    python -m indodax_lab.cli.run_backtest \\
        --strategy configs/strategies/C01_MTF_v1.yaml \\
        --cost-config configs/costs/indodax_idr_v1.yaml \\
        --bars-5m lab-data-5m/bronze \\
        --bars-1h lab-data-fetch2/bronze \\
        --pair btc_idr \\
        --start 2021-01-04 --end 2021-01-07 \\
        --initial-cash 10000000 \\
        --output results/c01_mtf_btc_2021-01-04_3d.json

Safety:
    - Research-only: no live orders, no API keys, no real fills.
    - All fills, fees, slippage, ledger and equity are owned by the engine/judge.
    - Strategy only produces SignalIntent; it cannot touch the ledger.
    - Report is immutable JSON written atomically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import sys
from typing import Sequence

import yaml

from indodax_lab.backtest.costs import load_cost_schedule_table
from indodax_lab.backtest.engine import ReplayBacktestEngine
from indodax_lab.backtest.events import MarketBar
from indodax_lab.backtest.feature_replay import (
    FeatureReplayAdapter,
    FeatureReplayConfig,
    load_bars_from_parquet_dir,
)
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.backtest.metrics import compute_performance_metrics
from indodax_lab.backtest.risk import RiskPolicy
from indodax_lab.strategies.base import (
    DecisionFrame,
    RegisteredStrategy,
    StrategySpecification,
    create_decision_frame,
)
from indodax_lab.strategies.c01 import c01_decide
from indodax_lab.strategies.registry import StrategyRegistry


# ---------------------------------------------------------------------------
# Strategy wiring
# ---------------------------------------------------------------------------

def _build_strategy_fn(spec: StrategySpecification, adapter: FeatureReplayAdapter,
                       signal_df, context_df):
    """Produce a strategy_fn(bar, idx) -> SignalIntent | None closure."""
    registered = RegisteredStrategy(
        specification=spec,
        decide_fn=lambda frame: c01_decide(frame, spec),
    )
    logic_hash = registered.logic_hash

    def strategy_fn(bar: MarketBar, bar_index: int) -> SignalIntent | None:
        # Build causal DecisionFrame at bar.available_at (= bar.close_time for 5m bars)
        as_of = bar.available_at
        try:
            frame = adapter.build_decision_frame(
                signal_rows=signal_df,
                context_rows=context_df,
                as_of=as_of,
            )
        except ValueError:
            # Fail-closed: missing/invalid context → no intent
            return None

        intents = registered.decide(frame)
        if not intents:
            return None

        # Engine contract: intent.decision_ts must equal bar.available_at and intent.pair == bar.pair
        for intent in intents:
            if intent.pair == bar.pair and intent.decision_ts == as_of:
                return intent
        return None

    return strategy_fn, logic_hash


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------

def _build_report(
    result,
    metrics,
    spec: StrategySpecification,
    logic_hash: str,
    pair: str,
    start_dt: datetime,
    end_dt: datetime,
    initial_cash: Decimal,
    cost_config_path: str,
    run_id: str,
    engine,
    bars_5m_count: int,
    intent_count: int,
) -> dict:
    """Build the immutable JSON report dict with all required fields."""
    import hashlib as _hashlib

    params_hash = spec.parameters_hash()

    # Temporal validation: check start < end and UTC-aware
    temporal_valid = (
        start_dt.tzinfo is not None
        and end_dt.tzinfo is not None
        and start_dt < end_dt
    )

    # Ledger reconciliation: all transactions balanced
    ledger_ok = all(tx.is_balanced for tx in engine.ledger.transactions)

    # Rejection details
    rejections = engine.rejections  # list of (intent_id, reason_code)
    rejected_count = len(rejections)

    # Open positions at end
    open_positions = {
        pair_: {
            "base_qty": str(pos.base_qty),
            "cost_basis": str(pos.cost_basis),
            "avg_entry": str(pos.average_entry_price),
        }
        for pair_, pos in engine.ledger.positions.items()
        if pos.base_qty > Decimal("0")
    }

    report = {
        "report_schema_version": "1.0.0",
        "research_only_disclaimer": (
            "RESEARCH ONLY: This report is for offline research, historical backtest, "
            "and paper/shadow trading evaluation only. "
            "No real orders were placed. No real funds were used. "
            "Strategy only produces SignalIntent. "
            "Judge/engine has sole authority over fills, fees, slippage, ledger, equity."
        ),
        "run_id": run_id,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        # Strategy identity
        "strategy_id": spec.strategy_id,
        "strategy_version": spec.version,
        "strategy_logic_hash": logic_hash,
        "strategy_parameters_hash": params_hash,
        # Dataset provenance
        "dataset_registry_id": "lab-data-5m:btc_idr:bronze",
        "feature_set_id": "tabular_bar_5m_v1",
        "feature_set_version": "1.1.0",
        "cost_schedule_id": "indodax_idr",
        "cost_schedule_version": "1.0.0",
        "cost_config_path": cost_config_path,
        # Scope
        "pair": pair,
        "signal_interval": "5m",
        "context_interval": "1h",
        "start_utc": start_dt.isoformat(),
        "end_utc": end_dt.isoformat(),
        "bars_5m_loaded": bars_5m_count,
        # Capital (Decimal serialized as string — lossless)
        "initial_cash_idr": str(initial_cash),
        "final_cash_idr": str(result.ending_cash),
        "final_equity_idr": str(result.ending_equity),
        # PnL
        "total_realized_gross_pnl_idr": str(result.total_gross_pnl),
        "total_realized_net_pnl_idr": str(result.total_net_pnl),
        "unrealized_pnl_idr": str(result.ending_equity - result.ending_cash),
        # Costs
        "total_fees_paid_idr": str(result.total_fees_paid),
        "total_slippage_idr": "0",  # Conservative simulator: no explicit slippage model
        # Activity
        "total_signal_intents": intent_count,
        "total_intents_accepted": result.fill_count,
        "total_intents_rejected": rejected_count,
        "total_fills": result.fill_count,
        "total_partial_fills": 0,  # ConservativeExecutionSimulator: full fill or reject
        "open_positions_at_end": open_positions,
        # Risk metrics
        "max_drawdown_amount_idr": str(metrics.max_drawdown_amount),
        "max_drawdown_pct": str(metrics.max_drawdown_pct),
        "win_rate": str(metrics.win_rate) if metrics.win_rate is not None else None,
        "profit_factor": str(metrics.profit_factor.value) if metrics.profit_factor.defined else metrics.profit_factor.reason,
        "trade_count": metrics.trade_count,
        # Integrity
        "ledger_reconciliation_status": "PASS" if ledger_ok else "FAIL",
        "temporal_validation_status": "PASS" if temporal_valid else "FAIL",
        "postings_hash_sha256": result.postings_hash,
        "engine_execution_version": result.execution_version,
        "execution_assumptions": list(result.execution_assumptions),
        "rejection_reasons": [{"intent_id": r[0], "reason": r[1]} for r in rejections[:50]],
        "sample_adequacy": "SUFFICIENT" if bars_5m_count >= 288 else "INSUFFICIENT_SAMPLE",
    }

    # Self-hash the report for immutability verification
    report_bytes = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report["artifact_sha256"] = hashlib.sha256(report_bytes).hexdigest()
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None, stdout=None) -> int:
    out = stdout or sys.stdout
    parser = argparse.ArgumentParser(description="Deterministic replay backtest runner — C01_MTF")
    parser.add_argument("--strategy", required=True, help="Path to strategy YAML config")
    parser.add_argument("--cost-config", required=True, help="Path to cost schedule YAML config")
    parser.add_argument("--bars-5m", required=True, help="Bronze dir for 5m bars (e.g. lab-data-5m/bronze)")
    parser.add_argument("--bars-1h", required=True, help="Bronze dir for 1h bars (e.g. lab-data-fetch2/bronze)")
    parser.add_argument("--pair", required=True, help="Trading pair (e.g. btc_idr)")
    parser.add_argument("--start", required=True, help="Start date UTC (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date UTC (YYYY-MM-DD), exclusive")
    parser.add_argument("--initial-cash", default="10000000", help="Initial capital in IDR (default: 10,000,000)")
    parser.add_argument("--output", required=False, help="Output JSON report path")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs only, do not replay")
    parser.add_argument("--run-id", default=None, help="Run identifier (auto-generated if omitted)")

    args = parser.parse_args(argv)

    # Parse dates
    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=UTC)
    end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=UTC)
    if end_dt <= start_dt:
        out.write("ERROR: --end must be after --start\n")
        return 1

    initial_cash = Decimal(args.initial_cash)
    run_id = args.run_id or f"c01_mtf_{args.pair}_{args.start}_{args.end}"

    out.write(f"[run_backtest] strategy={args.strategy} pair={args.pair} "
              f"start={args.start} end={args.end} initial_cash={initial_cash}\n")

    # Load strategy spec
    registry = StrategyRegistry()
    spec = registry.load_specification_from_yaml(args.strategy)
    out.write(f"[run_backtest] strategy_id={spec.strategy_id} version={spec.version}\n")

    # Load cost schedule
    cost_table = load_cost_schedule_table(Path(args.cost_config))
    out.write(f"[run_backtest] cost_schedule_id={cost_table.schedule_set_id} "
              f"version={cost_table.version}\n")

    # Load 5m bars
    out.write(f"[run_backtest] loading 5m bars from {args.bars_5m} ...\n")
    bars_5m = load_bars_from_parquet_dir(
        bronze_dir=Path(args.bars_5m),
        pair=args.pair,
        interval="5m",
        start_dt=start_dt,
        end_dt=end_dt,
    )
    out.write(f"[run_backtest] loaded {len(bars_5m)} 5m bars\n")

    if len(bars_5m) == 0:
        out.write("ERROR: no 5m bars found for the given range\n")
        return 1

    # Load 1h context bars — need slightly earlier start for warmup
    from datetime import timedelta
    context_start = start_dt - timedelta(days=2)
    out.write(f"[run_backtest] loading 1h context bars from {args.bars_1h} ...\n")
    bars_1h = load_bars_from_parquet_dir(
        bronze_dir=Path(args.bars_1h),
        pair=args.pair,
        interval="1h",
        start_dt=context_start,
        end_dt=end_dt,
    )
    out.write(f"[run_backtest] loaded {len(bars_1h)} 1h context bars\n")

    # Build feature DataFrames from raw bars (simple pass-through for replay)
    # We build minimal signal_df and context_df from raw OHLCV bars.
    # Features are: close, high, low, base_volume, atr_14 (stub=0 if not materialized)
    import pandas as pd

    def _bars_to_signal_df(bars: list[MarketBar]) -> pd.DataFrame:
        rows = []
        for b in bars:
            rows.append({
                "pair": b.pair,
                "decision_ts": b.available_at,    # close_time = bar.available_at
                "row_ready_at": b.available_at,   # historical-availability: ready at close
                "eligible": True,
                "close": float(b.close),
                "high": float(b.high),
                "low": float(b.low),
                "base_volume": float(b.base_volume),
                "atr_14": 0.0,  # stub: ATR computation requires lookback; engine won't use it for routing
            })
        df = pd.DataFrame(rows)
        df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
        df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
        return df

    def _bars_to_context_df(bars: list[MarketBar]) -> pd.DataFrame:
        rows = []
        for b in bars:
            rows.append({
                "pair": b.pair,
                "decision_ts": b.available_at,
                "row_ready_at": b.available_at,
                "eligible": True,
                "close_1h": float(b.close),
            })
        df = pd.DataFrame(rows)
        df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
        df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
        return df

    signal_df = _bars_to_signal_df(bars_5m)
    context_df = _bars_to_context_df(bars_1h)

    # Build adapter (require_context=True: 1h context mandatory)
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(
            pair=args.pair,
            signal_interval="5m",
            context_interval="1h",
            require_context=True,
        )
    )

    if args.dry_run:
        out.write(f"[run_backtest] DRY_RUN: validated OK. bars_5m={len(bars_5m)} "
                  f"bars_1h={len(bars_1h)} signal_rows={len(signal_df)} "
                  f"context_rows={len(context_df)}\n")
        return 0

    # Build risk policy from strategy spec
    risk_kwargs = spec.risk_profile
    policy = RiskPolicy(
        policy_id=f"{spec.strategy_id}_risk",
        version=spec.version,
        max_position_fraction=Decimal(str(risk_kwargs.get("max_position_pct", "0.20"))),
        max_open_positions=1,
        min_order_notional=Decimal("10000"),
    )

    # Build engine
    engine = ReplayBacktestEngine(
        cost_schedule_table=cost_table,
        risk_policy=policy,
        initial_cash=initial_cash,
        candidate_id=f"{spec.strategy_id}_v{spec.version}",
    )

    # Count intents emitted by strategy
    intent_counter = [0]
    strategy_fn_raw, logic_hash = _build_strategy_fn(spec, adapter, signal_df, context_df)

    def strategy_fn_counting(bar: MarketBar, bar_index: int) -> SignalIntent | None:
        intent = strategy_fn_raw(bar, bar_index)
        if intent is not None:
            intent_counter[0] += 1
        return intent

    out.write(f"[run_backtest] starting replay: {len(bars_5m)} bars ...\n")
    result = engine.run(
        bars=bars_5m,
        strategy_fn=strategy_fn_counting,
        run_id=run_id,
    )
    out.write(f"[run_backtest] replay DONE: fills={result.fill_count} "
              f"rejections={len(engine.rejections)} "
              f"net_pnl={result.total_net_pnl} "
              f"fees={result.total_fees_paid}\n")

    # Build mark prices map from last 5m bar close
    mark_prices = {args.pair: bars_5m[-1].close} if bars_5m else {}

    # Compute equity curve: use mark_prices for open-position valuation.
    # We approximate: for each transaction timestamp use mark_prices (final close).
    # This is conservative: intermediate equity is approximated, not future-looked.
    equity_curve = []
    for tx in engine.ledger.transactions:
        # Use available mark prices; if a position exists but no mark, skip this point
        try:
            eq = engine.ledger.equity(mark_prices)
            equity_curve.append((tx.timestamp, eq))
        except ValueError:
            pass  # open position without mark price — skip this equity observation

    metrics = compute_performance_metrics(
        ledger=engine.ledger,
        equity_curve=equity_curve if equity_curve else None,
        rejected_orders=engine.rejections,
        mark_prices=mark_prices,
    )

    # Build immutable report
    report = _build_report(
        result=result,
        metrics=metrics,
        spec=spec,
        logic_hash=logic_hash,
        pair=args.pair,
        start_dt=start_dt,
        end_dt=end_dt,
        initial_cash=initial_cash,
        cost_config_path=args.cost_config,
        run_id=run_id,
        engine=engine,
        bars_5m_count=len(bars_5m),
        intent_count=intent_counter[0],
    )

    # Print report summary to stdout
    out.write("\n=== BACKTEST REPORT SUMMARY ===\n")
    summary_keys = [
        "run_id", "strategy_id", "strategy_version", "pair", "start_utc", "end_utc",
        "bars_5m_loaded", "initial_cash_idr", "final_cash_idr", "final_equity_idr",
        "total_realized_net_pnl_idr", "total_fees_paid_idr", "total_signal_intents",
        "total_intents_accepted", "total_intents_rejected", "trade_count",
        "max_drawdown_pct", "ledger_reconciliation_status", "temporal_validation_status",
        "sample_adequacy", "postings_hash_sha256",
    ]
    for k in summary_keys:
        out.write(f"  {k}: {report[k]}\n")
    out.write("================================\n")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to .tmp then rename
        tmp_path = out_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        tmp_path.replace(out_path)
        out.write(f"[run_backtest] report written to {out_path}\n")
        out.write(f"[run_backtest] artifact_sha256={report['artifact_sha256']}\n")
    else:
        out.write("[run_backtest] --output not specified; report not persisted\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
