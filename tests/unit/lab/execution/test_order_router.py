"""Tests for OrderRouter, DeterministicFakeVenue, cancel-fill races, and UNKNOWN recovery."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.execution.fake_venue import DeterministicFakeVenue
from indodax_lab.execution.indodax_readonly import VenueOrder
from indodax_lab.execution.indodax_trading import IndodaxTradingVenue
from indodax_lab.execution.oms import OmsOrderState, OmsStateMachine
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.order_router import OrderRouter

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


@pytest.fixture
def temp_router(tmp_path: Path):
    db_path = tmp_path / "oms_orders.sqlite3"
    oms_store = OmsStore(db_path)
    venue = DeterministicFakeVenue()
    router = OrderRouter(oms_store=oms_store, venue=venue)
    return router, oms_store, venue


def test_order_router_normal_submit_acknowledged(temp_router) -> None:
    router, store, venue = temp_router
    order = OmsStateMachine.create(
        internal_order_id="int_1",
        client_order_id="cl_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.5"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_1")

    ack_order = router.submit_order(order, now=NOW)
    assert ack_order.state == OmsOrderState.ACKNOWLEDGED
    assert ack_order.venue_order_id is not None
    assert ack_order.venue_order_id.startswith("venue_")

    # Verify persisted in DB
    persisted = store.load_order("int_1")
    assert persisted is not None
    assert persisted.state == OmsOrderState.ACKNOWLEDGED
    assert persisted.version == 3  # NEW (v1) -> SUBMITTING (v2) -> ACK (v3)


def test_order_router_definite_reject(temp_router) -> None:
    router, store, venue = temp_router
    venue.submit_scenario = "REJECT"
    venue.reject_reason = "INSUFFICIENT_FUNDS"

    order = OmsStateMachine.create(
        internal_order_id="int_2",
        client_order_id="cl_2",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("1.0"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_2")

    rejected_order = router.submit_order(order, now=NOW)
    assert rejected_order.state == OmsOrderState.REJECTED
    assert "INSUFFICIENT_FUNDS" in str(rejected_order.last_reason)

    persisted = store.load_order("int_2")
    assert persisted is not None
    assert persisted.state == OmsOrderState.REJECTED


def test_order_router_uncertain_submit_transitions_to_unknown(temp_router) -> None:
    router, store, venue = temp_router
    # Order reached venue, but response timed out
    venue.submit_scenario = "TIMEOUT_AFTER"

    order = OmsStateMachine.create(
        internal_order_id="int_3",
        client_order_id="cl_3",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.2"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_3")

    unknown_order = router.submit_order(order, now=NOW)
    assert unknown_order.state == OmsOrderState.UNKNOWN

    persisted = store.load_order("int_3")
    assert persisted is not None
    assert persisted.state == OmsOrderState.UNKNOWN

    # Now resolve the unknown order via venue lookup
    resolved = router.resolve_unknown_order(unknown_order, now=NOW)
    assert resolved.state == OmsOrderState.ACKNOWLEDGED
    assert resolved.venue_order_id is not None


def test_order_router_cancel_fill_race_partial_fill(temp_router) -> None:
    router, store, venue = temp_router
    order = OmsStateMachine.create(
        internal_order_id="int_4",
        client_order_id="cl_4",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("1.0"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_4")
    ack_order = router.submit_order(order, now=NOW)

    # Inject race: 50% partial fill occurred right before cancel took effect
    venue.cancel_scenario = "PARTIAL_FILL_DURING_CANCEL"

    cancelled = router.cancel_order(ack_order, now=NOW)
    assert cancelled.state == OmsOrderState.UNKNOWN
    assert cancelled.filled_qty == Decimal("0")
    assert cancelled.average_fill_price is None

    persisted = store.load_order("int_4")
    assert persisted is not None
    assert persisted.state == OmsOrderState.UNKNOWN
    assert persisted.filled_qty == Decimal("0")
    assert persisted.average_fill_price is None


def test_order_router_cancel_fill_race_full_fill(temp_router) -> None:
    router, store, venue = temp_router
    order = OmsStateMachine.create(
        internal_order_id="int_5",
        client_order_id="cl_5",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("1.0"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_5")
    ack_order = router.submit_order(order, now=NOW)

    # Inject race: 100% full fill occurred right before cancel took effect
    venue.cancel_scenario = "FULL_FILL_DURING_CANCEL"

    filled = router.cancel_order(ack_order, now=NOW)
    assert filled.state == OmsOrderState.UNKNOWN
    assert filled.filled_qty == Decimal("0")
    assert filled.average_fill_price is None


def test_order_router_cancel_rejects_filled_status_with_partial_quantity(temp_router) -> None:
    router, store, venue = temp_router
    order = OmsStateMachine.create(
        internal_order_id="int_inconsistent_fill",
        client_order_id="cl_inconsistent_fill",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("1.0"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_inconsistent")
    ack_order = router.submit_order(order, now=NOW)
    partial_order = OmsStateMachine.transition(
        ack_order,
        OmsOrderState.PARTIALLY_FILLED,
        at=NOW,
        filled_qty=Decimal("0.4"),
        average_fill_price=Decimal("999000000"),
    )
    store.apply_transition(ack_order, partial_order, event_id="evt_partial_inconsistent")
    venue.cancel_order = lambda **_: VenueOrder(
        order_id=partial_order.venue_order_id or "venue_inconsistent",
        client_order_id=partial_order.client_order_id,
        pair=partial_order.pair,
        side=partial_order.side,
        order_type="limit",
        status="FILLED",
        price=partial_order.limit_price,
        original_qty=Decimal("1.0"),
        executed_qty=Decimal("0.4"),
        remaining_qty=Decimal("0.6"),
        submitted_at=NOW,
    )

    unresolved = router.cancel_order(partial_order, now=NOW)

    assert unresolved.state == OmsOrderState.UNKNOWN
    assert unresolved.filled_qty == Decimal("0.4")
    assert unresolved.average_fill_price == Decimal("999000000")


def test_indodax_trading_venue_security_boundary_no_withdrawals() -> None:
    venue = IndodaxTradingVenue(
        api_key="test_key",
        secret_key="test_secret",
    )
    # Institutional safety rule: trading adapter MUST NOT expose withdrawal methods
    assert not hasattr(venue, "withdraw")
    assert not hasattr(venue, "withdraw_coin")
    assert not hasattr(venue, "withdraw_rp")
    assert not hasattr(venue, "create_withdrawal")
