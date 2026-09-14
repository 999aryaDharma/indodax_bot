"""Tests for JOB-03: Evaluator-controlled research DAG.

RED tests written before implementation. Each test targets a specific acceptance criterion.

Contract: cadence window + snapshot + recipe -> idempotent DAG jobs with dependency states.

AC boundaries:
- AC1: HARD_FAIL is not reopened because the computer is idle.
- AC2: INVALID_RUN retry is bounded and must use the same config.
- AC3: NEAR_MISS requires a new hypothesis, budget, and version.
"""

from __future__ import annotations

import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.orchestration.dag import (
    DAGScheduler,
    ExperimentRecipe,
    HardFailCannotBeReopenedError,
    InvalidRunRetryConfig,
    InvalidRunRetryLimitExceededError,
    NearMissMustHaveNewVersionError,
    RepeatDecision,
    RepeatOutcome,
    RepeatPolicy,
    ResearchDAGJob,
)
from indodax_lab.evaluation.gates import EvaluationOutcome


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_recipe(recipe_id: str = "recipe_v1", version: str = "1.0.0") -> ExperimentRecipe:
    """Build a minimal ExperimentRecipe fixture."""
    return ExperimentRecipe(
        recipe_id=recipe_id,
        recipe_version=version,
        candidate_id="cand_001",
        snapshot_id="snap_20260901",
        cadence_window="2026-09-01/2026-09-07",
        config_hash="abc123",
    )


def _make_policy(
    max_invalid_run_retries: int = 2,
) -> RepeatPolicy:
    """Build a minimal RepeatPolicy."""
    return RepeatPolicy(
        policy_id="repeat_v1",
        max_invalid_run_retries=max_invalid_run_retries,
        near_miss_requires_new_version=True,
        hard_fail_reopenable=False,
    )


# ---------------------------------------------------------------------------
# AC0: Scheduler only repeats experiments allowed by evaluator on immutable input
# ---------------------------------------------------------------------------

def test_job_03_valid_contract():
    """JOB-03-AC0: Scheduler produces DAG job with repeat decision for evaluator-allowed experiments."""
    recipe = _make_recipe()
    policy = _make_policy()
    scheduler = DAGScheduler(policy=policy)

    # A PASS outcome — eligible for idempotent re-scheduling on new cadence window
    decision = scheduler.decide_repeat(
        recipe=recipe,
        prior_outcome=EvaluationOutcome.PASS,
        attempt_count=1,
        prior_recipe_version="1.0.0",
    )

    assert decision.outcome == RepeatOutcome.ALLOWED, (
        f"PASS outcome should be ALLOWED for repeat; got {decision.outcome}"
    )
    assert decision.reason is not None
    assert len(decision.reason) > 0


# ---------------------------------------------------------------------------
# AC1: HARD_FAIL is not reopened because the computer is idle
# ---------------------------------------------------------------------------

def test_job_03_contract_1():
    """JOB-03-AC1: HARD_FAIL outcome is permanently blocked; idleness alone cannot reopen it."""
    recipe = _make_recipe()
    policy = _make_policy()
    scheduler = DAGScheduler(policy=policy)

    # Simulate: system is 'idle' (would normally admit jobs) but prior run was HARD_FAIL
    with pytest.raises(HardFailCannotBeReopenedError):
        scheduler.decide_repeat(
            recipe=recipe,
            prior_outcome=EvaluationOutcome.HARD_FAIL,
            attempt_count=1,
            prior_recipe_version="1.0.0",
            system_idle=True,  # Idle system should NOT override HARD_FAIL block
        )


# ---------------------------------------------------------------------------
# AC2: INVALID_RUN retry is bounded and must use the same config
# ---------------------------------------------------------------------------

