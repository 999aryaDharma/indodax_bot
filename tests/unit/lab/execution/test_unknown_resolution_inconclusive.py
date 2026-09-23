"""Unit tests ensuring resolve_unknown_order preserves UNKNOWN state
on inconclusive venue queries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.execution.oms import OmsOrderState, OmsStateMachine, OmsStore
from indodax_lab.execution.order_router import OrderRouter, UnresolvedOrderStateError
from indodax_lab.execution.venue import TradingVenue

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_resolve_unknown_order_inconclusive_leaves_unknown(tmp_path: Path) -> None:
    venue = MagicMock(spec=TradingVenue)
    # Venue lookup returns None (e.g. timeout, rate limit, inconclusive)
    venue.get_order_by_client_order_id.return_value = None

    store = OmsStore(tmp_path / "oms.db")
    router = OrderRouter(oms_store=store, venue=venue)

    order = OmsStateMachine.create(
        internal_order_id="ord_unk_1",
        client_order_id="cl_unk_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_1")

    # Move to SUBMITTING -> UNKNOWN
    sub_order = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW,
        reason="SUBMIT_ATTEMPT",
    )
    store.apply_transition(order, sub_order, event_id="evt_sub_1")

    unknown_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.UNKNOWN,
        at=NOW,
        reason="POST_TIMEOUT",
    )
    store.apply_transition(sub_order, unknown_order, event_id="evt_unk_1")
    assert unknown_order.state == OmsOrderState.UNKNOWN

    resolved = router.resolve_unknown_order(unknown_order, now=NOW)

    # Invariant: Must remain UNKNOWN, never marked REJECTED or CANCELLED
    assert resolved.state == OmsOrderState.UNKNOWN
    assert resolved.internal_order_id == unknown_order.internal_order_id


def test_resolve_unknown_order_requires_fill_history_for_definitive_fill(tmp_path: Path) -> None:
    from indodax_lab.execution.indodax_readonly import VenueOrder

    venue = MagicMock(spec=TradingVenue)
    venue_order = VenueOrder(
        order_id="venue_ord_99",
        client_order_id="cl_unk_2",
        pair="btc_idr",
        side=OrderSide.BUY,
        order_type="limit",
        price=Decimal("1000000000"),
        original_qty=Decimal("0.05"),
        remaining_qty=Decimal("0"),
        executed_qty=Decimal("0.05"),
        status="filled",
        submitted_at=NOW,
    )
    venue.get_order_by_client_order_id.return_value = venue_order

    store = OmsStore(tmp_path / "oms.db")
    router = OrderRouter(oms_store=store, venue=venue)

    order = OmsStateMachine.create(
        internal_order_id="ord_unk_2",
        client_order_id="cl_unk_2",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_2")

    sub_order = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW,
        reason="SUBMIT_ATTEMPT",
    )
    store.apply_transition(order, sub_order, event_id="evt_sub_2")

    unknown_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.UNKNOWN,
        at=NOW,
        reason="TIMEOUT_BEFORE_ACK",
    )
    store.apply_transition(sub_order, unknown_order, event_id="evt_unk_2")

    with pytest.raises(UnresolvedOrderStateError, match="FILL_HISTORY_REQUIRED"):
        router.resolve_unknown_order(unknown_order, now=NOW)
    persisted = store.load_order(unknown_order.internal_order_id)
    assert persisted is not None
    assert persisted.state == OmsOrderState.UNKNOWN
    assert persisted.filled_qty == Decimal("0")
    assert persisted.average_fill_price is None
