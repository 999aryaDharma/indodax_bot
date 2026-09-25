"""Portfolio constructor translating strategy intents into target exposures and rebalance orders."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.ledger import Position
from indodax_lab.contracts.decision import SignalIntent


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class TargetExposure(BaseModel):
    """Target position inventory and rebalance delta for a single instrument."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    target_qty: Decimal
    current_qty: Decimal
    delta_qty: Decimal
    side: OrderSide | None = None
    mark_price: Decimal
    target_notional: Decimal
    delta_notional: Decimal

    @field_validator("target_qty", "current_qty", "mark_price", mode="before")
    @classmethod
    def parse_non_negative(cls, value: object) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec < 0:
            raise ValueError("NON_NEGATIVE_FINITE_DECIMAL_REQUIRED")
        return dec


class PendingReservation(BaseModel):
    """Unfilled order remainder reserved against one portfolio revision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: str
    strategy_id: str
    pair: str
    side: OrderSide
    remaining_qty: Decimal
    reserved_notional: Decimal
    reserved_fee: Decimal = Decimal("0")
    reserved_risk: Decimal = Decimal("0")

    @field_validator("order_id", "strategy_id")
    @classmethod
    def require_text_identity(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("RESERVATION_IDENTITY_REQUIRED")
        return normalized

    @field_validator("pair")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        pair = value.strip().lower()
        if not pair:
            raise ValueError("RESERVATION_PAIR_REQUIRED")
        return pair

    @field_validator(
        "remaining_qty", "reserved_notional", "reserved_fee", "reserved_risk", mode="before"
    )
    @classmethod
    def parse_amounts(cls, value: Any) -> Decimal:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError("INVALID_RESERVATION_AMOUNT")
        return amount

    @model_validator(mode="after")
    def require_positive_remainder(self) -> PendingReservation:
        if self.remaining_qty <= 0 or self.reserved_notional <= 0:
            raise ValueError("POSITIVE_RESERVATION_REMAINDER_REQUIRED")
        return self


class PortfolioPosition(BaseModel):
    """Immutable holding copied into a portfolio revision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    base_qty: Decimal
    cost_basis: Decimal


