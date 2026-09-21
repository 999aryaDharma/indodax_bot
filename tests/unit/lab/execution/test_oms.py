"""Tests for the durable OMS lifecycle and persistence boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import sqlite3

import pytest
from pydantic import ValidationError

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.execution.oms import (
    OmsOrderState,
    OmsStateMachine,
    OmsTransitionError,
)
from indodax_lab.execution.oms_store import (
    OmsConcurrencyError,
    OmsStateCorruptionError,
    OmsStore,
)


NOW = datetime(2026, 9, 21, 6, 0, tzinfo=UTC)


def _new_order():
    return OmsStateMachine.create(
        internal_order_id="internal-1",
        client_order_id="bot-20260921-1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.00005000"),
        created_at=NOW,
    )


def test_unknown_state_requires_reconciliation():
    order = _new_order()
    submitting = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
    )
    unknown = OmsStateMachine.transition(
        submitting,
        OmsOrderState.UNKNOWN,
        at=NOW + timedelta(seconds=2),
        reason="SUBMIT_TIMEOUT_AFTER_WRITE_POSSIBLE",
    )

    assert unknown.state == OmsOrderState.UNKNOWN
    assert unknown.venue_order_id is None
    assert unknown.last_reason == "SUBMIT_TIMEOUT_AFTER_WRITE_POSSIBLE"


def test_oms_store_persists_unknown_state_across_restart(tmp_path):
    path = tmp_path / "oms.sqlite3"
    store = OmsStore(path)
    order = _new_order()
    store.create_order(order, event_id="event-create")

    submitting = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
    )
    store.apply_transition(order, submitting, event_id="event-submitting")

    unknown = OmsStateMachine.transition(
        submitting,
        OmsOrderState.UNKNOWN,
        at=NOW + timedelta(seconds=2),
        reason="NETWORK_TIMEOUT",
    )
    store.apply_transition(submitting, unknown, event_id="event-unknown")

    reopened = OmsStore(path)
    restored = reopened.load_order(order.internal_order_id)

    assert restored == unknown
    assert reopened.load_nonterminal_orders() == (unknown,)


def test_unknown_can_only_resolve_from_venue_evidence():
    order = _new_order()
    submitting = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
    )
    unknown = OmsStateMachine.transition(
        submitting,
        OmsOrderState.UNKNOWN,
        at=NOW + timedelta(seconds=2),
    )

    acknowledged = OmsStateMachine.transition(
        unknown,
        OmsOrderState.ACKNOWLEDGED,
        at=NOW + timedelta(seconds=3),
        venue_order_id="venue-42",
    )

    assert acknowledged.state == OmsOrderState.ACKNOWLEDGED
    assert acknowledged.venue_order_id == "venue-42"


def test_illegal_direct_new_to_filled_is_rejected():
    with pytest.raises(OmsTransitionError, match="OMS_INVALID_TRANSITION"):
        OmsStateMachine.transition(
            _new_order(),
            OmsOrderState.FILLED,
            at=NOW + timedelta(seconds=1),
            venue_order_id="venue-42",
            average_fill_price=Decimal("1000000000"),
        )


def test_partial_fill_invariants_are_enforced():
    order = _new_order()
    submitting = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
    )

    partial = OmsStateMachine.transition(
        submitting,
        OmsOrderState.PARTIALLY_FILLED,
        at=NOW + timedelta(seconds=2),
        venue_order_id="venue-42",
        filled_qty=Decimal("0.00001000"),
        average_fill_price=Decimal("1000000000"),
    )

    assert partial.filled_qty == Decimal("0.00001000")
    with pytest.raises(OmsTransitionError, match="OMS_FILLED_QTY_REGRESSION"):
        OmsStateMachine.transition(
            partial,
            OmsOrderState.PARTIALLY_FILLED,
            at=NOW + timedelta(seconds=3),
            filled_qty=Decimal("0.00000900"),
        )


def test_transition_revalidates_nonfinite_values():
    order = _new_order()
    submitting = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
    )

    with pytest.raises((ValidationError, OmsTransitionError)):
        OmsStateMachine.transition(
            submitting,
            OmsOrderState.PARTIALLY_FILLED,
            at=NOW + timedelta(seconds=2),
            venue_order_id="venue-42",
            filled_qty=Decimal("NaN"),
            average_fill_price=Decimal("1000000000"),
        )


def test_stale_writer_cannot_overwrite_newer_order_state(tmp_path):
    store = OmsStore(tmp_path / "oms.sqlite3")
    order = _new_order()
    store.create_order(order, event_id="event-create")

    submitting = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
    )
    store.apply_transition(order, submitting, event_id="event-submitting")

    competing = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=2),
    )
    with pytest.raises(OmsConcurrencyError, match="OMS_STALE_WRITER"):
        store.apply_transition(order, competing, event_id="event-stale")


def test_tampered_oms_payload_fails_closed(tmp_path):
    path = tmp_path / "oms.sqlite3"
    store = OmsStore(path)
    order = _new_order()
    store.create_order(order, event_id="event-create")

    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE oms_orders SET payload = ? WHERE internal_order_id = ?",
            ("{}", order.internal_order_id),
        )
        conn.commit()

    with pytest.raises(OmsStateCorruptionError, match="OMS_ORDER_HASH_MISMATCH"):
        store.load_order(order.internal_order_id)
