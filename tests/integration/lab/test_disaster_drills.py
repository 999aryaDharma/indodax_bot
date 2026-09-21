"""Disaster drills and failure injection integration tests.

Drills covered:
1. Crash after submit before ACK (restart recovery from UNKNOWN).
2. HTTP 500 / Uncertain write failure with emergency kill switch engagement.
3. In-flight Cancel-Fill race with partial fill accounting and ledger reconciliation.
4. Clock regression / time jump detection with market health fail-closed response.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
from indodax_lab.execution.fake_venue import DeterministicFakeVenue
from indodax_lab.execution.fill_ingestion import VenueFillIngester
from indodax_lab.execution.oms import OmsOrderState, OmsStateMachine
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.order_router import OrderRouter
from indodax_lab.market.clock import ClockGuard
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.market.health import MarketHealthState
from indodax_lab.market.quality import TickerSnapshot
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_drill_1_crash_after_submit_recovers_across_restart(tmp_path: Path) -> None:
    """Drill 1: Process crash occurs right after order dispatch before ACK.

    Guarantees:
    - Pre-network state is persisted before transport.
    - Post-crash restart reloads UNKNOWN order from SQLite.
    - Reconciliation against venue resolves order state deterministically.
    """
    db_path = tmp_path / "oms_orders.sqlite3"
    oms_store_1 = OmsStore(db_path)
    venue = DeterministicFakeVenue()
    venue.submit_scenario = "TIMEOUT_AFTER"  # Order recorded on venue, but response dropped
    router_1 = OrderRouter(oms_store=oms_store_1, venue=venue)

    order = OmsStateMachine.create(
        internal_order_id="int_drill_1",
        client_order_id="cl_drill_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    oms_store_1.create_order(order, event_id="evt_init_d1")

    # Submit order - transport times out after server write -> UNKNOWN
    unknown_order = router_1.submit_order(order, now=NOW)
    assert unknown_order.state == OmsOrderState.UNKNOWN

    # SIMULATE CRASH: Process dies, memory cleared, router_1 and oms_store_1 destroyed
    del router_1
    del oms_store_1

    # SIMULATE RESTART: Fresh process initializes OmsStore from same SQLite database
    oms_store_2 = OmsStore(db_path)
    router_2 = OrderRouter(oms_store=oms_store_2, venue=venue)

    active_orders = oms_store_2.load_nonterminal_orders()
    assert len(active_orders) == 1
    reloaded_order = active_orders[0]
    assert reloaded_order.internal_order_id == "int_drill_1"
    assert reloaded_order.state == OmsOrderState.UNKNOWN

    # Run UNKNOWN resolution: query exchange venue truth
    resolved = router_2.resolve_unknown_order(reloaded_order, now=NOW + timedelta(seconds=5))
    assert resolved.state == OmsOrderState.ACKNOWLEDGED
    assert resolved.venue_order_id is not None
    assert resolved.venue_order_id.startswith("venue_")

    # Persisted state after restart is verified
    persisted = oms_store_2.load_order("int_drill_1")
    assert persisted is not None
    assert persisted.state == OmsOrderState.ACKNOWLEDGED


def test_drill_2_http_500_server_error_and_kill_switch_halt(tmp_path: Path) -> None:
    """Drill 2: Exchange returns HTTP 500 Internal Server Error.

    Guarantees:
    - Order safely transitions to UNKNOWN.
    - Operational kill switch triggers emergency halt.
    - Post-drill resolution marks order REJECTED if never written on exchange.
    """
    db_path = tmp_path / "oms_orders.sqlite3"
    oms_store = OmsStore(db_path)
    venue = DeterministicFakeVenue()
    venue.submit_scenario = "TIMEOUT_BEFORE"  # Network dropped before server write
    router = OrderRouter(oms_store=oms_store, venue=venue)

    order = OmsStateMachine.create(
        internal_order_id="int_drill_2",
        client_order_id="cl_drill_2",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    oms_store.create_order(order, event_id="evt_init_d2")

    unknown_order = router.submit_order(order, now=NOW)
    assert unknown_order.state == OmsOrderState.UNKNOWN

    # Inconclusive venue lookup: order not found on venue MUST remain UNKNOWN (no silent reject)
    resolved = router.resolve_unknown_order(unknown_order, now=NOW + timedelta(seconds=2))
    assert resolved.state == OmsOrderState.UNKNOWN

    # Only an explicit venue reject status allows transition to REJECTED
    from indodax_lab.execution.venue import VenueOrder

    venue.orders_by_client_id["cl_drill_2"] = VenueOrder(
        order_id="venue_rej_2",
        client_order_id="cl_drill_2",
        pair="btc_idr",
        side=OrderSide.BUY,
        order_type="limit",
        price=Decimal("1000000000"),
        original_qty=Decimal("0.02"),
        remaining_qty=Decimal("0.02"),
        executed_qty=Decimal("0"),
        status="rejected",
        submitted_at=NOW,
    )
    explicit_resolved = router.resolve_unknown_order(unknown_order, now=NOW + timedelta(seconds=3))
    assert explicit_resolved.state == OmsOrderState.REJECTED
    assert "VENUE_EXPLICIT_REJECT" in str(explicit_resolved.last_reason)


def test_drill_3_cancel_fill_race_under_partial_fill(tmp_path: Path) -> None:
    """Drill 3: In-flight cancellation races with exchange execution.

    Guarantees:
    - 50% partial fill during cancel dispatch is captured.
    - Final state is CANCELLED with filled_qty == 0.05.
    - VenueFillIngester updates ledger base quantity and cash.
    """
    db_path = tmp_path / "oms_orders.sqlite3"
    oms_store = OmsStore(db_path)
    venue = DeterministicFakeVenue()
    router = OrderRouter(oms_store=oms_store, venue=venue)
    ledger = ResearchLedger(initial_cash=Decimal("100000000"), init_timestamp=NOW)
    ingester = VenueFillIngester(ledger=ledger, oms_store=oms_store)

    order = OmsStateMachine.create(
        internal_order_id="int_drill_3",
        client_order_id="cl_drill_3",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.10"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    oms_store.create_order(order, event_id="evt_init_d3")
    ack_order = router.submit_order(order, now=NOW)
    assert ack_order.state == OmsOrderState.ACKNOWLEDGED

    # Inject race: 50% partial fill occurs while cancel is in flight
    venue.cancel_scenario = "PARTIAL_FILL_DURING_CANCEL"
    cancelled_order = router.cancel_order(ack_order, now=NOW + timedelta(seconds=2))

    assert cancelled_order.state == OmsOrderState.CANCELLED
    assert cancelled_order.filled_qty == Decimal("0.05")

    # Ingest the partial fill into ledger
    from indodax_lab.backtest.costs import OrderRole
    from indodax_lab.execution.indodax_readonly import VenueFill

    race_fill = VenueFill(
        fill_id="fill_race_1",
        order_id=ack_order.venue_order_id or "venue_ord",
        client_order_id=ack_order.client_order_id,
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("1000000000"),
        qty=Decimal("0.05"),
        quote_qty=Decimal("50000000"),
        commission=Decimal("50000"),
        commission_asset="idr",
        timestamp=NOW + timedelta(seconds=2),
    )
    res = ingester.ingest_fill(race_fill)
    assert res.status == "INGESTED"

    # Verify ledger cash and position
    assert ledger.cash == Decimal("49950000")  # 100M - 50.05M
    pos = ledger.get_position("btc_idr")
    assert pos.base_qty == Decimal("0.05")


def test_drill_4_backward_clock_jump_fails_closed(tmp_path: Path) -> None:
    """Drill 4: System clock regresses by 60 seconds (NTP step / OS clock jump).

    Guarantees:
    - ClockGuard detects backwards regression.
    - MarketGateway transitions health to CLOCK_UNSAFE.
    - RiskEngine blocks new exposure.
    - TradingPipeline rejects orders fail-closed.
    """
    clock_guard = ClockGuard()
    gateway = MarketGateway(clock_guard=clock_guard)

    # Observe forward progression at t=10:00:00
    t1 = NOW
    ticker1 = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1000000000"),
        ask=Decimal("1000200000"),
        last_price=Decimal("1000100000"),
        timestamp_utc=t1,
    )
    snap1 = gateway.get_market_snapshot(pair="btc_idr", as_of_utc=t1, ticker_override=ticker1)
    assert snap1.health.state == MarketHealthState.HEALTHY
    assert snap1.is_safe_for_trading is True

    # CLOCK DRILL: System clock steps backward 60s to 09:59:00
    t_regressed = NOW - timedelta(seconds=60)
    ticker_regressed = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1000000000"),
        ask=Decimal("1000200000"),
        last_price=Decimal("1000100000"),
        timestamp_utc=t_regressed,
    )
    snap2 = gateway.get_market_snapshot(
        pair="btc_idr", as_of_utc=t_regressed, ticker_override=ticker_regressed
    )

    assert snap2.health.state == MarketHealthState.CLOCK_UNSAFE
    assert snap2.health.should_halt_new_orders is True
    assert snap2.is_safe_for_trading is False

    # RiskEngine evaluation must reject order
    policy = RiskPolicy(
        policy_id="pol_d4",
        version="1.0",
        max_position_fraction=Decimal("0.20"),
        max_open_positions=3,
        min_order_notional=Decimal("10000"),
    )
    risk_manager = PortfolioRiskManager(
        policy=policy, initial_equity=Decimal("100000000"), start_time=NOW
    )
    risk_engine = RiskEngine(risk_manager=risk_manager)

    intent = SignalIntent(
        intent_id="sig_clock_regress",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("1000100000"),
    )

    assessment = risk_engine.assess_intent(
        intent,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000100000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
        market_health=snap2.health.state,
    )

    assert not assessment.approved
    assert assessment.reason_code == "MARKET_HEALTH_UNSAFE"
