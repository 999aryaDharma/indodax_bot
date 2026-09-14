"""Portfolio risk management, position sizing, and circuit breakers (SIM-02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import Position


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class RiskPolicy(BaseModel):
    """Versioned risk and portfolio constraints policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    version: str
    max_position_fraction: Decimal = Decimal("0.20")
    max_open_positions: int = 3
    min_order_notional: Decimal = Decimal("10000")
    max_daily_loss_fraction: Decimal = Decimal("0.05")
    max_weekly_loss_fraction: Decimal = Decimal("0.10")
    max_drawdown_halt_fraction: Decimal = Decimal("0.15")
    max_account_leverage: Decimal = Decimal("1.0")

    @field_validator(
        "max_position_fraction",
        "min_order_notional",
        "max_daily_loss_fraction",
        "max_weekly_loss_fraction",
        "max_drawdown_halt_fraction",
        "max_account_leverage",
        mode="before",
    )
    @classmethod
    def parse_decimal(cls, value: Any) -> Decimal:
        dec = Decimal(str(value))
        if not dec.is_finite() or dec < 0:
            raise ValueError("NON_NEGATIVE_FINITE_DECIMAL_REQUIRED")
        return dec


class RiskAssessmentResult(BaseModel):
    """Decision produced by the risk manager for an order intent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approved: bool
    approved_qty: Decimal = Decimal("0")
    approved_notional: Decimal = Decimal("0")
    reason_code: str
    rejection_reason: str | None = None


class PortfolioRiskManager:
    """Evaluates portfolio risk, sizes orders, and enforces circuit breakers."""

    def __init__(
        self,
        policy: RiskPolicy,
        initial_equity: Decimal,
        start_time: datetime,
        peak_equity: Decimal | None = None,
        is_halted: bool = False,
        halt_reason: str | None = None,
        halted_at: datetime | None = None,
        daily_start_equity: Decimal | None = None,
        daily_start_date: datetime | None = None,
        weekly_start_equity: Decimal | None = None,
        weekly_start_date: datetime | None = None,
    ) -> None:
        self.policy = policy
        self.initial_equity = Decimal(str(initial_equity))
        self.start_time = _ensure_utc(start_time, "start_time")
        self.peak_equity = Decimal(str(peak_equity)) if peak_equity is not None else self.initial_equity
        self.is_halted = is_halted
        self.halt_reason = halt_reason
        self.halted_at = _ensure_utc(halted_at, "halted_at") if halted_at is not None else None

        self.daily_start_equity = (
            Decimal(str(daily_start_equity)) if daily_start_equity is not None else self.initial_equity
        )
        self.daily_start_date = (
            _ensure_utc(daily_start_date, "daily_start_date")
            if daily_start_date is not None
            else self.start_time
        )
        self.weekly_start_equity = (
            Decimal(str(weekly_start_equity)) if weekly_start_equity is not None else self.initial_equity
        )
        self.weekly_start_date = (
            _ensure_utc(weekly_start_date, "weekly_start_date")
            if weekly_start_date is not None
            else self.start_time
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for durable persistence across restarts."""
        return {
            "policy": self.policy.model_dump(mode="json"),
            "initial_equity": str(self.initial_equity),
            "start_time": self.start_time.isoformat(),
            "peak_equity": str(self.peak_equity),
            "is_halted": self.is_halted,
            "halt_reason": self.halt_reason,
            "halted_at": self.halted_at.isoformat() if self.halted_at else None,
            "daily_start_equity": str(self.daily_start_equity),
            "daily_start_date": self.daily_start_date.isoformat(),
            "weekly_start_equity": str(self.weekly_start_equity),
            "weekly_start_date": self.weekly_start_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioRiskManager:
        """Restore state from serialized dictionary."""
        policy = RiskPolicy.model_validate(data["policy"])
        return cls(
            policy=policy,
            initial_equity=Decimal(data["initial_equity"]),
            start_time=datetime.fromisoformat(data["start_time"]),
            peak_equity=Decimal(data["peak_equity"]),
            is_halted=data["is_halted"],
            halt_reason=data["halt_reason"],
            halted_at=datetime.fromisoformat(data["halted_at"]) if data["halted_at"] else None,
            daily_start_equity=Decimal(data["daily_start_equity"]),
            daily_start_date=datetime.fromisoformat(data["daily_start_date"]),
            weekly_start_equity=Decimal(data["weekly_start_equity"]),
            weekly_start_date=datetime.fromisoformat(data["weekly_start_date"]),
        )

    def save_to_json(self, path: Path) -> None:
        """Persist risk state to JSON file."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_from_json(cls, path: Path) -> PortfolioRiskManager:
        """Load persisted risk state from JSON file."""
        raw = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(raw))

    def assess_order(
        self,
        intent: SignalIntent,
        current_equity: Decimal,
        current_positions: Mapping[str, Position],
        mark_prices: Mapping[str, Decimal],
        evaluation_time: datetime,
        available_cash: Decimal,
    ) -> RiskAssessmentResult:
        """Assess order sizing and enforce loss / drawdown circuit breakers."""
        eval_utc = _ensure_utc(evaluation_time, "evaluation_time")

        # Roll daily reference equity on date change
        if eval_utc.date() > self.daily_start_date.date():
            self.daily_start_equity = current_equity
            self.daily_start_date = eval_utc

        # Roll weekly reference equity on 7-day interval
        if eval_utc - self.weekly_start_date >= timedelta(days=7):
            self.weekly_start_equity = current_equity
            self.weekly_start_date = eval_utc

        # SIM-02-AC3: Drawdown halt tidak hilang setelah restart
        if self.is_halted:
            return RiskAssessmentResult(
                approved=False,
                reason_code="CIRCUIT_BREAKER_DRAWDOWN_HALT",
                rejection_reason=self.halt_reason,
            )

        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # Check maximum drawdown circuit breaker
        if self.peak_equity > Decimal("0"):
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            if drawdown >= self.policy.max_drawdown_halt_fraction:
                self.is_halted = True
                self.halt_reason = f"DRAWDOWN_BREACH:{drawdown:.4f}"
                self.halted_at = eval_utc
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="CIRCUIT_BREAKER_DRAWDOWN_HALT",
                    rejection_reason=self.halt_reason,
                )

        # SIM-02-AC2: Daily dan weekly loss memasukkan unrealized PnL
        # current_equity inherently includes marked open positions (cash + marked asset value)
        if self.daily_start_equity > Decimal("0"):
            daily_loss = (self.daily_start_equity - current_equity) / self.daily_start_equity
            if daily_loss >= self.policy.max_daily_loss_fraction:
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="CIRCUIT_BREAKER_DAILY_LOSS",
                    rejection_reason=f"DAILY_LOSS_LIMIT_REACHED:{daily_loss:.4f}",
                )

        if self.weekly_start_equity > Decimal("0"):
            weekly_loss = (self.weekly_start_equity - current_equity) / self.weekly_start_equity
            if weekly_loss >= self.policy.max_weekly_loss_fraction:
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="CIRCUIT_BREAKER_WEEKLY_LOSS",
                    rejection_reason=f"WEEKLY_LOSS_LIMIT_REACHED:{weekly_loss:.4f}",
                )

        # Mark price check
        price = mark_prices.get(intent.pair) or intent.limit_price
        if price is None or price <= Decimal("0"):
            return RiskAssessmentResult(
                approved=False,
                reason_code="MISSING_MARK_PRICE",
                rejection_reason=f"No valid mark price for {intent.pair}",
            )

        desired_notional = intent.desired_qty * price

        if intent.side == OrderSide.SELL:
            # Sell reduces exposure, verify against held position
            pos = current_positions.get(intent.pair)
            held_qty = pos.base_qty if pos else Decimal("0")
            if held_qty <= Decimal("0"):
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="NO_POSITION_TO_SELL",
                    rejection_reason=f"No open position held for {intent.pair}",
                )
            sell_qty = min(intent.desired_qty, held_qty)
            sell_notional = sell_qty * price
            if sell_notional < self.policy.min_order_notional:
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="BELOW_MIN_SIZE_REJECTED",
                    rejection_reason=f"Sell notional {sell_notional} < min {self.policy.min_order_notional}",
                )
            return RiskAssessmentResult(
                approved=True,
                approved_qty=sell_qty,
                approved_notional=sell_notional,
                reason_code="APPROVED",
            )

        # BUY order:
        # Check max open positions limit
        pos = current_positions.get(intent.pair)
        if pos is None or pos.base_qty <= Decimal("0"):
            open_count = sum(1 for p in current_positions.values() if p.base_qty > Decimal("0"))
            if open_count >= self.policy.max_open_positions:
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="MAX_POSITIONS_REACHED",
                    rejection_reason=f"Already reached max {self.policy.max_open_positions} open positions",
                )

        # SIM-02-AC0: Sizing respects shared capital, max position fraction, and available cash
        max_position_notional = current_equity * self.policy.max_position_fraction
        allowed_notional = min(desired_notional, max_position_notional, available_cash)

        # SIM-02-AC1: Size di bawah minimum ditolak bukan dibulatkan naik
        if allowed_notional < self.policy.min_order_notional:
            return RiskAssessmentResult(
                approved=False,
                approved_qty=Decimal("0"),
                approved_notional=Decimal("0"),
                reason_code="BELOW_MIN_SIZE_REJECTED",
                rejection_reason=(
                    f"Approved notional {allowed_notional} is below minimum {self.policy.min_order_notional}"
                ),
            )

        approved_qty = allowed_notional / price
        return RiskAssessmentResult(
            approved=True,
            approved_qty=approved_qty,
            approved_notional=allowed_notional,
            reason_code="APPROVED",
        )
