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
        forbidden_terms = ["sealed_test", "outer_test", "test", "sealed"]
        for term in forbidden_terms:
            if term in obj:
                raise SealedTestObjectiveForbiddenError(
                    f"SEALED_TEST_OBJECTIVE_FORBIDDEN: Objective '{data.get('target_objective')}' references "
                    f"forbidden partition keyword '{term}'. Search objectives must target inner validation only."
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

    max_trials: int = 30
    max_revisions: int = 1
    consumed_trials: int = 0
    revision_count: int = 0

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
        max_trials: int = 30,
        max_revisions: int = 1,
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
        """Resume search from state checkpoint, verifying strict configuration parity."""
        saved_space = state.get("search_space", {})
        saved_hash = state.get("search_space_hash")

        current_hash = search_space.space_hash()
        if current_hash != saved_hash or search_space.space_id != saved_space.get("space_id"):
            raise ResumeConfigMismatchError(
                f"RESUME_CONFIG_MISMATCH: Current search space ({search_space.space_id}:{current_hash[:10]}) "
                f"does not match saved checkpoint ({saved_space.get('space_id')}:{str(saved_hash)[:10]}). "
                "Resume is strictly rejected."
            )

        instance = cls(
            search_space=search_space,
            max_trials=state["budget"]["max_trials"],
            max_revisions=state["budget"]["max_revisions"],
        )
        instance.budget.consumed_trials = state["budget"]["consumed_trials"]
        instance.budget.revision_count = state["budget"]["revision_count"]

        for t_data in state.get("trials", []):
            outcome = TrialOutcome.model_validate(t_data)
            instance.trials.append(outcome)

        return instance
