"""Regression: ML-03 objective allowlist + hard caps (30 trials / 1 revision)."""
from __future__ import annotations

import pytest

from indodax_lab.models.tuning import (
    BoundedTrialSearch,
    SearchSpace,
    TrialBudget,
)


def test_ml03_allowlist_permits_inner_latest_objective() -> None:
    space = SearchSpace(
        space_id="sp_allow",
        version="1.0.0",
        params={"C": [0.01, 0.1]},
        target_objective="inner_val_latest_sharpe",
    )
    assert space.target_objective == "inner_val_latest_sharpe"


def test_ml03_rejects_non_inner_objective() -> None:
    with pytest.raises(Exception, match="SEALED_TEST_OBJECTIVE_FORBIDDEN"):
        SearchSpace(
            space_id="sp_bad",
            version="1.0.0",
            params={"C": [0.01]},
            target_objective="latest_sharpe",
        )


def test_ml03_caps_enforced() -> None:
    with pytest.raises(Exception, match="TRIAL_BUDGET|MAX_TRIALS|BUDGET"):
        TrialBudget(max_trials=31, max_revisions=1)
    with pytest.raises(Exception, match="REVISION|MAX_REVISIONS|BUDGET"):
        TrialBudget(max_trials=30, max_revisions=2)
    space = SearchSpace(
        space_id="sp_cap",
        version="1.0.0",
        params={"C": [0.01]},
        target_objective="inner_val_sharpe",
    )
    with pytest.raises(Exception, match="TRIAL_BUDGET|MAX_TRIALS|BUDGET"):
        BoundedTrialSearch(search_space=space, max_trials=100)
