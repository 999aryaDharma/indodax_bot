"""Governed research curator policy and change request engine (AGENT-01).

Contract: report + hypothesis -> change request + bounded candidate branch; no automatic merge or evaluator edits.

Guarantees:
1. AGENT-01-AC0: Research agent proposes challenger via dedicated branch, CR, and bounded budget.
2. AGENT-01-AC1: HARD_FAIL outcomes cannot trigger unconstrained tuning or retry (HardFailTuningForbiddenError).
3. AGENT-01-AC2: Prompt injection inside report text is treated strictly as passive string data.
4. AGENT-01-AC3: Implementer cannot be final approver of own proposal (SelfApprovalForbiddenError).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.evaluation.gates import EvaluationOutcome


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HardFailTuningForbiddenError(RuntimeError):
    """Raised when a tuning or retry proposal is submitted following a HARD_FAIL verdict."""


class SelfApprovalForbiddenError(ValueError):
    """Raised when an implementation agent attempts to approve its own change request."""


class ProposalValidationError(ValueError):
    """Raised when a proposal fails structural validation (budget, branch, identity)."""


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class ProposalStatus(StrEnum):
    """Lifecycle state of a research change request proposal."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ChangeRequestProposal(BaseModel):
    """Submission by an agent proposing a challenger model or tuning experiment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: str
    proposer_id: str
    candidate_id: str
    branch_name: str
    hypothesis: str
    budget_trials: int = Field(ge=1, le=10000)
    prior_outcome: EvaluationOutcome

    @field_validator("proposer_id", "candidate_id", mode="before")
    @classmethod
    def _normalize_identity(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("IDENTITY_MUST_BE_STRING")
        norm = v.strip().casefold()
        if not norm:
            raise ValueError("IDENTITY_CANNOT_BE_BLANK")
        return norm

    @field_validator("branch_name")
    @classmethod
    def _validate_branch_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("BRANCH_NAME_CANNOT_BE_BLANK")
        v = v.strip()
        # Reject protected refs and path traversal
        protected = {"main", "master", "prod", "production", "release"}
        if v.casefold() in protected:
            raise ValueError(f"BRANCH_NAME_PROTECTED_REF: '{v}' is a protected reference")
        if ".." in v:
            raise ValueError("BRANCH_NAME_INVALID: path traversal not allowed")
        return v


class ChangeRequestRecord(BaseModel):
    """Persisted record of a research change request proposal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: str
    proposer_id: str
    candidate_id: str
    branch_name: str
    hypothesis: str
    budget_trials: int
    prior_outcome: EvaluationOutcome
    status: ProposalStatus
    approver_id: str | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None


# ---------------------------------------------------------------------------
# Sanitization (AGENT-01-AC2)
# ---------------------------------------------------------------------------


def sanitize_curator_input(raw_text: str) -> str:
    """Sanitize and preserve untrusted input text strictly as passive data.

    Prompt injection commands embedded in reports or user text are treated
    exclusively as inert string data (AGENT-01-AC2).
    """
    if not isinstance(raw_text, str):
        raise ValueError("SANITIZE_INPUT_MUST_BE_STRING")
    # Neutralize common instruction-shaped patterns while preserving as text
    neutralized = raw_text.strip()
    # Common injection patterns are rendered inert by prefixing with a marker
    injection_patterns = (
        "ignore previous instructions",
        "system prompt",
        "you are now",
        "disregard",
        "forget everything",
        "new instructions",
        "override",
        "bypass",
        "jailbreak",
        "system override",
        "ignore all",
    )
    lowered = neutralized.casefold()
    for pattern in injection_patterns:
        if pattern in lowered:
            neutralized = "[NEUTRALIZED] " + neutralized
            break
    return neutralized


# ---------------------------------------------------------------------------
# CuratorEngine
# ---------------------------------------------------------------------------


