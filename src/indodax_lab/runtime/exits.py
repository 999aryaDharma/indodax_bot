"""C02 trailing/breakeven exit state machine (RP-02).

Exit semantics mirror the shadow engine's C02 position monitoring
(``paper/live_shadow_engine.py`` ``check_open_positions``), reused here as a
pure, persistible state machine:

- Trailing stop: ``stop_loss = max(stop_loss, highest_price - 2.0 * entry_atr)``
  — the stop ratchets up only, never down.
- Time-decay breakeven: once ``bars_held >= 14`` and the position is not up
  ``1.0 * entry_atr`` from entry, the stop moves to breakeven
  (``entry_price``) exactly once.
- Both advances happen once per new closed bar, identified by the bar's
  UTC ``close_time``; re-processing the same bar is a no-op.

All accounting is Decimal; all timestamps are UTC-aware. The state is a
frozen, canonically serializable pydantic model so it can be persisted and
reloaded by the execution state store without semantic drift.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import MarketBar

# C02 exit policy constants (versioned policy v1).
TRAILING_ATR_MULTIPLIER = Decimal("2.0")
BREAKEVEN_BARS_HELD = 14
BREAKEVEN_ATR_MULTIPLIER = Decimal("1.0")


def _ensure_utc(dt: object, field_name: str) -> object:
    if not hasattr(dt, "tzinfo") or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class PositionExitState(BaseModel):
    """Exit state for one open position (one per pair)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    strategy_id: str
    entry_price: Decimal
    entry_atr: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None = None
    highest_price: Decimal
    qty: Decimal
    bars_held: int = 0
    last_bar_close_time: object = None
    time_decay_breakeven: bool = False

    @field_validator("entry_price", "entry_atr", "stop_loss", "highest_price", "qty")
    @classmethod
    def _positive(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("POSITIVE_DECIMAL_REQUIRED")
        return value

    @field_validator("last_bar_close_time")
    @classmethod
    def _utc(cls, value: object) -> object:
        if value is not None:
            _ensure_utc(value, "last_bar_close_time")
        return value


class ExitState(BaseModel):
    """Persistible per-candidate exit state (one position per pair)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    positions: tuple[PositionExitState, ...] = ()

    def for_pair(self, pair: str) -> PositionExitState | None:
        for position in self.positions:
            if position.pair == pair:
                return position
        return None


class ExitDecision(BaseModel):
    """One exit decision before venue effects (no order is submitted)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    strategy_id: str
    side: OrderSide
    qty: Decimal
    price: Decimal
    reason: str


def open_position(
    state: ExitState,
    *,
    pair: str,
    strategy_id: str,
    entry_price: Decimal,
    entry_atr: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal | None = None,
    qty: Decimal,
) -> ExitState:
    """Open (or reset) a position's exit state from an entry intent."""
    position = PositionExitState(
        pair=pair,
        strategy_id=strategy_id,
        entry_price=entry_price,
        entry_atr=entry_atr,
        stop_loss=stop_loss,
        take_profit=take_profit,
        highest_price=entry_price,
        qty=qty,
    )
    others = tuple(item for item in state.positions if item.pair != pair)
    return ExitState(positions=others + (position,))


def advance_exit_state(state: ExitState, bar: MarketBar) -> ExitState:
    """Advance exit state once per new closed bar (causal, idempotent per bar).

    Re-processing the same bar (same UTC ``close_time``) leaves the state
    unchanged: the trailing/breakeven advance happens exactly once per new
    closed bar, never per evaluation.
    """
    advanced: list[PositionExitState] = []
    for position in state.positions:
        if position.pair != bar.pair:
            advanced.append(position)
            continue
        if position.last_bar_close_time == bar.close_time:
            # Same closed bar — no second advance.
            advanced.append(position)
            continue

        highest = max(position.highest_price, bar.high)
        bars_held = position.bars_held + 1
        stop = position.stop_loss

        # Trailing stop: ratchet up only, 2.0x ATR behind the highest price.
        trailing_sl = highest - TRAILING_ATR_MULTIPLIER * position.entry_atr
        if trailing_sl > stop:
            stop = trailing_sl

        # Time-decay breakeven: after 14 closed bars, if not up 1.0x ATR,
        # move the stop to breakeven exactly once.
        breakeven = position.time_decay_breakeven
        if (
            not breakeven
            and bars_held >= BREAKEVEN_BARS_HELD
            and highest < position.entry_price + BREAKEVEN_ATR_MULTIPLIER * position.entry_atr
        ):
            if position.entry_price > stop:
                stop = position.entry_price
            breakeven = True

        advanced.append(
            position.model_copy(
                update={
                    "highest_price": highest,
                    "bars_held": bars_held,
                    "stop_loss": stop,
                    "last_bar_close_time": bar.close_time,
                    "time_decay_breakeven": breakeven,
                }
            )
        )
    return ExitState(positions=tuple(advanced))


def exit_decisions(state: ExitState, bar: MarketBar) -> tuple[ExitDecision, ...]:
    """Stop-first exit decisions for one closed bar (before venue effects).

    A bar that spans both the stop and the target is ambiguous OHLCV evidence;
    the stop is evaluated first (conservative). The exit price is the
    conservative ``min(close, trigger)`` so a gap through the trigger never
    produces a better-than-trigger fill.
    """
    position = state.for_pair(bar.pair)
    if position is None:
        return ()

    hit_stop = bar.low <= position.stop_loss
    hit_target = (
        position.take_profit is not None and bar.high >= position.take_profit
    )

    if hit_stop:
        price = min(bar.close, position.stop_loss)
        return (
            ExitDecision(
                pair=position.pair,
                strategy_id=position.strategy_id,
                side=OrderSide.SELL,
                qty=position.qty,
                price=price,
                reason="STOP_LOSS",
            ),
        )
    if hit_target:
        price = min(bar.close, position.take_profit)
        return (
            ExitDecision(
                pair=position.pair,
                strategy_id=position.strategy_id,
                side=OrderSide.SELL,
                qty=position.qty,
                price=price,
                reason="TAKE_PROFIT",
            ),
        )
    return ()


__all__ = [
    "ExitDecision",
    "ExitState",
    "PositionExitState",
    "advance_exit_state",
    "exit_decisions",
    "open_position",
]
