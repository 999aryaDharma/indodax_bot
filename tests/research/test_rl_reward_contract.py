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
    assert report.is_net_cost_evaluated is False
    assert report.evidence_status == "UNEVALUATED"
    assert report.initial_capital == Decimal("500000.00")
    assert report.recommendation == "INCONCLUSIVE"
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

    # Decimal down-rounding must not overspend when many weights are equal.
    equal_allocations = comparator.allocate_cash({f"asset_{i}": 1 / 6 for i in range(6)})
    assert sum(equal_allocations.values()) <= Decimal("500000.00")


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


# ---------------------------------------------------------------------------
# Sprint-review fix cycle. Actor for every line below:
# opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
# ---------------------------------------------------------------------------


def test_inverse_vol_weights_never_amplify_degenerate_volatility() -> None:
    """R01-01-AC0: capital constraints must fail closed, not concentrate on a bad input.

    ``max(v, 1e-6)`` turned a zero or negative volatility into an inverse
    volatility of 1e6, so the degenerate asset received essentially 100% of the
    portfolio. An unknown or non-positive volatility is unknown, not maximal
    confidence.
    """
    comparator = AllocationBaselineComparator(initial_capital=Decimal("500000.00"))

    with pytest.raises(ValueError, match="NON_POSITIVE_VOLATILITY"):
        comparator.compute_inverse_vol_weights({"btc_idr": 0.0, "eth_idr": 0.04})
    with pytest.raises(ValueError, match="NON_POSITIVE_VOLATILITY"):
        comparator.compute_inverse_vol_weights({"btc_idr": -0.02, "eth_idr": 0.04})
    with pytest.raises(ValueError, match="NON_POSITIVE_VOLATILITY"):
        comparator.compute_inverse_vol_weights({"btc_idr": float("nan"), "eth_idr": 0.04})
    with pytest.raises(ValueError, match="NON_POSITIVE_VOLATILITY"):
        comparator.compute_inverse_vol_weights({"btc_idr": float("inf"), "eth_idr": 0.04})


def test_inverse_vol_weights_reject_an_empty_volatility_set() -> None:
    """An empty comparator set is a no-data case, not a valid baseline."""
    comparator = AllocationBaselineComparator(initial_capital=Decimal("500000.00"))
    with pytest.raises(ValueError, match="VOLATILITY_SET_EMPTY"):
        comparator.compute_inverse_vol_weights({})


def test_inverse_vol_weights_still_accept_real_positive_volatility() -> None:
    """Regression guard: the fail-closed guards must not reject legitimate input."""
    comparator = AllocationBaselineComparator(initial_capital=Decimal("500000.00"))
    weights = comparator.compute_inverse_vol_weights({"btc_idr": 0.02, "eth_idr": 0.04})
    assert weights["btc_idr"] > weights["eth_idr"] > 0.0
    assert pytest.approx(sum(weights.values()), rel=1e-9) == 1.0


def test_allocate_cash_rejects_an_empty_weight_map() -> None:
    """R01-01-AC0: deploying zero capital must not report a successful allocation.

    The sprint contract requires no-data to stay distinct from a zero-valued
    successful result. An empty weight map previously returned an empty
    allocation dict and reported success.
    """
    comparator = AllocationBaselineComparator(initial_capital=Decimal("500000.00"))
    with pytest.raises(ValueError, match="ALLOCATION_WEIGHTS_EMPTY"):
        comparator.allocate_cash({})


def test_feasibility_report_is_distinguishable_by_evaluated_configuration() -> None:
    """R01-01-AC0: the evidence artifact must pin the configuration it evaluated.

    ``fee_rate``, ``n_steps`` and ``random_seed`` were accepted and then
    discarded, so the report for a 0.3% fee run and the report for a 5% fee run
    were byte-identical evidence. A reviewer could not tell which configuration
    a feasibility record referred to.
    """
    baseline = evaluate_rl_allocation_feasibility(
        initial_cash=Decimal("500000.00"),
        fee_rate=0.003,
        n_steps=100,
        random_seed=42,
    )
    stressed = evaluate_rl_allocation_feasibility(
        initial_cash=Decimal("500000.00"),
        fee_rate=0.05,
        n_steps=7,
        random_seed=99,
    )

    # Behavioral core: two different configurations must not be the same evidence.
    assert baseline.model_dump() != stressed.model_dump()

    assert baseline.evaluated_fee_rate == pytest.approx(0.003)
    assert baseline.evaluated_n_steps == 100
    assert baseline.evaluated_random_seed == 42
    assert stressed.evaluated_fee_rate == pytest.approx(0.05)
    assert stressed.evaluated_n_steps == 7
    assert stressed.evaluated_random_seed == 99


