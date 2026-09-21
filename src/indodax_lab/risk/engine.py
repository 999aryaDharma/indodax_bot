"""Centralized risk engine enforcing financial, operational, and market health constraints."""

from __future__ import annotations

import hashlib
import hmac
import json
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
        risk_manager: PortfolioRiskManager | None = None,
        *,
        max_orders_per_minute: int = 15,
        kill_switch_path: Path | None = None,
        throttle_history_path: Path | None = None,
        reset_confirmation_secret: bytes | str | None = None,
    ) -> None:
        self.risk_manager = risk_manager
        self.max_orders_per_minute = max_orders_per_minute
        self.kill_switch_path = Path(kill_switch_path) if kill_switch_path is not None else None
        self.throttle_history_path = (
            Path(throttle_history_path) if throttle_history_path is not None else None
        )
        self.reset_confirmation_secret = (
            reset_confirmation_secret.encode("utf-8")
            if isinstance(reset_confirmation_secret, str)
            else reset_confirmation_secret
        )
        self._manual_kill_switch: bool = False
        self._order_timestamps: list[datetime] = []
        if self.throttle_history_path is not None and self.throttle_history_path.exists():
            self._load_throttle_history()

    def _load_throttle_history(self) -> None:
        if self.throttle_history_path is None or not self.throttle_history_path.exists():
            return
        try:
            raw = json.loads(self.throttle_history_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._order_timestamps = [
                    datetime.fromisoformat(ts).astimezone(UTC) for ts in raw if isinstance(ts, str)
                ]
        except Exception as exc:
            logger.warning(
                "Failed to load throttle history from %s: %s", self.throttle_history_path, exc
            )

    def _save_throttle_history(self) -> None:
        if self.throttle_history_path is None:
            return
        try:
            self.throttle_history_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.throttle_history_path.with_suffix(".tmp")
            data = [ts.isoformat() for ts in self._order_timestamps]
            temp.write_text(json.dumps(data), encoding="utf-8")
            temp.replace(self.throttle_history_path)
        except Exception as exc:
            logger.critical(
                "RiskEngine: Failed to save throttle history to %s: %s",
                self.throttle_history_path,
                exc,
            )
            raise RuntimeError(f"THROTTLE_HISTORY_PERSISTENCE_FAILED:{exc}") from exc

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

    def reset_kill_switch(
        self,
        *,
        operator_id: str,
        reason: str,
        reconciliation_healthy: bool,
        unknown_orders_count: int,
        confirmation_token: str | None = None,
    ) -> None:
        """Explicitly disarm the kill switch after verifying operator authority,
        audit rationale, and system health.
        """
        if not operator_id or not operator_id.strip():
            raise ValueError("OPERATOR_ID_REQUIRED")
        if not reason or not reason.strip():
            raise ValueError("RESET_REASON_REQUIRED")
        if not reconciliation_healthy:
            raise RuntimeError("CANNOT_RESET_KILL_SWITCH_UNHEALTHY_RECONCILIATION")
        if unknown_orders_count > 0:
            raise RuntimeError(
                f"CANNOT_RESET_KILL_SWITCH_UNKNOWN_ORDERS_EXIST:{unknown_orders_count}"
            )

        if self.reset_confirmation_secret is not None:
            if not confirmation_token:
                raise PermissionError("CONFIRMATION_TOKEN_REQUIRED")
            expected = hmac.new(
                self.reset_confirmation_secret,
                f"RESET_KILL_SWITCH:{operator_id}".encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(confirmation_token, expected):
                raise PermissionError("INVALID_CONFIRMATION_TOKEN")

        self._manual_kill_switch = False
        if self.kill_switch_path is not None and self.kill_switch_path.exists():
            self.kill_switch_path.unlink()
        logger.info("RiskEngine: Kill switch disarmed by %s (reason: %s)", operator_id, reason)

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
            self._save_throttle_history()

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
            limit_price=intent.limit_price,
            time_in_force=intent.time_in_force,
            created_at=created_at,
        )
