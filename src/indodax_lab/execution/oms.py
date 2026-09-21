"""Durable OMS domain state machine without venue write capability.

The OMS records intent and uncertainty. It does not submit or cancel orders itself.
A future write-capable venue adapter must go through this state machine.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from indodax_lab.backtest.costs import OrderSide


def _ensure_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return value


class OmsOrderState(StrEnum):
    """Canonical order lifecycle including uncertain write outcomes."""

    NEW = "NEW"
    SUBMITTING = "SUBMITTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


TERMINAL_STATES = {
    OmsOrderState.FILLED,
    OmsOrderState.CANCELLED,
    OmsOrderState.REJECTED,
}

_ALLOWED_TRANSITIONS: dict[OmsOrderState, set[OmsOrderState]] = {
    OmsOrderState.NEW: {OmsOrderState.SUBMITTING},
    OmsOrderState.SUBMITTING: {
        OmsOrderState.ACKNOWLEDGED,
        OmsOrderState.PARTIALLY_FILLED,
        OmsOrderState.FILLED,
        OmsOrderState.REJECTED,
        OmsOrderState.UNKNOWN,
    },
    OmsOrderState.ACKNOWLEDGED: {
        OmsOrderState.PARTIALLY_FILLED,
        OmsOrderState.FILLED,
        OmsOrderState.CANCEL_PENDING,
        OmsOrderState.CANCELLED,
        OmsOrderState.UNKNOWN,
    },
    OmsOrderState.PARTIALLY_FILLED: {
        OmsOrderState.PARTIALLY_FILLED,
        OmsOrderState.FILLED,
        OmsOrderState.CANCEL_PENDING,
        OmsOrderState.CANCELLED,
        OmsOrderState.UNKNOWN,
    },
    OmsOrderState.CANCEL_PENDING: {
        OmsOrderState.PARTIALLY_FILLED,
        OmsOrderState.FILLED,
        OmsOrderState.CANCELLED,
        OmsOrderState.UNKNOWN,
    },
    OmsOrderState.UNKNOWN: {
        OmsOrderState.ACKNOWLEDGED,
        OmsOrderState.PARTIALLY_FILLED,
        OmsOrderState.FILLED,
        OmsOrderState.CANCELLED,
        OmsOrderState.REJECTED,
    },
    OmsOrderState.FILLED: set(),
    OmsOrderState.CANCELLED: set(),
    OmsOrderState.REJECTED: set(),
}


class OmsOrder(BaseModel):
    """Immutable versioned OMS order snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    internal_order_id: str
    client_order_id: str
    pair: str
    side: OrderSide
    desired_qty: Decimal
    state: OmsOrderState = OmsOrderState.NEW
    venue_order_id: str | None = None
    filled_qty: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    last_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int = 1

    @field_validator("desired_qty", mode="before")
    @classmethod
    def validate_desired_qty(cls, value: Any) -> Decimal:
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed <= 0:
            raise ValueError("OMS_DESIRED_QTY_INVALID")
        return parsed

    @field_validator("filled_qty", mode="before")
    @classmethod
    def validate_filled_qty(cls, value: Any) -> Decimal:
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed < 0:
            raise ValueError("OMS_FILLED_QTY_INVALID")
        return parsed

    @field_validator("average_fill_price", mode="before")
    @classmethod
    def validate_average_fill_price(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        parsed = Decimal(str(value))
        if not parsed.is_finite() or parsed <= 0:
            raise ValueError("OMS_AVERAGE_FILL_PRICE_INVALID")
        return parsed

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "oms_timestamp")

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if not self.internal_order_id or not self.client_order_id:
            raise ValueError("OMS_ORDER_ID_REQUIRED")
        if self.version < 1:
            raise ValueError("OMS_VERSION_INVALID")
        if self.updated_at < self.created_at:
            raise ValueError("OMS_TIMESTAMP_ORDER_INVALID")
        if self.filled_qty > self.desired_qty:
            raise ValueError("OMS_OVERFILL")
        if self.state == OmsOrderState.FILLED and self.filled_qty != self.desired_qty:
            raise ValueError("OMS_FILLED_STATE_QTY_MISMATCH")
        if self.filled_qty > 0 and self.average_fill_price is None:
            raise ValueError("OMS_FILL_PRICE_REQUIRED")
        return self


class OmsTransitionError(RuntimeError):
    """Invalid lifecycle transition."""


class OmsStateMachine:
    """Pure deterministic state transition authority."""

    @staticmethod
    def create(
        *,
        internal_order_id: str,
        client_order_id: str,
        pair: str,
        side: OrderSide,
        desired_qty: Decimal,
        created_at: datetime,
    ) -> OmsOrder:
        _ensure_utc(created_at, "created_at")
        return OmsOrder(
            internal_order_id=internal_order_id,
            client_order_id=client_order_id,
            pair=pair,
            side=side,
            desired_qty=desired_qty,
            created_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
    def transition(
        order: OmsOrder,
        to_state: OmsOrderState,
        *,
        at: datetime,
        venue_order_id: str | None = None,
        filled_qty: Decimal | None = None,
        average_fill_price: Decimal | None = None,
        reason: str | None = None,
    ) -> OmsOrder:
        _ensure_utc(at, "transition_at")
        allowed = _ALLOWED_TRANSITIONS[order.state]
        if to_state not in allowed:
            raise OmsTransitionError(
                f"OMS_INVALID_TRANSITION:{order.state}->{to_state}"
            )
        if at < order.updated_at:
            raise OmsTransitionError("OMS_TRANSITION_TIME_REGRESSION")

        next_venue_id = venue_order_id or order.venue_order_id
        next_filled = (
            Decimal(str(filled_qty)) if filled_qty is not None else order.filled_qty
        )
        if not next_filled.is_finite() or next_filled < 0:
            raise OmsTransitionError("OMS_FILLED_QTY_INVALID")
        if next_filled < order.filled_qty:
            raise OmsTransitionError("OMS_FILLED_QTY_REGRESSION")
        next_avg = (
            Decimal(str(average_fill_price))
            if average_fill_price is not None
            else order.average_fill_price
        )
        if next_avg is not None and (not next_avg.is_finite() or next_avg <= 0):
            raise OmsTransitionError("OMS_AVERAGE_FILL_PRICE_INVALID")

        if to_state in {
            OmsOrderState.ACKNOWLEDGED,
            OmsOrderState.PARTIALLY_FILLED,
            OmsOrderState.FILLED,
            OmsOrderState.CANCEL_PENDING,
            OmsOrderState.CANCELLED,
        } and not next_venue_id:
            raise OmsTransitionError("OMS_VENUE_ORDER_ID_REQUIRED")

        if to_state == OmsOrderState.PARTIALLY_FILLED:
            if next_filled <= 0 or next_filled >= order.desired_qty:
                raise OmsTransitionError("OMS_PARTIAL_FILL_QTY_INVALID")
        if to_state == OmsOrderState.FILLED:
            next_filled = order.desired_qty
            if next_avg is None:
                raise OmsTransitionError("OMS_FILL_PRICE_REQUIRED")
        if next_filled > order.desired_qty:
            raise OmsTransitionError("OMS_OVERFILL")
        if next_filled > 0 and next_avg is None:
            raise OmsTransitionError("OMS_FILL_PRICE_REQUIRED")

        next_payload = order.model_dump()
        next_payload.update(
            {
                "state": to_state,
                "venue_order_id": next_venue_id,
                "filled_qty": next_filled,
                "average_fill_price": next_avg,
                "last_reason": reason,
                "updated_at": at,
                "version": order.version + 1,
            }
        )
        return OmsOrder.model_validate(next_payload)
