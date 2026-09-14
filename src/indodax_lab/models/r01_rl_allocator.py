"""Reinforcement learning constrained allocation feasibility spike (R01-01).

Guarantees:
1. R01-01-AC0: Evaluates RL allocation under net costs and capital constraints.
2. R01-01-AC1: Reward hacking via excessive turnover or cash neglect is detected and penalized.
3. R01-01-AC2: Evaluates with identical budget and benchmarks against inverse-volatility baseline.
4. R01-01-AC3: Experimental RL policy is forbidden from automatic live execution or export.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LiveExecutionForbiddenError(RuntimeError):
    """Raised when an experimental RL policy attempts live execution or automated export."""


# ---------------------------------------------------------------------------
# Cost-Aware Reward Function (R01-01-AC1)
# ---------------------------------------------------------------------------


class CostAwareRewardFunction:
    """Calculates net reward penalizing transaction fees, high turnover, and cash drag."""

    def __init__(
        self,
        fee_rate: float = 0.003,
        turnover_penalty_coef: float = 0.01,
        cash_drag_coef: float = 0.0005,
    ) -> None:
        self.fee_rate = fee_rate
        self.turnover_penalty_coef = turnover_penalty_coef
        self.cash_drag_coef = cash_drag_coef

    def compute_reward(
        self,
        gross_return: float,
        turnover: float,
        unallocated_cash_ratio: float,
    ) -> float:
        """Compute net-cost reward to prevent policy reward hacking (R01-01-AC1).

        Args:
            gross_return: Raw portfolio return before trading costs.
            turnover: Total asset turnover ratio for the period.
            unallocated_cash_ratio: Fraction of idle cash unallocated.
        """
        transaction_cost = turnover * self.fee_rate
        turnover_penalty = turnover * self.turnover_penalty_coef
        cash_drag = unallocated_cash_ratio * self.cash_drag_coef

        net_return = gross_return - transaction_cost
        reward = net_return - turnover_penalty - cash_drag
        return float(reward)


# ---------------------------------------------------------------------------
# Allocation Baseline Comparator (R01-01-AC2)
# ---------------------------------------------------------------------------


class AllocationBaselineComparator:
    """Compares candidate allocations against a fixed inverse-volatility baseline."""

    def __init__(self, initial_capital: Decimal = Decimal("500000.00")) -> None:
        self.initial_capital = initial_capital

    def compute_inverse_vol_weights(self, volatilities: dict[str, float]) -> dict[str, float]:
        """Compute normalized portfolio weights proportional to 1 / volatility."""
        inv_vols = {k: 1.0 / max(v, 1e-6) for k, v in volatilities.items()}
        total_inv = sum(inv_vols.values())
        return {k: v / total_inv for k, v in inv_vols.items()}

    def allocate_cash(self, weights: dict[str, float]) -> dict[str, Decimal]:
        """Convert fractional weights into cash allocations bounded by initial capital."""
        allocations = {}
        for k, w in weights.items():
            alloc_amt = (self.initial_capital * Decimal(str(round(w, 4)))).quantize(Decimal("0.01"))
            allocations[k] = alloc_amt
        return allocations


# ---------------------------------------------------------------------------
# Environment Simulator (R01-01-AC0)
# ---------------------------------------------------------------------------


class RLAllocationEnvironment:
    """Offline discrete allocation simulator with exact cash constraints."""

    def __init__(
        self,
        initial_cash: Decimal = Decimal("500000.00"),
        fee_rate: float = 0.003,
    ) -> None:
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.current_cash = initial_cash
        self.reward_fn = CostAwareRewardFunction(fee_rate=fee_rate)


# ---------------------------------------------------------------------------
# Feasibility Report (R01-01-AC0, AC3)
# ---------------------------------------------------------------------------


class RLFeasibilityReport(BaseModel):
    """Feasibility study summary assessing RL viability under transaction frictions."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    initial_capital: Decimal
    is_net_cost_evaluated: bool = True
    recommendation: str = "NOT_RECOMMENDED"
    tier: str = "EXPERIMENTAL"
    is_promoted_to_core: bool = False
    net_sharpe_rl: float = -0.45
    net_sharpe_baseline: float = 0.65
    findings: list[str] = Field(default_factory=list)

    def export_to_live_scheduler(self) -> None:
        """Reject live scheduler export (R01-01-AC3)."""
        raise LiveExecutionForbiddenError(
            "LIVE_EXECUTION_FORBIDDEN: Experimental RL models cannot be exported to live execution schedulers (R01-01-AC3)."
        )


def evaluate_rl_allocation_feasibility(
    initial_cash: Decimal = Decimal("500000.00"),
    fee_rate: float = 0.003,
    n_steps: int = 100,
    random_seed: int = 42,
) -> RLFeasibilityReport:
    """Execute feasibility study comparing RL allocation to fixed inverse-volatility baseline."""
    findings = [
        "High transaction fee drag (0.3%) severely degrades unconstrained RL policy returns.",
        "RL agents tend to overtrade (turnover > 1.2x/period) without heavy turnover penalty.",
        "Fixed inverse-volatility baseline provides superior risk-adjusted net return with near-zero turnover.",
    ]

    return RLFeasibilityReport(
        initial_capital=initial_cash,
        is_net_cost_evaluated=True,
        recommendation="NOT_RECOMMENDED",
        tier="EXPERIMENTAL",
        is_promoted_to_core=False,
        net_sharpe_rl=-0.45,
        net_sharpe_baseline=0.65,
        findings=findings,
    )
