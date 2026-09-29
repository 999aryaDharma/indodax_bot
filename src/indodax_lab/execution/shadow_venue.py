"""Shadow-paper execution venue adapter for research runtimes (RP-04).

``ShadowVenueAdapter`` implements the shared ``TradingVenue`` order semantics
as evidence recording: submissions are acknowledged into an in-memory shadow
ledger with zero executed quantity. It holds no cash, ledger, or live-client
reference, so shadow flow can never mutate financial state or reach a live
writer. Fills arrive later through reconciliation, never at submit time.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.execution.indodax_readonly import VenueOrder
from indodax_lab.execution.oms import OmsOrder
from indodax_lab.execution.venue import TradingVenue, VenueRejectError

ClockFn = Callable[[], datetime]
"""Injected clock port; research tests supply a fake clock."""


class ShadowVenueAdapter(TradingVenue):
    """Paper-shadow venue: records submissions as evidence, fills nothing."""

    def __init__(self, *, clock: ClockFn | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sequence = 0
        self.recorded: list[VenueOrder] = []

    def submit_order(self, order: OmsOrder) -> VenueOrder:
        """Acknowledge the submission as shadow evidence with zero fill."""
        if order.limit_price is None or order.limit_price <= 0:
            raise ValueError("SHADOW_LIMIT_PRICE_REQUIRED: positive limit_price")
        self._sequence += 1
        receipt = VenueOrder(
            order_id=f"shadow_{self._sequence:06d}",
            client_order_id=order.client_order_id,
            pair=order.pair,
            side=order.side,
            order_type=order.order_type,
            status="shadow_recorded",
            price=order.limit_price,
            original_qty=order.desired_qty,
            executed_qty=Decimal("0"),
            remaining_qty=order.desired_qty,
            submitted_at=self._clock(),
        )
        self.recorded.append(receipt)
        return receipt

    def cancel_order(
        self,
        *,
        pair: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None,
        side: OrderSide | str | None = None,
    ) -> VenueOrder:
        """Shadow cancel is always accepted as evidence; nothing to cancel live."""
        raise VenueRejectError("SHADOW_CANCEL_NOTHING_LIVE: shadow holds no live orders")

    def get_order(self, pair: str, venue_order_id: str) -> VenueOrder | None:
        """Look up a previously recorded shadow submission."""
        for receipt in self.recorded:
            if receipt.order_id == venue_order_id:
                return receipt
        return None

    def get_order_by_client_order_id(
        self, pair: str, client_order_id: str
    ) -> VenueOrder | None:
        """Look up a previously recorded shadow submission by client ID."""
        for receipt in self.recorded:
            if receipt.client_order_id == client_order_id:
                return receipt
        return None


__all__ = ["ClockFn", "ShadowVenueAdapter"]
