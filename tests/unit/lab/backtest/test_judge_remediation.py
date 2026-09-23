"""Audit regressions for cash admission and causal replay; offline literal fixtures."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from concurrent.futures import ThreadPoolExecutor
import socket

import pytest

from indodax_lab.backtest.costs import CostScheduleInterval, CostScheduleTable
from indodax_lab.backtest.engine import ReplayBacktestEngine
from indodax_lab.backtest.events import MarketBar, SignalIntent
from indodax_lab.backtest.execution import ConservativeExecutionSimulator
from indodax_lab.backtest.ledger import ResearchLedger, Position
from indodax_lab.backtest.orders import Fill
from indodax_lab.backtest.risk import RiskPolicy, PortfolioRiskManager
from indodax_lab.paper.portfolio import SharedCapitalLedger, PaperOrderIntent

TS = datetime(2024, 6, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("EXTERNAL_NETWORK_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def costs():
    return CostScheduleTable(schedule_set_id="fixture", version="1", intervals=tuple(
        CostScheduleInterval(schedule_id=f"{side}-{role}", market="spot_idr", side=side,
            role=role, valid_from=TS, service_fee_rate="0.01", tax_rate="0",
            exchange_fee_rate="0", min_notional="1", precision=2, sources=("fake",),
            evidence_verified=True)
        for side in ("buy", "sell") for role in ("taker", "maker")))


def policy(**kwargs):
    return RiskPolicy(policy_id="fixture", version="1", min_order_notional="1",
                      max_position_fraction="1", **kwargs)


def bar(hour, pair="btc_idr", price="100", **kwargs):
    p = D(price)
    data = dict(pair=pair, open_time=TS+timedelta(hours=hour),
                close_time=TS+timedelta(hours=hour+1), open=p, high=p, low=p,
                close=p, base_volume="100", quote_volume="10000")
    data.update(kwargs)
    return MarketBar(**data)


def intent(b, key="buy", qty="6", **kwargs):
    data = dict(intent_id=key, decision_ts=b.close_time, pair=b.pair,
                side="buy", desired_qty=qty)
    data.update(kwargs)
    return SignalIntent(**data)


@pytest.mark.parametrize("field,value", [("max_position_fraction", "1.1"),
    ("max_account_leverage", "2"), ("max_daily_loss_fraction", "1.1"),
    ("max_open_positions", 0)])
def test_invalid_risk_policy_fails_closed(field, value):
    data = dict(policy_id="p", version="1")
    data[field] = value
    with pytest.raises(ValueError):
        RiskPolicy(**data)


@pytest.mark.parametrize("factory", [ResearchLedger, SharedCapitalLedger])
@pytest.mark.parametrize("cash", ["-1", "NaN", "Infinity"])
def test_invalid_initial_cash(factory, cash):
    with pytest.raises(ValueError):
        factory(initial_cash=D(cash))


def test_halted_manager_allows_safe_sell():
    manager = PortfolioRiskManager(policy(), D("1000"), TS, is_halted=True)
    args = dict(current_equity=D("900"), current_positions={"btc_idr":
                Position(pair="btc_idr", base_qty="2")}, mark_prices={"btc_idr":D("100")},
                evaluation_time=TS+timedelta(hours=1), available_cash=D("700"))
    assert not manager.assess_order(intent(bar(0)), **args).approved
    assert manager.assess_order(intent(bar(0), side="sell", qty="2"), **args).approved


def test_invalid_mark_does_not_change_halt_state():
    manager = PortfolioRiskManager(policy(), D("1000"), TS)
    before = manager.to_dict()
    result = manager.assess_order(intent(bar(0)), D("100"), {}, {"btc_idr": D("NaN")},
                                  TS+timedelta(days=1), D("100"))
    assert not result.approved
    assert manager.to_dict() == before


def test_pending_buys_share_reserved_cash_and_release():
    engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
    bars = [bar(0), bar(0, "eth_idr"), bar(1), bar(1, "eth_idr")]
    result = engine.run(bars, lambda b, i: intent(b, key=b.pair) if i < 2 else None)
    assert result.fill_count == 2
    assert D("0") <= result.ending_cash < D("1")
    assert not engine.ledger.reservations


def test_gap_up_rechecks_actual_fee_inclusive_cash():
    engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
    result = engine.run([bar(0), bar(1, price="200")],
                        lambda b, i: intent(b, qty="10") if i == 0 else None)
    assert result.fill_count == 1
    assert D("0") <= result.ending_cash < D("1")
    assert engine.ledger.positions["btc_idr"].base_qty <= D("4.95049505")


@pytest.mark.parametrize("both", [False, True])
def test_exit_is_independent_and_never_backdated(both):
    engine = ReplayBacktestEngine(costs(), policy(max_drawdown_halt_fraction="0.01"), initial_cash=D("1000"))
    bars = [bar(0), bar(1, low="80", high="120" if both else "100", close="85")]
    result = engine.run(bars, lambda b, i: intent(b, qty="2", stop_loss="90",
                           take_profit="110") if i == 0 else None)
    assert result.fill_count == 2
    assert engine.ledger.positions["btc_idr"].base_qty == 0
    sell = engine.ledger.transactions[-1]
    assert sell.timestamp >= bars[1].close_time
    # Buy 200 + 2 fee; conservative observed close exit 170 - 1.70 fee.
    assert result.ending_cash == D("966.30")
    assert engine.risk_manager.is_halted


def test_open_fill_ignores_outcome_volume_and_extrema():
    def run(outcome):
        engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
        engine.run([bar(0), outcome], lambda b, i: intent(b) if i == 0 else None)
        return engine.ledger.transactions[1:]
    assert run(bar(1)) == run(bar(1, high="1000", low="1", base_volume="0.001"))


def test_maker_bar_evidence_is_not_backdated():
    b = bar(1, low="80")
    result = ConservativeExecutionSimulator(costs()).simulate_execution(
        intent(bar(0), qty="2", role_preference="maker", limit_price="90"), b)
    assert result.fill is not None
    assert result.fill.timestamp >= b.close_time


def test_missing_open_liquidity_is_rejected():
    result = ConservativeExecutionSimulator(costs()).simulate_execution(intent(bar(0)), bar(1))
    assert result.fill is None
    assert result.reason_code == "MISSING_CAUSAL_LIQUIDITY"


def test_same_engine_replay_resets_all_state():
    engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
    strategy = lambda b, i: intent(b) if i == 0 else None
    a = engine.run([bar(0), bar(1)], strategy)
    b = engine.run([bar(0), bar(1)], strategy)
    assert a == b


def test_shared_allocations_are_serialized(monkeypatch):
    import indodax_lab.paper.portfolio as portfolio
    from time import sleep
    real = portfolio.PaperPosition
    def slow_position(**kwargs):
        sleep(0.02)
        return real(**kwargs)
    monkeypatch.setattr(portfolio, "PaperPosition", slow_position)
    ledger = SharedCapitalLedger(initial_cash=D("1000"))
    intents = [PaperOrderIntent(event_id=str(i), candidate_id=str(i), pair="btc_idr",
                                allocated_cash="600", entry_price="100") for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(ledger.process_intent, intents))
    assert sum(r.approved for r in results) == 1
    assert ledger.available_cash == D("400")


def test_ledger_revalidates_forged_fee_without_mutation():
    ledger = ResearchLedger(initial_cash=D("1000"))
    fill = Fill(fill_id="f", order_id="o", event_id="e", pair="btc_idr", side="buy",
                qty="1", price="100", fees="1", timestamp=TS)
    with pytest.raises(ValueError):
        ledger.process_fill(fill.model_copy(update={"fees": D("-50")}))
    assert ledger.cash == D("1000")
    assert len(ledger.transactions) == 1


def test_execution_identity_discloses_proxy_and_binds_event_time():
    def run(delay):
        engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
        bars = [bar(0), bar(1+delay)]
        return engine.run(bars, lambda b, i: intent(b) if i == 0 else None)
    first = run(0)
    assert first.to_dict().get("execution_version") == "causal-bar-proxy-v2"
    assert "prior_closed_volume_is_not_observed_depth" in first.to_dict()["execution_assumptions"]
    assert first.postings_hash != run(1).postings_hash


def test_reservations_cancel_idempotently_and_protect_other_orders():
    ledger = ResearchLedger(initial_cash=D("1000"))
    ledger.reserve_cash("pending", D("800"))
    assert sum(ledger.reservations.values()) <= ledger.cash
    fill = Fill(fill_id="f", order_id="o", event_id="e", pair="btc_idr", side="buy",
                qty="3", price="100", fees="3", timestamp=TS)
    with pytest.raises(ValueError):
        ledger.process_fill(fill)
    assert ledger.release_reservation("pending") == D("800")
    assert ledger.release_reservation("pending") == 0
    ledger.process_fill(fill)
    assert ledger.cash == D("697")


@pytest.mark.parametrize("changes", [dict(is_closed=False), dict(open="0",low="0"),
    dict(available_at=TS), dict(available_at=datetime(2024,6,1)),
    dict(open_liquidity_base_volume="100"),
    dict(open_liquidity_base_volume="100", open_liquidity_available_at=TS+timedelta(hours=2))])
def test_bar_rejects_partial_and_noncausal_evidence(changes):
    with pytest.raises(ValueError):
        bar(1, **changes)


def test_stale_open_liquidity_is_rejected():
    b = bar(48, open_liquidity_base_volume="100", open_liquidity_available_at=TS)
    result = ConservativeExecutionSimulator(costs()).simulate_execution(intent(bar(47)), b)
    assert result.fill is None
    assert result.reason_code == "STALE_CAUSAL_LIQUIDITY"


def test_quantity_precision_never_rounds_minimum_up():
    simulator = ConservativeExecutionSimulator(costs(), quantity_precision=2)
    b = bar(1, price="3", open_liquidity_base_volume="100", open_liquidity_available_at=TS)
    result = simulator.simulate_execution(intent(bar(0), qty="0.334"), b)
    assert result.fill is None  # 0.33 * 3 = 0.99 is below literal fixture minimum 1.


def test_delayed_observation_cannot_supply_open_liquidity():
    engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
    delayed = bar(0, available_at=TS+timedelta(minutes=90))
    seen = []
    def strategy(b, i):
        seen.append((i, b.available_at))
        return intent(b, decision_ts=b.available_at) if i == 0 else None
    result = engine.run([delayed, bar(1), bar(2)], strategy)
    assert result.fill_count == 1
    assert engine.ledger.transactions[1].timestamp == TS+timedelta(hours=2)
    assert seen[0][1] == TS+timedelta(minutes=90)


def test_open_pair_never_uses_future_other_pair_close():
    def run(future_price):
        engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
        long_eth = bar(0, "eth_idr", close_time=TS+timedelta(hours=4),
                       close=future_price, high=future_price)
        bars = [bar(0), long_eth, bar(1), bar(2), bar(3)]
        result = engine.run(bars, lambda b, i: intent(b, qty="2") if i == 0 else None)
        return engine.ledger.transactions[1:]
    assert run("100") == run("10000")


def test_rejected_and_end_of_run_pending_orders_release_cash():
    engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
    engine.run([bar(0, base_volume="0"), bar(1)], lambda b, i: intent(b, key=str(i)))
    assert engine.ledger.cash == D("1000")
    assert not engine.ledger.reservations
    assert {reason for _, reason in engine.rejections} == {"INSUFFICIENT_DEPTH", "END_OF_REPLAY_CANCELLED"}


def test_maker_without_limit_rejects_without_crashing():
    engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
    result = engine.run([bar(0), bar(1)], lambda b, i:
        intent(b, role_preference="maker") if i == 0 else None)
    assert result.fill_count == 0
    assert ("buy", "MAKER_LIMIT_REQUIRED") in engine.rejections


def test_risk_position_cap_includes_rounded_fee_equity_loss():
    manager = PortfolioRiskManager(RiskPolicy(policy_id="p", version="1",
        max_position_fraction="0.5", min_order_notional="1"), D("1000"), TS)
    result = manager.assess_order(intent(bar(0), qty="10"), D("1000"), {},
        {"btc_idr":D("100")}, TS, D("1000"), estimated_fee_rate=D("0.01"), fee_precision=0)
    actual_fee = (result.approved_notional * D("0.01")).quantize(D("1"))
    assert result.approved_notional <= (D("1000") - actual_fee) * D("0.5")


def test_peak_and_drawdown_are_observed_without_strategy_intents():
    engine = ReplayBacktestEngine(costs(), policy(), initial_cash=D("1000"))
    bars = [bar(0), bar(1), bar(2, price="200"), bar(3, price="80"), bar(4, price="80")]
    def strategy(b, i):
        return intent(b, key=str(i), qty="2") if i in (0, 3) else None
    result = engine.run(bars, strategy)
    assert result.fill_count == 1
    assert engine.risk_manager.is_halted
    assert ("3", "CIRCUIT_BREAKER_DRAWDOWN_HALT") in engine.rejections


def test_actual_fill_rechecks_new_cost_schedule():
    boundary = TS + timedelta(hours=2)
    intervals = []
    for interval in costs().intervals:
        intervals.append(interval.model_copy(update={"valid_to": boundary}))
        intervals.append(interval.model_copy(update={"schedule_id":interval.schedule_id+"-new",
            "valid_from":boundary, "service_fee_rate":D("0.5")}))
    table = CostScheduleTable(schedule_set_id="changed", version="2", intervals=tuple(intervals))
    engine = ReplayBacktestEngine(table, policy(), initial_cash=D("1000"))
    result = engine.run([bar(0), bar(2)], lambda b, i: intent(b, qty="9") if i == 0 else None)
    assert result.fill_count == 1
    assert result.ending_cash == D("0.01000000")
    assert result.total_fees_paid == D("333.33")
    assert not engine.ledger.reservations


def test_research_ledger_serializes_competing_fills(monkeypatch):
    import indodax_lab.backtest.ledger as ledger_module
    from time import sleep
    real = ledger_module.LedgerTransaction
    def slow_transaction(**kwargs):
        sleep(0.02)
        return real(**kwargs)
    ledger = ResearchLedger(initial_cash=D("1000"))
    monkeypatch.setattr(ledger_module, "LedgerTransaction", slow_transaction)
    fills = [Fill(fill_id=str(i), order_id=str(i), event_id=str(i), pair="btc_idr",
        side="buy", qty="6", price="100", fees="6", timestamp=TS) for i in range(2)]
    def process(fill):
        try:
            ledger.process_fill(fill)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(process, fills)) == 1
    assert ledger.cash == D("394")
    assert ledger.positions["btc_idr"].base_qty == D("6")
    assert len(ledger.transactions) == 2
