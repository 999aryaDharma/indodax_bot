"""Simulated execution venue adapter for research runtimes (RP-04).

``SimulatorVenueAdapter`` implements the shared ``TradingVenue`` order
semantics with an injected fill model and clock. It returns normalized domain
fills and never mutates cash or ledger state directly.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.execution.indodax_readonly import VenueOrder
from indodax_lab.execution.oms import OmsOrder
from indodax_lab.execution.venue import (
    TradingVenue,
    UncertainVenueSubmissionError,
    VenueRejectError,
)


class SimulatedOutcome(BaseModel):
    """Deterministic fill-model outcome for one submission (RP-04-AC3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["ACK", "PARTIAL", "REJECT", "UNCERTAIN"] = "ACK"
    fill_qty: Decimal = Decimal("0")
    fill_price: Decimal | None = None
    reject_reason: str = "SIMULATED_REJECT"


ClockFn = Callable[[], datetime]
"""Injected clock port; research tests supply a fake clock."""


class SimulatorVenueAdapter(TradingVenue):
    """Research simulator venue: injected fill model, normalized domain fills.

    - ``ACK``: full immediate fill at the order limit price.
    - ``PARTIAL``: partial fill of ``fill_qty`` at ``fill_price`` (or limit).
    - ``REJECT``: raises ``VenueRejectError`` (shared OMS REJECTED path).
    - ``UNCERTAIN``: raises ``UncertainVenueSubmissionError`` (shared OMS
      UNKNOWN path; the caller must reconcile, never blindly resend).
    """

    def __init__(
        self,
        outcome: SimulatedOutcome | None = None,
        *,
        clock: ClockFn | None = None,
    ) -> None:
        self._outcome = outcome or SimulatedOutcome()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sequence = 0

    def submit_order(self, order: OmsOrder) -> VenueOrder:
        """Submit through the injected fill model, returning a normalized fill."""
        outcome = self._outcome
        if outcome.kind == "REJECT":
            raise VenueRejectError(f"SIMULATED_REJECT:{outcome.reject_reason}")
        if outcome.kind == "UNCERTAIN":
            raise UncertainVenueSubmissionError(
                "SIMULATED_UNCERTAIN: submission outcome unknown; reconcile by "
                "client_order_id, never blindly resend"
            )
        if order.limit_price is None or order.limit_price <= 0:
            raise ValueError("SIMULATED_LIMIT_PRICE_REQUIRED: positive limit_price")
        self._sequence += 1
        price = outcome.fill_price or order.limit_price
        if outcome.kind == "PARTIAL":
            if outcome.fill_qty <= 0 or outcome.fill_qty >= order.desired_qty:
                raise ValueError(
                    "SIMULATED_PARTIAL_QTY_INVALID: fill_qty must be within "
                    "(0, desired_qty)"
                )
            executed = outcome.fill_qty
        else:
            executed = order.desired_qty
        now = self._clock()
        return VenueOrder(
            order_id=f"sim_{self._sequence:06d}",
            client_order_id=order.client_order_id,
            pair=order.pair,
            side=order.side,
            order_type=order.order_type,
            status="filled" if executed == order.desired_qty else "partial",
            price=price,
            original_qty=order.desired_qty,
            executed_qty=executed,
            remaining_qty=order.desired_qty - executed,
            submitted_at=now,
        )

    def cancel_order(
        self,
        *,
        pair: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None,
        side: OrderSide | str | None = None,
    ) -> VenueOrder:
        """Simulated cancel: accepted for a known venue order ID, else rejected."""
        raise VenueRejectError("SIMULATED_CANCEL_UNTRACKED: no live order book")

    def get_order(self, pair: str, venue_order_id: str) -> VenueOrder | None:
        """Simulator keeps no order book; fills are returned at submit time."""
        return None

    def get_order_by_client_order_id(
        self, pair: str, client_order_id: str
    ) -> VenueOrder | None:
        """Simulator keeps no order book; fills are returned at submit time."""
        return None


__all__ = [
    "ClockFn",
    "SimulatedOutcome",
    "SimulatorVenueAdapter",
]
