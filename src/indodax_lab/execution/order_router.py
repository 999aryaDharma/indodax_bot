"""Order router and execution coordinator enforcing OMS durability and fail-closed uncertainty."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.execution.oms import (
    OmsOrder,
    OmsOrderState,
    OmsStateMachine,
)
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.venue import (
    TradingVenue,
    UncertainVenueSubmissionError,
    VenueRejectError,
)

logger = logging.getLogger("order_router")


class UnresolvedOrderStateError(RuntimeError):
    """Raised when an UNKNOWN order cannot be definitively reconciled with the venue."""


class OrderRouter:
    """Coordinates order submissions, cancellations, and UNKNOWN resolution with durability."""

    def __init__(self, oms_store: OmsStore, venue: TradingVenue) -> None:
        self.oms_store = oms_store
        self.venue = venue

    def _generate_event_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def submit_order(self, order: OmsOrder, *, now: datetime | None = None) -> OmsOrder:
        """Submit an order with guaranteed pre-network durability and uncertainty capture."""
        current_time = max(order.updated_at, now or datetime.now(UTC))

        # 1. NEW -> SUBMITTING
        submitting_order = OmsStateMachine.transition(
            order,
            OmsOrderState.SUBMITTING,
            at=current_time,
            reason="SUBMIT_DISPATCHED",
        )
        self.oms_store.apply_transition(
            order,
            submitting_order,
            event_id=self._generate_event_id("submitting"),
        )

        step_time = max(submitting_order.updated_at, now or datetime.now(UTC))

        # 2. Dispatch to venue
        try:
            venue_order = self.venue.submit_order(submitting_order)
        except VenueRejectError as exc:
            logger.warning(
                "OrderRouter: Order %s rejected by venue: %s",
                order.internal_order_id,
                exc,
            )
            rejected_order = OmsStateMachine.transition(
                submitting_order,
                OmsOrderState.REJECTED,
                at=step_time,
                reason=str(exc),
            )
            self.oms_store.apply_transition(
                submitting_order,
                rejected_order,
                event_id=self._generate_event_id("rejected"),
            )
            return rejected_order
        except (UncertainVenueSubmissionError, Exception) as exc:
            logger.critical(
                "OrderRouter: Uncertain write outcome for %s. Transitioning to UNKNOWN: %s",
                order.internal_order_id,
                exc,
            )
            unknown_order = OmsStateMachine.transition(
                submitting_order,
                OmsOrderState.UNKNOWN,
                at=step_time,
                reason=f"UNCERTAIN_WRITE:{exc}",
            )
            self.oms_store.apply_transition(
                submitting_order,
                unknown_order,
                event_id=self._generate_event_id("unknown"),
            )
            return unknown_order

        # 3. Successful ACK
        ack_order = OmsStateMachine.transition(
            submitting_order,
            OmsOrderState.ACKNOWLEDGED,
            at=step_time,
            venue_order_id=venue_order.order_id,
            reason="VENUE_ACKNOWLEDGED",
        )
        self.oms_store.apply_transition(
            submitting_order,
            ack_order,
            event_id=self._generate_event_id("ack"),
        )
        return ack_order

    def cancel_order(self, order: OmsOrder, *, now: datetime | None = None) -> OmsOrder:
        """Cancel an open order, correctly handling in-flight fills and cancel/fill races."""
        current_time = max(order.updated_at, now or datetime.now(UTC))

        # 1. ACKNOWLEDGED / PARTIALLY_FILLED -> CANCEL_PENDING
        pending_order = OmsStateMachine.transition(
            order,
            OmsOrderState.CANCEL_PENDING,
            at=current_time,
            reason="CANCEL_DISPATCHED",
        )
        self.oms_store.apply_transition(
            order,
            pending_order,
            event_id=self._generate_event_id("cancel_pending"),
        )

        step_time = max(pending_order.updated_at, now or datetime.now(UTC))

        # 2. Dispatch cancel to venue
        try:
            venue_order = self.venue.cancel_order(
                pair=order.pair,
                venue_order_id=order.venue_order_id,
                client_order_id=order.client_order_id,
                side=order.side,
            )
        except (UncertainVenueSubmissionError, Exception) as exc:
            logger.critical(
                "OrderRouter: Cancel uncertain for %s: %s. Transitioning to UNKNOWN.",
                order.internal_order_id,
                exc,
            )
            unknown_order = OmsStateMachine.transition(
                pending_order,
                OmsOrderState.UNKNOWN,
                at=step_time,
                reason=f"CANCEL_UNCERTAIN:{exc}",
            )
            self.oms_store.apply_transition(
                pending_order,
                unknown_order,
                event_id=self._generate_event_id("cancel_unknown"),
            )
            return unknown_order

        fill_price = venue_order.price or order.limit_price or order.average_fill_price
        # Check if fill occurred during cancel race:
        if venue_order.status == "filled" or venue_order.executed_qty == order.desired_qty:
            if fill_price is None or fill_price <= Decimal("0"):
                raise ValueError(f"FILL_PRICE_REQUIRED_FOR_CANCEL_RACE:{order.internal_order_id}")
            filled_order = OmsStateMachine.transition(
                pending_order,
                OmsOrderState.FILLED,
                at=step_time,
                filled_qty=order.desired_qty,
                average_fill_price=fill_price,
                reason="FILLED_DURING_CANCEL_RACE",
            )
            self.oms_store.apply_transition(
                pending_order,
                filled_order,
                event_id=self._generate_event_id("filled_during_cancel"),
            )
            return filled_order

        if venue_order.executed_qty > pending_order.filled_qty:
            if fill_price is None or fill_price <= Decimal("0"):
                raise ValueError(
                    f"FILL_PRICE_REQUIRED_FOR_PARTIAL_CANCEL:{order.internal_order_id}"
                )
            # Partial fill occurred before cancellation took effect
            partial_order = OmsStateMachine.transition(
                pending_order,
                OmsOrderState.PARTIALLY_FILLED,
                at=step_time,
                filled_qty=venue_order.executed_qty,
                average_fill_price=fill_price,
                reason="PARTIAL_FILL_DURING_CANCEL_RACE",
            )
            self.oms_store.apply_transition(
                pending_order,
                partial_order,
                event_id=self._generate_event_id("partial_during_cancel"),
            )
            pending_order = partial_order
            step_time = max(pending_order.updated_at, now or datetime.now(UTC))

        # Final CANCELLED transition
        cancelled_order = OmsStateMachine.transition(
            pending_order,
            OmsOrderState.CANCELLED,
            at=step_time,
            reason="VENUE_CANCELLED",
        )
        self.oms_store.apply_transition(
            pending_order,
            cancelled_order,
            event_id=self._generate_event_id("cancelled"),
        )
        return cancelled_order

    def resolve_unknown_order(self, order: OmsOrder, *, now: datetime | None = None) -> OmsOrder:
        """Query venue truth to deterministically resolve an UNKNOWN order state."""
        if order.state != OmsOrderState.UNKNOWN:
            return order

        now_utc = max(order.updated_at, now or datetime.now(UTC))
        venue_order = None
        if order.venue_order_id:
            venue_order = self.venue.get_order(order.pair, order.venue_order_id)
        if venue_order is None and order.client_order_id:
            venue_order = self.venue.get_order_by_client_order_id(order.pair, order.client_order_id)

        if venue_order is None:
            # Critical financial safety invariant:
            # An inconclusive lookup (None) CANNOT be treated as evidence of rejection.
            # Temporary transport drops or visibility delays could cause None.
            # The order must REMAIN in UNKNOWN state to prevent duplicate submissions.
            logger.warning(
                "OrderRouter: Order %s lookup inconclusive on venue. Remaining in UNKNOWN state.",
                order.internal_order_id,
            )
            return order

        status = venue_order.status.lower()
        if status in ("rejected",):
            resolved = OmsStateMachine.transition(
                order,
                OmsOrderState.REJECTED,
                at=now_utc,
                reason="VENUE_EXPLICIT_REJECT",
            )
        elif status == "open":
            target_state = OmsOrderState.ACKNOWLEDGED
            resolved = OmsStateMachine.transition(
                order,
                target_state,
                at=now_utc,
                venue_order_id=venue_order.order_id,
                reason="RESOLVED_OPEN_ON_VENUE",
            )
        elif status == "filled":
            target_state = OmsOrderState.FILLED
            fill_price = venue_order.price or order.limit_price or order.average_fill_price
            if fill_price is None or fill_price <= Decimal("0"):
                raise ValueError(f"FILL_PRICE_REQUIRED_FOR_RESOLVE:{order.internal_order_id}")
            resolved = OmsStateMachine.transition(
                order,
                target_state,
                at=now_utc,
                venue_order_id=venue_order.order_id,
                filled_qty=order.desired_qty,
                average_fill_price=fill_price,
                reason="RESOLVED_FILLED_ON_VENUE",
            )
        elif status in ("cancelled", "canceled"):
            target_state = OmsOrderState.CANCELLED
            resolved = OmsStateMachine.transition(
                order,
                target_state,
                at=now_utc,
                venue_order_id=venue_order.order_id,
                reason="RESOLVED_CANCELLED_ON_VENUE",
            )
        else:
            msg = (
                f"Cannot deterministically resolve order {order.internal_order_id} "
                f"with status {status}"
            )
            raise UnresolvedOrderStateError(msg)

        self.oms_store.apply_transition(
            order,
            resolved,
            event_id=self._generate_event_id("resolved"),
        )
        return resolved
