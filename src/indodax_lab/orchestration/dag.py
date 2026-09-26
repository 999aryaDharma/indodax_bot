"""Evaluator-controlled research DAG scheduler (JOB-03).

Contract: cadence window + snapshot + recipe -> idempotent DAG jobs with dependency states.

Guarantees:
1. JOB-03-AC0: Scheduler produces repeat decision for evaluator-authorized experiments.
2. JOB-03-AC1: HARD_FAIL outcome is permanently blocked; system idleness cannot reopen it.
3. JOB-03-AC2: INVALID_RUN retry is bounded by attempt cap and config must remain unchanged.
4. JOB-03-AC3: NEAR_MISS requires a new recipe version (hypothesis + budget + version bump).

Security: No real-money execution, no shell injection, job types allowlisted, no upstream artifact mutation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.evaluation.gates import EvaluationOutcome


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class HardFailCannotBeReopenedError(RuntimeError):
    """Raised when an attempt is made to reschedule a HARD_FAIL experiment.

    HARD_FAIL is a permanent gate verdict. Computer idleness or evaluator policy relaxation
    cannot override this; a new candidate version with a documented hypothesis is required.
    """


class InvalidRunRetryLimitExceededError(RuntimeError):
    """Raised when INVALID_RUN retries exceed the policy cap.

    Once the retry ceiling is reached, the job must be moved to BLOCKED_POLICY state
    rather than re-enqueued.
    """


class InvalidRunRetryConfigRequiredError(RuntimeError):
    """Raised when an INVALID_RUN retry is attempted without a config anchor to verify against.

    AC2 requires that an INVALID_RUN retry keeps the original config. Without the
    anchor record there is nothing to compare against, so the retry cannot be
    authorized: allowing it would silently permit config mutation on every retry,
    which is the "tuning on an invalid run" path the sprint forbids.
    """


class NearMissMustHaveNewVersionError(RuntimeError):
    """Raised when a NEAR_MISS experiment is retried with the same recipe version.

    A NEAR_MISS retry requires a new hypothesis, budget allocation, and incremented
    recipe version. Repeating the identical version is forbidden by ADR-003.
    """


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class ExperimentRecipe(BaseModel):
    """Immutable specification of an experiment to be scheduled as a DAG job."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipe_id: str
    recipe_version: str
    candidate_id: str
    snapshot_id: str
    cadence_window: str
    config_hash: str
    parameters: dict[str, Any] = {}


class RepeatPolicy(BaseModel):
    """Versioned policy governing when and how experiments may be repeated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = "repeat_policy_v1"
    max_invalid_run_retries: int = Field(default=2, ge=0)
    near_miss_requires_new_version: bool = True
    hard_fail_reopenable: bool = False

    @field_validator("max_invalid_run_retries")
    @classmethod
    def validate_retry_cap(cls, value: int) -> int:
        if value < 0:
            raise ValueError(
                f"RETRY_CAP_INVALID: max_invalid_run_retries must be >= 0, got {value}. "
                "A negative cap would block even the first run while appearing to be a policy."
            )
        return value

    @field_validator("hard_fail_reopenable")
    @classmethod
    def validate_hard_fail_reopenable(cls, value: bool) -> bool:
        # HARD_FAIL is a permanent gate verdict. The scheduler blocks it
        # unconditionally and never consults this field, so accepting `True`
        # would hand a caller false assurance that the gate had been relaxed.
        if value:
            raise ValueError(
                "HARD_FAIL_REOPEN_NOT_SUPPORTED: HARD_FAIL is a permanent verdict and cannot be "
                "made reopenable by policy. A new candidate version with a documented hypothesis "
                "is the only sanctioned path (JOB-03-AC1)."
            )
        return value


class RepeatOutcome(StrEnum):
    """Enumeration of scheduler repeat decisions."""

    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


class RepeatDecision(BaseModel):
    """Scheduler verdict on whether an experiment may be repeated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: RepeatOutcome
    reason: str
    recipe_id: str
    recipe_version: str


class InvalidRunRetryConfig(BaseModel):
    """Anchor record capturing the original config hash for INVALID_RUN retry validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    original_config_hash: str


class ResearchDAGJob(BaseModel):
    """A schedulable unit in the research DAG, linking recipe to evaluator decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_id: str
    recipe: ExperimentRecipe
    prior_outcome: EvaluationOutcome | None = None
    attempt_count: int = 0
    decision: RepeatDecision | None = None


# ---------------------------------------------------------------------------
# DAGScheduler
# ---------------------------------------------------------------------------