def test_feasibility_report_stays_fail_closed_after_pinning_config() -> None:
    """Regression guard: pinning the config must not turn UNEVALUATED into a pass."""
    report = evaluate_rl_allocation_feasibility(
        initial_cash=Decimal("500000.00"),
        fee_rate=0.003,
        n_steps=50,
        random_seed=42,
    )
    assert report.is_net_cost_evaluated is False
    assert report.evidence_status == "UNEVALUATED"
    assert report.recommendation == "INCONCLUSIVE"
    assert report.is_promoted_to_core is False
    assert report.tier == "EXPERIMENTAL"
    assert report.net_sharpe_rl is None
    assert report.net_sharpe_baseline is None
    assert any("UNEVALUATED" in finding for finding in report.findings)


def test_reward_penalty_is_monotonic_over_valid_observations() -> None:
    """R01-01-AC1: the anti-reward-hacking penalty must not invert on valid input.

    ``turnover`` and ``unallocated_cash_ratio`` were never validated, so a
    negative turnover flipped the sign of both the transaction cost and the
    turnover penalty and scored *higher* than doing nothing. The penalty must be
    monotonically non-increasing across the whole valid domain, so no observation
    inside that domain can ever be rewarded for trading more.
    """
    reward_fn = CostAwareRewardFunction(
        fee_rate=0.003,
        turnover_penalty_coef=0.01,
        cash_drag_coef=0.0005,
    )

    turnovers = [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    rewards = [
        reward_fn.compute_reward(gross_return=0.02, turnover=t, unallocated_cash_ratio=0.2)
        for t in turnovers
    ]
    for lower, higher in zip(rewards, rewards[1:], strict=False):
        assert higher < lower, f"reward rose as turnover increased: {rewards}"

    # Idle cash is penalised as cash drag, so reward falls as idle cash rises.
    cash_ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
    cash_rewards = [
        reward_fn.compute_reward(gross_return=0.02, turnover=0.1, unallocated_cash_ratio=c)
        for c in cash_ratios
    ]
    for less_cash_ratio, more_cash_ratio, less_cash_reward, more_cash_reward in zip(
        cash_ratios, cash_ratios[1:], cash_rewards, cash_rewards[1:], strict=False
    ):
        assert more_cash_reward < less_cash_reward, (
            f"reward rose as idle cash went {less_cash_ratio} -> {more_cash_ratio}: {cash_rewards}"
        )


def test_reward_function_rejects_impossible_observations() -> None:
    """R01-01-AC1: impossible observations must be rejected, never scored.

    Pre-fix, ``compute_reward(turnover=-0.5, ...)`` returned 0.0264 against 0.0199
    for zero turnover: a malformed observation, reachable from a sign error in an
    upstream weight diff, out-earned doing nothing. It is now refused outright.
    """
    reward_fn = CostAwareRewardFunction(
        fee_rate=0.003,
        turnover_penalty_coef=0.01,
        cash_drag_coef=0.0005,
    )

    with pytest.raises(ValueError, match="TURNOVER_INVALID"):
        reward_fn.compute_reward(gross_return=0.02, turnover=-0.5, unallocated_cash_ratio=0.2)
    with pytest.raises(ValueError, match="TURNOVER_INVALID"):
        reward_fn.compute_reward(gross_return=0.02, turnover=float("nan"), unallocated_cash_ratio=0.2)
    with pytest.raises(ValueError, match="UNALLOCATED_CASH_RATIO_INVALID"):
        reward_fn.compute_reward(gross_return=0.02, turnover=0.1, unallocated_cash_ratio=-0.1)
    with pytest.raises(ValueError, match="UNALLOCATED_CASH_RATIO_INVALID"):
        reward_fn.compute_reward(gross_return=0.02, turnover=0.1, unallocated_cash_ratio=1.5)



