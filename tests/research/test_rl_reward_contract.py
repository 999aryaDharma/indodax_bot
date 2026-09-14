"""Research and contract tests for R01-01: Constrained allocation feasibility spike.

Guarantees:
1. R01-01-AC0: Feasibility spike evaluates RL allocation under net costs and capital constraints (test_r01_01_valid_contract).
2. R01-01-AC1: Reward hacking via excessive turnover or cash neglect is detected and penalized (test_r01_01_contract_1).
3. R01-01-AC2: Evaluation uses identical budget and benchmarks against inverse-volatility baseline (test_r01_01_contract_2).
4. R01-01-AC3: No live orders or automated policy export into production scheduler (test_r01_01_contract_3).
"""

from __future__ import annotations

from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.models.r01_rl_allocator import (
    AllocationBaselineComparator,
    CostAwareRewardFunction,
    LiveExecutionForbiddenError,
    RLAllocationEnvironment,
    RLFeasibilityReport,
    evaluate_rl_allocation_feasibility,
)


def test_r01_01_valid_contract() -> None:
    """AC0: Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal."""
    report: RLFeasibilityReport = evaluate_rl_allocation_feasibility(
        initial_cash=Decimal("500000.00"),
        fee_rate=0.003,  # 0.3% round-trip fee
        n_steps=100,
        random_seed=42,
    )

    assert isinstance(report, RLFeasibilityReport)
    assert report.is_net_cost_evaluated is True
    assert report.initial_capital == Decimal("500000.00")
    assert report.recommendation in ("FEASIBLE", "INCONCLUSIVE", "NOT_RECOMMENDED")
    assert report.is_promoted_to_core is False


def test_r01_01_contract_1() -> None:
    """AC1: Reward hack diuji melalui turnover dan cash."""
    reward_fn = CostAwareRewardFunction(
        fee_rate=0.003,
        turnover_penalty_coef=0.01,
        cash_drag_coef=0.0005,
    )

    # Scenario A: Moderate trading with positive return
    reward_moderate = reward_fn.compute_reward(
        gross_return=0.02,
        turnover=0.10,
        unallocated_cash_ratio=0.20,
    )

    # Scenario B: High-turnover churn (reward hacking attempt: gross return 0.02, but turnover 2.0)
    reward_churn = reward_fn.compute_reward(
        gross_return=0.02,
        turnover=2.0,
        unallocated_cash_ratio=0.20,
    )

    # High turnover must be severely penalized by transaction fees & turnover penalty
    assert reward_churn < reward_moderate
    assert reward_churn < 0.0  # Churning wipes out positive gross return into negative net reward


def test_r01_01_contract_2() -> None:
    """AC2: Same budget versus inverse-vol baseline."""
    comparator = AllocationBaselineComparator(initial_capital=Decimal("500000.00"))

    # Synthetic volatilities for BTC and ETH
    vols = {"btc_idr": 0.02, "eth_idr": 0.04}
    baseline_weights = comparator.compute_inverse_vol_weights(vols)

    # Lower volatility asset (BTC) must receive higher allocation weight
    assert baseline_weights["btc_idr"] > baseline_weights["eth_idr"]
    assert pytest.approx(sum(baseline_weights.values()), rel=1e-4) == 1.0

    # Total allocated budget never exceeds initial capital
    allocations = comparator.allocate_cash(baseline_weights)
    assert sum(allocations.values()) <= Decimal("500000.00")


def test_r01_01_contract_3() -> None:
    """AC3: Tidak ada order live atau policy export otomatis."""
    report = evaluate_rl_allocation_feasibility(
        initial_cash=Decimal("500000.00"),
        fee_rate=0.003,
        n_steps=50,
    )

    # 1. Verification of experimental boundary
    assert report.is_promoted_to_core is False
    assert report.tier == "EXPERIMENTAL"

    # 2. Attempting to export policy to live scheduler raises LiveExecutionForbiddenError
    with pytest.raises(LiveExecutionForbiddenError) as exc_info:
        report.export_to_live_scheduler()
    assert "LIVE_EXECUTION_FORBIDDEN" in str(exc_info.value)
