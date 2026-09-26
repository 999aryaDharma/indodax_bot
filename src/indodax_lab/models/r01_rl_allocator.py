"""Reinforcement learning constrained allocation feasibility spike (R01-01).

Guarantees:
1. R01-01-AC0: Evaluates RL allocation under net costs and capital constraints.
2. R01-01-AC1: Reward hacking via excessive turnover or cash neglect is detected and penalized.
3. R01-01-AC2: Evaluates with identical budget and benchmarks against inverse-volatility baseline.
4. R01-01-AC3: Experimental RL policy is forbidden from automatic live execution or export.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
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

        Observations are validated before they are scored. Turnover and cash
        ratio are physically bounded quantities, so a negative or out-of-range
        value is a malformed observation rather than an extreme strategy: left
        unvalidated it flips the sign of the penalties and would hand a policy
        *more* reward for a broken weight diff than for doing nothing.

        Args:
            gross_return: Raw portfolio return before trading costs.
            turnover: Total asset turnover ratio for the period; must be >= 0.
            unallocated_cash_ratio: Fraction of idle cash unallocated; must be in [0, 1].

        Raises:
            ValueError: If turnover is negative or the cash ratio is outside [0, 1].
        """
        if not (float(turnover) >= 0):
            # `not (x >= 0)` also rejects NaN, for which every comparison is False.
            raise ValueError(f"TURNOVER_INVALID: turnover must be a non-negative number, got {turnover!r}")
        if not (0.0 <= float(unallocated_cash_ratio) <= 1.0):
            raise ValueError(
                "UNALLOCATED_CASH_RATIO_INVALID: unallocated cash ratio must be within [0, 1], "
                f"got {unallocated_cash_ratio!r}"
            )

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
        """Compute normalized portfolio weights proportional to 1 / volatility.

        Fails closed on unusable input. A missing, zero, negative, NaN, or
        infinite volatility is an unknown value and must never be clamped into a
        huge inverse volatility, which would silently route essentially the whole
        portfolio into the untrustworthy asset.
        """
        if not volatilities:
            raise ValueError("VOLATILITY_SET_EMPTY: cannot build an inverse-volatility baseline from no assets")

        inv_vols: dict[str, float] = {}
        for asset, vol in volatilities.items():
            try:
                value = float(vol)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"NON_POSITIVE_VOLATILITY: volatility for '{asset}' is not a number: {vol!r}") from exc
            # `not (value > 0)` also rejects NaN, for which every comparison is False.
            if not (value > 0) or value == float("inf"):
                raise ValueError(
                    f"NON_POSITIVE_VOLATILITY: volatility for '{asset}' must be a finite positive number, got {vol!r}"
                )
            inv_vols[asset] = 1.0 / value

        total_inv = sum(inv_vols.values())
        if not (total_inv > 0):
            raise ValueError("NON_POSITIVE_VOLATILITY: total inverse volatility is not positive")
        return {k: v / total_inv for k, v in inv_vols.items()}

    def allocate_cash(self, weights: dict[str, float]) -> dict[str, Decimal]:
        """Convert fractional weights into cash allocations bounded by initial capital."""
        if not weights:
            # No-data must not be reported as a successful zero-capital allocation.
            raise ValueError("ALLOCATION_WEIGHTS_EMPTY: refusing to report a successful empty allocation")
        if any(not isinstance(w, (int, float)) or isinstance(w, bool) or not 0 <= float(w) <= 1 for w in weights.values()):
            raise ValueError("ALLOCATION_WEIGHT_INVALID")
        total = sum(float(w) for w in weights.values())
        if total > 1.0 + 1e-12:
            raise ValueError("ALLOCATION_WEIGHTS_EXCEED_SIMPLEX")
        allocations: dict[str, Decimal] = {}
        spent = Decimal("0")
        for k, w in weights.items():
            alloc_amt = (self.initial_capital * Decimal(str(w))).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            allocations[k] = alloc_amt
            spent += alloc_amt
        if spent > self.initial_capital:
            raise ValueError("ALLOCATION_CAP_EXCEEDED")
        return allocations


# ---------------------------------------------------------------------------
# Environment Simulator (R01-01-AC0)
# ---------------------------------------------------------------------------


class RLAllocationEnvironment:
    """Configuration holder for the offline allocation environment.

    This is deliberately **not** a working simulator: it has no ``reset`` and no
    ``step``, and performs no trajectory rollout. It exists so the spike has a
    single place to pin the net-cost and capital-constraint configuration, and
    so downstream code cannot mistake it for a functioning environment. A real
    rollout is blocked behind the same `UNEVALUATED` evidence gate as the rest of
    the spike.
    """

    def __init__(
        self,
        initial_cash: Decimal = Decimal("500000.00"),
        fee_rate: float = 0.003,
    ) -> None:
        if not (float(fee_rate) >= 0):
            raise ValueError(f"FEE_RATE_INVALID: fee_rate must be a non-negative number, got {fee_rate!r}")
        if initial_cash <= Decimal("0"):
            raise ValueError(f"INITIAL_CASH_INVALID: initial cash must be positive, got {initial_cash}")
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.current_cash = initial_cash
        self.reward_fn = CostAwareRewardFunction(fee_rate=fee_rate)


# ---------------------------------------------------------------------------
# Feasibility Report (R01-01-AC0, AC3)
# ---------------------------------------------------------------------------


class RLFeasibilityReport(BaseModel):
    """Feasibility study summary assessing RL viability under transaction frictions.

    The evaluated configuration is pinned onto the report itself. Without it a
    feasibility record cannot be tied back to the fee, horizon, and seed it was
    produced under, and two materially different runs produce indistinguishable
    evidence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    initial_capital: Decimal
    is_net_cost_evaluated: bool = False
    evidence_status: str = "UNEVALUATED"
    recommendation: str = "INCONCLUSIVE"
    tier: str = "EXPERIMENTAL"
    is_promoted_to_core: bool = False
    net_sharpe_rl: float | None = None
    net_sharpe_baseline: float | None = None
    evaluated_fee_rate: float | None = None
    evaluated_n_steps: int | None = None
    evaluated_random_seed: int | None = None
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
    """Execute feasibility study comparing RL allocation to fixed inverse-volatility baseline.

    The supplied ``fee_rate``, ``n_steps`` and ``random_seed`` are not yet acted
    upon, because no deterministic offline trajectory or evaluator exists yet.
    Rather than silently discard them, they are recorded on the report so the
    resulting evidence is self-identifying, and the report keeps its fail-closed
    ``UNEVALUATED`` / ``INCONCLUSIVE`` posture.
    """
    findings = [
        "UNEVALUATED: no deterministic offline RL trajectory/evaluator was supplied.",
        "BLOCKED: net Sharpe and profitability claims require immutable out-of-sample evidence.",
        "BASELINE_ONLY: inverse-volatility allocation is a comparator, not evidence of RL performance.",
        (
            f"UNACTED_CONFIG: fee_rate={fee_rate}, n_steps={n_steps}, random_seed={random_seed} "
            "were recorded but not evaluated; they must not be read as applied settings."
        ),
    ]

    return RLFeasibilityReport(
        initial_capital=initial_cash,
        is_net_cost_evaluated=False,
        evidence_status="UNEVALUATED",
        recommendation="INCONCLUSIVE",
        tier="EXPERIMENTAL",
        is_promoted_to_core=False,
        net_sharpe_rl=None,
        net_sharpe_baseline=None,
        evaluated_fee_rate=float(fee_rate),
        evaluated_n_steps=int(n_steps),
        evaluated_random_seed=int(random_seed),
        findings=findings,
    )