class PortfolioState(BaseModel):
    """Immutable financial snapshot; cash is ledger cash before pending reservations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valuation_currency: str
    cash_balance: Decimal
    positions: tuple[PortfolioPosition, ...] = ()
    mark_prices: tuple[tuple[str, Decimal], ...] = ()
    reservations: tuple[PendingReservation, ...] = ()
    revision: int = Field(ge=0, strict=True)

    @field_validator("cash_balance", mode="before")
    @classmethod
    def parse_cash(cls, value: Any) -> Decimal:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError("INVALID_PORTFOLIO_CASH")
        return amount

    @field_validator("valuation_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        currency = value.strip().upper()
        if not currency:
            raise ValueError("VALUATION_CURRENCY_REQUIRED")
        return currency

    @field_validator("positions", mode="before")
    @classmethod
    def normalize_positions(cls, value: Any) -> Any:
        rows = tuple(value.values()) if isinstance(value, Mapping) else value
        if rows is None:
            return rows
        return tuple(
            PortfolioPosition(pair=row.pair, base_qty=row.base_qty, cost_basis=row.cost_basis)
            if isinstance(row, Position)
            else row
            for row in rows
        )

    @field_validator("mark_prices", mode="before")
    @classmethod
    def normalize_marks(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(
                sorted((str(pair).lower(), Decimal(str(price))) for pair, price in value.items())
            )
        return value

    @field_validator("reservations", mode="before")
    @classmethod
    def normalize_reservations(cls, value: Any) -> Any:
        return tuple(value.values()) if isinstance(value, Mapping) else value

    @model_validator(mode="after")
    def validate_snapshot(self) -> PortfolioState:
        positions = self.positions_by_pair
        marks = self.mark_prices_by_pair
        if len(positions) != len(self.positions):
            raise ValueError("DUPLICATE_PORTFOLIO_POSITION_PAIR")
        if len({r.order_id for r in self.reservations}) != len(self.reservations):
            raise ValueError("DUPLICATE_PENDING_RESERVATION_ID")
        if any(not price.is_finite() or price <= 0 for price in marks.values()):
            raise ValueError("INVALID_PORTFOLIO_MARK")
        if len(marks) != len(self.mark_prices):
            raise ValueError("DUPLICATE_PORTFOLIO_MARK")
        if any(position.base_qty > 0 and pair not in marks for pair, position in positions.items()):
            raise ValueError("MISSING_POSITION_MARK")
        if any(r.side == OrderSide.BUY and r.pair not in marks for r in self.reservations):
            raise ValueError("MISSING_RESERVATION_MARK")
        held = {pair: position.base_qty for pair, position in positions.items()}
        for pair, reserved_qty in self.pending_sell_qty_by_pair.items():
            if reserved_qty > held.get(pair, Decimal("0")):
                raise ValueError("SELL_RESERVATIONS_EXCEED_POSITION")
        if self.reserved_cash > self.cash_balance:
            raise ValueError("RESERVATIONS_EXCEED_CASH")
        return self

    @property
    def positions_by_pair(self) -> dict[str, Position]:
        return {position.pair.lower(): position for position in self.positions}

    @property
    def mark_prices_by_pair(self) -> dict[str, Decimal]:
        return {pair.lower(): price for pair, price in self.mark_prices}

    @property
    def reserved_cash(self) -> Decimal:
        return sum(
            (
                r.reserved_notional + r.reserved_fee
                for r in self.reservations
                if r.side == OrderSide.BUY
            ),
            Decimal("0"),
        )

    @property
    def available_cash(self) -> Decimal:
        return self.cash_balance - self.reserved_cash

    @property
    def pending_exposure_by_pair(self) -> dict[str, Decimal]:
        exposure: dict[str, Decimal] = {}
        marks = self.mark_prices_by_pair
        for reservation in self.reservations:
            if reservation.side == OrderSide.BUY:
                marked_notional = reservation.remaining_qty * marks[reservation.pair]
                exposure[reservation.pair] = (
                    exposure.get(reservation.pair, Decimal("0"))
                    + max(reservation.reserved_notional, marked_notional)
                )
        return exposure

    @property
    def pending_risk_by_strategy(self) -> dict[str, Decimal]:
        risk: dict[str, Decimal] = {}
        for reservation in self.reservations:
            if reservation.side == OrderSide.BUY:
                risk[reservation.strategy_id] = (
                    risk.get(reservation.strategy_id, Decimal("0")) + reservation.reserved_risk
                )
        return risk

    @property
    def pending_sell_qty_by_pair(self) -> dict[str, Decimal]:
        quantities: dict[str, Decimal] = {}
        for reservation in self.reservations:
            if reservation.side == OrderSide.SELL:
                quantities[reservation.pair] = (
                    quantities.get(reservation.pair, Decimal("0")) + reservation.remaining_qty
                )
        return quantities

    @property
    def equity(self) -> Decimal:
        marks = self.mark_prices_by_pair
        asset_value = sum(
            (
                position.base_qty * marks.get(pair, Decimal("0"))
                for pair, position in self.positions_by_pair.items()
            ),
            Decimal("0"),
        )
        return self.cash_balance + asset_value


class AllocationPolicy(BaseModel):
    """Versioned deterministic contention order for same-pair strategy intents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    version: str
    strategy_priorities: tuple[tuple[str, int], ...] = ()

    @field_validator("policy_id", "version")
    @classmethod
    def require_policy_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ALLOCATION_POLICY_IDENTITY_REQUIRED")
        return value

    @field_validator("strategy_priorities", mode="before")
    @classmethod
    def normalize_priorities(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            if any(type(priority) is not int for priority in value.values()):
                raise ValueError("INVALID_STRATEGY_PRIORITY_MAP")
            return tuple(sorted((str(key), priority) for key, priority in value.items()))
        if value is not None and any(
            not isinstance(item, (list, tuple))
            or len(item) != 2
            or type(item[1]) is not int
            for item in value
        ):
            raise ValueError("INVALID_STRATEGY_PRIORITY_MAP")
        return value

    @model_validator(mode="after")
    def validate_priorities(self) -> AllocationPolicy:
        keys = [key for key, _ in self.strategy_priorities]
        if len(keys) != len(set(keys)) or any(
            not key.strip() or isinstance(priority, bool) or not isinstance(priority, int)
            for key, priority in self.strategy_priorities
        ):
            raise ValueError("INVALID_STRATEGY_PRIORITY_MAP")
        return self

    @property
    def priority_map(self) -> dict[str, int]:
        return dict(self.strategy_priorities)


class PortfolioConstructor:
    """Deterministic constructor translating strategy intents and marks into target exposures."""

    def __init__(
        self,
        *,
        min_order_notional: Decimal = Decimal("10000"),
        lot_size_step: Decimal = Decimal("0.00000001"),
        quantity_precision: int = 8,
    ) -> None:
        self.min_order_notional = Decimal(str(min_order_notional))
        if not self.min_order_notional.is_finite() or self.min_order_notional <= 0:
            raise ValueError("INVALID_MIN_ORDER_NOTIONAL")
        self.lot_size_step = Decimal(str(lot_size_step))
        self.quantity_precision = quantity_precision

    def construct_exposures(
        self,
        intents: Sequence[SignalIntent],
        current_positions: Mapping[str, Position],
        mark_prices: Mapping[str, Decimal],
    ) -> tuple[TargetExposure, ...]:
        """Compute target exposures by combining strategy intents with current positions."""
        exposures: list[TargetExposure] = []
        intents_by_pair: dict[str, SignalIntent] = {}
        for intent in intents:
            pair = intent.pair.lower()
            if pair in intents_by_pair:
                raise ValueError(f"SAME_PAIR_INTENT_CONFLICT:{pair}")
            intents_by_pair[pair] = intent
        all_pairs = set(intents_by_pair.keys()) | {p.lower() for p in current_positions.keys()}

        for pair in sorted(all_pairs):
            mark_price = mark_prices.get(pair)
            if mark_price is None or mark_price <= Decimal("0"):
                raise ValueError(f"MISSING_OR_INVALID_MARK_PRICE:{pair}")

            pos = current_positions.get(pair)
            current_qty = pos.base_qty if pos is not None else Decimal("0")
            intent = intents_by_pair.get(pair)

            if intent is not None:
                if intent.side == OrderSide.BUY:
                    # Incremental or target buy
                    target_qty = current_qty + intent.desired_qty
                elif intent.side == OrderSide.SELL:
                    # Desired reduction
                    target_qty = max(Decimal("0"), current_qty - intent.desired_qty)
                else:
                    target_qty = current_qty
            else:
                target_qty = current_qty

            # Quantize target_qty
            target_qty = target_qty.quantize(
                Decimal(10) ** -self.quantity_precision, rounding=ROUND_DOWN
            )
            delta_qty = target_qty - current_qty

            if delta_qty > Decimal("0"):
                side = OrderSide.BUY
            elif delta_qty < Decimal("0"):
                side = OrderSide.SELL
            else:
                side = None

            delta_abs = abs(delta_qty)
            target_notional = target_qty * mark_price
            delta_notional = delta_abs * mark_price

            exposures.append(
                TargetExposure(
                    pair=pair,
                    target_qty=target_qty,
                    current_qty=current_qty,
                    delta_qty=delta_qty,
                    side=side,
                    mark_price=mark_price,
                    target_notional=target_notional,
                    delta_notional=delta_notional,
                )
            )

        return tuple(exposures)

    def construct_orders(
        self,
        intents: Sequence[SignalIntent],
        state: PortfolioState,
        allocation_policy: AllocationPolicy | None,
    ) -> tuple[SignalIntent, ...]:
        """Validate, arbitrate and deterministically order candidate intents."""
        if not isinstance(state, PortfolioState):
            raise ValueError("PORTFOLIO_STATE_REQUIRED")
        if allocation_policy is not None and not isinstance(allocation_policy, AllocationPolicy):
            raise ValueError("VERSIONED_ALLOCATION_POLICY_REQUIRED")

        unique: dict[str, SignalIntent] = {}
        grouped: dict[str, list[SignalIntent]] = {}
        marks = state.mark_prices_by_pair
        for intent in intents:
            identity = intent.intent_id
            if identity in unique:
                if unique[identity] != intent:
                    raise ValueError(f"DUPLICATE_INTENT_ID_CONFLICT:{identity}")
                continue
            unique[identity] = intent
            pair = intent.pair.lower()
            if pair not in marks:
                raise ValueError(f"MISSING_OR_INVALID_MARK_PRICE:{pair}")
            grouped.setdefault(pair, []).append(intent)

        priorities = allocation_policy.priority_map if allocation_policy else {}
        selected: list[SignalIntent] = []
        for pair, candidates in grouped.items():
            if len(candidates) > 1 and allocation_policy is None:
                raise ValueError(f"SAME_PAIR_INTENT_CONFLICT:{pair}")
            winner = min(
                candidates,
                key=lambda item: (
                    -priorities.get(item.strategy_id, 0),
                    item.strategy_id,
                    item.intent_id,
                ),
            )
            selected.append(winner)
        return tuple(
            sorted(
                selected,
                key=lambda item: (
                    -priorities.get(item.strategy_id, 0),
                    item.strategy_id,
                    item.intent_id,
                    item.pair.lower(),
                ),
            )
        )

    def generate_rebalance_intents(
        self,
        exposures: Sequence[TargetExposure],
        *,
        decision_ts: datetime,
        strategy_id: str = "portfolio_rebalance",
    ) -> tuple[SignalIntent, ...]:
        """Convert target exposure deltas into executable SignalIntents."""
        _ensure_utc(decision_ts, "decision_ts")
        rebalance_intents: list[SignalIntent] = []

        for exp in exposures:
            if exp.side is None or exp.delta_qty == Decimal("0"):
                continue

            delta_abs = abs(exp.delta_qty).quantize(
                Decimal(10) ** -self.quantity_precision, rounding=ROUND_DOWN
            )
            if delta_abs <= Decimal("0"):
                continue

            delta_notional = delta_abs * exp.mark_price
            if delta_notional < self.min_order_notional:
                continue

            intent_id = f"rebal_{exp.pair}_{uuid.uuid4().hex[:8]}"
            rebalance_intents.append(
                SignalIntent(
                    intent_id=intent_id,
                    decision_ts=decision_ts,
                    pair=exp.pair,
                    side=exp.side,
                    desired_qty=delta_abs,
                    limit_price=exp.mark_price,
                    strategy_id=strategy_id,
                )
            )

        return tuple(rebalance_intents)
