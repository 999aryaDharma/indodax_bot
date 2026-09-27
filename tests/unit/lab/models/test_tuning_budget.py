"""Unit tests for ML-03 Bounded trial search.

Acceptance Criteria:
- ML-03-AC0 (test_ml_03_valid_contract): Search mencatat trial budget dan tidak memakai sealed test sebagai objective.
- ML-03-AC1 (test_ml_03_contract_1): Trial gagal tetap menghabiskan budget.
- ML-03-AC2 (test_ml_03_contract_2): Resume config mismatch ditolak.
- ML-03-AC3 (test_ml_03_contract_3): Maksimum 30 trial dan satu near-miss revision per model.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from indodax_lab.models.tuning import (
    BoundedTrialSearch,
    ResumeConfigMismatchError,
    RevisionBudgetExhaustedError,
    SealedTestObjectiveForbiddenError,
    SearchSpace,
    TrialBudget,
    TrialBudgetExhaustedError,
    TrialStatus,
)

# ADR-003 "Default budgets" pins the classical/ML search caps as research policy:
# ML 30 trials, and at most one near-miss revision per model. The literals below are
# the contract, deliberately not imported from the implementation.
ADR003_MAX_TRIALS = 30
ADR003_MAX_REVISIONS = 1


def test_ml_03_valid_contract() -> None:
    """ML-03-AC0: Search mencatat trial budget dan tidak memakai sealed test sebagai objective."""
    # 1. Sealed test as objective is strictly forbidden
    with pytest.raises(SealedTestObjectiveForbiddenError, match="SEALED_TEST_OBJECTIVE_FORBIDDEN"):
        SearchSpace(
            space_id="sp_m01_lr",
            version="1.0.0",
            params={"C": [0.01, 0.1, 1.0], "l1_ratio": [0.1, 0.5]},
            target_objective="sealed_test_sharpe",
        )

    with pytest.raises(SealedTestObjectiveForbiddenError, match="SEALED_TEST_OBJECTIVE_FORBIDDEN"):
        SearchSpace(
            space_id="sp_m01_lr",
            version="1.0.0",
            params={"C": [0.01, 0.1, 1.0]},
            target_objective="test_net_profit",
        )

    # 2. Valid inner validation objective
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1, 1.0], "l1_ratio": [0.1, 0.5]},
        target_objective="inner_val_sharpe",
    )
    search = BoundedTrialSearch(search_space=space)

    assert search.budget.max_trials == 30
    assert search.budget.consumed_trials == 0
    assert search.budget.remaining_trials == 30

    # Execute 2 trials
    search.register_trial(
        trial_id="trial_1",
        params={"C": 0.01, "l1_ratio": 0.1},
        status=TrialStatus.SUCCESS,
        objective_score=1.25,
    )
    search.register_trial(
        trial_id="trial_2",
        params={"C": 0.1, "l1_ratio": 0.5},
        status=TrialStatus.SUCCESS,
        objective_score=1.65,
    )

    assert search.budget.consumed_trials == 2
    assert search.budget.remaining_trials == 28
    winning = search.get_winning_recipe()
    assert winning.params["C"] == 0.1
    assert winning.objective_score == 1.65


def test_ml_03_contract_1() -> None:
    """ML-03-AC1: Trial gagal tetap menghabiskan budget."""
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.001, 0.01, 0.1]},
        target_objective="inner_val_sharpe",
    )
    search = BoundedTrialSearch(search_space=space, max_trials=5)

    # Register failed trials (e.g. solver non-convergence or memory limit)
    search.register_trial(
        trial_id="trial_fail_1",
        params={"C": 0.001},
        status=TrialStatus.FAILED,
        error_message="SOLVER_DIVERGENCE",
    )
    search.register_trial(
        trial_id="trial_fail_2",
        params={"C": 0.01},
        status=TrialStatus.FAILED,
        error_message="TIMEOUT_EXCEEDED",
    )

    # Invariant: Budget consumed even on failed trials
    assert search.budget.consumed_trials == 2
    assert search.budget.remaining_trials == 3

    # Consume the remaining 3 trials with failures
    for i in range(3, 6):
        search.register_trial(
            trial_id=f"trial_fail_{i}",
            params={"C": 0.1},
            status=TrialStatus.FAILED,
            error_message="MEMORY_LIMIT",
        )

    assert search.budget.consumed_trials == 5
    assert search.budget.remaining_trials == 0

    # 6th trial must be blocked because budget is exhausted
    with pytest.raises(TrialBudgetExhaustedError, match="TRIAL_BUDGET_EXHAUSTED"):
        search.register_trial(
            trial_id="trial_fail_6",
            params={"C": 0.1},
            status=TrialStatus.SUCCESS,
            objective_score=2.0,
        )


def test_ml_03_contract_2() -> None:
    """ML-03-AC2: Resume config mismatch ditolak."""
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1, 1.0]},
        target_objective="inner_val_sharpe",
    )
    search = BoundedTrialSearch(search_space=space)
    for i in range(5):
        search.register_trial(
            trial_id=f"trial_{i}",
            params={"C": 0.01},
            status=TrialStatus.SUCCESS,
            objective_score=1.0 + i * 0.1,
        )

    state = search.export_state()
    assert state["budget"]["consumed_trials"] == 5

    # 1. Resuming with matching search space succeeds
    resumed_search = BoundedTrialSearch.from_state(state, search_space=space)
    assert resumed_search.budget.consumed_trials == 5
    assert resumed_search.budget.remaining_trials == 25

    # 2. Resuming with modified params in search space must be rejected
    mutated_space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1, 5.0]},  # altered candidate values
        target_objective="inner_val_sharpe",
    )
    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(state, search_space=mutated_space)

    # 3. Resuming with different space_id must be rejected
    different_id_space = SearchSpace(
        space_id="sp_m02_xgb",
        version="1.0.0",
        params={"C": [0.01, 0.1, 1.0]},
        target_objective="inner_val_sharpe",
    )
    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(state, search_space=different_id_space)


def test_ml_03_contract_3() -> None:
    """ML-03-AC3: Maksimum 30 trial dan satu near-miss revision per model."""
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1]},
        target_objective="inner_val_sharpe",
    )
    search = BoundedTrialSearch(search_space=space, max_trials=30, max_revisions=1)

    # Run 10 trials
    for i in range(10):
        search.register_trial(
            trial_id=f"t_{i}",
            params={"C": 0.01},
            status=TrialStatus.SUCCESS,
            objective_score=0.95,
        )

    assert search.budget.consumed_trials == 10

    # First near-miss revision is allowed
    revised_space_1 = SearchSpace(
        space_id="sp_m01_lr_rev1",
        version="1.1.0",
        params={"C": [0.05, 0.2]},
        target_objective="inner_val_sharpe",
    )
    search.revise_search_space(revised_space_1)
    assert search.budget.revision_count == 1
    # Invariant: Revision does NOT reset consumed trials
    assert search.budget.consumed_trials == 10
    assert search.budget.remaining_trials == 20

    # Second revision must be strictly blocked (max 1 near-miss revision per model)
    revised_space_2 = SearchSpace(
        space_id="sp_m01_lr_rev2",
        version="1.2.0",
        params={"C": [0.5, 1.0]},
        target_objective="inner_val_sharpe",
    )
    with pytest.raises(RevisionBudgetExhaustedError, match="REVISION_BUDGET_EXHAUSTED"):
        search.revise_search_space(revised_space_2)

    # Consume the remaining 20 trials
    for i in range(10, 30):
        search.register_trial(
            trial_id=f"t_{i}",
            params={"C": 0.05},
            status=TrialStatus.SUCCESS,
            objective_score=1.1,
        )

    assert search.budget.consumed_trials == 30
    assert search.budget.remaining_trials == 0

    # Attempting 31st trial exceeds maximum 30 trial cap
    with pytest.raises(TrialBudgetExhaustedError, match="TRIAL_BUDGET_EXHAUSTED"):
        search.register_trial(
            trial_id="t_31",
            params={"C": 0.05},
            status=TrialStatus.SUCCESS,
            objective_score=1.2,
        )


def test_ml_03_edge_cases_and_winning_recipe() -> None:
    """Edge cases: no successful trials, negative scores, and space hash determinism."""
    space = SearchSpace(
        space_id="sp_edge",
        version="1.0.0",
        params={"learning_rate": [0.01, 0.05]},
        target_objective="inner_val_pnl",
    )
    search = BoundedTrialSearch(search_space=space)

    # 1. get_winning_recipe with zero successful trials raises ValueError
    with pytest.raises(ValueError, match="NO_SUCCESSFUL_TRIALS_FOUND"):
        search.get_winning_recipe()

    search.register_trial(
        trial_id="t_fail",
        params={"learning_rate": 0.01},
        status=TrialStatus.FAILED,
        error_message="OOM",
    )
    with pytest.raises(ValueError, match="NO_SUCCESSFUL_TRIALS_FOUND"):
        search.get_winning_recipe()

    # 2. Negative scores properly ranked
    search.register_trial(
        trial_id="t_succ_1",
        params={"learning_rate": 0.01},
        status=TrialStatus.SUCCESS,
        objective_score=-0.50,
    )
    search.register_trial(
        trial_id="t_succ_2",
        params={"learning_rate": 0.05},
        status=TrialStatus.SUCCESS,
        objective_score=-0.10,
    )
    winning = search.get_winning_recipe()
    assert winning.trial_id == "t_succ_2"
    assert winning.objective_score == -0.10

    # 3. Hash determinism
    h1 = space.space_hash()
    space_clone = SearchSpace(
        space_id="sp_edge",
        version="1.0.0",
        params={"learning_rate": [0.01, 0.05]},
        target_objective="inner_val_pnl",
    )
    assert h1 == space_clone.space_hash()


# ---------------------------------------------------------------------------
# Regression: objective guard was substring-based (ML-03-AC0)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "lookalike",
    [
        "outer_val_loss",
        "outer_validation_loss",
        "holdout_pnl",
        "sealed_test_v2_sharpe",
        "test_sharpe",
        "innerval_sharpe",
        "inner_val_sharpe_v2",
        "cv_test_pnl",
        "latest_pnl",
        "",
    ],
)
def test_ml_03_ac0_objective_guard_is_an_exact_allowlist(lookalike: str) -> None:
    """Only registered inner-validation objectives may drive a search.

    The previous guard was a substring scan for `test`/`sealed`, so lookalike names such
    as `outer_val_loss` and `holdout_pnl` slipped through and let sealed or out-of-fold
    data act as the tuning objective.
    """
    with pytest.raises(SealedTestObjectiveForbiddenError, match="SEALED_TEST_OBJECTIVE_FORBIDDEN"):
        SearchSpace(
            space_id="sp_m01_lr",
            version="1.0.0",
            params={"C": [0.01, 0.1]},
            target_objective=lookalike,
        )


@pytest.mark.parametrize(
    "allowed",
    ["inner_val_sharpe", "inner_val_pnl", "inner_val_log_loss", "inner_val_brier"],
)
def test_ml_03_ac0_registered_inner_validation_objectives_are_accepted(allowed: str) -> None:
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1]},
        target_objective=allowed,
    )
    assert space.target_objective == allowed


# ---------------------------------------------------------------------------
# Regression: ADR-003 caps were never enforced (ML-03-AC3)
# ---------------------------------------------------------------------------

def test_ml_03_ac3_constructor_refuses_to_raise_the_adr003_trial_cap() -> None:
    """ADR-003 caps ML search at 30 trials; the cap must not be raisable by the caller."""
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1]},
        target_objective="inner_val_sharpe",
    )

    with pytest.raises(ValueError, match="BUDGET_POLICY_VIOLATION"):
        BoundedTrialSearch(search_space=space, max_trials=ADR003_MAX_TRIALS + 1)

    with pytest.raises(ValueError, match="BUDGET_POLICY_VIOLATION"):
        BoundedTrialSearch(search_space=space, max_trials=0)

    # The documented cap itself stays constructible and the budget is a real cap.
    capped = BoundedTrialSearch(search_space=space, max_trials=ADR003_MAX_TRIALS)
    assert capped.budget.max_trials == ADR003_MAX_TRIALS


def test_ml_03_ac3_constructor_refuses_to_raise_the_adr003_revision_cap() -> None:
    """ADR-003 permits at most one near-miss revision per model."""
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1]},
        target_objective="inner_val_sharpe",
    )

    with pytest.raises(ValueError, match="BUDGET_POLICY_VIOLATION"):
        BoundedTrialSearch(search_space=space, max_revisions=ADR003_MAX_REVISIONS + 1)

    with pytest.raises(ValueError, match="BUDGET_POLICY_VIOLATION"):
        BoundedTrialSearch(search_space=space, max_revisions=-1)

    # A budget of 0 revisions is *stricter* than the cap, not a cap violation, so it
    # stays constructible and must fail closed on the very first revision attempt.
    locked = BoundedTrialSearch(search_space=space, max_revisions=0)
    with pytest.raises(RevisionBudgetExhaustedError, match="REVISION_BUDGET_EXHAUSTED"):
        locked.revise_search_space(space)
    assert locked.budget.revision_count == 0

    single = BoundedTrialSearch(search_space=space, max_revisions=ADR003_MAX_REVISIONS)
    assert single.budget.max_revisions == ADR003_MAX_REVISIONS


def test_ml_03_ac3_trial_budget_under_the_cap_still_fails_closed() -> None:
    """A sub-cap budget must still stop the next trial instead of silently allowing it."""
    space = SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1]},
        target_objective="inner_val_sharpe",
    )
    search = BoundedTrialSearch(search_space=space, max_trials=3)
    for i in range(3):
        search.register_trial(
            trial_id=f"t_{i}", params={"C": 0.01}, status=TrialStatus.SUCCESS, objective_score=0.5
        )

    with pytest.raises(TrialBudgetExhaustedError, match="TRIAL_BUDGET_EXHAUSTED"):
        search.register_trial(
            trial_id="t_over", params={"C": 0.01}, status=TrialStatus.SUCCESS, objective_score=0.9
        )


def test_ml_03_trial_budget_model_cannot_be_constructed_over_the_adr003_cap() -> None:
    """The cap is enforced on the budget record itself, not only on the search wrapper."""
    with pytest.raises(ValueError, match="BUDGET_POLICY_VIOLATION"):
        TrialBudget(max_trials=ADR003_MAX_TRIALS + 1, max_revisions=ADR003_MAX_REVISIONS)

    with pytest.raises(ValueError, match="BUDGET_POLICY_VIOLATION"):
        TrialBudget(max_trials=ADR003_MAX_TRIALS, max_revisions=ADR003_MAX_REVISIONS + 1)


# ---------------------------------------------------------------------------
# Regression: from_state trusted serialized counters (ML-03-AC2 / AC3)
# ---------------------------------------------------------------------------

def _search_space() -> SearchSpace:
    return SearchSpace(
        space_id="sp_m01_lr",
        version="1.0.0",
        params={"C": [0.01, 0.1]},
        target_objective="inner_val_sharpe",
    )


def _state_with_one_trial() -> dict:
    space = _search_space()
    search = BoundedTrialSearch(search_space=space)
    search.register_trial(
        trial_id="t_0", params={"C": 0.01}, status=TrialStatus.SUCCESS, objective_score=0.5
    )
    return search.export_state()


def test_ml_03_from_state_rejects_understated_consumed_trials() -> None:
    """`from_state` must reconstruct the trial counter, not trust the serialized value.

    Tampering the persisted counter downward would otherwise hand back a search that
    believes it still has a full trial budget while trials are already recorded.
    """
    state = _state_with_one_trial()
    assert len(state["trials"]) == 1
    state["budget"]["consumed_trials"] = 0

    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(state, search_space=_search_space())


def test_ml_03_from_state_rejects_overstated_consumed_trials() -> None:
    state = _state_with_one_trial()
    state["budget"]["consumed_trials"] = 99

    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(state, search_space=_search_space())


def test_ml_03_from_state_rejects_raised_trial_cap() -> None:
    """A serialized budget must not be able to raise the ADR-003 trial cap on resume."""
    state = _state_with_one_trial()
    state["budget"]["max_trials"] = ADR003_MAX_TRIALS + 1

    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(state, search_space=_search_space())


def test_ml_03_from_state_rejects_raised_revision_cap_and_count() -> None:
    state = _state_with_one_trial()

    raised_cap = _state_with_one_trial()
    raised_cap["budget"]["max_revisions"] = ADR003_MAX_REVISIONS + 1
    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(raised_cap, search_space=_search_space())

    over_consumed = _state_with_one_trial()
    over_consumed["budget"]["revision_count"] = ADR003_MAX_REVISIONS + 1
    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(over_consumed, search_space=_search_space())

    negative = _state_with_one_trial()
    negative["budget"]["revision_count"] = -1
    with pytest.raises(ResumeConfigMismatchError, match="RESUME_CONFIG_MISMATCH"):
        BoundedTrialSearch.from_state(negative, search_space=_search_space())


def test_ml_03_from_state_preserves_the_budget_a_matching_checkpoint_reports() -> None:
    """A consistent checkpoint still resumes with the same remaining budget."""
    space = _search_space()
    state = _state_with_one_trial()
    resumed = BoundedTrialSearch.from_state(state, search_space=space)

    assert resumed.budget.consumed_trials == 1
    assert resumed.budget.remaining_trials == ADR003_MAX_TRIALS - 1
    assert len(resumed.trials) == 1


@pytest.mark.parametrize(
    ("objective", "trials", "winner"),
    [
        ("inner_val_log_loss", (("low", 0.1), ("high", 0.9)), "low"),
        ("inner_val_brier", (("zero", 0.0), ("positive", 0.1)), "zero"),
        ("inner_val_pnl", (("negative", -1.0), ("zero", 0.0)), "zero"),
    ],
)
def test_ml_03_winning_recipe_respects_objective_direction_and_zero(
    objective: str, trials: tuple[tuple[str, float], ...], winner: str
) -> None:
    space = SearchSpace(
        space_id="sp_direction",
        version="1.0.0",
        params={},
        target_objective=objective,
    )
    search = BoundedTrialSearch(space)
    for trial_id, score in trials:
        search.register_trial(
            trial_id=trial_id,
            params={},
            status=TrialStatus.SUCCESS,
            objective_score=score,
        )

    assert search.get_winning_recipe().trial_id == winner


def test_ml_03_revision_history_rejects_checkpoint_counter_downgrade() -> None:
    original = SearchSpace(
        space_id="sp_revision_original",
        version="1.0.0",
        params={"C": [0.1]},
        target_objective="inner_val_sharpe",
    )
    revised = SearchSpace(
        space_id="sp_revision_once",
        version="1.1.0",
        params={"C": [0.2]},
        target_objective="inner_val_sharpe",
    )
    search = BoundedTrialSearch(original)
    search.revise_search_space(revised)
    state = search.export_state()
    state["budget"]["revision_count"] = 0

    with pytest.raises(ResumeConfigMismatchError, match="revision history"):
        BoundedTrialSearch.from_state(state, search_space=revised)


def test_ml_03_legacy_unrevised_checkpoint_remains_resumable() -> None:
    space = _search_space()
    state = _state_with_one_trial()
    state.pop("initial_search_space_hash")
    state.pop("revision_history")

    resumed = BoundedTrialSearch.from_state(state, search_space=space)

    assert resumed.budget.revision_count == 0
    assert resumed.budget.consumed_trials == 1


def test_ml_03_public_budget_fields_cannot_be_mutated_after_validation() -> None:
    search = BoundedTrialSearch(_search_space())

    with pytest.raises(ValidationError):
        search.budget.max_trials = ADR003_MAX_TRIALS + 1
    with pytest.raises(ValidationError):
        search.budget.consumed_trials = 0
    with pytest.raises(AttributeError):
        search.budget = TrialBudget()

