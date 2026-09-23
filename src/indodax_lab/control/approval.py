"""Operator manual approval store for semi-automated execution mode."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict

from indodax_lab.execution.oms import OmsOrder

logger = logging.getLogger("approval_store")


def generate_approval_token(
    proposal_id: str,
    operator_id: str,
    expires_at: datetime,
    secret_key: bytes | str,
    nonce: str | None = None,
    action: str = "APPROVE_PROPOSAL",
) -> str:
    """Generate deterministic HMAC-SHA256 authorization token
    bound to proposal, operator, expiry, and nonce.
    """
    secret = secret_key.encode() if isinstance(secret_key, str) else secret_key
    exp_iso = expires_at.isoformat()
    if nonce is not None:
        payload = f"{action}:{proposal_id}:{operator_id}:{exp_iso}:{nonce}".encode()
    else:
        payload = f"{proposal_id}:{operator_id}:{exp_iso}".encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def verify_approval_token(
    token: str,
    proposal_id: str,
    operator_id: str,
    expires_at: datetime,
    secret_key: bytes | str,
    nonce: str | None = None,
    action: str = "APPROVE_PROPOSAL",
) -> bool:
    """Constant-time verification of operator approval authorization token."""
    expected = generate_approval_token(
        proposal_id=proposal_id,
        operator_id=operator_id,
        expires_at=expires_at,
        secret_key=secret_key,
        nonce=nonce,
        action=action,
    )
    if hmac.compare_digest(token, expected):
        return True
    if nonce is not None:
        # Fallback to check legacy un-nonced format
        legacy_expected = generate_approval_token(
            proposal_id=proposal_id,
            operator_id=operator_id,
            expires_at=expires_at,
            secret_key=secret_key,
            nonce=None,
        )
        return hmac.compare_digest(token, legacy_expected)
    return False


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
    approval_token: str | None = None
    snapshot_digest: str | None = None


class ManualApprovalStore:
    """Thread-safe store managing pending order proposals and cryptographic/token confirmations."""

    def __init__(
        self,
        default_ttl_seconds: int = 300,
        persistence_path: Path | None = None,
        signing_secret: bytes | str | None = None,
    ) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self.persistence_path = Path(persistence_path) if persistence_path is not None else None
        if signing_secret is not None:
            self.signing_secret: bytes | None = (
                signing_secret.encode() if isinstance(signing_secret, str) else signing_secret
            )
        else:
            self.signing_secret = None
        self._lock = RLock()
        self._proposals: dict[str, PendingProposal] = {}
        self._used_nonces: set[str] = set()
        if self.persistence_path is not None and self.persistence_path.exists():
            self._load()

    def _save(self) -> None:
        if self.persistence_path is None:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.persistence_path.with_suffix(".tmp")
        data = {pid: prop.model_dump(mode="json") for pid, prop in self._proposals.items()}
        data_json = json.dumps(data, sort_keys=True)
        digest = hashlib.sha256(data_json.encode("utf-8")).hexdigest()
        wrapper = {
            "version": 1,
            "proposals": data,
            "integrity_sha256": digest,
        }
        temp_path.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
        temp_path.replace(self.persistence_path)

    def _load(self) -> None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        text = self.persistence_path.read_text(encoding="utf-8")
        if not text.strip():
            return
        raw = json.loads(text)
        if isinstance(raw, dict) and "integrity_sha256" in raw and "proposals" in raw:
            proposals_data = raw["proposals"]
            calc_digest = hashlib.sha256(
                json.dumps(proposals_data, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if calc_digest != raw["integrity_sha256"]:
                raise ValueError("APPROVAL_PERSISTENCE_INTEGRITY_COMPROMISED")
            raw_props = proposals_data
        else:
            raw_props = raw
        self._proposals = {
            pid: PendingProposal.model_validate(pdata) for pid, pdata in raw_props.items()
        }

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
        snapshot_digest: str | None = None,
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
            snapshot_digest=snapshot_digest,
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
        token: str | None = None,
        nonce: str | None = None,
        snapshot_digest: str | None = None,
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

            # PM-03 Invariant: Nonce must be single-use
            if nonce is not None and nonce in self._used_nonces:
                raise PermissionError(f"NONCE_ALREADY_USED:{nonce}")

            if self.signing_secret is not None:
                if not token:
                    raise PermissionError(f"MISSING_APPROVAL_TOKEN:{proposal_id}")
                if not verify_approval_token(
                    token,
                    proposal_id,
                    operator_id,
                    current.expires_at,
                    self.signing_secret,
                    nonce=nonce,
                ):
                    raise PermissionError(f"INVALID_APPROVAL_TOKEN:{proposal_id}")

            if nonce is not None:
                self._used_nonces.add(nonce)

            update_dict: dict[str, Any] = {
                "status": ProposalStatus.APPROVED,
                "decided_at": at,
                "decided_by": operator_id,
                "decision_reason": reason,
                "approval_token": token,
            }
            if snapshot_digest is not None:
                update_dict["snapshot_digest"] = snapshot_digest

            approved = current.model_copy(update=update_dict)
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
