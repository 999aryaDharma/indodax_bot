"""Trading venue interface and execution error hierarchy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from indodax_lab.execution.indodax_readonly import VenueOrder
from indodax_lab.execution.oms import OmsOrder


class VenueError(RuntimeError):
    """Base exception for venue interaction failures."""


class VenueRejectError(VenueError):
    """The exchange definitively rejected the order (e.g. invalid price, insufficient balance)."""


class UncertainVenueSubmissionError(VenueError):
    """The order was dispatched to the venue, but the network connection timed out or failed.

    Crucial: this error MUST NOT trigger automated retries.
    The order state in the OMS MUST transition to UNKNOWN until reconciled.
    """


@runtime_checkable
class TradingVenue(Protocol):
    """Protocol for execution-capable venue adapters (real or simulated)."""

    def submit_order(self, order: OmsOrder) -> VenueOrder:
        """Submit a new order to the venue."""
        ...

    def cancel_order(
        self,
        *,
        pair: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> VenueOrder:
        """Request cancellation of an open order."""
        ...

    def get_order(self, pair: str, venue_order_id: str) -> VenueOrder | None:
        """Lookup an order by exchange venue order ID."""
        ...

    def get_order_by_client_order_id(self, pair: str, client_order_id: str) -> VenueOrder | None:
        """Lookup an order by caller-provided client order ID."""
        ...
