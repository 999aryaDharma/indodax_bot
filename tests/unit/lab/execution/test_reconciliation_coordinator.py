"""Tests for cursor-gated reconciliation coordination."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.execution.reconciliation import (
    ReconciliationIssue,
    ReconciliationReport,
    ReconciliationStatus,
)
from indodax_lab.execution.reconciliation_coordinator import (
    DurableReconciliationCoordinator,
)
from indodax_lab.execution.reconciliation_store import ReconciliationCursorStore


NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


class FakeService:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.report


def _report(status: ReconciliationStatus) -> ReconciliationReport:
    issues = ()
    if status != ReconciliationStatus.HEALTHY:
        issues = (
            ReconciliationIssue(
                code="TEST_MISMATCH",
                detail="intentional test mismatch",
            ),
        )
    return ReconciliationReport(
        status=status,
        evaluated_at=NOW,
        issues=issues,
    )


def test_healthy_cycle_advances_durable_cursor(tmp_path):
    store = ReconciliationCursorStore(tmp_path / "cursor.sqlite3")
    start_ms = int((NOW - timedelta(minutes=1)).timestamp() * 1000)
    store.initialize(scope_id="prod-idr", start_ms=start_ms, at=NOW)
    service = FakeService(_report(ReconciliationStatus.HEALTHY))
    coordinator = DurableReconciliationCoordinator(
        service=service,
        cursor_store=store,
        scope_id="prod-idr",
        overlap_ms=5000,
    )

    result = coordinator.run(
        ledger=ResearchLedger(initial_cash=Decimal("0"), init_timestamp=NOW),
        tracked_pairs=("btc_idr",),
        expected_open_order_ids=frozenset(),
        evaluation_time=NOW,
        history_limit=100,
    )

    assert result.cursor_advanced
    assert result.cursor_after.revision == 2
    assert result.cursor_after.next_start_ms == int(NOW.timestamp() * 1000) - 5000
    assert service.calls[0]["fill_window_start_ms"] == start_ms


def test_unhealthy_cycle_does_not_advance_cursor(tmp_path):
    store = ReconciliationCursorStore(tmp_path / "cursor.sqlite3")
    start_ms = int((NOW - timedelta(minutes=1)).timestamp() * 1000)
    cursor = store.initialize(scope_id="prod-idr", start_ms=start_ms, at=NOW)
    service = FakeService(_report(ReconciliationStatus.HALT_NEW_ORDERS))
    coordinator = DurableReconciliationCoordinator(
        service=service,
        cursor_store=store,
        scope_id="prod-idr",
    )

    result = coordinator.run(
        ledger=ResearchLedger(initial_cash=Decimal("0"), init_timestamp=NOW),
        tracked_pairs=("btc_idr",),
        expected_open_order_ids=frozenset(),
        evaluation_time=NOW,
    )

    assert not result.cursor_advanced
    assert result.cursor_after == cursor
    assert store.load("prod-idr") == cursor
