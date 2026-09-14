"""Deterministic replay judge and market event simulation engine (SIM-03)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import hashlib
from pathlib import Path
from typing import Callable, Sequence

from indodax_lab.backtest.costs import CostScheduleTable
from indodax_lab.backtest.events import ExecutionStatus, MarketBar, SignalIntent
from indodax_lab.backtest.execution import ConservativeExecutionSimulator
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.backtest.result import BacktestResult
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy


class ReplayBacktestEngine:
    """Deterministic replay engine ensuring reproducible execution, postings, and metrics."""

    def __init__(
        self,
        cost_schedule_table: CostScheduleTable,
        risk_policy: RiskPolicy,
        initial_cash: Decimal = Decimal("500000"),
        candidate_id: str = "default_candidate",
        valuation_currency: str = "IDR",
    ) -> None:
        self.candidate_id = candidate_id
        self.initial_cash = Decimal(str(initial_cash))
        self.valuation_currency = valuation_currency
        self.cost_schedule_table = cost_schedule_table
        self.risk_policy = risk_policy

        self.ledger = ResearchLedger(
            initial_cash=self.initial_cash,
            valuation_currency=self.valuation_currency,
        )
        self.risk_manager = PortfolioRiskManager(
            policy=self.risk_policy,
            initial_equity=self.initial_cash,
            start_time=datetime(2024, 1, 1, tzinfo=UTC),
        )
        self.simulator = ConservativeExecutionSimulator(
            cost_schedule_table=self.cost_schedule_table,
        )

    def run(
        self,
        bars: Sequence[MarketBar],
        strategy_fn: Callable[[MarketBar, int], SignalIntent | None],
        run_id: str = "run-001",
    ) -> BacktestResult:
        """Execute deterministic simulation across a causal sequence of market bars."""
        if not bars:
            raise ValueError("EMPTY_BARS_SEQUENCE")

        # Stable event sort by (open_time, pair) to ensure identical replay order
        sorted_bars = sorted(bars, key=lambda b: (b.open_time, b.pair))
        start_time = sorted_bars[0].open_time
        end_time = sorted_bars[-1].close_time

        pending_intents: list[SignalIntent] = []
        fill_count = 0

        for idx, bar in enumerate(sorted_bars):
            # 1. Process pending orders at next-open on this bar
            remaining_pending = []
            for intent in pending_intents:
                if intent.pair == bar.pair:
                    exec_res = self.simulator.simulate_execution(intent, bar)
                    if exec_res.status in (ExecutionStatus.FILLED, ExecutionStatus.PARTIAL):
                        if exec_res.fill is not None:
                            self.ledger.process_fill(exec_res.fill)
                            fill_count += 1
                else:
                    remaining_pending.append(intent)
            pending_intents = remaining_pending

            # 2. Strategy produces intent based on current closed bar
            intent = strategy_fn(bar, idx)
            if intent is not None:
                # 3. Risk assessment on current equity and positions
                mark_prices = {bar.pair: bar.close}
                curr_equity = self.ledger.equity(mark_prices=mark_prices)
                risk_res = self.risk_manager.assess_order(
                    intent=intent,
                    current_equity=curr_equity,
                    current_positions=self.ledger.positions,
                    mark_prices=mark_prices,
                    evaluation_time=bar.close_time,
                    available_cash=self.ledger.cash,
                )
                if risk_res.approved and risk_res.approved_qty > Decimal("0"):
                    # Approved intent queued for next-bar execution
                    approved_intent = intent.model_copy(
                        update={"desired_qty": risk_res.approved_qty}
                    )
                    pending_intents.append(approved_intent)

        # Final marking
        last_bar = sorted_bars[-1]
        ending_equity = self.ledger.equity(mark_prices={last_bar.pair: last_bar.close})

        # Compute deterministic postings hash
        hasher = hashlib.sha256()
        for tx in self.ledger.transactions:
            for p in tx.postings:
                entry = f"{tx.transaction_id}:{p.account}:{p.amount}:{p.currency}|"
                hasher.update(entry.encode("utf-8"))
        postings_hash = hasher.hexdigest()

        return BacktestResult(
            run_id=run_id,
            candidate_id=self.candidate_id,
            start_time=start_time,
            end_time=end_time,
            initial_cash=self.initial_cash,
            ending_cash=self.ledger.cash,
            ending_equity=ending_equity,
            total_net_pnl=self.ledger.total_net_pnl,
            total_gross_pnl=self.ledger.total_realized_gross_pnl,
            total_fees_paid=self.ledger.total_fees_paid,
            fill_count=fill_count,
            transaction_count=len(self.ledger.transactions),
            postings_hash=postings_hash,
            status="SUCCESS",
        )

    def run_and_publish(
        self,
        bars: Sequence[MarketBar],
        strategy_fn: Callable[[MarketBar, int], SignalIntent | None],
        output_path: Path,
        simulate_crash_before_publish: bool = False,
        run_id: str = "run-001",
    ) -> BacktestResult:
        """Run simulation and atomically publish result manifest."""
        res = self.run(bars=bars, strategy_fn=strategy_fn, run_id=run_id)

        # SIM-03-AC2: Crash sebelum publish tidak menghasilkan run sukses
        if simulate_crash_before_publish:
            raise RuntimeError("SIMULATED_CRASH_BEFORE_PUBLISH")

        res.save_json(output_path)
        return res
