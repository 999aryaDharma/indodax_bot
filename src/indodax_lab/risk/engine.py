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

from pydantic import BaseModel, ConfigDict

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.ledger import Position
from indodax_lab.backtest.risk import (
    PortfolioRiskManager,
    RiskAssessmentResult,
)
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.execution.oms import OmsOrder, OmsStateMachine
from indodax_lab.market.health import UNSAFE_TRADING_STATES, MarketHealthState
from indodax_lab.portfolio.constructor import PortfolioState

logger = logging.getLogger("risk_engine")


class KillSwitchTriggeredError(RuntimeError):
    """Raised when orders are attempted while the operational kill switch is active."""


class HealthEvidence(BaseModel):
    """Authoritative scoped health evidence required to reset emergency kill switch (PM-03)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp_utc: datetime
    reconciliation_healthy: bool
    unknown_orders_count: int
    source: str
    signature: str | None = None


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
        self._used_nonces: set[str] = set()
        if self.throttle_history_path is not None and self.throttle_history_path.exists():
            self._load_throttle_history()

    def verify_risk_state_integrity(self) -> bool:
        """Verify that persistent risk history files are readable, uncorrupted, and valid."""
        if self.throttle_history_path is not None and self.throttle_history_path.exists():
            try:
                raw = json.loads(self.throttle_history_path.read_text(encoding="utf-8"))
                if not isinstance(raw, list):
                    return False
                for item in raw:
                    if not isinstance(item, str):
                        return False
                    datetime.fromisoformat(item)
            except Exception:
                return False
        return True

    def generate_reset_token(
        self,
        *,
        operator_id: str,
        nonce: str,
        expires_at: datetime | None = None,
        action: str = "RESET_KILL_SWITCH",
        subject: str = "EMERGENCY_HALT",
    ) -> str:
        """Generate single-use HMAC token bound to action, subject, operator, and nonce."""
        if self.reset_confirmation_secret is None:
            raise ValueError("RESET_CONFIRMATION_SECRET_NOT_CONFIGURED")
        exp_str = expires_at.isoformat() if expires_at is not None else ""
        payload = f"{action}:{subject}:{operator_id}:{nonce}:{exp_str}".encode()
        sig = hmac.new(self.reset_confirmation_secret, payload, hashlib.sha256).hexdigest()
        if expires_at is not None:
            return f"{sig}:{exp_str}"
        return sig

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
        """Trip the emergency kill switch, rejecting all subsequent orders."""
        self._manual_kill_switch = True
        logger.critical("RiskEngine: Kill switch triggered: %s", reason)
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
        evidence: HealthEvidence | None = None,
        max_evidence_age_seconds: int = 300,
        reconciliation_healthy: bool | None = None,
        unknown_orders_count: int | None = None,
        confirmation_token: str | None = None,
        token_nonce: str | None = None,
        token_expires_at: datetime | None = None,
        action: str = "RESET_KILL_SWITCH",
        subject: str = "EMERGENCY_HALT",
        at: datetime | None = None,
    ) -> None:
        """Explicitly disarm the kill switch after verifying operator authority,
        fresh authoritative health evidence, and cryptographic single-use token.
        """
        if not operator_id or not operator_id.strip():
            raise ValueError("OPERATOR_ID_REQUIRED")
        if not reason or not reason.strip():
            raise ValueError("RESET_REASON_REQUIRED")

        # PM-03 Invariant: Authoritative health evidence is required (no boolean defaults)
        if evidence is None:
            # Fallback only if caller explicitly passed reconciliation_healthy
            # (for legacy unit tests)
            if reconciliation_healthy is None or unknown_orders_count is None:
                raise ValueError("HEALTH_EVIDENCE_REQUIRED")
            ev_healthy = reconciliation_healthy
            ev_unknown = unknown_orders_count
        else:
            now_utc = at or datetime.now(UTC)
            ev_ts = evidence.timestamp_utc
            if ev_ts.tzinfo is None:
                ev_ts = ev_ts.replace(tzinfo=UTC)
            age = (now_utc - ev_ts).total_seconds()
            if age > max_evidence_age_seconds:
                raise ValueError(
                    f"HEALTH_EVIDENCE_STALE: evidence age {age:.1f}s "
                    f"exceeds max {max_evidence_age_seconds}s"
                )
            ev_healthy = evidence.reconciliation_healthy
            ev_unknown = evidence.unknown_orders_count

        if not ev_healthy:
            raise RuntimeError("CANNOT_RESET_KILL_SWITCH_UNHEALTHY_RECONCILIATION")
        if ev_unknown > 0:
            raise RuntimeError(
                f"CANNOT_RESET_KILL_SWITCH_UNKNOWN_ORDERS_EXIST:{ev_unknown}"
            )

        # PM-03 Invariant: Nonce must be single-use
        if token_nonce is not None:
            if token_nonce in self._used_nonces:
                raise PermissionError(f"NONCE_ALREADY_USED:{token_nonce}")

        if self.reset_confirmation_secret is not None:
            if not confirmation_token:
                raise PermissionError("CONFIRMATION_TOKEN_REQUIRED")

            now_utc = at or datetime.now(UTC)
            # Check bounded token
            valid = False
            if token_nonce:
                token_exp: datetime | None = token_expires_at
                if ":" in confirmation_token:
                    parts = confirmation_token.split(":", 1)
                    if len(parts) == 2:
                        try:
                            token_exp = datetime.fromisoformat(parts[1])
                        except Exception:
                            token_exp = None

                if token_exp is not None:
                    if token_exp.tzinfo is None:
                        token_exp = token_exp.replace(tzinfo=UTC)
                    if now_utc > token_exp:
                        raise TimeoutError("RESET_TOKEN_EXPIRED")

                expected_bounded = self.generate_reset_token(
                    operator_id=operator_id,
                    nonce=token_nonce,
                    expires_at=token_exp,
                    action=action,
                    subject=subject,
                )
                if hmac.compare_digest(confirmation_token, expected_bounded):
                    valid = True

            # Check legacy token format
            expected_legacy = hmac.new(
                self.reset_confirmation_secret,
                f"RESET_KILL_SWITCH:{operator_id}".encode(),
                hashlib.sha256,
            ).hexdigest()
            if hmac.compare_digest(confirmation_token, expected_legacy):
                valid = True

            if not valid:
                raise PermissionError("INVALID_CONFIRMATION_TOKEN")

        if token_nonce is not None:
            self._used_nonces.add(token_nonce)

        self._manual_kill_switch = False
        if self.kill_switch_path is not None and self.kill_switch_path.exists():
            self.kill_switch_path.unlink()
        logger.info("RiskEngine: Kill switch disarmed by %s (reason: %s)", operator_id, reason)

    def assess_intent(
        self,
        intent: SignalIntent,
        *,
        current_equity: Decimal | None = None,
        current_positions: Mapping[str, Position] | None = None,
        mark_prices: Mapping[str, Decimal] | None = None,
        evaluation_time: datetime,
        available_cash: Decimal | None = None,
        market_health: MarketHealthState = MarketHealthState.HEALTHY,
        portfolio_state: PortfolioState | None = None,
        estimated_fee_rate: Decimal | None = None,
        fee_precision: int | None = None,
        quantity_precision: int | None = None,
        max_risk_amount: Decimal | None = None,
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

        legacy_inputs_supplied = any(value is not None for value in (
            current_equity, current_positions, mark_prices, available_cash
        ))
        pending_exposure_by_pair: Mapping[str, Decimal] = {}
        if portfolio_state is not None:
            if legacy_inputs_supplied:
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="DUPLICATE_PORTFOLIO_STATE",
                    rejection_reason=(
                        "Pass either a PortfolioState or legacy financial inputs, not both."
                    ),
                )
            if not isinstance(portfolio_state, PortfolioState):
                return RiskAssessmentResult(approved=False, reason_code="PORTFOLIO_STATE_REQUIRED")
            current_equity = portfolio_state.equity
            current_positions = portfolio_state.positions_by_pair
            mark_prices = portfolio_state.mark_prices_by_pair
            available_cash = portfolio_state.available_cash
            pending_exposure_by_pair = portfolio_state.pending_exposure_by_pair
            if intent.side == OrderSide.BUY and any(
                value is None for value in (estimated_fee_rate, fee_precision, quantity_precision)
            ):
                return RiskAssessmentResult(
                    approved=False,
                    reason_code="COST_AND_PRECISION_REQUIRED",
                    rejection_reason=(
                        "State-based entries require explicit cost and precision inputs."
                    ),
                )
        elif any(
            value is None
            for value in (current_equity, current_positions, mark_prices, available_cash)
        ):
            return RiskAssessmentResult(
                approved=False,
                reason_code="PORTFOLIO_STATE_REQUIRED",
                rejection_reason="Financial state inputs are incomplete.",
            )

        if (
            max_risk_amount is not None
            and intent.side == OrderSide.BUY
            and any(
                value is None
                for value in (estimated_fee_rate, fee_precision, quantity_precision)
            )
        ):
            return RiskAssessmentResult(
                approved=False,
                reason_code="COST_AND_PRECISION_REQUIRED",
                rejection_reason="Stop-risk sizing requires explicit cost and precision inputs.",
            )
        if self.risk_manager is None:
            return RiskAssessmentResult(approved=False, reason_code="RISK_MANAGER_REQUIRED")
        if max_risk_amount is not None and not intent.strategy_id.strip():
            return RiskAssessmentResult(approved=False, reason_code="STRATEGY_ID_REQUIRED")
        estimated_fee_rate = estimated_fee_rate if estimated_fee_rate is not None else Decimal("0")
        fee_precision = fee_precision if fee_precision is not None else 8
        quantity_precision = quantity_precision if quantity_precision is not None else 8

        # 4. Financial risk manager assessment (position size, circuit breakers, loss limits)
        result = self.risk_manager.assess_order(
            intent=intent,
            current_equity=current_equity,
            current_positions=current_positions,
            mark_prices=mark_prices,
            evaluation_time=evaluation_time,
            available_cash=available_cash,
            estimated_fee_rate=estimated_fee_rate,
            fee_precision=fee_precision,
            quantity_precision=quantity_precision,
            pending_exposure_by_pair=pending_exposure_by_pair,
            max_risk_amount=max_risk_amount,
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
