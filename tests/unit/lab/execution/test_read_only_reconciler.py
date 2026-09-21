"""Tests for production-shaped read-only reconciliation orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.backtest.orders import Fill
from indodax_lab.execution.indodax_readonly import (
    VenueAccountSnapshot,
    VenueBalance,
    VenueFill,
)
from indodax_lab.execution.read_only_reconciler import (
    PrivateReadOnlyReconciliationService,
)
from indodax_lab.execution.reconciliation import ReconciliationStatus


NOW = datetime(2026, 9, 21, 7, 0, tzinfo=UTC)


class FakeReadOnlyClient:
    def __init__(self, *, account, orders_by_pair=None, fills_by_pair=None):
        self.account = account
        self.orders_by_pair = orders_by_pair or {}
        self.fills_by_pair = fills_by_pair or {}
        self.calls = []

    def get_account_snapshot(self):
        self.calls.append(("account",))
        return self.account

    def get_open_orders(self, pair):
        self.calls.append(("orders", pair))
        return tuple(self.orders_by_pair.get(pair, ()))

    def get_trade_fills(self, pair, **kwargs):
        self.calls.append(("fills", pair, kwargs))
        return tuple(self.fills_by_pair.get(pair, ()))


def _account(idr: str = "100000") -> VenueAccountSnapshot:
    return VenueAccountSnapshot(
        server_time=NOW,
        balances={
            "idr": VenueBalance("idr", Decimal(idr), Decimal("0")),
            "btc": VenueBalance("btc", Decimal("0"), Decimal("0")),
        },
    )


def test_service_fetches_private_truth_and_returns_healthy():
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)
    client = FakeReadOnlyClient(account=_account())
    service = PrivateReadOnlyReconciliationService(client)

    start_ms = int((NOW - timedelta(minutes=5)).timestamp() * 1000)
    report = service.run(
        ledger=ledger,
        tracked_pairs=("btc_idr",),
        expected_open_order_ids=frozenset(),
        fill_window_start_ms=start_ms,
        evaluation_time=NOW,
        history_limit=10,
    )

    assert report.status == ReconciliationStatus.HEALTHY
    assert ("orders", "btc_idr") in client.calls
    fill_call = next(call for call in client.calls if call[0] == "fills")
    assert fill_call[2]["start_time_ms"] == start_ms
    assert fill_call[2]["end_time_ms"] == int(NOW.timestamp() * 1000)
    assert fill_call[2]["sort"] == "asc"


def test_saturated_fill_window_halts_instead_of_silently_truncating():
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)
    fills = tuple(
        VenueFill(
            fill_id=f"fill-{index}",
            order_id=f"order-{index}",
            client_order_id=None,
            pair="btc_idr",
            side="buy",
            role="taker",
            qty=Decimal("0.000001"),
            quote_qty=Decimal("1000"),
            price=Decimal("1000000000"),
            commission=Decimal("0"),
            commission_asset="idr",
            timestamp=NOW,
        )
        for index in range(10)
    )
    client = FakeReadOnlyClient(
        account=_account(),
        fills_by_pair={"btc_idr": fills},
    )
    service = PrivateReadOnlyReconciliationService(client)

    report = service.run(
        ledger=ledger,
        tracked_pairs=("btc_idr",),
        expected_open_order_ids=frozenset(),
        fill_window_start_ms=int((NOW - timedelta(minutes=5)).timestamp() * 1000),
        evaluation_time=NOW,
        history_limit=10,
    )

    assert report.status == ReconciliationStatus.HALT_NEW_ORDERS
    codes = {issue.code for issue in report.issues}
    assert "FILL_WINDOW_SATURATED" in codes


def test_service_rejects_implicit_or_too_wide_fill_window():
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)
    service = PrivateReadOnlyReconciliationService(FakeReadOnlyClient(account=_account()))

    try:
        service.run(
            ledger=ledger,
            tracked_pairs=("btc_idr",),
            expected_open_order_ids=frozenset(),
            fill_window_start_ms=0,
            evaluation_time=NOW,
        )
    except ValueError as exc:
        assert str(exc) == "FILL_WINDOW_START_REQUIRED"
    else:
        raise AssertionError("missing fill cursor must fail closed")

    too_old = int((NOW - timedelta(days=8)).timestamp() * 1000)
    try:
        service.run(
            ledger=ledger,
            tracked_pairs=("btc_idr",),
            expected_open_order_ids=frozenset(),
            fill_window_start_ms=too_old,
            evaluation_time=NOW,
        )
    except ValueError as exc:
        assert str(exc) == "FILL_WINDOW_EXCEEDS_INDODAX_7_DAY_LIMIT"
    else:
        raise AssertionError("unsupported history window must fail closed")


def test_ledger_fill_absent_from_venue_history_halts():
    ledger = ResearchLedger(initial_cash=Decimal("100000"), init_timestamp=NOW)
    ledger.process_fill(
        Fill(
            fill_id="ledger-only-fill",
            order_id="order-1",
            event_id="venue-fill:ledger-only-fill",
            pair="btc_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            qty=Decimal("0.00001"),
            price=Decimal("1000000000"),
            fees=Decimal("0"),
            timestamp=NOW - timedelta(minutes=1),
            fee_components={"venue_commission": Decimal("0")},
        )
    )
    client = FakeReadOnlyClient(
        account=VenueAccountSnapshot(
            server_time=NOW,
            balances={
                "idr": VenueBalance("idr", ledger.cash, Decimal("0")),
                "btc": VenueBalance("btc", Decimal("0.00001"), Decimal("0")),
            },
        )
    )
    service = PrivateReadOnlyReconciliationService(client)

    report = service.run(
        ledger=ledger,
        tracked_pairs=("btc_idr",),
        expected_open_order_ids=frozenset(),
        fill_window_start_ms=int((NOW - timedelta(minutes=5)).timestamp() * 1000),
        evaluation_time=NOW,
        history_limit=10,
    )

    assert report.status == ReconciliationStatus.HALT_NEW_ORDERS
    assert "LEDGER_FILL_MISSING_AT_VENUE" in {
        issue.code for issue in report.issues
    }
