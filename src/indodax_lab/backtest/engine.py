"""Deterministic replay judge and market event simulation engine (SIM-03)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Callable, Sequence

from indodax_lab.backtest.costs import CostScheduleTable, OrderRole, OrderSide, lookup_cost
from indodax_lab.backtest.events import ExecutionStatus, MarketBar
from indodax_lab.backtest.execution import ConservativeExecutionSimulator
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.backtest.ledger import ResearchLedger, Position
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

        sorted_bars = sorted((MarketBar.model_validate(b.model_dump()) for b in bars),
                             key=lambda b: (b.open_time, b.pair))
        start_time = sorted_bars[0].open_time
        end_time = max(b.available_at for b in sorted_bars)
        previous_close = {}
        for bar in sorted_bars:
            if bar.open_time < previous_close.get(bar.pair, bar.open_time):
                raise ValueError("OVERLAPPING_OR_DUPLICATE_PAIR_BARS")
            previous_close[bar.pair] = bar.close_time
        # Every run owns fresh cash, inventory, IDs and circuit-breaker history.
        self.ledger = ResearchLedger(self.initial_cash, self.valuation_currency, start_time)
        self.risk_manager = PortfolioRiskManager(self.risk_policy, self.initial_cash, start_time)
        self.rejections: list[tuple[str, str]] = []
        pending_intents: list[SignalIntent] = []
        barriers: dict[str, tuple[SignalIntent, datetime]] = {}
        marks: dict[str, Decimal] = {}
        mark_times: dict[str, datetime] = {}
        closed_bars: dict[str, MarketBar] = {}
        seen_intents: set[str] = set()
        fill_count = 0

        def size(intent, price, timestamp):
            if intent.role_preference == OrderRole.MAKER and intent.limit_price is None:
                self.rejections.append((intent.intent_id, "MAKER_LIMIT_REQUIRED"))
                return None, None
            schedule = lookup_cost(self.cost_schedule_table, market=self.simulator.market,
                side=intent.side, role=intent.role_preference,
                fee_basis_ts=(intent.decision_ts if intent.limit_price is not None else timestamp))
            positions = {pair: p.model_copy(deep=True) for pair, p in self.ledger.positions.items()}
            # Pending risk occupies position count and exposure, not just cash.
            for waiting in pending_intents:
                if (intent.side == OrderSide.BUY and waiting.intent_id != intent.intent_id
                        and waiting.side == OrderSide.BUY):
                    pos = positions.setdefault(waiting.pair, Position(pair=waiting.pair))
                    pos.base_qty += waiting.desired_qty
            prices = dict(marks)
            prices[intent.pair] = price
            result = self.risk_manager.assess_order(intent, self.ledger.equity(marks),
                positions, prices, timestamp, self.ledger.available_cash,
                estimated_fee_rate=schedule.total_rate, fee_precision=schedule.precision,
                quantity_precision=self.simulator.quantity_precision)
            if not result.approved:
                self.rejections.append((intent.intent_id, result.reason_code))
                return None, schedule
            if result.approved_notional < schedule.min_notional:
                self.rejections.append((intent.intent_id, "MIN_NOTIONAL_VIOLATION"))
                return None, schedule
            return intent.model_copy(update={"desired_qty": result.approved_qty}), schedule

        def execute(intent, event_bar):
            nonlocal fill_count
            # Shared ledger lock covers release, re-admission and posting together.
            with self.ledger.allocation_lock:
                self.ledger.release_reservation(intent.intent_id)
                maker = intent.role_preference == OrderRole.MAKER
                price = intent.limit_price if maker else event_bar.open
                ts = event_bar.available_at if maker else event_bar.open_time
                approved, _ = size(intent, price, ts)
                if approved is None:
                    return
                result = self.simulator.simulate_execution(approved, event_bar)
                if result.fill is None:
                    self.rejections.append((intent.intent_id, result.reason_code))
                    return
                self.ledger.process_fill(result.fill)
                fill_count += 1
                if intent.side == OrderSide.BUY:
                    if intent.pair not in barriers:
                        barriers[intent.pair] = (intent, result.fill.timestamp)
                elif self.ledger.positions[intent.pair].base_qty == 0:
                    barriers.pop(intent.pair, None)

        # Closed observations occur at availability; opens never see future OHLCV.
        events = sorted([(b.available_at, 0, b.pair, i, b) for i, b in enumerate(sorted_bars)]
                        + [(b.open_time, 1, b.pair, i, b) for i, b in enumerate(sorted_bars)])
        for timestamp, phase, _, idx, bar in events:
            price_ts = bar.close_time if phase == 0 else bar.open_time
            if price_ts >= mark_times.get(bar.pair, price_ts):
                marks[bar.pair] = bar.close if phase == 0 else bar.open
                mark_times[bar.pair] = price_ts
            self.risk_manager.observe_equity(self.ledger.equity(marks), timestamp)
            if phase == 1:
                prior = closed_bars.get(bar.pair)
                event_bar = bar
                if bar.open_liquidity_base_volume is None and prior is not None:
                    event_bar = bar.model_copy(update={
                        "open_liquidity_base_volume": prior.base_volume,
                        "open_liquidity_available_at": prior.available_at})
                eligible = [i for i in pending_intents if i.pair == bar.pair
                            and i.role_preference == OrderRole.TAKER and i.decision_ts <= timestamp]
                for order in eligible:
                    pending_intents.remove(order)
                    execute(order, event_bar)
                continue

            # Maker trade-through is completed-bar evidence, timestamped here.
            eligible = [i for i in pending_intents if i.pair == bar.pair
                        and i.role_preference == OrderRole.MAKER and i.decision_ts <= bar.open_time]
            for order in eligible:
                pending_intents.remove(order)
                execute(order, bar)
            held = barriers.get(bar.pair)
            if held is not None and held[1] <= bar.open_time:
                entry, _ = held
                stop_hit = entry.stop_loss is not None and bar.low <= entry.stop_loss
                target_hit = entry.take_profit is not None and bar.high >= entry.take_profit
                if stop_hit or target_hit:
                    # SL_FIRST. Delayed observation cannot earn a better stop/target price.
                    boundary = entry.stop_loss if stop_hit else entry.take_profit
                    exit_price = min(boundary, bar.close, bar.open) if stop_hit else min(boundary, bar.close)
                    pos = self.ledger.positions[bar.pair]
                    exit_intent = SignalIntent(intent_id=f"exit-{entry.intent_id}-{timestamp.isoformat()}",
                        decision_ts=timestamp, pair=bar.pair, side=OrderSide.SELL,
                        desired_qty=pos.base_qty, strategy_id=entry.strategy_id)
                    # Derived executable observation at availability, not a fabricated historical fill.
                    exit_event = MarketBar(pair=bar.pair, open_time=timestamp,
                        close_time=timestamp+timedelta(microseconds=1), open=exit_price,
                        high=exit_price, low=exit_price, close=exit_price,
                        base_volume=bar.base_volume, quote_volume=bar.quote_volume,
                        open_liquidity_base_volume=bar.base_volume,
                        open_liquidity_available_at=timestamp)
                    execute(exit_intent, exit_event)
            prior = closed_bars.get(bar.pair)
            if prior is None or bar.close_time > prior.close_time:
                closed_bars[bar.pair] = bar
            intent = strategy_fn(bar, idx)
            if intent is None:
                continue
            intent = SignalIntent.model_validate(intent.model_dump())
            if intent.decision_ts != timestamp or intent.pair != bar.pair:
                raise ValueError("STRATEGY_INTENT_NOT_AT_OBSERVATION_AVAILABILITY")
            if intent.intent_id in seen_intents:
                raise ValueError("DUPLICATE_INTENT_ID")
            seen_intents.add(intent.intent_id)
            with self.ledger.allocation_lock:
                approved, schedule = size(intent, intent.limit_price or marks[bar.pair], timestamp)
                if approved is not None:
                    if approved.side == OrderSide.BUY:
                        gross = approved.desired_qty * (approved.limit_price or marks[bar.pair])
                        fee = (gross * schedule.total_rate).quantize(Decimal(10) ** -schedule.precision)
                        self.ledger.reserve_cash(approved.intent_id, gross + fee)
                    pending_intents.append(approved)
        for intent in pending_intents:
            self.ledger.release_reservation(intent.intent_id)
            self.rejections.append((intent.intent_id, "END_OF_REPLAY_CANCELLED"))
        ending_equity = self.ledger.equity(mark_prices=marks)

        assumptions = (
            "prior_closed_volume_is_not_observed_depth",
            "maker_trade_through_proxy_no_queue_priority",
            "SL_FIRST_exit_at_observation_availability",
            "liquidity_max_age_one_bar_interval",
            f"quantity_precision={self.simulator.quantity_precision}",
            f"max_participation_rate={self.simulator.max_participation_rate}",
            f"require_trade_through_for_maker={self.simulator.require_trade_through_for_maker}",
        )
        # Canonical transactions bind time, pair and quantity as well as valued postings.
        hasher = hashlib.sha256()
        hasher.update(json.dumps({"execution_version": self.simulator.execution_version,
                                 "assumptions": assumptions}, sort_keys=True).encode("utf-8"))
        for tx in self.ledger.transactions:
            hasher.update(json.dumps(tx.model_dump(mode="json"), sort_keys=True,
                                     separators=(",", ":")).encode("utf-8"))
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
            execution_version=self.simulator.execution_version,
            execution_assumptions=assumptions,
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
