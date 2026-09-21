"""Production-shaped read-only reconciliation orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import AbstractSet, Sequence

from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.execution.indodax_readonly import IndodaxReadOnlyClient
from indodax_lab.execution.reconciliation import (
    ReconciliationEngine,
    ReconciliationIssue,
    ReconciliationReport,
    ReconciliationStatus,
)


class PrivateReadOnlyReconciliationService:
    """Fetch private venue truth and compare it with internal authority."""

    def __init__(
        self,
        client: IndodaxReadOnlyClient,
        engine: ReconciliationEngine | None = None,
    ) -> None:
        self.client = client
        self.engine = engine or ReconciliationEngine()

    def run(
        self,
        *,
        ledger: ResearchLedger,
        tracked_pairs: Sequence[str],
        expected_open_order_ids: AbstractSet[str],
        fill_window_start_ms: int,
        evaluation_time: datetime,
        history_limit: int = 1000,
    ) -> ReconciliationReport:
        """Execute one side-effect-free reconciliation cycle.

        fill_window_start_ms must come from a durable reconciliation cursor or
        reviewed activation boundary. There is deliberately no implicit last-N-hours
        fallback because silently omitting a fill is unsafe.
        """

        if evaluation_time.tzinfo is None or evaluation_time.utcoffset() != timedelta(0):
            raise ValueError("UTC_TIMEZONE_AWARE_REQUIRED:evaluation_time")
        if not tracked_pairs:
            raise ValueError("TRACKED_PAIRS_REQUIRED")
        if fill_window_start_ms <= 0:
            raise ValueError("FILL_WINDOW_START_REQUIRED")
        if not 10 <= history_limit <= 1000:
            raise ValueError("HISTORY_LIMIT_OUT_OF_RANGE")

        end_ms = int(evaluation_time.timestamp() * 1000)
        if fill_window_start_ms > end_ms:
            raise ValueError("FILL_WINDOW_START_IN_FUTURE")
        if end_ms - fill_window_start_ms > 7 * 24 * 60 * 60 * 1000:
            raise ValueError("FILL_WINDOW_EXCEEDS_INDODAX_7_DAY_LIMIT")

        account = self.client.get_account_snapshot()
        venue_orders = []
        venue_fills = []
        saturated_pairs: list[str] = []

        for pair in tracked_pairs:
            venue_orders.extend(self.client.get_open_orders(pair))
            pair_fills = self.client.get_trade_fills(
                pair,
                start_time_ms=fill_window_start_ms,
                end_time_ms=end_ms,
                limit=history_limit,
                sort="asc",
            )
            venue_fills.extend(pair_fills)
            if len(pair_fills) >= history_limit:
                saturated_pairs.append(pair)

        tracked_pair_set = {pair.lower() for pair in tracked_pairs}
        expected_recent_fill_ids = frozenset(
            tx.fill_id
            for tx in ledger.transactions
            if tx.fill_id is not None
            and tx.pair is not None
            and tx.pair.lower() in tracked_pair_set
            and fill_window_start_ms
            <= int(tx.timestamp.timestamp() * 1000)
            <= end_ms
        )

        report = self.engine.reconcile(
            ledger=ledger,
            account=account,
            venue_open_orders=tuple(venue_orders),
            venue_fills=tuple(venue_fills),
            expected_open_order_ids=expected_open_order_ids,
            expected_recent_fill_ids=expected_recent_fill_ids,
            tracked_pairs=tuple(tracked_pairs),
            evaluation_time=evaluation_time,
        )
        if not saturated_pairs:
            return report

        issues = report.issues + tuple(
            ReconciliationIssue(
                code="FILL_WINDOW_SATURATED",
                detail=(
                    f"pair={pair} returned >= {history_limit} fills; "
                    "history completeness is not proven"
                ),
            )
            for pair in saturated_pairs
        )
        return ReconciliationReport(
            status=ReconciliationStatus.HALT_NEW_ORDERS,
            evaluated_at=evaluation_time,
            issues=issues,
        )
