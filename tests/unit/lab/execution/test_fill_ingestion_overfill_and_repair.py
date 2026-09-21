"""Unit tests for fill ingestion overfill protection and crash-consistent self-healing."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.execution.fill_ingestion import (
    FillIngestionStatus,
    OverfillInvariantError,
    VenueFill,
    VenueFillIngester,
)
from indodax_lab.execution.oms import OmsOrderState, OmsStateMachine, OmsStore

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_fill_ingestion_overfill_raises_invariant_error(tmp_path: Path) -> None:
    db_path = tmp_path / "oms.db"
    store = OmsStore(db_path)
    ledger = ResearchLedger(initial_cash=Decimal("100000000"), init_timestamp=NOW)
    ingester = VenueFillIngester(ledger=ledger, oms_store=store)

    # Create order desiring 0.05 BTC
    order = OmsStateMachine.create(
        internal_order_id="ord_test_overfill",
        client_order_id="cl_overfill_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    store.create_order(order, event_id="evt_init_1")
    sub_order = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW,
        reason="SUBMIT",
    )
    store.apply_transition(order, sub_order, event_id="evt_sub_1")
    ack_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.ACKNOWLEDGED,
        at=NOW,
        reason="ACK",
        venue_order_id="venue_ord_100",
    )
    store.apply_transition(sub_order, ack_order, event_id="evt_ack_1")

    # Ingest fill with 0.06 BTC (exceeds desired 0.05 BTC)
    venue_fill = VenueFill(
        fill_id="fill_over_1",
        order_id="venue_ord_100",
        client_order_id="cl_overfill_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.06"),
        quote_qty=Decimal("60000000"),
        price=Decimal("1000000000"),
        commission=Decimal("60000"),
        commission_asset="idr",
        timestamp=NOW,
    )

    with pytest.raises(OverfillInvariantError, match="OVERFILL_INVARIANT_BREACH"):
        ingester.ingest_fill(venue_fill)


def test_fill_ingestion_duplicate_replay_repairs_stale_oms_order(tmp_path: Path) -> None:
    db_path = tmp_path / "oms.db"
    store = OmsStore(db_path)
    ledger = ResearchLedger(initial_cash=Decimal("100000000"), init_timestamp=NOW)
    ingester = VenueFillIngester(ledger=ledger, oms_store=store)

    # Order desiring 0.05 BTC
    order = OmsStateMachine.create(
        internal_order_id="ord_test_repair",
        client_order_id="cl_repair_1",
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
        reason="SUBMIT",
    )
    store.apply_transition(order, sub_order, event_id="evt_sub_2")
    ack_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.ACKNOWLEDGED,
        at=NOW,
        reason="ACK",
        venue_order_id="venue_ord_200",
    )
    store.apply_transition(sub_order, ack_order, event_id="evt_ack_2")

    venue_fill = VenueFill(
        fill_id="fill_repair_1",
        order_id="venue_ord_200",
        client_order_id="cl_repair_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.05"),
        quote_qty=Decimal("50000000"),
        price=Decimal("1000000000"),
        commission=Decimal("50000"),
        commission_asset="idr",
        timestamp=NOW,
    )

    # Simulate crash consistency gap:
    # 1. Normalizing & processing fill directly into ledger (as if ledger committed first)
    from indodax_lab.execution.fill_normalizer import normalize_venue_fill

    norm_fill = normalize_venue_fill(venue_fill)
    ledger.process_fill(norm_fill)

    # Verify OMS order is still ACKNOWLEDGED (unrepaired)
    loaded = store.load_order("ord_test_repair")
    assert loaded is not None
    assert loaded.state == OmsOrderState.ACKNOWLEDGED
    assert loaded.filled_qty == Decimal("0")

    # 2. Now replay the fill through ingester
    res = ingester.ingest_fill(venue_fill)

    # Duplicate was recognized and skipped on ledger
    assert res.status == FillIngestionStatus.DUPLICATE_SKIPPED

    # Invariant: OMS order was automatically self-healed to FILLED
    assert res.oms_order is not None
    assert res.oms_order.state == OmsOrderState.FILLED
    assert res.oms_order.filled_qty == Decimal("0.05")

    # Loaded OMS order from store is also now FILLED
    reloaded = store.load_order("ord_test_repair")
    assert reloaded is not None
    assert reloaded.state == OmsOrderState.FILLED