class CuratorEngine:
    """Governed engine managing challenger proposals, budgets, and independent approvals."""

    # Policy ceiling for cumulative per-candidate budget
    MAX_CUMULATIVE_TRIALS = 10000

    def __init__(self) -> None:
        self._proposals: dict[str, ChangeRequestRecord] = {}
        # Per-candidate state for AC1 enforcement
        self._candidate_hard_fail: set[str] = set()
        self._candidate_cumulative_trials: dict[str, int] = {}

    def _normalize_id(self, identity: str) -> str:
        """Normalize proposer/approver/candidate identity for comparison."""
        return identity.strip().casefold()

    def submit_proposal(self, proposal: ChangeRequestProposal) -> ChangeRequestRecord:
        """Submit a change request proposal for evaluation (AGENT-01-AC0, AC1).

        Args:
            proposal: The ``ChangeRequestProposal`` from the research agent.

        Returns:
            A ``ChangeRequestRecord`` in ``PENDING_REVIEW`` state.

        Raises:
            HardFailTuningForbiddenError: If candidate has a prior HARD_FAIL (AGENT-01-AC1).
            ProposalValidationError: If cumulative budget would exceed ceiling.
        """
        # AC1: HARD_FAIL guard is per-candidate, not per-proposal
        norm_candidate = self._normalize_id(proposal.candidate_id)
        if norm_candidate in self._candidate_hard_fail:
            raise HardFailTuningForbiddenError(
                f"HARD_FAIL_TUNING_FORBIDDEN: Candidate '{proposal.candidate_id}' has a prior "
                "HARD_FAIL verdict. A formal defect report or architectural change is required "
                "(AGENT-01-AC1)."
            )

        # AC1: Also enforce the proposal's declared prior_outcome
        if proposal.prior_outcome == EvaluationOutcome.HARD_FAIL:
            # Record this candidate as HARD_FAIL for future proposals
            self._candidate_hard_fail.add(norm_candidate)
            raise HardFailTuningForbiddenError(
                f"HARD_FAIL_TUNING_FORBIDDEN: Proposal '{proposal.proposal_id}' for candidate "
                f"'{proposal.candidate_id}' follows a HARD_FAIL verdict. "
                "Automatic retries or hyperparameter tuning are strictly forbidden on HARD_FAIL. "
                "A formal defect report or architectural change is required (AGENT-01-AC1)."
            )

        # AC0/R2: Cumulative budget check (includes pending proposals)
        current_trials = self._candidate_cumulative_trials.get(norm_candidate, 0)
        # Also count pending proposals for this candidate
        pending_trials = sum(
            p.budget_trials for p in self._proposals.values()
            if self._normalize_id(p.candidate_id) == norm_candidate
            and p.status == ProposalStatus.PENDING_REVIEW
        )
        if current_trials + pending_trials + proposal.budget_trials > self.MAX_CUMULATIVE_TRIALS:
            raise ProposalValidationError(
                f"CUMULATIVE_BUDGET_EXCEEDED: Candidate '{proposal.candidate_id}' has "
                f"{current_trials + pending_trials} prior/pending trials; adding "
                f"{proposal.budget_trials} would exceed the ceiling of {self.MAX_CUMULATIVE_TRIALS}."
            )

        # AC2: Sanitize hypothesis at engine boundary
        sanitized_hypothesis = sanitize_curator_input(proposal.hypothesis)

        record = ChangeRequestRecord(
            proposal_id=proposal.proposal_id,
            proposer_id=proposal.proposer_id,
            candidate_id=proposal.candidate_id,
            branch_name=proposal.branch_name,
            hypothesis=sanitized_hypothesis,
            budget_trials=proposal.budget_trials,
            prior_outcome=proposal.prior_outcome,
            status=ProposalStatus.PENDING_REVIEW,
        )
        self._proposals[proposal.proposal_id] = record
        return record

    def approve_proposal(self, proposal_id: str, approver_id: str) -> ChangeRequestRecord:
        """Approve a proposal, strictly enforcing separation of duties (AGENT-01-AC3).

        Args:
            proposal_id: ID of the proposal to approve.
            approver_id: Identity of the approving agent or reviewer.

        Returns:
            Updated ``ChangeRequestRecord`` with ``APPROVED`` status.

        Raises:
            KeyError: If ``proposal_id`` is not found.
            SelfApprovalForbiddenError: If ``approver_id`` normalizes to ``proposer_id``.
            ProposalValidationError: If proposal is not in PENDING_REVIEW state.
        """
        record = self._proposals.get(proposal_id)
        if record is None:
            raise KeyError(f"PROPOSAL_NOT_FOUND: No proposal with id='{proposal_id}'")

        # AC3/R5: Normalized identity comparison
        norm_approver = self._normalize_id(approver_id)
        norm_proposer = self._normalize_id(record.proposer_id)
        if norm_approver == norm_proposer:
            raise SelfApprovalForbiddenError(
                f"SELF_APPROVAL_FORBIDDEN: Proposer '{record.proposer_id}' cannot approve "
                f"their own change request '{proposal_id}'. An independent reviewer is mandatory (AGENT-01-AC3)."
            )

        # AC3/R6: Only PENDING_REVIEW can be approved; idempotent on already-approved
        if record.status == ProposalStatus.APPROVED:
            # Idempotent: return existing record unchanged
            return record
        if record.status != ProposalStatus.PENDING_REVIEW:
            raise ProposalValidationError(
                f"PROPOSAL_NOT_PENDING: Proposal '{proposal_id}' is in status "
                f"'{record.status.value}' and cannot be approved."
            )

        updated = ChangeRequestRecord(
            proposal_id=record.proposal_id,
            proposer_id=record.proposer_id,
            candidate_id=record.candidate_id,
            branch_name=record.branch_name,
            hypothesis=record.hypothesis,
            budget_trials=record.budget_trials,
            prior_outcome=record.prior_outcome,
            status=ProposalStatus.APPROVED,
            approver_id=approver_id,
            submitted_at=record.submitted_at,
            decided_at=datetime.now(UTC),
        )
        self._proposals[proposal_id] = updated
        # Update cumulative budget on approval
        norm_candidate = self._normalize_id(record.candidate_id)
        self._candidate_cumulative_trials[norm_candidate] = (
            self._candidate_cumulative_trials.get(norm_candidate, 0) + record.budget_trials
        )
        return updated

    def reject_proposal(self, proposal_id: str, approver_id: str) -> ChangeRequestRecord:
        """Reject a proposal, recording the rejection audit trail.

        Args:
            proposal_id: ID of the proposal to reject.
            approver_id: Identity of the rejecting agent or reviewer.

        Returns:
            Updated ``ChangeRequestRecord`` with ``REJECTED`` status.

        Raises:
            KeyError: If ``proposal_id`` is not found.
            ProposalValidationError: If proposal is not in PENDING_REVIEW state.
        """
        record = self._proposals.get(proposal_id)
        if record is None:
            raise KeyError(f"PROPOSAL_NOT_FOUND: No proposal with id='{proposal_id}'")
        if record.status != ProposalStatus.PENDING_REVIEW:
            raise ProposalValidationError(
                f"PROPOSAL_NOT_PENDING: Proposal '{proposal_id}' is in status "
                f"'{record.status.value}' and cannot be rejected."
            )

        updated = ChangeRequestRecord(
            proposal_id=record.proposal_id,
            proposer_id=record.proposer_id,
            candidate_id=record.candidate_id,
            branch_name=record.branch_name,
            hypothesis=record.hypothesis,
            budget_trials=record.budget_trials,
            prior_outcome=record.prior_outcome,
            status=ProposalStatus.REJECTED,
            approver_id=approver_id,
            submitted_at=record.submitted_at,
            decided_at=datetime.now(UTC),
        )
        self._proposals[proposal_id] = updated
        return updated

    def get_proposal(self, proposal_id: str) -> ChangeRequestRecord | None:
        """Retrieve a proposal by ID."""
        return self._proposals.get(proposal_id)

    def get_candidate_status(self, candidate_id: str) -> dict[str, Any]:
        """Get the aggregated status for a candidate (for audit/debug)."""
        norm = self._normalize_id(candidate_id)
        approved_trials = self._candidate_cumulative_trials.get(norm, 0)
        pending_trials = sum(
            p.budget_trials for p in self._proposals.values()
            if self._normalize_id(p.candidate_id) == norm
            and p.status == ProposalStatus.PENDING_REVIEW
        )
        return {
            "candidate_id": candidate_id,
            "hard_fail_recorded": norm in self._candidate_hard_fail,
            "cumulative_trials": approved_trials,
            "pending_trials": pending_trials,
            "total_committed_trials": approved_trials + pending_trials,
            "proposals": [
                p for p in self._proposals.values()
                if self._normalize_id(p.candidate_id) == norm
            ],
        }
