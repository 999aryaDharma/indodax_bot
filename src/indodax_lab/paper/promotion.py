"""Champion replacement gate and promotion registry (SHADOW-03).

Contract: sealed pass + >=90 days AND >=100 pooled closed forward trades + no policy breach -> versioned promotion.

Guarantees:
1. SHADOW-03-AC0: Challenger with sealed pass, >=90 days, and >=100 trades replaces champion.
2. SHADOW-03-AC1: >=100 trades in <90 days fails duration gate (InsufficientForwardDurationError).
3. SHADOW-03-AC2: >=90 days with <100 trades fails trade count gate (InsufficientForwardTradesError).
4. SHADOW-03-AC3: Challenger training/evaluation activities do not modify the active champion pointer.

Review hardening (ops-shadow batch):
- The "sufficient quality" gate is enforced and fails closed: ``outperformance`` has no
  default, so an incomplete evidence package cannot be constructed.
- Promotion requires an explicit, recorded human approval bound to the exact evidence
  digest; self-approval by the challenger owner is refused.
- Stale evaluation records are refused; a decision records the previous champion so the
  promotion can be rolled back to a compatible verified bundle.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.models.lob.queue_evidence import QueueQualificationReport

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InsufficientForwardDurationError(ValueError):
    """Raised when candidate has insufficient forward evaluation days (minimum 90)."""


class InsufficientForwardTradesError(ValueError):
    """Raised when candidate has insufficient closed forward trades (minimum 100)."""


class UnsealedCandidatePromotionError(ValueError):
    """Raised when a candidate has not passed the sealed evaluation phase."""


class PolicyBreachPromotionError(ValueError):
    """Raised when a candidate has an unexcused risk policy breach in forward evaluation."""


class InsufficientQualityPromotionError(ValueError):
    """Raised when a candidate fails the "sufficient quality" outperformance gate."""


class MissingPromotionApprovalError(ValueError):
    """Raised when a promotion is attempted without an explicit recorded approval."""


class SelfApprovedPromotionError(ValueError):
    """Raised when the challenger owner attempts to approve their own promotion."""


class StalePromotionEvidenceError(ValueError):
    """Raised when the approval does not cover the supplied evidence, or the evidence expired."""


class NoPromotedChampionError(ValueError):
    """Raised when a rollback is requested but no promotion has been recorded."""


class QueueEvidencePromotionError(ValueError):
    """Raised when LOB queue execution lacks complete versioned qualification evidence."""


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


def _canonical_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return value


class ChallengerEvidence(BaseModel):
    """Audited evidence package for a challenger candidate requesting champion replacement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    candidate_version: str
    # Provenance: which evaluated run produced this package and when.
    evidence_id: str
    evaluated_at_utc: datetime
    is_sealed_pass: bool
    forward_days: int = Field(ge=0)
    closed_trades_count: int = Field(ge=0)
    has_policy_breach: bool = False
    # No default: an evidence package that omits the quality verdict cannot be
    # constructed, so the gate can never silently default to allow.
    outperformance: bool
    execution_contract: Literal["bar_proxy_v1", "lob_queue_v1"] = "bar_proxy_v1"
    queue_qualification: QueueQualificationReport | None = None

    @field_validator("evaluated_at_utc")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, "evaluated_at_utc")

    def evidence_digest(self) -> str:
        """Stable fingerprint an approver signs off, so a forged package is detectable."""
        return _canonical_digest(
            {
                "evidence_id": self.evidence_id,
                "candidate_id": self.candidate_id,
                "candidate_version": self.candidate_version,
                "evaluated_at_utc": self.evaluated_at_utc.isoformat(),
                "is_sealed_pass": self.is_sealed_pass,
                "forward_days": self.forward_days,
                "closed_trades_count": self.closed_trades_count,
                "has_policy_breach": self.has_policy_breach,
                "outperformance": self.outperformance,
                "execution_contract": self.execution_contract,
                "queue_qualification": (
                    self.queue_qualification.model_dump(mode="json")
                    if self.queue_qualification is not None
                    else None
                ),
            }
        )


