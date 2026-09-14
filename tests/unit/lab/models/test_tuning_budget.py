"""Unit tests for ML-03 Bounded trial search.

Acceptance Criteria:
- ML-03-AC0 (test_ml_03_valid_contract): Search mencatat trial budget dan tidak memakai sealed test sebagai objective.
- ML-03-AC1 (test_ml_03_contract_1): Trial gagal tetap menghabiskan budget.
- ML-03-AC2 (test_ml_03_contract_2): Resume config mismatch ditolak.
- ML-03-AC3 (test_ml_03_contract_3): Maksimum 30 trial dan satu near-miss revision per model.
"""

from __future__ import annotations

import pytest

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

