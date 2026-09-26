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
import re
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.evaluation.gates import EvaluationOutcome


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HardFailTuningForbiddenError(RuntimeError):
    """Raised when a tuning or retry proposal is submitted following a HARD_FAIL verdict."""


class SelfApprovalForbiddenError(ValueError):
    """Raised when an implementation agent attempts to approve its own change request."""


class DuplicateProposalError(ValueError):
    """Raised when a proposal_id is reused with conflicting content."""


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class ProposalStatus(StrEnum):
    """Lifecycle state of a research change request proposal."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ADR-003 bounded search budget mirrored from ML-03 TrialBudget default.
MAX_BUDGET_TRIALS = 30

_BRANCH_RE = re.compile(r"^(feat|fix|exp|chore)/[a-z0-9][a-z0-9._/-]{0,127}$")
_RESERVED_BRANCHES = {"main", "dev", "master", "prod", "production"}


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


def validate_branch_name(branch_name: str) -> str:
    """Validate a candidate branch name fail-closed (AGENT-01-AC0).

    Only namespaced branches (feat|fix|exp|chore)/... are accepted; reserved
    integration branches and path escapes are rejected without side effects.
    """
    if not branch_name or branch_name in _RESERVED_BRANCHES or not _BRANCH_RE.match(branch_name):
        raise ValueError(
            f"BRANCH_NAME_INVALID: '{branch_name}' is not a bounded candidate branch. "
            "Expected '<feat|fix|exp|chore>/<slug>' (AGENT-01-AC0)."
        )
    if ".." in branch_name:
        raise ValueError(f"BRANCH_NAME_INVALID: '{branch_name}' contains path escape (AGENT-01-AC0).")
    return branch_name


def validate_budget_trials(budget_trials: int) -> int:
    """Validate the trial budget against the ADR-003 bound (AGENT-01-AC0)."""
    if isinstance(budget_trials, bool) or not isinstance(budget_trials, int):
        raise ValueError("BUDGET_TRIALS_INVALID: budget_trials must be an int (AGENT-01-AC0).")
    if not 1 <= budget_trials <= MAX_BUDGET_TRIALS:
        raise ValueError(
            f"BUDGET_TRIALS_OUT_OF_BOUNDS: {budget_trials} outside 1..{MAX_BUDGET_TRIALS} (AGENT-01-AC0)."
        )
    return budget_trials


class CuratorEngine:
    """Governed engine managing challenger proposals, budgets, and independent approvals."""

    def __init__(
        self,
        outcome_lookup: Callable[[str], EvaluationOutcome | None] | None = None,
    ) -> None:
        self._proposals: dict[str, ChangeRequestRecord] = {}
        # Registry lookup mapping candidate_id -> authoritative EvaluationOutcome.
        # When present it overrides the self-reported prior_outcome on the proposal,
        # so a HARD_FAIL verdict cannot be spoofed away (AGENT-01-AC1).
        self._outcome_lookup = outcome_lookup

    def _authoritative_outcome(self, proposal: ChangeRequestProposal) -> EvaluationOutcome:
        if self._outcome_lookup is None:
            return proposal.prior_outcome
        try:
            resolved = self._outcome_lookup(proposal.candidate_id)
        except Exception:
            resolved = None
        return resolved if resolved is not None else proposal.prior_outcome

    def submit_proposal(self, proposal: ChangeRequestProposal) -> ChangeRequestRecord:
        """Submit a change request proposal for evaluation (AGENT-01-AC0, AC1).

        Args:
            proposal: The ``ChangeRequestProposal`` from the research agent.

        Returns:
            A ``ChangeRequestRecord`` in ``PENDING_REVIEW`` state. Identical
            resubmission of a known ``proposal_id`` returns the stored record.

        Raises:
            HardFailTuningForbiddenError: If the authoritative outcome is ``HARD_FAIL`` (AGENT-01-AC1).
            ValueError: If budget or branch validation fails (AGENT-01-AC0).
            DuplicateProposalError: If ``proposal_id`` is reused with conflicting content.
        """
        validate_budget_trials(proposal.budget_trials)
        validate_branch_name(proposal.branch_name)

        existing = self._proposals.get(proposal.proposal_id)
        if existing is not None:
            if (
                existing.proposer_id == proposal.proposer_id
                and existing.candidate_id == proposal.candidate_id
                and existing.branch_name == proposal.branch_name
                and existing.hypothesis == proposal.hypothesis
                and existing.budget_trials == proposal.budget_trials
                and existing.prior_outcome == proposal.prior_outcome
            ):
                return existing
            raise DuplicateProposalError(
                f"DUPLICATE_PROPOSAL_CONFLICT: proposal_id '{proposal.proposal_id}' already exists "
                "with different content. Reuse of proposal IDs with conflicting content is forbidden."
            )

        # AC1: authoritative HARD_FAIL must not trigger unconstrained tuning or retry
        authoritative = self._authoritative_outcome(proposal)
        if authoritative == EvaluationOutcome.HARD_FAIL:
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
