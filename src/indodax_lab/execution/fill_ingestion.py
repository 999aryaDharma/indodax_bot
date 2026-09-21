"""Venue execution ingestion pipeline posting normalized fills into the research ledger."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from indodax_lab.backtest.ledger import DuplicateFillError, ResearchLedger
from indodax_lab.backtest.orders import Fill
from indodax_lab.execution.fill_normalizer import (
    VenueFillNormalizationError,
    normalize_venue_fill,
)
from indodax_lab.execution.indodax_readonly import VenueFill
from indodax_lab.execution.oms import OmsOrder, OmsOrderState, OmsStateMachine
from indodax_lab.execution.oms_store import OmsStore

logger = logging.getLogger("fill_ingester")


class FillIngestionStatus(StrEnum):
    INGESTED = "INGESTED"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    REJECTED = "REJECTED"


class OverfillInvariantError(RuntimeError):
    """Raised when observed venue fills exceed the target order desired quantity."""


class FillIngestionResult:
    def __init__(
        self,
        fill_id: str,
        status: FillIngestionStatus,
        fill: Fill | None = None,
        oms_order: OmsOrder | None = None,
        error: str | None = None,
    ) -> None:
        self.fill_id = fill_id
        self.status = status
        self.fill = fill
        self.oms_order = oms_order
        self.error = error


class VenueFillIngester:
    """Ingest venue executions into double-entry ledger and update OMS state machine."""

    def __init__(
        self,
        *,
        ledger: ResearchLedger,
        oms_store: OmsStore | None = None,
        valuation_currency: str = "IDR",
        quote_notional_tolerance: Decimal = Decimal("1.0"),
        fail_closed: bool = True,
    ) -> None:
        self.ledger = ledger
        self.oms_store = oms_store
        self.valuation_currency = valuation_currency
        self.quote_notional_tolerance = quote_notional_tolerance
        self.fail_closed = fail_closed

    def ingest_fill(self, venue_fill: VenueFill) -> FillIngestionResult:
        """Ingest a single venue fill deterministically."""
        # 1. Normalization with fail-closed non-quote fee validation
        try:
            norm_fill = normalize_venue_fill(
                venue_fill,
                valuation_currency=self.valuation_currency,
                quote_notional_tolerance=self.quote_notional_tolerance,
            )
        except (VenueFillNormalizationError, ValueError) as exc:
            logger.warning(
                "VenueFillIngester: Failed normalizing fill %s: %s",
                venue_fill.fill_id,
                exc,
            )
            if self.fail_closed:
                raise
            return FillIngestionResult(
                fill_id=venue_fill.fill_id,
                status=FillIngestionStatus.REJECTED,
                error=str(exc),
            )

        # 2. Check if already processed in ledger (idempotent duplicate prevention)
        processed_ids = self.ledger.to_dict()["processed_fill_ids"]
        if norm_fill.fill_id in processed_ids:
            # Crash consistency self-healing:
            # If a crash occurred after ledger posting but before OMS sync,
            # repair the stale OMS order state rather than leaving it out of sync.
            repaired_oms = self._repair_oms_order_if_stale(norm_fill, venue_fill)
            return FillIngestionResult(
                fill_id=norm_fill.fill_id,
                status=FillIngestionStatus.DUPLICATE_SKIPPED,
                fill=norm_fill,
                oms_order=repaired_oms,
            )

        # 3. Post to double-entry ledger
        try:
            self.ledger.process_fill(norm_fill)
        except DuplicateFillError:
            repaired_oms = self._repair_oms_order_if_stale(norm_fill, venue_fill)
            return FillIngestionResult(
                fill_id=norm_fill.fill_id,
                status=FillIngestionStatus.DUPLICATE_SKIPPED,
                fill=norm_fill,
                oms_order=repaired_oms,
            )

        # 4. If OMS store configured, synchronize matching order
        updated_oms_order: OmsOrder | None = None
        if self.oms_store is not None:
            updated_oms_order = self._sync_oms_order(norm_fill, venue_fill)

        return FillIngestionResult(
            fill_id=norm_fill.fill_id,
            status=FillIngestionStatus.INGESTED,
            fill=norm_fill,
            oms_order=updated_oms_order,
        )

    def _repair_oms_order_if_stale(self, norm_fill: Fill, venue_fill: VenueFill) -> OmsOrder | None:
        """Idempotently repair an OMS order if a crash left the ledger updated but OMS stale."""
        if self.oms_store is None:
            return None
        target_order = self._find_matching_order(venue_fill)
        if target_order is None:
            return None
        # If target order is still in ACKNOWLEDGED or has not accounted for this fill
        if target_order.filled_qty < target_order.desired_qty:
            logger.warning(
                "VenueFillIngester: Detected stale OMS order %s "
                "during duplicate fill replay. Repairing.",
                target_order.internal_order_id,
            )
            return self._sync_oms_order(norm_fill, venue_fill)
        return None

    def _find_matching_order(self, venue_fill: VenueFill) -> OmsOrder | None:
        if self.oms_store is None:
            return None
        for order in self.oms_store.load_nonterminal_orders():
            if (order.venue_order_id and order.venue_order_id == venue_fill.order_id) or (
                venue_fill.client_order_id and order.client_order_id == venue_fill.client_order_id
            ):
                return order
        return None

    def _sync_oms_order(self, norm_fill: Fill, venue_fill: VenueFill) -> OmsOrder | None:
        """Synchronize OMS order state from fill evidence."""
        if self.oms_store is None:
            return None

        target_order = self._find_matching_order(venue_fill)
        if target_order is None:
            return None

        # Compute new fill quantity and volume-weighted average price (VWAP)
        prev_qty = target_order.filled_qty
        new_fill_qty = norm_fill.qty
        total_filled_qty = prev_qty + new_fill_qty

        # Strict fail-closed check: OVERFILL IS FORBIDDEN
        if total_filled_qty > target_order.desired_qty:
            raise OverfillInvariantError(
                f"OVERFILL_INVARIANT_BREACH: observed total fills {total_filled_qty} "
                f"exceeds desired {target_order.desired_qty} "
                f"for order {target_order.internal_order_id}"
            )

        prev_avg_price = target_order.average_fill_price or Decimal("0")
        weighted_notional = (prev_qty * prev_avg_price) + (new_fill_qty * norm_fill.price)
        avg_price = (
            weighted_notional / total_filled_qty if total_filled_qty > 0 else norm_fill.price
        )

        step_time = max(target_order.updated_at, norm_fill.timestamp)

        if total_filled_qty >= target_order.desired_qty:
            target_state = OmsOrderState.FILLED
            final_qty = target_order.desired_qty
        else:
            target_state = OmsOrderState.PARTIALLY_FILLED
            final_qty = total_filled_qty

        updated_order = OmsStateMachine.transition(
            target_order,
            target_state,
            at=step_time,
            filled_qty=final_qty,
            average_fill_price=avg_price,
            reason=f"VENUE_FILL_INGESTED:{norm_fill.fill_id}",
        )
        self.oms_store.apply_transition(
            target_order,
            updated_order,
            event_id=f"evt_fill_{norm_fill.fill_id}_{uuid.uuid4().hex[:8]}",
        )
        return updated_order

    def ingest_fills(self, venue_fills: Sequence[VenueFill]) -> tuple[FillIngestionResult, ...]:
        """Ingest a batch of venue fills in strict chronological order."""
        sorted_fills = sorted(venue_fills, key=lambda f: f.timestamp)
        results = []
        for fill in sorted_fills:
            results.append(self.ingest_fill(fill))
        return tuple(results)
