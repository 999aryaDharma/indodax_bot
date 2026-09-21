"""Deterministic fake venue simulator for race conditions and recovery tests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.execution.indodax_readonly import VenueOrder
from indodax_lab.execution.oms import OmsOrder
from indodax_lab.execution.venue import (
    TradingVenue,
    UncertainVenueSubmissionError,
    VenueRejectError,
)

logger = logging.getLogger("fake_venue")


class DeterministicFakeVenue(TradingVenue):
    """Fully programmable execution venue simulator.

    Supports deterministic injection of:
    - Normal immediate acknowledgments
    - Explicit rejects
    - Network timeouts before order write
    - Network timeouts AFTER order write (simulating uncertain post-dispatch disconnects)
    - Fill races during cancel requests
    - Partial fills
    - Server 500 / rate limits (429)
    """

    def __init__(self) -> None:
        self.orders: dict[str, VenueOrder] = {}
        self.orders_by_client_id: dict[str, VenueOrder] = {}
        self._next_id = 1000

        # Programmable behavior hooks
        # Scenarios: SUCCESS, REJECT, TIMEOUT_BEFORE, TIMEOUT_AFTER, 500, 429
        self.submit_scenario: str = "SUCCESS"
        # Scenarios: SUCCESS, REJECT, PARTIAL_FILL_DURING_CANCEL, FULL_FILL_DURING_CANCEL, TIMEOUT
        self.cancel_scenario: str = "SUCCESS"
        self.reject_reason: str = "INSUFFICIENT_BALANCE"

    def submit_order(self, order: OmsOrder) -> VenueOrder:
        """Process an order submission according to current scenario."""
        if self.submit_scenario == "REJECT":
            raise VenueRejectError(f"EXCHANGE_REJECT_{self.reject_reason}")

        if self.submit_scenario == "TIMEOUT_BEFORE":
            raise ConnectionError("Network unreachable before write")

        # Generate venue order ID
        self._next_id += 1
        venue_order_id = f"venue_{self._next_id}"

        venue_order = VenueOrder(
            order_id=venue_order_id,
            client_order_id=order.client_order_id,
            pair=order.pair,
            side=order.side,
            order_type="limit",
            price=order.average_fill_price or Decimal("1000"),
            original_qty=order.desired_qty,
            remaining_qty=order.desired_qty,
            executed_qty=Decimal("0"),
            status="open",
            submitted_at=datetime.now(UTC),
        )

        # Record on the venue's book
        self.orders[venue_order_id] = venue_order
        self.orders_by_client_id[order.client_order_id] = venue_order

        if self.submit_scenario == "TIMEOUT_AFTER":
            # Order recorded on exchange, but transport dropped before client received ACK!
            raise UncertainVenueSubmissionError("ReadTimeout: Network dropped after server write")

        if self.submit_scenario == "500":
            raise UncertainVenueSubmissionError("HTTP 500 Internal Server Error")

        if self.submit_scenario == "429":
            raise VenueRejectError("HTTP 429 Rate Limit Exceeded")

        return venue_order

    def cancel_order(
        self,
        *,
        pair: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> VenueOrder:
        """Process an order cancellation according to current scenario."""
        target: VenueOrder | None = None
        if venue_order_id and venue_order_id in self.orders:
            target = self.orders[venue_order_id]
        elif client_order_id and client_order_id in self.orders_by_client_id:
            target = self.orders_by_client_id[client_order_id]

        if target is None:
            raise VenueRejectError("ORDER_NOT_FOUND")

        if self.cancel_scenario == "TIMEOUT":
            raise UncertainVenueSubmissionError("ReadTimeout during cancel dispatch")

        now_utc = datetime.now(UTC)
        if self.cancel_scenario == "FULL_FILL_DURING_CANCEL":
            # Race condition: Order was completely filled right before cancel arrived
            filled_order = VenueOrder(
                order_id=target.order_id,
                client_order_id=target.client_order_id,
                pair=target.pair,
                side=target.side,
                order_type=target.order_type,
                price=target.price,
                original_qty=target.original_qty,
                remaining_qty=Decimal("0"),
                executed_qty=target.original_qty,
                status="filled",
                submitted_at=target.submitted_at,
                finished_at=now_utc,
            )
            self.orders[target.order_id] = filled_order
            if target.client_order_id:
                self.orders_by_client_id[target.client_order_id] = filled_order
            return filled_order

        if self.cancel_scenario == "PARTIAL_FILL_DURING_CANCEL":
            # Race condition: Order was partially filled before being cancelled
            partial_fill = target.original_qty / Decimal("2")
            partially_cancelled = VenueOrder(
                order_id=target.order_id,
                client_order_id=target.client_order_id,
                pair=target.pair,
                side=target.side,
                order_type=target.order_type,
                price=target.price,
                original_qty=target.original_qty,
                remaining_qty=target.original_qty - partial_fill,
                executed_qty=partial_fill,
                status="cancelled",
                submitted_at=target.submitted_at,
                finished_at=now_utc,
            )
            self.orders[target.order_id] = partially_cancelled
            if target.client_order_id:
                self.orders_by_client_id[target.client_order_id] = partially_cancelled
            return partially_cancelled

        # Default clean cancel
        cancelled = VenueOrder(
            order_id=target.order_id,
            client_order_id=target.client_order_id,
            pair=target.pair,
            side=target.side,
            order_type=target.order_type,
            price=target.price,
            original_qty=target.original_qty,
            remaining_qty=target.remaining_qty,
            executed_qty=target.executed_qty,
            status="cancelled",
            submitted_at=target.submitted_at,
            finished_at=now_utc,
        )
        self.orders[target.order_id] = cancelled
        if target.client_order_id:
            self.orders_by_client_id[target.client_order_id] = cancelled
        return cancelled

    def get_order(self, pair: str, venue_order_id: str) -> VenueOrder | None:
        return self.orders.get(venue_order_id)

    def get_order_by_client_order_id(self, pair: str, client_order_id: str) -> VenueOrder | None:
        return self.orders_by_client_id.get(client_order_id)

    def simulate_fill(
        self,
        venue_order_id: str,
        fill_qty: Decimal,
        price: Decimal,
    ) -> VenueOrder:
        """Explicitly inject a fill into an existing open order on the fake venue."""
        if venue_order_id not in self.orders:
            raise KeyError(f"Order {venue_order_id} not found on fake venue")
        current = self.orders[venue_order_id]
        new_filled = current.executed_qty + fill_qty
        new_remaining = max(Decimal("0"), current.original_qty - new_filled)
        new_status = "filled" if new_remaining == Decimal("0") else "open"

        updated = VenueOrder(
            order_id=current.order_id,
            client_order_id=current.client_order_id,
            pair=current.pair,
            side=current.side,
            order_type=current.order_type,
            price=price,
            original_qty=current.original_qty,
            remaining_qty=new_remaining,
            executed_qty=new_filled,
            status=new_status,
            submitted_at=current.submitted_at,
            finished_at=datetime.now(UTC) if new_status == "filled" else None,
        )
        self.orders[venue_order_id] = updated
        if current.client_order_id:
            self.orders_by_client_id[current.client_order_id] = updated
        return updated