class PromotionApproval(BaseModel):
    """Explicit, recorded human approval for one specific evidence package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approver_id: str
    approved_at_utc: datetime
    evidence_id: str
    evidence_digest: str
    reason: str

    @field_validator("approved_at_utc")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, "approved_at_utc")


class PromotionDecision(BaseModel):
    """Audit record capturing the promotion verdict and resulting champion pointer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    promoted: bool
    reason: str
    champion_id: str
    champion_version: str
    previous_champion_id: str
    previous_champion_version: str
    approved_by: str
    evidence_digest: str
    promoted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# ChampionRegistry
# ---------------------------------------------------------------------------


class ChampionRegistry:
    """Authority managing champion pointer and enforcing the 90-day/100-trade gate."""

    def __init__(
        self,
        initial_champion_id: str,
        initial_champion_version: str,
        min_forward_days: int = 90,
        min_closed_trades: int = 100,
        max_evidence_age_days: int = 30,
    ) -> None:
        if max_evidence_age_days <= 0:
            raise ValueError("INVALID_MAX_EVIDENCE_AGE_DAYS")
        self.active_champion_id: str = initial_champion_id
        self.active_champion_version: str = initial_champion_version
        self.min_forward_days: int = min_forward_days
        self.min_closed_trades: int = min_closed_trades
        self.max_evidence_age_days: int = max_evidence_age_days
        self._challenger_activity_log: list[dict[str, Any]] = []
        self._promotion_history: list[PromotionDecision] = []

    def record_challenger_activity(self, candidate_id: str, action: str) -> None:
        """Record training or evaluation of a challenger without altering champion (SHADOW-03-AC3)."""
        self._challenger_activity_log.append(
            {
                "candidate_id": candidate_id,
                "action": action,
                "logged_at_utc": datetime.now(UTC),
            }
        )
        # Active champion pointer is strictly untouched

    @property
    def promotion_history(self) -> list[PromotionDecision]:
        return list(self._promotion_history)

    def evaluate_promotion(
        self,
        challenger: ChallengerEvidence,
        approval: PromotionApproval | None = None,
    ) -> PromotionDecision:
        """Evaluate a challenger against the champion replacement gate (SHADOW-03-AC0..AC3).

        Args:
            challenger: The ``ChallengerEvidence`` package.
            approval: Explicit recorded human approval bound to this exact evidence
                digest. ``None`` is refused fail-closed.

        Returns:
            A ``PromotionDecision`` reflecting the atomic pointer update.

        Raises:
            MissingPromotionApprovalError: If no explicit approval is supplied.
            SelfApprovedPromotionError: If the challenger owner approved their own promotion.
            StalePromotionEvidenceError: If the approval does not cover this evidence,
                or the evidence is older than ``max_evidence_age_days``.
            UnsealedCandidatePromotionError: If candidate is not a sealed pass.
            InsufficientForwardDurationError: If forward evaluation duration < 90 days (AC1).
            InsufficientForwardTradesError: If closed forward trades count < 100 (AC2).
            PolicyBreachPromotionError: If candidate incurred any policy breach.
            InsufficientQualityPromotionError: If candidate does not demonstrate sufficient
                quality (outperformance).
        """
        # Fail closed on an absent, self-issued, mismatched or expired approval before
        # any gate is evaluated, so no promotion can happen without a recorded human.
        if approval is None:
            raise MissingPromotionApprovalError(
                "MISSING_PROMOTION_APPROVAL: Champion replacement is a separate, explicitly "
                "recorded human decision. Promotion without an approval is refused "
                "(SHADOW-03)."
            )
        if not approval.approver_id:
            raise MissingPromotionApprovalError(
                "MISSING_PROMOTION_APPROVER: An approval must name a human approver."
            )
        if approval.approver_id == challenger.candidate_id:
            raise SelfApprovedPromotionError(
                f"SELF_APPROVAL_FORBIDDEN: '{approval.approver_id}' proposed candidate "
                f"'{challenger.candidate_id}' and cannot be its final approver."
            )
        actual_digest = challenger.evidence_digest()
        if (
            approval.evidence_id != challenger.evidence_id
            or approval.evidence_digest != actual_digest
        ):
            raise StalePromotionEvidenceError(
                "PROMOTION_APPROVAL_EVIDENCE_MISMATCH: The recorded approval does not cover "
                f"evidence '{challenger.evidence_id}'; a forged or superseded evaluation "
                "record cannot drive a promotion (SHADOW-03)."
            )
        now = datetime.now(UTC)
        if now - challenger.evaluated_at_utc > timedelta(days=self.max_evidence_age_days):
            raise StalePromotionEvidenceError(
                f"STALE_PROMOTION_EVIDENCE: Evidence '{challenger.evidence_id}' was evaluated "
                f"{challenger.evaluated_at_utc.isoformat()}, older than the "
                f"{self.max_evidence_age_days}-day promotion evidence window."
            )
        if challenger.evaluated_at_utc > now:
            raise StalePromotionEvidenceError(
                "FUTURE_PROMOTION_EVIDENCE: Evidence is dated after the promotion decision."
            )

        if challenger.execution_contract == "lob_queue_v1":
            queue_report = challenger.queue_qualification
            if queue_report is None:
                raise QueueEvidencePromotionError("QUEUE_QUALIFICATION_MISSING")
            failure = queue_report.failure_reason(
                challenger.candidate_id, challenger.candidate_version
            )
            if failure is not None:
                raise QueueEvidencePromotionError(failure)
        elif challenger.queue_qualification is not None:
            raise QueueEvidencePromotionError("QUEUE_REPORT_WITHOUT_LOB_EXECUTION_CONTRACT")

        # Sealed pass gate
        if not challenger.is_sealed_pass:
            raise UnsealedCandidatePromotionError(
                f"UNSEALED_PROMOTION_FORBIDDEN: Candidate '{challenger.candidate_id}' "
                "has not passed the sealed test evaluation phase."
            )

        # AC1: 90-day duration gate
        if challenger.forward_days < self.min_forward_days:
            raise InsufficientForwardDurationError(
                f"INSUFFICIENT_FORWARD_DURATION: Candidate '{challenger.candidate_id}' "
                f"has {challenger.forward_days} forward days, but minimum {self.min_forward_days} "
                "days are required. Rapid trade generation does not satisfy this requirement (SHADOW-03-AC1)."
            )

        # AC2: 100 closed trades gate
        if challenger.closed_trades_count < self.min_closed_trades:
            raise InsufficientForwardTradesError(
                f"INSUFFICIENT_FORWARD_TRADES: Candidate '{challenger.candidate_id}' "
                f"has {challenger.closed_trades_count} closed trades, but minimum {self.min_closed_trades} "
                "trades are required. Long duration without sample size does not satisfy this requirement (SHADOW-03-AC2)."
            )

        # Policy breach gate
        if challenger.has_policy_breach:
            raise PolicyBreachPromotionError(
                f"POLICY_BREACH_FORBIDDEN: Candidate '{challenger.candidate_id}' "
                "incurred a policy breach during forward evaluation."
            )

        # Sufficient-quality gate (fails closed: no default on the evidence field)
        if not challenger.outperformance:
            raise InsufficientQualityPromotionError(
                f"INSUFFICIENT_FORWARD_QUALITY: Candidate '{challenger.candidate_id}' "
                "did not demonstrate sufficient quality against the active champion."
            )

        # AC0: All gates satisfied -> atomic champion pointer swap
        previous_id = self.active_champion_id
        previous_version = self.active_champion_version
        self.active_champion_id = challenger.candidate_id
        self.active_champion_version = challenger.candidate_version

        decision = PromotionDecision(
            promoted=True,
            reason=(
                f"CHAMPION_REPLACED: Challenger '{challenger.candidate_id}' v{challenger.candidate_version} "
                f"satisfied sealed pass, {challenger.forward_days} forward days (>={self.min_forward_days}), "
                f"{challenger.closed_trades_count} closed trades (>={self.min_closed_trades}), "
                f"no policy breach, sufficient quality, approved by '{approval.approver_id}'."
            ),
            champion_id=self.active_champion_id,
            champion_version=self.active_champion_version,
            previous_champion_id=previous_id,
            previous_champion_version=previous_version,
            approved_by=approval.approver_id,
            evidence_digest=actual_digest,
        )
        self._promotion_history.append(decision)
        return decision

    def rollback_last_promotion(self) -> PromotionDecision:
        """Restore the champion recorded as previous on the most recent promotion."""
        if not self._promotion_history:
            raise NoPromotedChampionError(
                "NO_PROMOTION_TO_ROLL_BACK: No champion replacement has been recorded."
            )
        decision = self._promotion_history.pop()
        self.active_champion_id = decision.previous_champion_id
        self.active_champion_version = decision.previous_champion_version
        return decision
