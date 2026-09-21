"""Authoritative fail-closed pre-write gate controlling all venue write permissions.

Enforces:
- Authoritative execution snapshot containing ledger, OMS, risk revisions, cash, equity, positions,
  reconciliation health and timestamp.
- Strict freshness: rejects missing, future, stale, unhealthy, or wrong-scope evidence.
- Strict re-risk: rejects state changes (cash, positions, price slippage, order qty) after approval.
- Zero new exposure when unresolved UNKNOWN orders exist in OMS.
- Single-use WritePermits bound to order, snapshot, and candidate digests.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.execution.oms import OmsOrder

if TYPE_CHECKING:
    from indodax_lab.control.approval import PendingProposal


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    """Enforce timezone-aware UTC datetime."""
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def _ensure_finite_decimal(val: Decimal, field_name: str) -> Decimal:
    """Enforce finite Decimal value."""
    if not val.is_finite():
        raise ValueError(f"NON_FINITE_DECIMAL_REJECTED:{field_name}")
    return val


class AuthorityGateError(RuntimeError):
    """Base exception for all pre-write authority gate rejections."""


class MissingEvidenceError(AuthorityGateError):
    """Raised when mandatory evidence (snapshot, capital, reconciliation) is absent."""


class StaleEvidenceError(AuthorityGateError):
    """Raised when reconciliation or state evidence is older than allowable threshold."""


class FutureEvidenceError(AuthorityGateError):
    """Raised when an evidence timestamp claims a time in the future."""


class WrongScopeError(AuthorityGateError):
    """Raised when evidence scope does not match the order's market or account scope."""


class UnhealthyEvidenceError(AuthorityGateError):
    """Raised when market, clock, or reconciliation state is unhealthy."""


class ReapprovalRequiredError(AuthorityGateError):
    """Raised when state drift after approval requires human re-approval."""


class UnknownOrdersError(AuthorityGateError):
    """Raised when unresolved UNKNOWN orders exist, blocking new venue exposure."""


class InvalidPermitError(PermissionError):
    """Base exception for invalid or missing write permits."""


class ExpiredPermitError(InvalidPermitError):
    """Raised when a write permit has exceeded its time-to-live."""


class PermitAlreadyUsedError(InvalidPermitError):
    """Raised when a single-use permit is submitted more than once."""


class ExecutionSnapshot(BaseModel):
    """Authoritative point-in-time state evidence required for venue write authorization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str
    created_at: datetime
    ledger_revision: int | str
    oms_revision: int | str
    risk_revision: int | str
    available_cash: Decimal
    current_equity: Decimal
    positions: dict[str, Decimal] = Field(default_factory=dict)
    mark_prices: dict[str, Decimal] = Field(default_factory=dict)
    market_healthy: bool = True
    clock_healthy: bool = True
    reconciliation_healthy: bool = True
    reconciliation_scope: str
    reconciliation_time: datetime
    unknown_orders_count: int = 0

    @field_validator("created_at", "reconciliation_time")
    @classmethod
    def _validate_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v, "datetime")

    @field_validator("available_cash", "current_equity")
    @classmethod
    def _validate_capital(cls, v: Decimal) -> Decimal:
        return _ensure_finite_decimal(v, "capital")

    @field_validator("positions", mode="before")
    @classmethod
    def _normalize_positions(cls, v: Any) -> dict[str, Decimal]:
        if not isinstance(v, (dict, Mapping)):
            return {}
        result: dict[str, Decimal] = {}
        for k, val in v.items():
            pair_key = str(k).lower()
            if hasattr(val, "base_qty"):
                result[pair_key] = _ensure_finite_decimal(
                    Decimal(str(val.base_qty)), f"positions[{pair_key}]"
                )
            else:
                result[pair_key] = _ensure_finite_decimal(
                    Decimal(str(val)), f"positions[{pair_key}]"
                )
        return result

    @field_validator("mark_prices", mode="before")
    @classmethod
    def _normalize_mark_prices(cls, v: Any) -> dict[str, Decimal]:
        if not isinstance(v, (dict, Mapping)):
            return {}
        result: dict[str, Decimal] = {}
        for k, val in v.items():
            pair_key = str(k).lower()
            result[pair_key] = _ensure_finite_decimal(Decimal(str(val)), f"mark_prices[{pair_key}]")
        return result

    def compute_digest(self) -> str:
        """Compute deterministic canonical digest of execution snapshot."""
        payload = {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
            "ledger_revision": str(self.ledger_revision),
            "oms_revision": str(self.oms_revision),
            "risk_revision": str(self.risk_revision),
            "available_cash": self.available_cash,
            "current_equity": self.current_equity,
            "positions": {k: self.positions[k] for k in sorted(self.positions.keys())},
            "mark_prices": {k: self.mark_prices[k] for k in sorted(self.mark_prices.keys())},
            "market_healthy": self.market_healthy,
            "clock_healthy": self.clock_healthy,
            "reconciliation_healthy": self.reconciliation_healthy,
            "reconciliation_scope": self.reconciliation_scope,
            "reconciliation_time": self.reconciliation_time.isoformat(),
            "unknown_orders_count": self.unknown_orders_count,
        }
        return manifest_digest(payload)


def compute_order_digest(order: OmsOrder) -> str:
    """Compute deterministic canonical digest of order parameters."""
    side_str = getattr(order.side, "value", str(order.side))
    payload = {
        "internal_order_id": order.internal_order_id,
        "client_order_id": order.client_order_id,
        "pair": order.pair.lower(),
        "side": side_str,
        "desired_qty": order.desired_qty,
        "limit_price": order.limit_price,
    }
    return manifest_digest(payload)


class WritePermit(BaseModel):
    """Cryptographic single-use permit authorizing exactly one venue write operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    permit_id: str
    order_internal_id: str
    order_digest: str
    candidate_ref: str
    snapshot_digest: str
    action: str = "SUBMIT"  # "SUBMIT" or "CANCEL"
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def _validate_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v, "permit_time")

    def verify_order(self, order: OmsOrder) -> bool:
        """Verify that permit matches the exact order parameters."""
        if self.order_internal_id != order.internal_order_id:
            return False
        return compute_order_digest(order) == self.order_digest


