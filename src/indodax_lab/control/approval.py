"""Operator manual approval store for semi-automated execution mode."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
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

    def __init__(
        self,
        default_ttl_seconds: int = 300,
        persistence_path: Path | None = None,
    ) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self.persistence_path = Path(persistence_path) if persistence_path is not None else None
        self._lock = RLock()
        self._proposals: dict[str, PendingProposal] = {}
        if self.persistence_path is not None and self.persistence_path.exists():
            self._load()

    def _save(self) -> None:
        if self.persistence_path is None:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.persistence_path.with_suffix(".tmp")
        data = {pid: prop.model_dump(mode="json") for pid, prop in self._proposals.items()}
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(self.persistence_path)

    def _load(self) -> None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        text = self.persistence_path.read_text(encoding="utf-8")
        if not text.strip():
            return
        raw = json.loads(text)
        self._proposals = {pid: PendingProposal.model_validate(pdata) for pid, pdata in raw.items()}

    def get(self, proposal_id: str) -> PendingProposal | None:
        """Fetch a single proposal by ID."""
        with self._lock:
            return self._proposals.get(proposal_id)

    def get_all(self) -> tuple[PendingProposal, ...]:
        """Return all proposals regardless of state."""
        with self._lock:
            return tuple(self._proposals.values())

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
            self._save()

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
                self._save()
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
            self._save()
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
            self._save()
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
            if expired_list:
                self._save()
        return tuple(expired_list)
