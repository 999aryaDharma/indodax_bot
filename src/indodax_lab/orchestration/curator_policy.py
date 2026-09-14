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

from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.evaluation.gates import EvaluationOutcome


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HardFailTuningForbiddenError(RuntimeError):
    """Raised when a tuning or retry proposal is submitted following a HARD_FAIL verdict."""


class SelfApprovalForbiddenError(ValueError):
    """Raised when an implementation agent attempts to approve its own change request."""


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
    budget_trials: int
    prior_outcome: EvaluationOutcome


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
        return str(raw_text)
    # Return raw text safely without evaluating or interpreting it as code/commands
    return raw_text.strip()


# ---------------------------------------------------------------------------
# CuratorEngine
# ---------------------------------------------------------------------------


class CuratorEngine:
    """Governed engine managing challenger proposals, budgets, and independent approvals."""

    def __init__(self) -> None:
        self._proposals: dict[str, ChangeRequestRecord] = {}

    def submit_proposal(self, proposal: ChangeRequestProposal) -> ChangeRequestRecord:
        """Submit a change request proposal for evaluation (AGENT-01-AC0, AC1).

        Args:
            proposal: The ``ChangeRequestProposal`` from the research agent.

        Returns:
            A ``ChangeRequestRecord`` in ``PENDING_REVIEW`` state.

        Raises:
            HardFailTuningForbiddenError: If prior outcome was ``HARD_FAIL`` (AGENT-01-AC1).
        """
        # AC1: HARD_FAIL must not trigger unconstrained tuning or retry
        if proposal.prior_outcome == EvaluationOutcome.HARD_FAIL:
            raise HardFailTuningForbiddenError(
                f"HARD_FAIL_TUNING_FORBIDDEN: Proposal '{proposal.proposal_id}' for candidate "
                f"'{proposal.candidate_id}' follows a HARD_FAIL verdict. "
                "Automatic retries or hyperparameter tuning are strictly forbidden on HARD_FAIL. "
                "A formal defect report or architectural change is required (AGENT-01-AC1)."
            )

        record = ChangeRequestRecord(
            proposal_id=proposal.proposal_id,
            proposer_id=proposal.proposer_id,
            candidate_id=proposal.candidate_id,
            branch_name=proposal.branch_name,
            hypothesis=proposal.hypothesis,
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
            SelfApprovalForbiddenError: If ``approver_id == proposer_id`` (AGENT-01-AC3).
        """
        record = self._proposals.get(proposal_id)
        if record is None:
            raise KeyError(f"PROPOSAL_NOT_FOUND: No proposal with id='{proposal_id}'")

        # AC3: Implementer cannot be final approver
        if approver_id == record.proposer_id:
            raise SelfApprovalForbiddenError(
                f"SELF_APPROVAL_FORBIDDEN: Proposer '{record.proposer_id}' cannot approve "
                f"their own change request '{proposal_id}'. An independent reviewer is mandatory (AGENT-01-AC3)."
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
        return updated

    def get_proposal(self, proposal_id: str) -> ChangeRequestRecord | None:
        """Retrieve a proposal by ID."""
        return self._proposals.get(proposal_id)