def test_job_03_contract_2():
    """JOB-03-AC2: INVALID_RUN retry is bounded; using a different config_hash is rejected."""
    recipe = _make_recipe(recipe_id="recipe_v1", version="1.0.0")
    policy = _make_policy(max_invalid_run_retries=2)
    scheduler = DAGScheduler(policy=policy)

    # Sub-case A: retry within limit with same config → should be ALLOWED
    decision_ok = scheduler.decide_repeat(
        recipe=recipe,
        prior_outcome=EvaluationOutcome.INVALID_RUN,
        attempt_count=1,
        prior_recipe_version="1.0.0",
    )
    assert decision_ok.outcome == RepeatOutcome.ALLOWED, (
        "INVALID_RUN within retry limit with same config must be ALLOWED"
    )

    # Sub-case B: retry at limit → BLOCKED
    with pytest.raises(InvalidRunRetryLimitExceededError):
        scheduler.decide_repeat(
            recipe=recipe,
            prior_outcome=EvaluationOutcome.INVALID_RUN,
            attempt_count=3,  # exceeds max_invalid_run_retries=2
            prior_recipe_version="1.0.0",
        )

    # Sub-case C: retry with different config_hash → rejected (config must stay the same)
    recipe_changed_config = ExperimentRecipe(
        recipe_id="recipe_v1",
        recipe_version="1.0.0",
        candidate_id="cand_001",
        snapshot_id="snap_20260901",
        cadence_window="2026-09-01/2026-09-07",
        config_hash="DIFFERENT_HASH",  # changed from "abc123"
    )
    invalid_config = InvalidRunRetryConfig(
        original_config_hash="abc123",
    )
    with pytest.raises(ValueError, match="CONFIG_MUST_NOT_CHANGE"):
        scheduler.decide_repeat(
            recipe=recipe_changed_config,
            prior_outcome=EvaluationOutcome.INVALID_RUN,
            attempt_count=1,
            prior_recipe_version="1.0.0",
            original_retry_config=invalid_config,
        )


# ---------------------------------------------------------------------------
# AC3: NEAR_MISS requires a new hypothesis, budget, and version
# ---------------------------------------------------------------------------

def test_job_03_contract_3():
    """JOB-03-AC3: NEAR_MISS cannot retry with same recipe version; requires new version."""
    recipe_same_version = _make_recipe(version="1.0.0")
    policy = _make_policy()
    scheduler = DAGScheduler(policy=policy)

    # Retrying with the same version as prior NEAR_MISS → must raise NearMissMustHaveNewVersionError
    with pytest.raises(NearMissMustHaveNewVersionError):
        scheduler.decide_repeat(
            recipe=recipe_same_version,
            prior_outcome=EvaluationOutcome.NEAR_MISS,
            attempt_count=1,
            prior_recipe_version="1.0.0",  # same version as current recipe
        )

    # Retrying with a bumped version → should be ALLOWED
    recipe_new_version = _make_recipe(version="2.0.0")
    decision = scheduler.decide_repeat(
        recipe=recipe_new_version,
        prior_outcome=EvaluationOutcome.NEAR_MISS,
        attempt_count=1,
        prior_recipe_version="1.0.0",  # prior was v1, current is v2 → OK
    )
    assert decision.outcome == RepeatOutcome.ALLOWED, (
        "NEAR_MISS with a new recipe version must be ALLOWED"
    )


# ---------------------------------------------------------------------------
# Edge case: idempotent re-run on same cadence window with PASS is allowed
# ---------------------------------------------------------------------------

def test_job_03_idempotent_same_window():
    """Edge case: A PASS outcome for the same window/recipe is idempotent (outcome=ALLOWED, reason notes idempotency)."""
    recipe = _make_recipe()
    policy = _make_policy()
    scheduler = DAGScheduler(policy=policy)

    d1 = scheduler.decide_repeat(
        recipe=recipe,
        prior_outcome=EvaluationOutcome.PASS,
        attempt_count=1,
        prior_recipe_version="1.0.0",
    )
    d2 = scheduler.decide_repeat(
        recipe=recipe,
        prior_outcome=EvaluationOutcome.PASS,
        attempt_count=1,
        prior_recipe_version="1.0.0",
    )
    # Both decisions should be deterministic (same inputs → same outcome)
    assert d1.outcome == d2.outcome
    assert d1.reason == d2.reason
