"""Portfolio constructor translating strategy intents into target exposures and rebalance orders."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import Position


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
        intents_by_pair: dict[str, SignalIntent] = {i.pair.lower(): i for i in intents}
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
