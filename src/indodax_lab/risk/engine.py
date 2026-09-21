"""Centralized risk engine enforcing financial, operational, and market health constraints."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import Position
from indodax_lab.backtest.risk import (
    PortfolioRiskManager,
    RiskAssessmentResult,
)
from indodax_lab.execution.oms import OmsOrder, OmsStateMachine
from indodax_lab.market.health import UNSAFE_TRADING_STATES, MarketHealthState

logger = logging.getLogger("risk_engine")


class KillSwitchTriggeredError(RuntimeError):
    """Raised when orders are attempted while the operational kill switch is active."""


class RiskEngine:
    """Central institutional risk authority governing pre-trade validation and kill switch."""

    def __init__(
        self,
        risk_manager: PortfolioRiskManager,
        *,
        max_orders_per_minute: int = 15,
        kill_switch_path: Path | None = None,
    ) -> None:
        self.risk_manager = risk_manager
        self.max_orders_per_minute = max_orders_per_minute
        self.kill_switch_path = Path(kill_switch_path) if kill_switch_path is not None else None
        self._manual_kill_switch: bool = False
        self._order_timestamps: list[datetime] = []

    @property
    def is_kill_switch_active(self) -> bool:
        """True if either programmatic or filesystem kill switch is triggered."""
        if self._manual_kill_switch:
            return True
        if self.kill_switch_path is not None and self.kill_switch_path.exists():
            return True
        return False

    def trigger_kill_switch(self, reason: str = "MANUAL_TRIGGER") -> None:
        """Trigger immediate emergency operational halt."""
        logger.critical("RiskEngine: Kill switch triggered: %s", reason)
        self._manual_kill_switch = True
        if self.kill_switch_path is not None:
            self.kill_switch_path.parent.mkdir(parents=True, exist_ok=True)
            self.kill_switch_path.write_text(
                f"HALTED:{reason}:{datetime.now(UTC).isoformat()}\n",
                encoding="utf-8",
            )

    def reset_kill_switch(self) -> None:
        """Explicitly disarm the kill switch."""
        self._manual_kill_switch = False
        if self.kill_switch_path is not None and self.kill_switch_path.exists():
            self.kill_switch_path.unlink()

    def assess_intent(
        self,
        intent: SignalIntent,
        *,
        current_equity: Decimal,
        current_positions: Mapping[str, Position],
        mark_prices: Mapping[str, Decimal],
        evaluation_time: datetime,
        available_cash: Decimal,
        market_health: MarketHealthState = MarketHealthState.HEALTHY,
    ) -> RiskAssessmentResult:
        """Evaluate intent across operational, market health, and financial risk constraints."""
        # 1. Operational kill switch
        if self.is_kill_switch_active:
            return RiskAssessmentResult(
                approved=False,
                reason_code="KILL_SWITCH_ACTIVE",
                rejection_reason="Operational kill switch is engaged.",
            )

        # 2. Market health gate (fail closed if unsafe)
        if market_health in UNSAFE_TRADING_STATES:
            # Entries are strictly blocked when market health is unsafe
            if intent.side == OrderSide.BUY:
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="MARKET_HEALTH_UNSAFE",
                    rejection_reason=(
                        f"Market health state {market_health} is unsafe for new exposure."
                    ),
                )

        # 3. Rate limiting / throttle check
        window_start = evaluation_time - timedelta(seconds=60)
        recent_orders = [ts for ts in self._order_timestamps if ts >= window_start]
        if len(recent_orders) >= self.max_orders_per_minute:
            return RiskAssessmentResult(
                approved=False,
                reason_code="RATE_LIMIT_EXCEEDED",
                rejection_reason=f"Exceeded max {self.max_orders_per_minute} orders per minute.",
            )

        # 4. Financial risk manager assessment (position size, circuit breakers, loss limits)
        result = self.risk_manager.assess_order(
            intent=intent,
            current_equity=current_equity,
            current_positions=current_positions,
            mark_prices=mark_prices,
            evaluation_time=evaluation_time,
            available_cash=available_cash,
        )

        if result.approved:
            # Record order timestamp in throttle history
            self._order_timestamps = recent_orders + [evaluation_time]

        return result

    def create_oms_order_from_assessment(
        self,
        intent: SignalIntent,
        assessment: RiskAssessmentResult,
        *,
        internal_order_id: str,
        client_order_id: str,
        created_at: datetime,
    ) -> OmsOrder:
        """Create a compliant, risk-approved OmsOrder."""
        if not assessment.approved:
            raise ValueError(f"CANNOT_CREATE_ORDER_FOR_UNAPPROVED_INTENT:{assessment.reason_code}")
        if assessment.approved_qty <= Decimal("0"):
            raise ValueError("APPROVED_QTY_ZERO")

        return OmsStateMachine.create(
            internal_order_id=internal_order_id,
            client_order_id=client_order_id,
            pair=intent.pair,
            side=intent.side,
            desired_qty=assessment.approved_qty,
            created_at=created_at,
        )
