"""Coordinator that couples reconciliation evidence with durable cursor advancement."""

from __future__ import annotations

from collections.abc import Sequence, Set
from dataclasses import dataclass
from datetime import datetime

from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.execution.fill_ingestion import VenueFillIngester
from indodax_lab.execution.read_only_reconciler import (
    PrivateReadOnlyReconciliationService,
)
from indodax_lab.execution.reconciliation import ReconciliationReport
from indodax_lab.execution.reconciliation_store import (
    ReconciliationCursor,
    ReconciliationCursorStore,
)


@dataclass(frozen=True)
class ReconciliationCycleResult:
    """One durable reconciliation cycle and its cursor movement."""

    report: ReconciliationReport
    cursor_before: ReconciliationCursor
    cursor_after: ReconciliationCursor

    @property
    def cursor_advanced(self) -> bool:
        return self.cursor_after.revision > self.cursor_before.revision


class DurableReconciliationCoordinator:
    """Advance fill-history evidence only after a healthy reconciliation cycle."""

    def __init__(
        self,
        *,
        service: PrivateReadOnlyReconciliationService,
        cursor_store: ReconciliationCursorStore,
        scope_id: str,
        overlap_ms: int = 5000,
        fill_ingester: VenueFillIngester | None = None,
    ) -> None:
        if not scope_id.strip():
            raise ValueError("RECONCILIATION_SCOPE_REQUIRED")
        if overlap_ms < 0:
            raise ValueError("RECONCILIATION_CURSOR_OVERLAP_INVALID")
        self.service = service
        self.cursor_store = cursor_store
        self.scope_id = scope_id
        self.overlap_ms = overlap_ms
        self.fill_ingester = fill_ingester

    def run(
        self,
        *,
        ledger: ResearchLedger,
        tracked_pairs: Sequence[str],
        expected_open_order_ids: Set[str],
        evaluation_time: datetime,
        history_limit: int = 1000,
        auto_ingest_fills: bool = False,
    ) -> ReconciliationCycleResult:
        cursor = self.cursor_store.load(self.scope_id)
        if cursor is None:
            raise RuntimeError("RECONCILIATION_CURSOR_NOT_INITIALIZED")

        end_ms = int(evaluation_time.timestamp() * 1000)

        # Ingest fills into ledger before reconciliation if requested
        if auto_ingest_fills and self.fill_ingester is not None:
            if hasattr(self.service, "client") and hasattr(self.service.client, "get_trade_fills"):
                for pair in tracked_pairs:
                    pair_fills = self.service.client.get_trade_fills(
                        pair,
                        start_time_ms=cursor.next_start_ms,
                        end_time_ms=end_ms,
                        limit=history_limit,
                        sort="asc",
                    )
                    self.fill_ingester.ingest_fills(pair_fills)

        report = self.service.run(
            ledger=ledger,
            tracked_pairs=tracked_pairs,
            expected_open_order_ids=expected_open_order_ids,
            fill_window_start_ms=cursor.next_start_ms,
            evaluation_time=evaluation_time,
            history_limit=history_limit,
        )
        if not report.healthy:
            return ReconciliationCycleResult(
                report=report,
                cursor_before=cursor,
                cursor_after=cursor,
            )

        observed_end_ms = int(evaluation_time.timestamp() * 1000)
        advanced = self.cursor_store.advance_after_healthy(
            cursor,
            observed_end_ms=observed_end_ms,
            overlap_ms=self.overlap_ms,
            at=evaluation_time,
        )
        return ReconciliationCycleResult(
            report=report,
            cursor_before=cursor,
            cursor_after=advanced,
        )
