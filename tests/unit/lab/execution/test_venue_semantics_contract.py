"""Unit tests for venue parser cancellation and supported order semantics (PM-04, FR-23).

Validates:
- AC0 (test_pm_04_0): Original equals executed plus remaining in declared units.
- AC1 (test_pm_04_1): Cancel acknowledgement plus inconclusive lookup stays UNKNOWN.
- AC2 (test_pm_04_2): Fill/cancel race never invents zero fill.
- AC3 (test_pm_04_3): Unsupported order/TIF produces no HTTP call.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.control.authority import WritePermit
from indodax_lab.execution.indodax_readonly import (
    IndodaxReadOnlyClient,
    VenueOrder,
    VenueProtocolError,
)
from indodax_lab.execution.indodax_trading import IndodaxTradingVenue
from indodax_lab.execution.oms import OmsOrder, OmsOrderState, OmsStateMachine
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.order_router import OrderRouter, UnresolvedOrderStateError
from indodax_lab.execution.venue import UncertainVenueSubmissionError

_T0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_order(
    internal_id: str = "ord_test_01",
    client_id: str = "cl_test_01",
    side: OrderSide = OrderSide.BUY,
    qty: Decimal = Decimal("1.0"),
    price: Decimal = Decimal("500000000"),
    order_type: str = "limit",
    tif: str = "GTC",
    state: OmsOrderState = OmsOrderState.NEW,
    filled_qty: Decimal = Decimal("0"),
) -> OmsOrder:
    return OmsOrder(
        internal_order_id=internal_id,
        client_order_id=client_id,
        pair="btc_idr",
        side=side,
        desired_qty=qty,
        limit_price=price,
        order_type=order_type,
        time_in_force=tif,
        state=state,
        filled_qty=filled_qty,
        created_at=_T0,
        updated_at=_T0,
    )


# =========================================================================
# AC0: Original equals executed plus remaining in declared units
# =========================================================================
def test_pm_04_0() -> None:
    """PM-04-AC0: Original equals executed plus remaining in declared units."""
    # 1. Base quantity representation (legacy open order with base quantities)
    row_base = {
        "order_id": "1001",
        "client_order_id": "cl_1001",
        "type": "buy",
        "price": "500000000",
        "order_btc": "1.50000000",
        "remain_btc": "0.50000000",
        "submit_time": 1735732800,
    }
    vo_base = IndodaxReadOnlyClient._parse_legacy_open_order("btc_idr", row_base)
    assert vo_base.original_qty == Decimal("1.50000000")
    assert vo_base.remaining_qty == Decimal("0.50000000")
    assert vo_base.executed_qty == Decimal("1.00000000")
    assert vo_base.original_qty == vo_base.executed_qty + vo_base.remaining_qty

    # 2. Quote quantity representation (legacy order with quote/rp amounts)
    row_quote = {
        "order_id": "1002",
        "client_order_id": "cl_1002",
        "type": "buy",
        "price": "500000000",
        "order_rp": "750000000",  # 750M IDR / 500M IDR/BTC = 1.5 BTC
        "remain_rp": "250000000",  # 250M IDR / 500M IDR/BTC = 0.5 BTC
        "submit_time": 1735732800,
    }
    vo_quote = IndodaxReadOnlyClient._parse_legacy_order("btc_idr", row_quote)
    assert vo_quote.original_qty == Decimal("1.5")
    assert vo_quote.remaining_qty == Decimal("0.5")
    assert vo_quote.executed_qty == Decimal("1.0")
    assert vo_quote.original_qty == vo_quote.executed_qty + vo_quote.remaining_qty

    # 3. Trade API v2 order parsing with exact oriQty and executedQty
    row_v2 = {
        "orderId": "2001",
        "clientOrderId": "cl_2001",
        "symbol": "btcidr",
        "side": "buy",
        "type": "limit",
        "status": "partially_filled",
        "price": "500000000",
        "oriQty": "2.00000000",
        "executedQty": "0.80000000",
        "submitTime": 1735732800000,
    }
    vo_v2 = IndodaxReadOnlyClient._parse_v2_order("btc_idr", row_v2)
    assert vo_v2.original_qty == Decimal("2.00000000")
    assert vo_v2.executed_qty == Decimal("0.80000000")
    assert vo_v2.remaining_qty == Decimal("1.20000000")
    assert vo_v2.original_qty == vo_v2.executed_qty + vo_v2.remaining_qty
    assert isinstance(vo_v2.original_qty, Decimal)
    assert isinstance(vo_v2.executed_qty, Decimal)
    assert isinstance(vo_v2.remaining_qty, Decimal)

    # 4. Inconsistent quantities in VenueOrder must be rejected fail-closed
    with pytest.raises(VenueProtocolError, match="VENUE_ORDER_QUANTITY_INCONSISTENT"):
        VenueOrder(
            order_id="bad_1",
            client_order_id="cl_bad_1",
            pair="btc_idr",
            side=OrderSide.BUY,
            order_type="limit",
            status="OPEN",
            price=Decimal("500000000"),
            original_qty=Decimal("1.0"),
            executed_qty=Decimal("0.5"),
            remaining_qty=Decimal("0.3"),  # 0.5 + 0.3 = 0.8 != 1.0!
            submitted_at=_T0,
        )

    # 5. Non-Decimal or negative quantities must be rejected
    with pytest.raises(VenueProtocolError):
        VenueOrder(
            order_id="bad_2",
            client_order_id="cl_bad_2",
            pair="btc_idr",
            side=OrderSide.BUY,
            order_type="limit",
            status="OPEN",
            price=Decimal("500000000"),
            original_qty=1.0,  # float instead of Decimal
            executed_qty=0.5,
            remaining_qty=0.5,
            submitted_at=_T0,
        )

    with pytest.raises(VenueProtocolError):
        VenueOrder(
            order_id="bad_3",
            client_order_id="cl_bad_3",
            pair="btc_idr",
            side=OrderSide.BUY,
            order_type="limit",
            status="OPEN",
            price=Decimal("500000000"),
            original_qty=Decimal("-1.0"),  # negative
            executed_qty=Decimal("0"),
            remaining_qty=Decimal("-1.0"),
            submitted_at=_T0,
        )


# =========================================================================
# AC1: Cancel acknowledgement plus inconclusive lookup stays UNKNOWN
# =========================================================================
def test_pm_04_1(tmp_path: Path) -> None:
    """PM-04-AC1: Cancel acknowledgement plus inconclusive lookup stays UNKNOWN."""
    mock_session = MagicMock()

    # Cancel API returns success=1, but subsequent getOrder returns 404 or success=0 (inconclusive)
    cancel_resp = MagicMock()
    cancel_resp.status_code = 200
    cancel_resp.json.return_value = {"success": 1, "return": {"order_id": "v_ord_01"}}

    get_order_resp = MagicMock()
    get_order_resp.status_code = 200
    get_order_resp.json.return_value = {"success": 0, "error": "Order not found"}

    mock_session.post.side_effect = [cancel_resp, get_order_resp]

    venue = IndodaxTradingVenue(
        api_key="test_api_key",
        secret_key="test_secret_key",
        http_session=mock_session,
    )

    # 1. Venue cancel with inconclusive lookup raises UncertainVenueSubmissionError
    with pytest.raises(
        UncertainVenueSubmissionError, match="CANCEL_ACKNOWLEDGED_BUT_STATE_INCONCLUSIVE"
    ):
        venue.cancel_order(
            pair="btc_idr",
            venue_order_id="v_ord_01",
            client_order_id="cl_ord_01",
            side=OrderSide.BUY,
        )

    # 2. OrderRouter coordinates cancel uncertainty into OmsOrderState.UNKNOWN
    mock_session.post.side_effect = [cancel_resp, get_order_resp]
    oms_store = OmsStore(tmp_path / "oms.db")
    router = OrderRouter(oms_store=oms_store, venue=venue)

    initial_order = _make_order("int_01", "cl_ord_01", state=OmsOrderState.NEW)
    oms_store.create_order(initial_order, event_id="evt_create")
    sub_order = OmsStateMachine.transition(
        initial_order,
        OmsOrderState.SUBMITTING,
        at=_T0,
        reason="SUBMIT_DISPATCHED",
    )
    oms_store.apply_transition(initial_order, sub_order, event_id="evt_sub")
    ack_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.ACKNOWLEDGED,
        at=_T0,
        venue_order_id="v_ord_01",
        reason="VENUE_ACKNOWLEDGED",
    )
    oms_store.apply_transition(sub_order, ack_order, event_id="evt_ack")

    # Dispatch cancel through router (with required WritePermit)
    permit = WritePermit(
        permit_id="perm_test_cancel_01",
        order_internal_id=ack_order.internal_order_id,
        order_digest="digest_placeholder",
        candidate_ref="candidate_test_01",
        snapshot_digest="snap_test_01",
        action="CANCEL",
        created_at=_T0,
        expires_at=_T0 + timedelta(hours=1),
    )
    routed_order = router.cancel_order(ack_order, permit=permit, now=_T0)
    assert routed_order.state == OmsOrderState.UNKNOWN
    assert "CANCEL_UNCERTAIN" in str(routed_order.last_reason)

    # 3. resolve_unknown_order with inconclusive lookup keeps order in UNKNOWN
    # (never manufactures a fake cancelled state)
    inconclusive_get = MagicMock()
    inconclusive_get.status_code = 200
    inconclusive_get.json.return_value = {"success": 0, "error": "Order still unavailable"}
    mock_session.post.side_effect = [inconclusive_get]

    still_unknown = router.resolve_unknown_order(routed_order)
    assert still_unknown.state == OmsOrderState.UNKNOWN

    # Unrecognized venue order status raises UnresolvedOrderStateError
    mock_venue_unknown = MagicMock()
    mock_venue_unknown.get_order.return_value = VenueOrder(
        order_id="v_ord_01",
        client_order_id="cl_ord_01",
        pair="btc_idr",
        side=OrderSide.BUY,
        order_type="limit",
        status="WEIRD_UNHANDLED_STATUS",
        price=Decimal("500000000"),
        original_qty=Decimal("1.0"),
        executed_qty=Decimal("0.5"),
        remaining_qty=Decimal("0.5"),
        submitted_at=_T0,
    )
    router_with_weird = OrderRouter(oms_store=oms_store, venue=mock_venue_unknown)
    with pytest.raises(UnresolvedOrderStateError, match="Cannot deterministically resolve order"):
        router_with_weird.resolve_unknown_order(routed_order)

    # Order in OMS store remains definitively UNKNOWN
    current_stored = oms_store.load_order(routed_order.internal_order_id)
    assert current_stored is not None
    assert current_stored.state == OmsOrderState.UNKNOWN


# =========================================================================
# AC2: Fill/cancel race never invents zero fill
# =========================================================================
def test_pm_04_2(tmp_path: Path) -> None:
    """PM-04-AC2: Fill/cancel race never invents zero fill."""
    oms_store = OmsStore(tmp_path / "oms_race.db")
    mock_venue = MagicMock()

    router = OrderRouter(oms_store=oms_store, venue=mock_venue)

    # 1. Partial fill race: order desired_qty=1.0. During cancel, 0.4 was executed before cancel.
    initial_order = _make_order(
        "int_race_1",
        "cl_race_1",
        qty=Decimal("1.0"),
        filled_qty=Decimal("0"),
    )
    oms_store.create_order(initial_order, event_id="evt_c1")
    sub_order = OmsStateMachine.transition(
        initial_order,
        OmsOrderState.SUBMITTING,
        at=_T0,
    )
    oms_store.apply_transition(initial_order, sub_order, event_id="evt_s1")
    ack_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.ACKNOWLEDGED,
        at=_T0,
        venue_order_id="v_race_1",
    )
    oms_store.apply_transition(sub_order, ack_order, event_id="evt_a1")

    # Venue reports partial fill during cancel
    partial_venue_order = VenueOrder(
        order_id="v_race_1",
        client_order_id="cl_race_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        order_type="limit",
        status="CANCELLED",
        price=Decimal("500000000"),
        original_qty=Decimal("1.0"),
        executed_qty=Decimal("0.4"),
        remaining_qty=Decimal("0.6"),
        submitted_at=_T0,
    )
    mock_venue.cancel_order.return_value = partial_venue_order

    cancelled_order = router.cancel_order(ack_order)
    assert cancelled_order.state == OmsOrderState.CANCELLED
    # Critical invariant: must preserve 0.4 executed fill, NEVER invent 0.0 fill
    assert cancelled_order.filled_qty == Decimal("0.4")
    assert cancelled_order.average_fill_price == Decimal("500000000")

    # 2. Full fill race: order desired_qty=1.0. Completely filled before cancel took effect.
    initial_order_2 = _make_order(
        "int_race_2",
        "cl_race_2",
        qty=Decimal("1.0"),
        filled_qty=Decimal("0"),
    )
    oms_store.create_order(initial_order_2, event_id="evt_c2")
    sub_order_2 = OmsStateMachine.transition(
        initial_order_2,
        OmsOrderState.SUBMITTING,
        at=_T0,
    )
    oms_store.apply_transition(initial_order_2, sub_order_2, event_id="evt_s2")
    ack_order_2 = OmsStateMachine.transition(
        sub_order_2,
        OmsOrderState.ACKNOWLEDGED,
        at=_T0,
        venue_order_id="v_race_2",
    )
    oms_store.apply_transition(sub_order_2, ack_order_2, event_id="evt_a2")

    full_fill_venue_order = VenueOrder(
        order_id="v_race_2",
        client_order_id="cl_race_2",
        pair="btc_idr",
        side=OrderSide.BUY,
        order_type="limit",
        status="FILLED",
        price=Decimal("500000000"),
        original_qty=Decimal("1.0"),
        executed_qty=Decimal("1.0"),
        remaining_qty=Decimal("0"),
        submitted_at=_T0,
    )
    mock_venue.cancel_order.return_value = full_fill_venue_order

    filled_order = router.cancel_order(ack_order_2)
    assert filled_order.state == OmsOrderState.FILLED
    assert filled_order.filled_qty == Decimal("1.0")


# =========================================================================
# AC3: Unsupported order/TIF produces no HTTP call
# =========================================================================
def test_pm_04_3(tmp_path: Path) -> None:
    """PM-04-AC3: Unsupported order/TIF produces no HTTP call."""
    mock_session = MagicMock()
    venue = IndodaxTradingVenue(
        api_key="test_api_key",
        secret_key="test_secret_key",
        http_session=mock_session,
    )
    mock_venue = MagicMock()
    oms_store = OmsStore(tmp_path / "oms_unsupp.db")
    router = OrderRouter(
        oms_store=oms_store,
        venue=mock_venue,
        enforce_production_semantics=True,
    )

    # 1. Unsupported order type: MARKET produces no HTTP call
    market_order = _make_order("int_unsupp_1", "cl_unsupp_1", order_type="market", price=None)
    with pytest.raises(ValueError, match="UNSUPPORTED_ORDER_SEMANTICS"):
        venue.submit_order(market_order)
    assert mock_session.post.call_count == 0

    # Also test OrderRouter pre-validation rejects before any DB transition or venue dispatch
    oms_store.create_order(market_order, event_id="evt_unsupp_1")
    with pytest.raises(ValueError, match="UNSUPPORTED_ORDER_SEMANTICS"):
        router.submit_order(market_order)
    assert mock_venue.submit_order.call_count == 0

    # 2. Unsupported time-in-force: IOC produces no HTTP call
    ioc_order = _make_order("int_unsupp_2", "cl_unsupp_2", tif="IOC")
    with pytest.raises(ValueError, match="UNSUPPORTED_ORDER_SEMANTICS"):
        venue.submit_order(ioc_order)
    assert mock_session.post.call_count == 0

    oms_store.create_order(ioc_order, event_id="evt_unsupp_2")
    with pytest.raises(ValueError, match="UNSUPPORTED_ORDER_SEMANTICS"):
        router.submit_order(ioc_order)
    assert mock_venue.submit_order.call_count == 0

    # 3. Unsupported time-in-force: FOK produces no HTTP call
    fok_order = _make_order("int_unsupp_3", "cl_unsupp_3", tif="FOK")
    with pytest.raises(ValueError, match="UNSUPPORTED_ORDER_SEMANTICS"):
        venue.submit_order(fok_order)
    assert mock_session.post.call_count == 0

    oms_store.create_order(fok_order, event_id="evt_unsupp_3")
    with pytest.raises(ValueError, match="UNSUPPORTED_ORDER_SEMANTICS"):
        router.submit_order(fok_order)
    assert mock_venue.submit_order.call_count == 0
