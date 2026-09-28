"""Governed research curator policy and change request engine (AGENT-01).

Contract: report + hypothesis -> change request + bounded candidate branch;
no automatic merge or evaluator edits.

Guarantees:
1. AGENT-01-AC0: Research agent proposes challenger via dedicated branch, CR,
   and bounded budget.
2. AGENT-01-AC1: HARD_FAIL outcomes cannot trigger unconstrained tuning or
   retry (HardFailTuningForbiddenError).
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
# Policy bounds — INITIAL fail-closed values, PENDING OWNER RATIFICATION
# ---------------------------------------------------------------------------
# The governance spec declares a "bounded candidate branch" without numeric
# ceilings, so these named constants are initial fail-closed values only.
# They are recorded for owner ratification in
# docs/sprints/handoffs/AGENT-01-HANDOFF.md (BLOCKING fix round) and must not
# be presented as approved policy.
MAX_PROPOSAL_TRIALS = 10_000  # ceiling for a single change request proposal
MAX_CUMULATIVE_CANDIDATE_TRIALS = 10_000  # cumulative ceiling per candidate_id

# Refs that may never host challenger work; AC0 requires a dedicated branch.
PROTECTED_BRANCH_REFS = frozenset({"main", "master", "prod", "production", "release"})


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
# Fail-closed validation helpers (shared by construction, model validators and
# the engine boundary so every entry path raises the module's typed errors)
# ---------------------------------------------------------------------------


def _require_identity(value: Any, label: str) -> str:
    """Normalize an agent identity (strip + casefold); reject blank/non-string."""
    if not isinstance(value, str):
        raise ProposalValidationError(f"IDENTITY_MUST_BE_STRING: {label} must be a string")
    norm = value.strip().casefold()
    if not norm:
        raise ProposalValidationError(f"IDENTITY_CANNOT_BE_BLANK: {label} cannot be blank")
    return norm


def _require_branch(value: Any) -> str:
    """Validate a dedicated challenger branch; reject blank/protected refs/traversal."""
    if not isinstance(value, str):
        raise ProposalValidationError("BRANCH_NAME_MUST_BE_STRING: branch_name must be a string")
    branch = value.strip()
    if not branch:
        raise ProposalValidationError("BRANCH_NAME_CANNOT_BE_BLANK: branch_name cannot be blank")
    if branch.casefold() in PROTECTED_BRANCH_REFS:
        raise ProposalValidationError(
            f"BRANCH_NAME_PROTECTED_REF: '{branch}' is a protected reference"
        )
    if ".." in branch:
        raise ProposalValidationError("BRANCH_NAME_INVALID: path traversal not allowed")
    return branch


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
    budget_trials: int = Field(ge=1, le=MAX_PROPOSAL_TRIALS)
    prior_outcome: EvaluationOutcome

    def __init__(self, **data: Any) -> None:
        # Typed construction boundary (R5): pydantic wraps ValueError raised in
        # field validators into its own ValidationError, so run the module's
        # fail-closed checks first to raise ProposalValidationError consistently.
        if "proposer_id" in data:
            data["proposer_id"] = _require_identity(data["proposer_id"], "proposer_id")
        if "candidate_id" in data:
            data["candidate_id"] = _require_identity(data["candidate_id"], "candidate_id")
        if "branch_name" in data:
            data["branch_name"] = _require_branch(data["branch_name"])
        super().__init__(**data)

    @field_validator("proposer_id", "candidate_id", mode="before")
    @classmethod
    def _normalize_identity(cls, v: Any) -> str:
        # Second layer for model_validate paths; construction raises typed already.
        return _require_identity(v, "identity")

    @field_validator("branch_name")
    @classmethod
    def _validate_branch_name(cls, v: Any) -> str:
        return _require_branch(v)


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
        raise ProposalValidationError("SANITIZE_INPUT_MUST_BE_STRING: raw_text must be a string")
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

    def __init__(self) -> None:
        # In-memory audit state. Durable persistence is out of scope for this
        # fix round (R7 recorded as CR backlog in the AGENT-01 handoff).
        self._proposals: dict[str, ChangeRequestRecord] = {}
        # Per-candidate state for AC1 enforcement
        self._candidate_hard_fail: set[str] = set()
        self._candidate_cumulative_trials: dict[str, int] = {}

    @staticmethod
    def _candidate_key(value: Any) -> str | None:
        """Lenient candidate key for HARD_FAIL bookkeeping; never raises (fail closed first)."""
        if not isinstance(value, str):
            return None
        key = value.strip().casefold()
        return key or None

    @staticmethod
    def _decided_at(record: ChangeRequestRecord) -> datetime:
        """Terminal decision timestamp; monotonic per proposal (never before submitted_at)."""
        return max(datetime.now(UTC), record.submitted_at)

    def submit_proposal(self, proposal: ChangeRequestProposal) -> ChangeRequestRecord:
        """Submit a change request proposal for evaluation (AGENT-01-AC0, AC1).

        Args:
            proposal: The ``ChangeRequestProposal`` from the research agent.

        Returns:
            A ``ChangeRequestRecord`` in ``PENDING_REVIEW`` state.

        Raises:
            HardFailTuningForbiddenError: If candidate has a prior HARD_FAIL (AGENT-01-AC1).
            ProposalValidationError: If the proposal is unvalidated, duplicates an
                existing ``proposal_id``, or would exceed the budget ceiling.
        """
        if not isinstance(proposal, ChangeRequestProposal):
            raise ProposalValidationError(
                "PROPOSAL_TYPE_INVALID: expected a ChangeRequestProposal instance"
            )

        # AC1/R1: remember any HARD_FAIL claim per candidate BEFORE all other
        # checks, so a rejected submission still blocks future tuning of this
        # candidate regardless of the proposal_id or asserted prior_outcome.
        if proposal.prior_outcome == EvaluationOutcome.HARD_FAIL:
            key = self._candidate_key(proposal.candidate_id)
            if key is not None:
                self._candidate_hard_fail.add(key)
            raise HardFailTuningForbiddenError(
                f"HARD_FAIL_TUNING_FORBIDDEN: Proposal '{proposal.proposal_id}' for candidate "
                f"'{proposal.candidate_id}' follows a HARD_FAIL verdict. "
                "Automatic retries or hyperparameter tuning are strictly forbidden on HARD_FAIL. "
                "A formal defect report or architectural change is required (AGENT-01-AC1)."
            )

        # Fail closed at the engine boundary: re-run canonical validation so
        # instances that bypassed model validation (e.g. model_construct)
        # cannot slip through identity, branch or budget checks.
        validated = ChangeRequestProposal(**proposal.model_dump())

        # AC1/R1: per-candidate memory, independent of proposal_id and of the
        # prior_outcome the new submission asserts.
        candidate_id = validated.candidate_id
        if candidate_id in self._candidate_hard_fail:
            raise HardFailTuningForbiddenError(
                f"HARD_FAIL_TUNING_FORBIDDEN: Candidate '{candidate_id}' has a prior "
                "HARD_FAIL verdict. A formal defect report or architectural change is required "
                "(AGENT-01-AC1)."
            )

        # Coordinator delta: a duplicate proposal_id must never overwrite an
        # existing record (APPROVED -> PENDING would erase the audit trail).
        if validated.proposal_id in self._proposals:
            raise ProposalValidationError(
                f"DUPLICATE_PROPOSAL_ID: proposal '{validated.proposal_id}' already exists; "
                "resubmission cannot overwrite an existing record (audit preservation)."
            )

        # AC0/R2: Cumulative budget check (includes pending proposals)
        current_trials = self._candidate_cumulative_trials.get(candidate_id, 0)
        pending_trials = sum(
            p.budget_trials for p in self._proposals.values()
            if p.candidate_id == candidate_id
            and p.status == ProposalStatus.PENDING_REVIEW
        )
        total_committed = current_trials + pending_trials
        if total_committed + validated.budget_trials > MAX_CUMULATIVE_CANDIDATE_TRIALS:
            raise ProposalValidationError(
                f"CUMULATIVE_BUDGET_EXCEEDED: Candidate '{candidate_id}' has "
                f"{total_committed} prior/pending trials; adding "
                f"{validated.budget_trials} would exceed the ceiling of "
                f"{MAX_CUMULATIVE_CANDIDATE_TRIALS}."
            )

        # AC2: Sanitize hypothesis at engine boundary
        sanitized_hypothesis = sanitize_curator_input(validated.hypothesis)

        record = ChangeRequestRecord(
            proposal_id=validated.proposal_id,
            proposer_id=validated.proposer_id,
            candidate_id=validated.candidate_id,
            branch_name=validated.branch_name,
            hypothesis=sanitized_hypothesis,
            budget_trials=validated.budget_trials,
            prior_outcome=validated.prior_outcome,
            status=ProposalStatus.PENDING_REVIEW,
            submitted_at=datetime.now(UTC),
        )
        self._proposals[record.proposal_id] = record
        return record

    def approve_proposal(self, proposal_id: str, approver_id: str) -> ChangeRequestRecord:
        """Approve a proposal, strictly enforcing separation of duties (AGENT-01-AC3).

        Args:
            proposal_id: ID of the proposal to approve.
            approver_id: Identity of the approving agent or reviewer.

        Returns:
            Updated ``ChangeRequestRecord`` with ``APPROVED`` status.

        Raises:
            ProposalValidationError: If ``proposal_id`` is unknown (R9), the
                approver identity is blank/non-string (R5), or the proposal is
                not in ``PENDING_REVIEW`` state (R6 — decisions are terminal).
            SelfApprovalForbiddenError: If ``approver_id`` normalizes to ``proposer_id``.
        """
        record = self._proposals.get(proposal_id)
        if record is None:
            raise ProposalValidationError(
                f"PROPOSAL_NOT_FOUND: No proposal with id='{proposal_id}'"
            )

        # AC3/R5: Typed, normalized identity comparison — a blank approver can
        # never APPROVE, and case/whitespace variants of the proposer are caught.
        approver = _require_identity(approver_id, "approver_id")
        if approver == _require_identity(record.proposer_id, "proposer_id"):
            raise SelfApprovalForbiddenError(
                f"SELF_APPROVAL_FORBIDDEN: Proposer '{record.proposer_id}' cannot approve "
                f"their own change request '{proposal_id}'. An independent reviewer is "
                "mandatory (AGENT-01-AC3)."
            )

        # AC3/R6: Decisions are terminal — a decided proposal is never re-decided,
        # so repeated approve can never overwrite approver/decided_at.
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
            approver_id=approver,
            submitted_at=record.submitted_at,
            decided_at=self._decided_at(record),
        )
        self._proposals[proposal_id] = updated
        # Update cumulative budget on approval
        self._candidate_cumulative_trials[record.candidate_id] = (
            self._candidate_cumulative_trials.get(record.candidate_id, 0) + record.budget_trials
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
            ProposalValidationError: If ``proposal_id`` is unknown (R9), the
                identity is blank/non-string (R5), or the proposal is not in
                ``PENDING_REVIEW`` state (R6 — decisions are terminal).
        """
        record = self._proposals.get(proposal_id)
        if record is None:
            raise ProposalValidationError(
                f"PROPOSAL_NOT_FOUND: No proposal with id='{proposal_id}'"
            )
        actor = _require_identity(approver_id, "approver_id")
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
            approver_id=actor,
            submitted_at=record.submitted_at,
            decided_at=self._decided_at(record),
        )
        self._proposals[proposal_id] = updated
        return updated

    def get_proposal(self, proposal_id: str) -> ChangeRequestRecord | None:
        """Retrieve a proposal by ID."""
        return self._proposals.get(proposal_id)

    def get_candidate_status(self, candidate_id: str) -> dict[str, Any]:
        """Get the aggregated status for a candidate (for audit/debug)."""
        norm = _require_identity(candidate_id, "candidate_id")
        approved_trials = self._candidate_cumulative_trials.get(norm, 0)
        pending_trials = sum(
            p.budget_trials for p in self._proposals.values()
            if p.candidate_id == norm
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
                if p.candidate_id == norm
            ],
        }
