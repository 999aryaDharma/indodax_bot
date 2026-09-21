"""Tests for VenueFillIngester and auto-ingestion coordination."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.execution.fill_ingestion import (
    FillIngestionStatus,
    VenueFillIngester,
)
from indodax_lab.execution.fill_normalizer import VenueFillNormalizationError
from indodax_lab.execution.indodax_readonly import (
    VenueAccountSnapshot,
    VenueBalance,
    VenueFill,
)
from indodax_lab.execution.oms import OmsOrderState, OmsStateMachine
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.reconciliation_coordinator import (
    DurableReconciliationCoordinator,
)
from indodax_lab.execution.reconciliation_store import ReconciliationCursorStore

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def make_venue_fill(
    *,
    fill_id: str = "fill_1",
    order_id: str = "venue_ord_1",
    client_order_id: str | None = "cl_1",
    pair: str = "btc_idr",
    side: OrderSide = OrderSide.BUY,
    qty: Decimal = Decimal("0.05"),
    price: Decimal = Decimal("1000000000"),
    commission: Decimal = Decimal("50000"),
    commission_asset: str = "idr",
    timestamp: datetime = NOW,
) -> VenueFill:
    quote_qty = qty * price
    return VenueFill(
        fill_id=fill_id,
        order_id=order_id,
        client_order_id=client_order_id,
        pair=pair,
        side=side,
        role=OrderRole.TAKER,
        price=price,
        qty=qty,
        quote_qty=quote_qty,
        commission=commission,
        commission_asset=commission_asset,
        timestamp=timestamp,
    )


@pytest.fixture
def temp_env(tmp_path: Path):
    ledger = ResearchLedger(initial_cash=Decimal("150000000"), init_timestamp=NOW)
    oms_store = OmsStore(tmp_path / "oms.sqlite3")
    cursor_store = ReconciliationCursorStore(tmp_path / "cursor.sqlite3")
    ingester = VenueFillIngester(ledger=ledger, oms_store=oms_store)
    return ledger, oms_store, cursor_store, ingester


def test_fill_ingestion_single_buy_updates_ledger_and_oms(temp_env) -> None:
    ledger, oms_store, _, ingester = temp_env

    # Seed an ACKNOWLEDGED order in OMS
    order = OmsStateMachine.create(
        internal_order_id="int_1",
        client_order_id="cl_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.10"),
        created_at=NOW,
    )
    oms_store.create_order(order, event_id="evt_1")
    sub_order = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
        reason="SUBMIT",
    )
    oms_store.apply_transition(order, sub_order, event_id="evt_sub_1")
    ack_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.ACKNOWLEDGED,
        at=NOW + timedelta(seconds=2),
        venue_order_id="venue_ord_1",
        reason="ACK",
    )
    oms_store.apply_transition(sub_order, ack_order, event_id="evt_2")

    # Ingest partial fill (0.05 of 0.10)
    v_fill = make_venue_fill(
        fill_id="f_1",
        order_id="venue_ord_1",
        qty=Decimal("0.05"),
        price=Decimal("1000000000"),
        commission=Decimal("50000"),
        timestamp=NOW + timedelta(seconds=3),
    )
    res = ingester.ingest_fill(v_fill)

    assert res.status == FillIngestionStatus.INGESTED
    assert res.fill is not None
    assert res.oms_order is not None
    assert res.oms_order.state == OmsOrderState.PARTIALLY_FILLED
    assert res.oms_order.filled_qty == Decimal("0.05")

    # Check ledger state: initial cash 150_000_000 - (50_000_000 + 50_000) = 99_950_000
    assert ledger.cash == Decimal("99950000")
    pos = ledger.get_position("btc_idr")
    assert pos.base_qty == Decimal("0.05")


def test_fill_ingestion_completes_order_to_filled(temp_env) -> None:
    ledger, oms_store, _, ingester = temp_env

    order = OmsStateMachine.create(
        internal_order_id="int_2",
        client_order_id="cl_2",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        created_at=NOW,
    )
    oms_store.create_order(order, event_id="evt_1")
    sub_order = OmsStateMachine.transition(
        order,
        OmsOrderState.SUBMITTING,
        at=NOW + timedelta(seconds=1),
        reason="SUBMIT",
    )
    oms_store.apply_transition(order, sub_order, event_id="evt_sub_2")
    ack_order = OmsStateMachine.transition(
        sub_order,
        OmsOrderState.ACKNOWLEDGED,
        at=NOW + timedelta(seconds=2),
        venue_order_id="venue_ord_2",
        reason="ACK",
    )
    oms_store.apply_transition(sub_order, ack_order, event_id="evt_2")

    v_fill = make_venue_fill(
        fill_id="f_complete",
        order_id="venue_ord_2",
        qty=Decimal("0.05"),
        price=Decimal("1000000000"),
        commission=Decimal("50000"),
        timestamp=NOW + timedelta(seconds=3),
    )
    res = ingester.ingest_fill(v_fill)

    assert res.status == FillIngestionStatus.INGESTED
    assert res.oms_order.state == OmsOrderState.FILLED
    assert res.oms_order.filled_qty == Decimal("0.05")


def test_fill_ingestion_duplicate_fill_skipped_idempotently(temp_env) -> None:
    ledger, _, _, ingester = temp_env
    v_fill = make_venue_fill(fill_id="f_dup")

    res1 = ingester.ingest_fill(v_fill)
    assert res1.status == FillIngestionStatus.INGESTED
    tx_count_before = len(ledger.transactions)
    cash_before = ledger.cash

    # Second ingestion of same fill
    res2 = ingester.ingest_fill(v_fill)
    assert res2.status == FillIngestionStatus.DUPLICATE_SKIPPED
    assert len(ledger.transactions) == tx_count_before
    assert ledger.cash == cash_before


def test_fill_ingestion_non_quote_commission_fails_closed(temp_env) -> None:
    ledger, _, _, ingester = temp_env
    v_fill = make_venue_fill(
        fill_id="f_bad_asset",
        commission_asset="btc",
    )

    with pytest.raises(VenueFillNormalizationError, match="NON_QUOTE_COMMISSION"):
        ingester.ingest_fill(v_fill)

    # Ingestion failed, ledger unchanged
    assert "f_bad_asset" not in ledger.to_dict()["processed_fill_ids"]


def test_fill_ingestion_quote_notional_mismatch_fails_closed(temp_env) -> None:
    ledger, _, _, ingester = temp_env
    # Mismatch quote_qty
    v_fill = VenueFill(
        fill_id="f_mismatch",
        order_id="v_mismatch",
        client_order_id=None,
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("1000000000"),
        qty=Decimal("0.05"),
        quote_qty=Decimal("49000000"),  # calculated is 50000000
        commission=Decimal("50000"),
        commission_asset="idr",
        timestamp=NOW,
    )

    with pytest.raises(VenueFillNormalizationError, match="VENUE_QUOTE_QTY_MISMATCH"):
        ingester.ingest_fill(v_fill)


class FakeClient:
    def __init__(self, fills: list[VenueFill], balances: dict[str, Decimal]) -> None:
        self.fills = fills
        self.balances = balances

    def get_trade_fills(self, pair: str, **kwargs) -> list[VenueFill]:
        return [f for f in self.fills if f.pair == pair]

    def get_open_orders(self, pair: str) -> list:
        return []

    def get_account_snapshot(self) -> VenueAccountSnapshot:
        bal_map = {
            k: VenueBalance(currency=k, available=v, hold=Decimal("0"))
            for k, v in self.balances.items()
        }
        return VenueAccountSnapshot(
            balances=bal_map,
            server_time=NOW,
        )


class FakeService:
    def __init__(self, client: FakeClient) -> None:
        self.client = client

    def run(self, *, ledger, tracked_pairs, fill_window_start_ms, evaluation_time, **kwargs):
        from indodax_lab.execution.reconciliation import (
            ReconciliationEngine,
        )

        engine = ReconciliationEngine()
        account = self.client.get_account_snapshot()
        venue_fills = self.client.get_trade_fills("btc_idr")
        return engine.reconcile(
            ledger=ledger,
            account=account,
            venue_open_orders=(),
            venue_fills=tuple(venue_fills),
            expected_open_order_ids=frozenset(),
            expected_recent_fill_ids=frozenset(f.fill_id for f in venue_fills),
            tracked_pairs=tuple(tracked_pairs),
            evaluation_time=evaluation_time,
        )


def test_durable_reconciliation_coordinator_auto_ingests_and_advances(tmp_path: Path) -> None:
    start_ms = int((NOW - timedelta(minutes=5)).timestamp() * 1000)
    cursor_store = ReconciliationCursorStore(tmp_path / "cursor.sqlite3")
    cursor_store.initialize(scope_id="prod_scope", start_ms=start_ms, at=NOW)

    ledger = ResearchLedger(initial_cash=Decimal("150000000"), init_timestamp=NOW)
    ingester = VenueFillIngester(ledger=ledger)

    v_fill = make_venue_fill(
        fill_id="f_auto",
        qty=Decimal("0.05"),
        price=Decimal("1000000000"),
        commission=Decimal("50000"),
        timestamp=NOW,
    )
    # Venue balance after the buy:
    # IDR: 150_000_000 - 50_050_000 = 99_950_000
    # BTC: 0.05
    client = FakeClient(
        fills=[v_fill],
        balances={"idr": Decimal("99950000"), "btc": Decimal("0.05")},
    )
    service = FakeService(client)

    coordinator = DurableReconciliationCoordinator(
        service=service,
        cursor_store=cursor_store,
        scope_id="prod_scope",
        overlap_ms=5000,
        fill_ingester=ingester,
    )

    # Run with auto_ingest_fills=True
    result = coordinator.run(
        ledger=ledger,
        tracked_pairs=("btc_idr",),
        expected_open_order_ids=frozenset(),
        evaluation_time=NOW,
        auto_ingest_fills=True,
    )

    assert result.report.healthy
    assert result.cursor_advanced
    assert "f_auto" in ledger.to_dict()["processed_fill_ids"]