class DAGScheduler:
    """Evaluator-controlled scheduler that enforces repeat policies for research DAG jobs.

    Produces idempotent ``RepeatDecision`` for a given ``(recipe, prior_outcome, attempt_count)``
    triple. Same inputs always yield the same decision (deterministic, no mutable state).
    """

    def __init__(self, policy: RepeatPolicy | None = None) -> None:
        self.policy = policy or RepeatPolicy()

    def decide_repeat(
        self,
        recipe: ExperimentRecipe,
        prior_outcome: EvaluationOutcome,
        attempt_count: int,
        prior_recipe_version: str,
        system_idle: bool = False,
        original_retry_config: InvalidRunRetryConfig | None = None,
    ) -> RepeatDecision:
        """Determine whether the given experiment recipe may be rescheduled.

        Args:
            recipe: The experiment recipe to potentially reschedule.
            prior_outcome: The most recent ``EvaluationOutcome`` for this candidate/recipe.
            attempt_count: Number of times this recipe has already been attempted. Must be >= 0.
            prior_recipe_version: Version string of the recipe in the prior run.
            system_idle: Whether the host system is currently idle. Does NOT override HARD_FAIL.
            original_retry_config: Anchor record holding the original ``config_hash``. Required for
                ``INVALID_RUN`` retries so config immutability can be verified.

        Returns:
            A ``RepeatDecision`` with ``outcome=ALLOWED`` or ``outcome=BLOCKED``.

        Raises:
            HardFailCannotBeReopenedError: If ``prior_outcome`` is ``HARD_FAIL``.
            InvalidRunRetryConfigRequiredError: If ``prior_outcome`` is ``INVALID_RUN`` and no
                config anchor was supplied.
            InvalidRunRetryLimitExceededError: If ``INVALID_RUN`` attempt count exceeds policy cap.
            NearMissMustHaveNewVersionError: If ``NEAR_MISS`` is retried with the same version.
            ValueError: If ``attempt_count`` is negative, or if an ``INVALID_RUN`` retry uses a
                different config_hash.
        """
        # --- AC1: HARD_FAIL is a permanent block regardless of system state ---
        if prior_outcome == EvaluationOutcome.HARD_FAIL:
            raise HardFailCannotBeReopenedError(
                f"HARD_FAIL_PERMANENT_BLOCK: Recipe '{recipe.recipe_id}' v{recipe.recipe_version} "
                "produced a HARD_FAIL verdict and cannot be rescheduled. System idleness "
                "(system_idle={system_idle}) does not override this gate. A new candidate "
                "version with a revised hypothesis is required."
            )

        # --- AC2: INVALID_RUN retry must be bounded and use the same config ---
        if prior_outcome == EvaluationOutcome.INVALID_RUN:
            # The cap is meaningless for a negative counter, and an unguarded
            # negative value satisfies `attempt_count > cap` for every cap,
            # granting unlimited retries to a caller with broken bookkeeping.
            if attempt_count < 0:
                raise ValueError(
                    f"ATTEMPT_COUNT_INVALID: attempt_count must be >= 0, got {attempt_count}. "
                    "A negative count would bypass the INVALID_RUN retry cap entirely."
                )

            # The config-immutability guard must not be skippable by omission.
            # Without an anchor there is nothing to compare against, so the
            # retry cannot be proven to have kept its config.
            if original_retry_config is None:
                raise InvalidRunRetryConfigRequiredError(
                    f"RETRY_CONFIG_ANCHOR_REQUIRED: INVALID_RUN retry of recipe "
                    f"'{recipe.recipe_id}' was submitted without an InvalidRunRetryConfig anchor, "
                    "so config immutability cannot be verified. Pass the original config_hash, "
                    "or submit the change as a new recipe version (JOB-03-AC2)."
                )

            if recipe.config_hash != original_retry_config.original_config_hash:
                raise ValueError(
                    f"CONFIG_MUST_NOT_CHANGE: INVALID_RUN retry must use the same config. "
                    f"Original config_hash='{original_retry_config.original_config_hash}', "
                    f"current config_hash='{recipe.config_hash}'. "
                    "Changing config on an INVALID_RUN retry is forbidden; submit as a new recipe version."
                )

            # Attempt cap check
            if attempt_count > self.policy.max_invalid_run_retries:
                raise InvalidRunRetryLimitExceededError(
                    f"INVALID_RUN_RETRY_LIMIT_EXCEEDED: Recipe '{recipe.recipe_id}' has been attempted "
                    f"{attempt_count} times, exceeding the policy cap of "
                    f"{self.policy.max_invalid_run_retries}. Move to BLOCKED_POLICY state."
                )

            return RepeatDecision(
                outcome=RepeatOutcome.ALLOWED,
                reason=(
                    f"INVALID_RUN_RETRY_WITHIN_LIMIT: attempt {attempt_count} of "
                    f"{self.policy.max_invalid_run_retries} allowed retries. "
                    "Config hash verified unchanged."
                ),
                recipe_id=recipe.recipe_id,
                recipe_version=recipe.recipe_version,
            )

        # --- AC3: NEAR_MISS requires a new recipe version ---
        if prior_outcome == EvaluationOutcome.NEAR_MISS:
            if self.policy.near_miss_requires_new_version and recipe.recipe_version == prior_recipe_version:
                raise NearMissMustHaveNewVersionError(
                    f"NEAR_MISS_REQUIRES_NEW_VERSION: Recipe '{recipe.recipe_id}' produced a NEAR_MISS "
                    f"verdict at version '{prior_recipe_version}'. A repeat must use a new recipe version "
                    "with a revised hypothesis and budget allocation. "
                    f"Current version '{recipe.recipe_version}' is unchanged — bump the version."
                )

            return RepeatDecision(
                outcome=RepeatOutcome.ALLOWED,
                reason=(
                    f"NEAR_MISS_NEW_VERSION_ACCEPTED: Prior v{prior_recipe_version} produced NEAR_MISS; "
                    f"new v{recipe.recipe_version} accepted with hypothesis revision required."
                ),
                recipe_id=recipe.recipe_id,
                recipe_version=recipe.recipe_version,
            )

        # --- AC0: PASS and REGIME_EDGE → idempotent re-scheduling allowed ---
        return RepeatDecision(
            outcome=RepeatOutcome.ALLOWED,
            reason=(
                f"EVALUATOR_AUTHORIZED: Prior outcome '{prior_outcome}' permits scheduling. "
                f"Recipe '{recipe.recipe_id}' v{recipe.recipe_version} on cadence window "
                f"'{recipe.cadence_window}' is eligible."
            ),
            recipe_id=recipe.recipe_id,
            recipe_version=recipe.recipe_version,
        )
