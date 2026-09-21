"""Tests for exchange-versus-ledger reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.backtest.orders import Fill
from indodax_lab.execution.indodax_readonly import (
    VenueAccountSnapshot,
    VenueBalance,
    VenueFill,
    VenueOrder,
)
from indodax_lab.execution.reconciliation import (
    ReconciliationEngine,
    ReconciliationStatus,
)


NOW = datetime(2026, 9, 21, 5, 0, tzinfo=UTC)


def _account(idr: str, btc: str = "0") -> VenueAccountSnapshot:
    return VenueAccountSnapshot(
        server_time=NOW,
        balances={
            "idr": VenueBalance("idr", Decimal(idr), Decimal("0")),
            "btc": VenueBalance("btc", Decimal(btc), Decimal("0")),
        },
    )


def _ledger_with_btc() -> ResearchLedger:
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)
    ledger.process_fill(
        Fill(
            fill_id="venue-fill-1",
            order_id="order-1",
            event_id="event-1",
            pair="btc_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            qty=Decimal("0.00005"),
            price=Decimal("1000000000"),
            fees=Decimal("100"),
            timestamp=NOW,
            fee_components={"total": Decimal("100")},
        )
    )
    return ledger


def test_matching_balances_orders_and_fills_are_healthy():
    ledger = _ledger_with_btc()
    report = ReconciliationEngine().reconcile(
        ledger=ledger,
        account=_account(str(ledger.cash), "0.00005"),
        venue_open_orders=(),
        venue_fills=(
            VenueFill(
                fill_id="venue-fill-1",
                order_id="order-1",
                client_order_id="bot-1",
                pair="btc_idr",
                side=OrderSide.BUY,
                role=OrderRole.TAKER,
                qty=Decimal("0.00005"),
                quote_qty=Decimal("50000"),
                price=Decimal("1000000000"),
                commission=Decimal("100"),
                commission_asset="idr",
                timestamp=NOW,
            ),
        ),
        expected_open_order_ids=frozenset(),
        tracked_pairs=("btc_idr",),
        evaluation_time=NOW,
    )

    assert report.status == ReconciliationStatus.HEALTHY
    assert report.issues == ()


def test_quote_balance_mismatch_halts_new_orders():
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)

    report = ReconciliationEngine().reconcile(
        ledger=ledger,
        account=_account("99999"),
        evaluation_time=NOW,
    )

    assert report.status == ReconciliationStatus.HALT_NEW_ORDERS
    assert {issue.code for issue in report.issues} == {"QUOTE_BALANCE_MISMATCH"}


def test_unexpected_venue_order_halts_new_orders():
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)
    order = VenueOrder(
        order_id="venue-order-1",
        client_order_id="bot-1",
        pair="btc_idr",
        side=OrderSide.BUY,
        order_type="limit",
        status="OPEN",
        price=Decimal("1000000000"),
        original_qty=Decimal("0.00005"),
        executed_qty=Decimal("0"),
        remaining_qty=Decimal("0.00005"),
        submitted_at=NOW,
    )

    report = ReconciliationEngine().reconcile(
        ledger=ledger,
        account=_account("100000"),
        venue_open_orders=(order,),
        expected_open_order_ids=frozenset(),
        evaluation_time=NOW,
    )

    assert report.status == ReconciliationStatus.HALT_NEW_ORDERS
    assert "UNEXPECTED_VENUE_OPEN_ORDER" in {
        issue.code for issue in report.issues
    }


def test_venue_fill_missing_from_ledger_halts_new_orders():
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)
    venue_fill = VenueFill(
        fill_id="unseen-fill",
        order_id="order-2",
        client_order_id=None,
        pair="btc_idr",
        side=OrderSide.SELL,
        role=OrderRole.MAKER,
        qty=Decimal("0.00001"),
        quote_qty=Decimal("10000"),
        price=Decimal("1000000000"),
        commission=Decimal("10"),
        commission_asset="idr",
        timestamp=NOW,
    )

    report = ReconciliationEngine().reconcile(
        ledger=ledger,
        account=_account("100000"),
        venue_fills=(venue_fill,),
        evaluation_time=NOW,
    )

    assert report.status == ReconciliationStatus.HALT_NEW_ORDERS
    assert "VENUE_FILL_MISSING_FROM_LEDGER" in {
        issue.code for issue in report.issues
    }
