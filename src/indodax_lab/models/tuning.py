"""Bounded hyperparameter trial search and budget enforcement (ML-03).

Guarantees:
1. ML-03-AC0: Search strictly prohibits sealed/outer test as objective; objectives must target inner validation.
2. ML-03-AC1: Failed trials consume budget; technical or convergence failures count against max trials.
3. ML-03-AC2: Resuming search requires exact matching search space configuration; mismatches are rejected.
4. ML-03-AC3: Maximum 30 trials and at most 1 near-miss revision per model (ADR-003). Revisions do not reset trial count.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SealedTestObjectiveForbiddenError(Exception):
    """Raised when a search objective attempts to target sealed or test partitions."""


class TrialBudgetExhaustedError(RuntimeError):
    """Raised when trial attempts exceed the bounded trial budget."""


class RevisionBudgetExhaustedError(RuntimeError):
    """Raised when near-miss revisions exceed the allowable revision budget."""


class ResumeConfigMismatchError(ValueError):
    """Raised when resuming a search with mismatched search space parameters or identities."""


class BudgetPolicyViolationError(ValueError):
    """Raised when a requested budget exceeds the ADR-003 research policy caps."""


# ADR-003 "Default budgets": ML search is capped at 30 trials, and NEAR_MISS allows at
# most one model/horizon revision under its remaining trial budget. These are the
# absolute research-policy ceilings; a caller may pick a *lower* budget but never a
# higher one, and no revision round can reset a consumed trial budget.
ADR003_MAX_TRIALS = 30
ADR003_MAX_REVISIONS = 1

# ML-03-AC0 requires the tuning objective to target inner validation only. This is an
# exact allowlist rather than a keyword scan: substring matching lets lookalikes such as
# `outer_val_loss` or `holdout_pnl` through, and those objectives read sealed or
# out-of-fold data during the search.
ALLOWED_TARGET_OBJECTIVES = frozenset(
    {
        "inner_val_accuracy",
        "inner_val_auc",
        "inner_val_brier",
        "inner_val_coverage",
        "inner_val_log_loss",
        "inner_val_mae",
        "inner_val_pnl",
        "inner_val_rmse",
        "inner_val_sharpe",
    }
)


class TrialStatus(StrEnum):
    """Execution status of a single hyperparameter evaluation trial."""

    SUCCESS = "success"
    FAILED = "failed"
    INVALID = "invalid"


class SearchSpace(BaseModel):
    """Immutable, versioned hyperparameter search space with explicit target objective."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    space_id: str
    version: str
    params: dict[str, Any]
    target_objective: str

    def __init__(self, **data: Any) -> None:
        obj = str(data.get("target_objective", "")).strip().lower()
        if obj not in ALLOWED_TARGET_OBJECTIVES:
            raise SealedTestObjectiveForbiddenError(
                f"SEALED_TEST_OBJECTIVE_FORBIDDEN: Objective "
                f"'{data.get('target_objective')}' is not a registered inner-validation "
                f"objective. Search objectives must exactly match one of "
                f"{sorted(ALLOWED_TARGET_OBJECTIVES)}; sealed/outer/test lookalikes are rejected."
            )
        super().__init__(**data)

    def space_hash(self) -> str:
        """Deterministic content-addressed hash of the search space configuration."""
        payload = {
            "space_id": self.space_id,
            "version": self.version,
            "params": self.params,
            "target_objective": self.target_objective,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TrialBudget(BaseModel):
    """Mutable budget tracker enforcing trial counts and revision limits (ADR-003)."""

    model_config = ConfigDict(extra="forbid")

    max_trials: int = ADR003_MAX_TRIALS
    max_revisions: int = ADR003_MAX_REVISIONS
    consumed_trials: int = 0
    revision_count: int = 0

    @model_validator(mode="after")
    def enforce_adr003_caps(self) -> TrialBudget:
        """The ADR-003 ceilings are absolute, so they are enforced on the record itself.

        Enforcing here (not only in ``BoundedTrialSearch.__init__``) also covers budgets
        rebuilt from a persisted checkpoint during resume.
        """
        if not 1 <= self.max_trials <= ADR003_MAX_TRIALS:
            raise BudgetPolicyViolationError(
                f"BUDGET_POLICY_VIOLATION: max_trials={self.max_trials} is outside the ADR-003 "
                f"range [1, {ADR003_MAX_TRIALS}] for ML research search."
            )
        if not 0 <= self.max_revisions <= ADR003_MAX_REVISIONS:
            raise BudgetPolicyViolationError(
                f"BUDGET_POLICY_VIOLATION: max_revisions={self.max_revisions} is outside the ADR-003 "
                f"range [0, {ADR003_MAX_REVISIONS}]; at most {ADR003_MAX_REVISIONS} near-miss "
                "revision is permitted per model."
            )
        return self

    @property
    def remaining_trials(self) -> int:
        return max(0, self.max_trials - self.consumed_trials)


class TrialOutcome(BaseModel):
    """Immutable audit record of an individual trial execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trial_id: str
    trial_index: int
    params: dict[str, Any]
    status: TrialStatus
    objective_score: float | None = None
    error_message: str | None = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BoundedTrialSearch:
    """Manages bounded hyperparameter exploration, budget exhaustion, and checkpoint resumption."""

    def __init__(
        self,
        search_space: SearchSpace,
        max_trials: int = ADR003_MAX_TRIALS,
        max_revisions: int = ADR003_MAX_REVISIONS,
    ) -> None:
        self.search_space = search_space
        self.budget = TrialBudget(
            max_trials=max_trials,
            max_revisions=max_revisions,
            consumed_trials=0,
            revision_count=0,
        )
        self.trials: list[TrialOutcome] = []

    def register_trial(
        self,
        trial_id: str,
        params: dict[str, Any],
        status: TrialStatus,
        objective_score: float | None = None,
        error_message: str | None = None,
    ) -> TrialOutcome:
        """Register trial outcome and consume 1 trial from budget (success or failure)."""
        if self.budget.remaining_trials <= 0:
            raise TrialBudgetExhaustedError(
                f"TRIAL_BUDGET_EXHAUSTED: Maximum allowable trials ({self.budget.max_trials}) reached. "
                "Further trials are blocked."
            )

        trial_index = len(self.trials) + 1
        outcome = TrialOutcome(
            trial_id=trial_id,
            trial_index=trial_index,
            params=dict(params),
            status=status,
            objective_score=objective_score,
            error_message=error_message,
            evaluated_at=datetime.now(UTC),
        )

        self.trials.append(outcome)
        self.budget.consumed_trials += 1
        return outcome

    def revise_search_space(self, new_search_space: SearchSpace) -> None:
        """Apply a near-miss revision without resetting consumed trial budget."""
        if self.budget.revision_count >= self.budget.max_revisions:
            raise RevisionBudgetExhaustedError(
                f"REVISION_BUDGET_EXHAUSTED: Maximum allowable revisions ({self.budget.max_revisions}) reached. "
                "Per ADR-003, at most 1 near-miss revision is permitted per model."
            )

        self.search_space = new_search_space
        self.budget.revision_count += 1

    def get_winning_recipe(self) -> TrialOutcome:
        """Identify best parameter configuration among successful trials."""
        successful_trials = [t for t in self.trials if t.status == TrialStatus.SUCCESS and t.objective_score is not None]
        if not successful_trials:
            raise ValueError("NO_SUCCESSFUL_TRIALS_FOUND: Cannot retrieve winning recipe when zero trials succeeded.")

        return max(successful_trials, key=lambda t: t.objective_score or float("-inf"))

    def export_state(self) -> dict[str, Any]:
        """Export state checkpoint for durable persistence and resumption."""
        return {
            "search_space": self.search_space.model_dump(mode="json"),
            "search_space_hash": self.search_space.space_hash(),
            "budget": self.budget.model_dump(mode="json"),
            "trials": [t.model_dump(mode="json") for t in self.trials],
        }

    @classmethod
    def from_state(cls, state: dict[str, Any], search_space: SearchSpace) -> BoundedTrialSearch:
        """Resume search from a checkpoint, re-deriving budget counters instead of trusting them.

        Every trial the search ever recorded is present in ``state["trials"]``, and every
        recorded trial consumed budget, so the consumed-trial counter is *reconstructed*
        from the trial log and cross-checked against the persisted value. A tampered
        counter (or a tampered cap) is a resume rejection, not a silent budget reset.
        """
        saved_space = state.get("search_space", {})
        saved_hash = state.get("search_space_hash")

        current_hash = search_space.space_hash()
        if current_hash != saved_hash or search_space.space_id != saved_space.get("space_id"):
            raise ResumeConfigMismatchError(
                f"RESUME_CONFIG_MISMATCH: Current search space ({search_space.space_id}:{current_hash[:10]}) "
                f"does not match saved checkpoint ({saved_space.get('space_id')}:{str(saved_hash)[:10]}). "
                "Resume is strictly rejected."
            )

        saved_budget = state.get("budget")
        if not isinstance(saved_budget, dict):
            raise ResumeConfigMismatchError(
                "RESUME_CONFIG_MISMATCH: Checkpoint carries no readable budget block. "
                "Budget counters are reconstructed, never assumed."
            )

        max_trials = saved_budget.get("max_trials")
        max_revisions = saved_budget.get("max_revisions")
        if (
            not isinstance(max_trials, int)
            or isinstance(max_trials, bool)
            or not 1 <= max_trials <= ADR003_MAX_TRIALS
            or not isinstance(max_revisions, int)
            or isinstance(max_revisions, bool)
            or not 0 <= max_revisions <= ADR003_MAX_REVISIONS
        ):
            raise ResumeConfigMismatchError(
                f"RESUME_CONFIG_MISMATCH: Checkpoint budget (max_trials={max_trials}, "
                f"max_revisions={max_revisions}) is outside the ADR-003 caps "
                f"(max_trials<={ADR003_MAX_TRIALS}, max_revisions<={ADR003_MAX_REVISIONS}). "
                "Resume is strictly rejected."
            )

        outcomes = [TrialOutcome.model_validate(t) for t in state.get("trials", [])]
        reconstructed_consumed = len(outcomes)
        claimed_consumed = saved_budget.get("consumed_trials")
        if claimed_consumed != reconstructed_consumed:
            raise ResumeConfigMismatchError(
                f"RESUME_CONFIG_MISMATCH: Checkpoint claims consumed_trials={claimed_consumed} but "
                f"records {reconstructed_consumed} trial outcomes. Failed trials consume budget, so "
                "the trial log is authoritative. Resume is strictly rejected."
            )

        claimed_revisions = saved_budget.get("revision_count")
        if (
            not isinstance(claimed_revisions, int)
            or isinstance(claimed_revisions, bool)
            or not 0 <= claimed_revisions <= max_revisions
        ):
            raise ResumeConfigMismatchError(
                f"RESUME_CONFIG_MISMATCH: Checkpoint revision_count={claimed_revisions} is not a "
                f"count in [0, {max_revisions}]. Resume is strictly rejected."
            )

        instance = cls(
            search_space=search_space,
            max_trials=max_trials,
            max_revisions=max_revisions,
        )
        # Re-derived from the trial log, not read back from the checkpoint.
        instance.budget.consumed_trials = reconstructed_consumed
        instance.budget.revision_count = claimed_revisions
        instance.trials.extend(outcomes)

        return instance
