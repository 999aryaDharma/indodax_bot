"""Order router and execution coordinator enforcing OMS durability and fail-closed uncertainty."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from indodax_lab.control.authority import WritePermit
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

    def __init__(
        self,
        oms_store: OmsStore,
        venue: TradingVenue,
        *,
        require_permit: bool = False,
        enforce_production_semantics: bool | None = None,
    ) -> None:
        from indodax_lab.execution.indodax_trading import IndodaxTradingClient

        self.oms_store = oms_store
        self.venue = venue
        self.require_permit = require_permit
        if enforce_production_semantics is None:
            self.enforce_production_semantics = (
                require_permit or isinstance(venue, IndodaxTradingClient)
            )
        else:
            self.enforce_production_semantics = enforce_production_semantics
        self._consumed_permit_ids: set[str] = set()

    def _generate_event_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def submit_order(
        self,
        order: OmsOrder,
        *,
        permit: WritePermit | None = None,
        now: datetime | None = None,
    ) -> OmsOrder:
        """Submit an order with guaranteed pre-network durability and uncertainty capture."""
        current_time = max(order.updated_at, now or datetime.now(UTC))

        from indodax_lab.execution.indodax_trading import IndodaxTradingClient

        # Pre-write permit enforcement at real writer / configured boundary
        if (
            self.require_permit
            or isinstance(self.venue, IndodaxTradingClient)
            or permit is not None
        ):
            if permit is None:
                raise PermissionError(
                    "MISSING_WRITE_PERMIT: Direct real-writer call without valid permit fails"
                )
            if permit.permit_id in self._consumed_permit_ids:
                raise PermissionError(f"PERMIT_ALREADY_USED:{permit.permit_id}")
            if current_time > permit.expires_at:
                raise PermissionError(f"PERMIT_EXPIRED:{permit.permit_id}")
            if permit.action != "SUBMIT":
                raise PermissionError(f"PERMIT_ACTION_MISMATCH:{permit.action}!=SUBMIT")
            if permit.order_internal_id != order.internal_order_id:
                raise PermissionError(
                    f"PERMIT_ORDER_MISMATCH:{permit.order_internal_id}!={order.internal_order_id}"
                )
            if not permit.verify_order(order):
                raise PermissionError("PERMIT_ORDER_DIGEST_MISMATCH")
            self._consumed_permit_ids.add(permit.permit_id)

        # Supported order semantics pre-validation (PM-04-FR3)
        if self.enforce_production_semantics:
            if order.limit_price is None or order.limit_price <= Decimal("0"):
                raise ValueError(
                    f"UNSUPPORTED_ORDER_SEMANTICS:ORDER_LIMIT_PRICE_REQUIRED:"
                    f"{order.client_order_id} - "
                    "Production Indodax venue requires order_type=limit and positive limit_price"
                )
            if order.order_type.lower() != "limit" or str(order.time_in_force).upper() != "GTC":
                raise ValueError(
                    f"UNSUPPORTED_ORDER_SEMANTICS:{order.order_type}:{order.time_in_force} - "
                    "Production Indodax venue requires order_type=limit and time_in_force=GTC"
                )

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

    def cancel_order(
        self,
        order: OmsOrder,
        *,
        permit: WritePermit | None = None,
        now: datetime | None = None,
    ) -> OmsOrder:
        """Cancel an open order, correctly handling in-flight fills and cancel/fill races."""
        current_time = max(order.updated_at, now or datetime.now(UTC))

        from indodax_lab.execution.indodax_trading import IndodaxTradingClient

        # Pre-write permit enforcement at cancel writer boundary
        if (
            self.require_permit
            or isinstance(self.venue, IndodaxTradingClient)
            or permit is not None
        ):
            if permit is None:
                raise PermissionError("MISSING_WRITE_PERMIT: Cancel without valid permit fails")
            if permit.permit_id in self._consumed_permit_ids:
                raise PermissionError(f"PERMIT_ALREADY_USED:{permit.permit_id}")
            if current_time > permit.expires_at:
                raise PermissionError(f"PERMIT_EXPIRED:{permit.permit_id}")
            if permit.action != "CANCEL":
                raise PermissionError(f"PERMIT_ACTION_MISMATCH:{permit.action}!=CANCEL")
            if permit.order_internal_id != order.internal_order_id:
                raise PermissionError(
                    f"PERMIT_ORDER_MISMATCH:{permit.order_internal_id}!={order.internal_order_id}"
                )
            self._consumed_permit_ids.add(permit.permit_id)

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

        fill_price = order.average_fill_price
        if venue_order.executed_qty > pending_order.filled_qty:
            unknown_order = OmsStateMachine.transition(
                pending_order,
                OmsOrderState.UNKNOWN,
                at=step_time,
                venue_order_id=venue_order.order_id,
                reason="FILL_HISTORY_REQUIRED_AFTER_CANCEL",
            )
            self.oms_store.apply_transition(
                pending_order,
                unknown_order,
                event_id=self._generate_event_id("cancel_fill_history_required"),
            )
            return unknown_order

        venue_status = venue_order.status.upper()
        if (
            venue_order.executed_qty < pending_order.filled_qty
            or (
                venue_status in {"FILLED", "FINISHED"}
                and venue_order.executed_qty != order.desired_qty
            )
        ):
            unknown_order = OmsStateMachine.transition(
                pending_order,
                OmsOrderState.UNKNOWN,
                at=step_time,
                venue_order_id=venue_order.order_id,
                reason="CANCEL_STATE_INCONSISTENT_WITH_FILL_QUANTITY",
            )
            self.oms_store.apply_transition(
                pending_order,
                unknown_order,
                event_id=self._generate_event_id("cancel_inconsistent_fill_state"),
            )
            return unknown_order

        if venue_status not in {"CANCELLED", "CANCELED", "FILLED", "FINISHED"}:
            unknown_order = OmsStateMachine.transition(
                pending_order,
                OmsOrderState.UNKNOWN,
                at=step_time,
                venue_order_id=venue_order.order_id,
                reason=f"CANCEL_STATE_INCONCLUSIVE:{venue_order.status}",
            )
            self.oms_store.apply_transition(
                pending_order, unknown_order, event_id=self._generate_event_id("cancel_unknown")
            )
            return unknown_order
        # Check if fill occurred during cancel race:
        is_filled = (
            venue_status in {"FILLED", "FINISHED"}
            or venue_order.executed_qty == order.desired_qty
        )
        if is_filled:
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
        if order.state not in {OmsOrderState.UNKNOWN, OmsOrderState.PARTIALLY_FILLED}:
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
        if venue_order.executed_qty > order.filled_qty:
            raise UnresolvedOrderStateError(
                f"FILL_HISTORY_REQUIRED:{order.internal_order_id} "
                f"venue={venue_order.executed_qty} oms={order.filled_qty}"
            )
        if venue_order.executed_qty < order.filled_qty:
            raise UnresolvedOrderStateError(
                f"FILL_QUANTITY_REGRESSION:{order.internal_order_id}"
            )
        if order.filled_qty and order.average_fill_price is None:
            raise UnresolvedOrderStateError(f"FILL_HISTORY_REQUIRED:{order.internal_order_id}")

        if status in ("rejected",):
            resolved = OmsStateMachine.transition(
                order,
                OmsOrderState.REJECTED,
                at=now_utc,
                reason="VENUE_EXPLICIT_REJECT",
            )
        elif status in ("open", "new", "partially_filled"):
            target_state = (
                OmsOrderState.PARTIALLY_FILLED
                if venue_order.executed_qty
                else OmsOrderState.ACKNOWLEDGED
            )
            resolved = OmsStateMachine.transition(
                order,
                target_state,
                at=now_utc,
                venue_order_id=venue_order.order_id,
                filled_qty=order.filled_qty,
                average_fill_price=order.average_fill_price,
                reason="RESOLVED_OPEN_ON_VENUE",
            )
        elif status == "filled":
            target_state = OmsOrderState.FILLED
            if venue_order.executed_qty != order.desired_qty or order.average_fill_price is None:
                raise UnresolvedOrderStateError(
                    f"FILL_HISTORY_REQUIRED:{order.internal_order_id}"
                )
            resolved = OmsStateMachine.transition(
                order,
                target_state,
                at=now_utc,
                venue_order_id=venue_order.order_id,
                filled_qty=order.desired_qty,
                average_fill_price=order.average_fill_price,
                reason="RESOLVED_FILLED_ON_VENUE",
            )
        elif status in ("cancelled", "canceled"):
            target_state = OmsOrderState.CANCELLED
            resolved = OmsStateMachine.transition(
                order,
                target_state,
                at=now_utc,
                venue_order_id=venue_order.order_id,
                filled_qty=order.filled_qty,
                average_fill_price=order.average_fill_price,
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