class AuthorityGate:
    """Authoritative fail-closed pre-write gate controlling all venue write permissions."""

    def __init__(
        self,
        *,
        max_reconciliation_age_seconds: float = 120.0,
        permit_ttl_seconds: float = 30.0,
        max_slippage_bps: int = 100,
    ) -> None:
        self.max_reconciliation_age_seconds = max_reconciliation_age_seconds
        self.permit_ttl_seconds = permit_ttl_seconds
        self.max_slippage_bps = max_slippage_bps

    def authorize(
        self,
        order: OmsOrder,
        execution_snapshot: ExecutionSnapshot,
        release_ref: str | ArtifactRef,
        approval: PendingProposal | None,
        now: datetime,
    ) -> WritePermit:
        """Evaluate pre-write evidence and issue single-use WritePermit or fail closed."""
        now_utc = _ensure_utc(now, "now")

        # 1. Evidence existence (AC0)
        if execution_snapshot is None or not isinstance(execution_snapshot, ExecutionSnapshot):
            raise MissingEvidenceError(
                "MISSING_EXECUTION_SNAPSHOT: Valid ExecutionSnapshot required"
            )
        if execution_snapshot.available_cash is None or execution_snapshot.current_equity is None:
            raise MissingEvidenceError(
                "MISSING_PORTFOLIO_SNAPSHOT: Authoritative capital required"
            )
        if execution_snapshot.reconciliation_time is None:
            raise MissingEvidenceError(
                "MISSING_RECONCILIATION_REPORT: Reconciliation report required"
            )

        # 2. Evidence freshness and health (AC1)
        if execution_snapshot.reconciliation_time > now_utc:
            raise FutureEvidenceError(
                f"FUTURE_RECONCILIATION_TIMESTAMP: "
                f"{execution_snapshot.reconciliation_time} > {now_utc}"
            )
        if execution_snapshot.created_at > now_utc:
            raise FutureEvidenceError(
                f"FUTURE_SNAPSHOT_TIMESTAMP: {execution_snapshot.created_at} > {now_utc}"
            )

        rec_age = (now_utc - execution_snapshot.reconciliation_time).total_seconds()
        if rec_age > self.max_reconciliation_age_seconds:
            raise StaleEvidenceError(
                f"STALE_RECONCILIATION_EVIDENCE: "
                f"age {rec_age:.1f}s > {self.max_reconciliation_age_seconds}s"
            )

        order_pair = order.pair.lower()
        scope = execution_snapshot.reconciliation_scope.lower()
        if scope not in ("all", "global", order_pair, f"spot:{order_pair}"):
            raise WrongScopeError(
                f"WRONG_RECONCILIATION_SCOPE: "
                f"Snapshot scope '{scope}' does not cover order pair '{order_pair}'"
            )

        if not execution_snapshot.reconciliation_healthy:
            raise UnhealthyEvidenceError(
                "RECONCILIATION_UNHEALTHY: Reconciliation status is unhealthy"
            )
        if not execution_snapshot.clock_healthy:
            raise UnhealthyEvidenceError("CLOCK_UNHEALTHY: Clock synchronization is unhealthy")
        if not execution_snapshot.market_healthy:
            raise UnhealthyEvidenceError(
                "MARKET_UNHEALTHY: Market health state is unsafe for trading"
            )

        # 3. Unknown orders check (AC3)
        if execution_snapshot.unknown_orders_count > 0:
            raise UnknownOrdersError(
                f"UNKNOWN_ORDERS_BLOCK_EXPOSURE: "
                f"{execution_snapshot.unknown_orders_count} unresolved UNKNOWN orders"
            )

        # 4. Approval and post-approval state drift check (AC2)
        if approval is not None:
            app_status = getattr(approval.status, "value", str(approval.status))
            if app_status != "APPROVED":
                raise ReapprovalRequiredError(f"PROPOSAL_NOT_APPROVED: status={approval.status}")
            if now_utc > approval.expires_at:
                raise ReapprovalRequiredError(
                    f"APPROVAL_EXPIRED: expired at {approval.expires_at} < {now_utc}"
                )

            # Order parameter parity check
            app_order = approval.order
            if app_order.pair.lower() != order_pair:
                raise ReapprovalRequiredError("APPROVAL_PAIR_MISMATCH")
            app_side = getattr(app_order.side, "value", str(app_order.side))
            ord_side = getattr(order.side, "value", str(order.side))
            if app_side != ord_side:
                raise ReapprovalRequiredError("APPROVAL_SIDE_MISMATCH")
            if app_order.desired_qty != order.desired_qty:
                raise ReapprovalRequiredError(
                    f"APPROVAL_QUANTITY_CHANGED: "
                    f"approved {app_order.desired_qty} != order {order.desired_qty}"
                )
            if app_order.limit_price != order.limit_price:
                raise ReapprovalRequiredError(
                    f"APPROVAL_PRICE_CHANGED: "
                    f"approved {app_order.limit_price} != order {order.limit_price}"
                )

            # Post-approval cash capacity re-risk
            side_str = getattr(order.side, "value", str(order.side)).upper()
            mark_price = execution_snapshot.mark_prices.get(order_pair, Decimal("0"))
            eval_price = order.limit_price or mark_price

            if "BUY" in side_str:
                required_cash = order.desired_qty * eval_price
                if required_cash > execution_snapshot.available_cash:
                    raise ReapprovalRequiredError(
                        f"INSUFFICIENT_CASH_AFTER_APPROVAL: "
                        f"required {required_cash} > available {execution_snapshot.available_cash}"
                    )
            elif "SELL" in side_str:
                held_qty = execution_snapshot.positions.get(order_pair, Decimal("0"))
                if order.desired_qty > held_qty:
                    raise ReapprovalRequiredError(
                        f"INSUFFICIENT_POSITION_AFTER_APPROVAL: "
                        f"required {order.desired_qty} > held {held_qty}"
                    )

            # Slippage re-check
            if order.limit_price is not None and mark_price > Decimal("0"):
                diff = abs(mark_price - order.limit_price)
                slippage_bps = int((diff / order.limit_price) * 10000)
                if slippage_bps > self.max_slippage_bps:
                    raise ReapprovalRequiredError(
                        f"PRICE_SLIPPAGE_EXCEEDED_AFTER_APPROVAL: "
                        f"{slippage_bps}bps > {self.max_slippage_bps}bps"
                    )

        # 5. Issue WritePermit
        candidate_str = release_ref.sha256 if hasattr(release_ref, "sha256") else str(release_ref)
        order_digest = compute_order_digest(order)
        snapshot_digest = execution_snapshot.compute_digest()

        return WritePermit(
            permit_id=f"permit_sub_{uuid.uuid4().hex[:16]}",
            order_internal_id=order.internal_order_id,
            order_digest=order_digest,
            candidate_ref=candidate_str,
            snapshot_digest=snapshot_digest,
            action="SUBMIT",
            created_at=now_utc,
            expires_at=now_utc + timedelta(seconds=self.permit_ttl_seconds),
        )

    def authorize_cancel(
        self,
        order: OmsOrder,
        execution_snapshot: ExecutionSnapshot,
        release_ref: str | ArtifactRef,
        now: datetime,
    ) -> WritePermit:
        """Evaluate evidence and issue single-use cancel permit."""
        now_utc = _ensure_utc(now, "now")

        # Cancellation does not increase exposure, but requires valid uncorrupted snapshot
        if execution_snapshot is None or not isinstance(execution_snapshot, ExecutionSnapshot):
            raise MissingEvidenceError(
                "MISSING_EXECUTION_SNAPSHOT: Valid ExecutionSnapshot required"
            )

        if execution_snapshot.reconciliation_time > now_utc:
            raise FutureEvidenceError("FUTURE_RECONCILIATION_TIMESTAMP")

        candidate_str = release_ref.sha256 if hasattr(release_ref, "sha256") else str(release_ref)
        order_digest = compute_order_digest(order)
        snapshot_digest = execution_snapshot.compute_digest()

        return WritePermit(
            permit_id=f"permit_cnc_{uuid.uuid4().hex[:16]}",
            order_internal_id=order.internal_order_id,
            order_digest=order_digest,
            candidate_ref=candidate_str,
            snapshot_digest=snapshot_digest,
            action="CANCEL",
            created_at=now_utc,
            expires_at=now_utc + timedelta(seconds=self.permit_ttl_seconds),
        )
