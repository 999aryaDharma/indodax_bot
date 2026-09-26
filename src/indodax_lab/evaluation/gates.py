"""Hard gates and selection diagnostics for experiment evaluation (EVAL-02).

Contract:
metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS,
DSR/PBO when eligible.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum
from numbers import Integral
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator

from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus
from indodax_lab.evaluation.statistics import compute_deflated_sharpe_ratio, compute_pbo

# EVAL-02-F4: metrics that a strategy-quality gate consumes. Each must be present and
# finite; an absent or non-finite value is *unknown* evidence, never a passing value.
_GATED_METRICS = ("sharpe_ratio", "profit_factor", "max_drawdown", "trade_count")


def _finite_metric(metrics: dict[str, Any], name: str) -> float | None:
    """Return ``name`` as a finite float, or None when absent or unusable."""
    if name not in metrics:
        return None
    raw_value = metrics[name]
    if name == "trade_count" and (
        isinstance(raw_value, bool) or not isinstance(raw_value, Integral)
    ):
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _invalid_run(
    run: ExperimentRunRecord,
    metrics: dict[str, Any],
    passed_gates: list[str],
    failed_gates: list[str],
    reasons: list[str],
    policy: EvaluationPolicy,
) -> EvaluationResult:
    return EvaluationResult(
        run_id=run.run_id,
        candidate_id=run.candidate_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        outcome=EvaluationOutcome.INVALID_RUN,
        passed_gates=passed_gates,
        failed_gates=failed_gates,
        reasons=reasons,
        dsr=None,
        dsr_status="NOT_ESTIMABLE",
        pbo=None,
        pbo_status="NOT_ESTIMABLE",
        metrics=metrics,
    )


class EvaluationOutcome(StrEnum):
    """Categorical evaluation verdict separating validity from strategy quality."""

    INVALID_RUN = "INVALID_RUN"
    HARD_FAIL = "HARD_FAIL"
    NEAR_MISS = "NEAR_MISS"
    REGIME_EDGE = "REGIME_EDGE"
    PASS = "PASS"


class EvaluationPolicy(BaseModel):
    """Immutable, versioned evaluation gate policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = "eval_policy_v1"
    policy_version: str = "1.0.0"
    min_trade_count: int = 30
    min_profit_factor: float = 1.0
    min_sharpe_ratio: float = 0.5
    max_drawdown_pct: float = 0.20
    require_verified_cost_model: bool = True
    require_clean_worktree: bool = True
    seed_aggregation_method: str = "median"

    @field_validator("policy_id", "policy_version")
    @classmethod
    def validate_policy_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("EVALUATION_POLICY_IDENTITY_REQUIRED")
        return value

    @field_validator("min_trade_count", mode="before")
    @classmethod
    def validate_min_trade_count(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("EVALUATION_MIN_TRADE_COUNT_MUST_BE_POSITIVE_INTEGER")
        return value

    @field_validator("min_profit_factor", "min_sharpe_ratio", "max_drawdown_pct")
    @classmethod
    def validate_finite_thresholds(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("EVALUATION_THRESHOLDS_MUST_BE_FINITE")
        return value

    @field_validator("min_profit_factor")
    @classmethod
    def validate_min_profit_factor(cls, value: float) -> float:
        if value < 0:
            raise ValueError("EVALUATION_MIN_PROFIT_FACTOR_MUST_BE_NONNEGATIVE")
        return value

    @field_validator("max_drawdown_pct")
    @classmethod
    def validate_max_drawdown(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("EVALUATION_MAX_DRAWDOWN_MUST_BE_FRACTION")
        return value

    @field_validator("require_verified_cost_model")
    @classmethod
    def require_verified_costs(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("EVALUATION_POLICY_MUST_REQUIRE_VERIFIED_COSTS")
        return value

    @field_validator("seed_aggregation_method")
    @classmethod
    def validate_seed_aggregation(cls, value: str) -> str:
        if value not in {"median", "mean", "worst"}:
            raise ValueError("UNSUPPORTED_SEED_AGGREGATION_METHOD")
        return value


class EvaluationResult(BaseModel):
    """Detailed evaluation outcome with gate breakdown and statistical diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    candidate_id: str
    policy_id: str
    policy_version: str
    outcome: EvaluationOutcome
    passed_gates: list[str]
    failed_gates: list[str]
    reasons: list[str]
    dsr: float | None = None
    dsr_status: str = "NOT_ESTIMABLE"
    pbo: float | None = None
    pbo_status: str = "NOT_ESTIMABLE"
    metrics: dict[str, Any]


class MultiSeedEvaluationResult(BaseModel):
    """Result of evaluating a candidate across multiple seeds without cherry-picking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    policy_id: str
    policy_version: str
    seed_runs: list[str]
    aggregation_method: str
    finalist_metric: dict[str, Any]
    overall_outcome: EvaluationOutcome
    reasons: list[str]


def evaluate_run(
    run: ExperimentRunRecord,
    policy: EvaluationPolicy | None = None,
    trial_count: int = 1,
) -> EvaluationResult:
    """Evaluate an experiment run against versioned hard gates and honesty invariants.

    Invariants:
    - High scores never conceal unverified or unknown costs (INVALID_RUN).
    - Small sample sizes yield insufficient evidence and cannot pass (HARD_FAIL).
    - Statistical diagnostics (DSR/PBO) report NOT_ESTIMABLE when sample/trials inadequate.
    """
    if policy is None:
        policy = EvaluationPolicy()

    passed_gates: list[str] = []
    failed_gates: list[str] = []
    reasons: list[str] = []

    metrics = run.metrics or {}

    # 1. Run Validity Gates (INVALID_RUN checks)
    # EVAL-02-AC1 / EVAL-02-F1: High score does not conceal unknown costs.
    # Fail-closed: cost evidence must be an explicit `True`. An absent flag is
    # *unknown* cost, never verified cost.
    is_cost_verified = metrics.get("cost_model_verified") is True
    cost_schedule_hash = run.cost_schedule_hash.strip().lower()
    if (
        not is_cost_verified
        or not cost_schedule_hash
        or cost_schedule_hash == "unknown"
    ):
        failed_gates.append("COST_MODEL_VERIFIED")
        reasons.append("COST_MODEL_UNKNOWN")
        return _invalid_run(run, metrics, passed_gates, failed_gates, reasons, policy)
    passed_gates.append("COST_MODEL_VERIFIED")

    # Dirty worktree gate
    if policy.require_clean_worktree and run.is_dirty:
        failed_gates.append("CLEAN_WORKTREE")
        reasons.append("DIRTY_WORKTREE_PROMOTION_FORBIDDEN")
        return _invalid_run(run, metrics, passed_gates, failed_gates, reasons, policy)
    passed_gates.append("CLEAN_WORKTREE")

    if run.status != ExperimentRunStatus.SUCCESS:
        failed_gates.append("RUN_EXECUTION_SUCCESS")
        reasons.append("RUN_FAILED_TECHNICAL")
        return _invalid_run(run, metrics, passed_gates, failed_gates, reasons, policy)
    passed_gates.append("RUN_EXECUTION_SUCCESS")

    # EVAL-02-F4: every quality-gate input must be present and finite. Comparison against
    # NaN is always False, so an unchecked NaN would satisfy *every* threshold and reach
    # PASS. Reject the run as invalid instead of gating on unusable evidence.
    resolved: dict[str, float] = {}
    unusable: list[str] = []
    for name in _GATED_METRICS:
        value = _finite_metric(metrics, name)
        if value is None:
            unusable.append(name)
        else:
            resolved[name] = value
    if unusable:
        failed_gates.append("METRICS_PRESENT_AND_FINITE")
        reasons.append("METRIC_MISSING_OR_NON_FINITE:" + ",".join(sorted(unusable)))
        return _invalid_run(run, metrics, passed_gates, failed_gates, reasons, policy)
    passed_gates.append("METRICS_PRESENT_AND_FINITE")

    # 2. Strategy Quality & Evidence Gates
    # EVAL-02-AC2: Sample size gate
    trade_count = int(resolved["trade_count"])
    if trade_count < policy.min_trade_count:
        failed_gates.append("SAMPLE_SIZE_ADEQUATE")
        reasons.append("INSUFFICIENT_SAMPLE_SIZE")
    else:
        passed_gates.append("SAMPLE_SIZE_ADEQUATE")

    # Sharpe ratio gate
    sharpe = resolved["sharpe_ratio"]
    if sharpe < policy.min_sharpe_ratio:
        failed_gates.append("SHARPE_GATE")
        reasons.append("SHARPE_BELOW_THRESHOLD")
    else:
        passed_gates.append("SHARPE_GATE")

    # Profit factor gate
    profit_factor = resolved["profit_factor"]
    if profit_factor < policy.min_profit_factor:
        failed_gates.append("PROFIT_FACTOR_GATE")
        reasons.append("PROFIT_FACTOR_BELOW_THRESHOLD")
    else:
        passed_gates.append("PROFIT_FACTOR_GATE")

    # Drawdown gate
    max_dd = resolved["max_drawdown"]
    if max_dd > policy.max_drawdown_pct:
        failed_gates.append("DRAWDOWN_GATE")
        reasons.append("DRAWDOWN_EXCEEDS_THRESHOLD")
    else:
        passed_gates.append("DRAWDOWN_GATE")

    # 3. Outcome classification
    # EVAL-02-F2: a risk breach is a hard fail. Softening a maximum-drawdown breach into
    # NEAR_MISS because the score was positive would present a losing run as a near miss.
    if failed_gates:
        # Check whether this is a borderline failure that remains inside the hard risk limit.
        if "INSUFFICIENT_SAMPLE_SIZE" in reasons:
            outcome = EvaluationOutcome.HARD_FAIL
        elif "DRAWDOWN_EXCEEDS_THRESHOLD" in reasons:
            outcome = EvaluationOutcome.HARD_FAIL
        elif sharpe > 0.0 and profit_factor >= 1.0:
            outcome = EvaluationOutcome.NEAR_MISS
        else:
            outcome = EvaluationOutcome.HARD_FAIL
    else:
        outcome = EvaluationOutcome.PASS

    # 4. Statistical diagnostics
    returns = metrics.get("returns", [])
    dsr_val, dsr_status = compute_deflated_sharpe_ratio(
        sharpe_ratio=sharpe,
        trial_count=trial_count,
        returns=returns,
    )
    pbo_val, pbo_status = compute_pbo(metrics.get("matrix_returns"))

    return EvaluationResult(
        run_id=run.run_id,
        candidate_id=run.candidate_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        outcome=outcome,
        passed_gates=passed_gates,
        failed_gates=failed_gates,
        reasons=reasons,
        dsr=dsr_val,
        dsr_status=dsr_status,
        pbo=pbo_val,
        pbo_status=pbo_status,
        metrics=metrics,
    )


def evaluate_multi_seed_runs(
    runs: Sequence[ExperimentRunRecord],
    policy: EvaluationPolicy | None = None,
    seed_selection: str | None = None,
) -> MultiSeedEvaluationResult:
    """Evaluate candidate across multiple seeds, strictly forbidding best-seed cherry-picking.

    Invariants:
    - EVAL-02-AC3: Selecting 'best' seed is strictly rejected.
    - Uses honest statistical aggregation (median, mean, or worst seed).
    """
    if not runs:
        raise ValueError("NO_RUNS_PROVIDED_FOR_EVALUATION")

    if policy is None:
        policy = EvaluationPolicy()

    selected_method = policy.seed_aggregation_method if seed_selection is None else seed_selection
    if not isinstance(selected_method, str):
        raise ValueError(f"UNSUPPORTED_SEED_AGGREGATION_METHOD:{selected_method}")
    normalized_selection = selected_method.strip().lower()
    if normalized_selection in ("best", "max", "highest", "cherry_pick"):
        raise ValueError(
            "BEST_SEED_SELECTION_FORBIDDEN: cherry-picking the best seed as finalist "
            "is forbidden by EVAL-02."
        )
    canonical_selection = "worst" if normalized_selection == "min" else normalized_selection
    if canonical_selection != policy.seed_aggregation_method:
        raise ValueError("SEED_AGGREGATION_POLICY_MISMATCH")
    normalized_selection = canonical_selection

    first_run = runs[0]
    run_ids = [run.run_id for run in runs]
    identical_cost_basis = len({r.cost_schedule_hash for r in runs}) == 1
    all_costs_verified = (
        identical_cost_basis
        and all(r.metrics.get("cost_model_verified") is True for r in runs)
        and bool(first_run.cost_schedule_hash.strip())
        and first_run.cost_schedule_hash.strip().lower() != "unknown"
    )

    def invalid_result(reason: str) -> MultiSeedEvaluationResult:
        return MultiSeedEvaluationResult(
            candidate_id=first_run.candidate_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            seed_runs=run_ids,
            aggregation_method=normalized_selection,
            finalist_metric={"cost_model_verified": all_costs_verified},
            overall_outcome=EvaluationOutcome.INVALID_RUN,
            reasons=[reason],
        )

    identity_fields = (
        "candidate_id",
        "candidate_version",
        "family",
        "parent_run_id",
        "git_sha",
        "environment_hash",
        "dataset_snapshot_id",
        "dataset_hash",
        "config_hash",
        "cost_schedule_hash",
        "execution_hash",
    )
    if any(not isinstance(run_id, str) or not run_id.strip() for run_id in run_ids):
        return invalid_result("MULTI_SEED_RUN_ID_REQUIRED")
    if len(set(run_ids)) != len(run_ids):
        return invalid_result("MULTI_SEED_DUPLICATE_RUN_ID")

    required_identity_fields = tuple(
        field for field in identity_fields if field != "parent_run_id"
    )
    missing_identity = [
        field
        for field in required_identity_fields
        if any(
            not isinstance(getattr(run, field), str) or not getattr(run, field).strip()
            for run in runs
        )
    ]
    if missing_identity:
        return invalid_result("MULTI_SEED_IDENTITY_MISSING:" + ",".join(missing_identity))
    if any(run.parent_run_id is not None and not run.parent_run_id.strip() for run in runs):
        return invalid_result("MULTI_SEED_IDENTITY_MISSING:parent_run_id")

    mismatched = [
        field
        for field in identity_fields
        if any(getattr(run, field) != getattr(first_run, field) for run in runs[1:])
    ]
    if mismatched:
        return invalid_result("MULTI_SEED_IDENTITY_MISMATCH:" + ",".join(mismatched))

    # Reuse the single-run validity boundary before aggregating. Unknown values,
    # failed runs and policy-invalid inputs must not be replaced with defaults.
    seed_evaluations: list[EvaluationResult] = []
    for run in runs:
        validation = evaluate_run(run, policy, trial_count=len(runs))
        if validation.outcome == EvaluationOutcome.INVALID_RUN:
            return invalid_result(
                f"MULTI_SEED_RUN_INVALID:{run.run_id}:{','.join(validation.reasons)}"
            )
        seed_evaluations.append(validation)

    sharpes = [float(r.metrics.get("sharpe_ratio", 0.0)) for r in runs]
    pfs = [float(r.metrics.get("profit_factor", 0.0)) for r in runs]
    trade_counts = [int(r.metrics.get("trade_count", 0)) for r in runs]
    dds = [float(r.metrics.get("max_drawdown", 0.0)) for r in runs]

    if normalized_selection == "median":
        agg_sharpe = float(np.median(sharpes))
        agg_pf = float(np.median(pfs))
        agg_tc = int(np.median(trade_counts))
        agg_dd = float(np.median(dds))
    elif normalized_selection == "mean":
        agg_sharpe = float(np.mean(sharpes))
        agg_pf = float(np.mean(pfs))
        agg_tc = int(np.mean(trade_counts))
        agg_dd = float(np.mean(dds))
    elif normalized_selection in ("worst", "min"):
        agg_sharpe = float(np.min(sharpes))
        agg_pf = float(np.min(pfs))
        agg_tc = int(np.min(trade_counts))
        agg_dd = float(np.max(dds))
    else:
        raise ValueError(f"UNSUPPORTED_SEED_AGGREGATION_METHOD:{seed_selection}")

    # EVAL-02-F5: the aggregate is only as trustworthy as its least trustworthy seed.
    # The representative run below is re-gated by `evaluate_run`, so it must carry real
    # cost evidence: verified only when every seed declared verification and every seed
    # was priced with the same cost schedule. Without this the aggregate silently loses
    # the cost evidence and EVAL-02-AC1 no longer protects the multi-seed path.
    finalist_metric = {
        "sharpe_ratio": agg_sharpe,
        "profit_factor": agg_pf,
        "trade_count": agg_tc,
        "max_drawdown": agg_dd,
        "seed_count": len(runs),
        "cost_model_verified": all_costs_verified,
    }

    # Evaluate using representative synthetic run record
    rep_run = ExperimentRunRecord(
        run_id=f"{first_run.candidate_id}_multiseed_agg",
        candidate_id=first_run.candidate_id,
        candidate_version=first_run.candidate_version,
        family=first_run.family,
        git_sha=first_run.git_sha,
        is_dirty=any(r.is_dirty for r in runs),
        environment_hash=first_run.environment_hash,
        dataset_snapshot_id=first_run.dataset_snapshot_id,
        dataset_hash=first_run.dataset_hash,
        config_hash=first_run.config_hash,
        cost_schedule_hash=first_run.cost_schedule_hash,
        execution_hash=first_run.execution_hash,
        status=ExperimentRunStatus.SUCCESS,
        metrics=finalist_metric,
        created_at=first_run.created_at,
        promotable=all(r.promotable for r in runs),
    )

    eval_res = evaluate_run(rep_run, policy, trial_count=len(runs))
    drawdown_breaches = [
        result.run_id
        for result in seed_evaluations
        if "DRAWDOWN_EXCEEDS_THRESHOLD" in result.reasons
    ]
    overall_outcome = (
        EvaluationOutcome.HARD_FAIL if drawdown_breaches else eval_res.outcome
    )
    reasons = list(eval_res.reasons)
    if drawdown_breaches:
        reasons.append("MULTI_SEED_DRAWDOWN_EXCEEDS_THRESHOLD:" + ",".join(drawdown_breaches))

    return MultiSeedEvaluationResult(
        candidate_id=first_run.candidate_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        seed_runs=[r.run_id for r in runs],
        aggregation_method=normalized_selection,
        finalist_metric=finalist_metric,
        overall_outcome=overall_outcome,
        reasons=reasons,
    )
