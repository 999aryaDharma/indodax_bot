"""Operator manual approval store for semi-automated execution mode."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import RLock

from pydantic import BaseModel, ConfigDict

from indodax_lab.execution.oms import OmsOrder

logger = logging.getLogger("approval_store")


class ProposalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PendingProposal(BaseModel):
    """An approved order intent awaiting human operator confirmation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: str
    order: OmsOrder
    created_at: datetime
    expires_at: datetime
    status: ProposalStatus = ProposalStatus.PENDING
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_reason: str | None = None


class ManualApprovalStore:
    """Thread-safe store managing pending order proposals and cryptographic/token confirmations."""

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._lock = RLock()
        self._proposals: dict[str, PendingProposal] = {}

    def propose(
        self,
        order: OmsOrder,
        *,
        at: datetime,
        ttl_seconds: int | None = None,
    ) -> PendingProposal:
        """Create a new pending proposal."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = at + timedelta(seconds=ttl)
        proposal_id = f"prop_{uuid.uuid4().hex[:12]}"

        proposal = PendingProposal(
            proposal_id=proposal_id,
            order=order,
            created_at=at,
            expires_at=expires_at,
            status=ProposalStatus.PENDING,
        )

        with self._lock:
            self._proposals[proposal_id] = proposal

        logger.info(
            "ManualApprovalStore: Proposed order %s (%s) expires at %s",
            order.internal_order_id,
            proposal_id,
            expires_at.isoformat(),
        )
        return proposal

    def approve(
        self,
        proposal_id: str,
        *,
        operator_id: str,
        at: datetime,
        reason: str = "OPERATOR_APPROVED",
    ) -> PendingProposal:
        """Operator explicitly approves order proposal."""
        with self._lock:
            if proposal_id not in self._proposals:
                raise KeyError(f"PROPOSAL_NOT_FOUND:{proposal_id}")

            current = self._proposals[proposal_id]
            if current.status != ProposalStatus.PENDING:
                raise ValueError(f"CANNOT_APPROVE_NON_PENDING_PROPOSAL:{current.status}")

            if at > current.expires_at:
                expired = current.model_copy(
                    update={
                        "status": ProposalStatus.EXPIRED,
                        "decided_at": at,
                        "decision_reason": "TTL_EXPIRED",
                    }
                )
                self._proposals[proposal_id] = expired
                raise TimeoutError(f"PROPOSAL_EXPIRED:{proposal_id}")

            approved = current.model_copy(
                update={
                    "status": ProposalStatus.APPROVED,
                    "decided_at": at,
                    "decided_by": operator_id,
                    "decision_reason": reason,
                }
            )
            self._proposals[proposal_id] = approved
            logger.info("ManualApprovalStore: Approved %s by %s", proposal_id, operator_id)
            return approved

    def reject(
        self,
        proposal_id: str,
        *,
        operator_id: str,
        at: datetime,
        reason: str = "OPERATOR_REJECTED",
    ) -> PendingProposal:
        """Operator explicitly rejects order proposal."""
        with self._lock:
            if proposal_id not in self._proposals:
                raise KeyError(f"PROPOSAL_NOT_FOUND:{proposal_id}")

            current = self._proposals[proposal_id]
            if current.status != ProposalStatus.PENDING:
                raise ValueError(f"CANNOT_REJECT_NON_PENDING_PROPOSAL:{current.status}")

            rejected = current.model_copy(
                update={
                    "status": ProposalStatus.REJECTED,
                    "decided_at": at,
                    "decided_by": operator_id,
                    "decision_reason": reason,
                }
            )
            self._proposals[proposal_id] = rejected
            logger.info("ManualApprovalStore: Rejected %s by %s", proposal_id, operator_id)
            return rejected

    def get_pending(self, *, now: datetime | None = None) -> tuple[PendingProposal, ...]:
        """Return all unexpired pending proposals."""
        check_time = now or datetime.now(UTC)
        with self._lock:
            pending = []
            for p in self._proposals.values():
                if p.status == ProposalStatus.PENDING and check_time <= p.expires_at:
                    pending.append(p)
            return tuple(pending)

    def clean_expired(self, at: datetime) -> tuple[PendingProposal, ...]:
        """Mark expired pending proposals as EXPIRED."""
        expired_list = []
        with self._lock:
            for pid, p in list(self._proposals.items()):
                if p.status == ProposalStatus.PENDING and at > p.expires_at:
                    exp = p.model_copy(
                        update={
                            "status": ProposalStatus.EXPIRED,
                            "decided_at": at,
                            "decision_reason": "TTL_EXPIRED",
                        }
                    )
                    self._proposals[pid] = exp
                    expired_list.append(exp)
        return tuple(expired_list)
