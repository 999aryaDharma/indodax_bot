"""Hard gates and selection diagnostics for experiment evaluation (EVAL-02).

Contract:
metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Sequence
import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator

from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus
from indodax_lab.evaluation.statistics import compute_deflated_sharpe_ratio, compute_pbo


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


class EvaluationResult(BaseModel):
    """Detailed evaluation outcome with gate breakdown and statistical diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    candidate_id: str
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
    seed_runs: list[str]
    aggregation_method: str
    finalist_metric: dict[str, Any]
    overall_outcome: EvaluationOutcome


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
    # EVAL-02-AC1: High score does not conceal unknown costs
    is_cost_verified = metrics.get("cost_model_verified", True)
    if not is_cost_verified or not run.cost_schedule_hash or run.cost_schedule_hash.lower() == "unknown":
        failed_gates.append("COST_MODEL_VERIFIED")
        reasons.append("COST_MODEL_UNKNOWN")
        return EvaluationResult(
            run_id=run.run_id,
            candidate_id=run.candidate_id,
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
    passed_gates.append("COST_MODEL_VERIFIED")

    # Dirty worktree gate
    if policy.require_clean_worktree and run.is_dirty:
        failed_gates.append("CLEAN_WORKTREE")
        reasons.append("DIRTY_WORKTREE_PROMOTION_FORBIDDEN")
        return EvaluationResult(
            run_id=run.run_id,
            candidate_id=run.candidate_id,
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
    passed_gates.append("CLEAN_WORKTREE")

    if run.status != ExperimentRunStatus.SUCCESS:
        failed_gates.append("RUN_EXECUTION_SUCCESS")
        reasons.append("RUN_FAILED_TECHNICAL")
        return EvaluationResult(
            run_id=run.run_id,
            candidate_id=run.candidate_id,
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
    passed_gates.append("RUN_EXECUTION_SUCCESS")

    # 2. Strategy Quality & Evidence Gates
    # EVAL-02-AC2: Sample size gate
    trade_count = int(metrics.get("trade_count", 0))
    if trade_count < policy.min_trade_count:
        failed_gates.append("SAMPLE_SIZE_ADEQUATE")
        reasons.append("INSUFFICIENT_SAMPLE_SIZE")
    else:
        passed_gates.append("SAMPLE_SIZE_ADEQUATE")

    # Sharpe ratio gate
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    if sharpe < policy.min_sharpe_ratio:
        failed_gates.append("SHARPE_GATE")
        reasons.append("SHARPE_BELOW_THRESHOLD")
    else:
        passed_gates.append("SHARPE_GATE")

    # Profit factor gate
    profit_factor = float(metrics.get("profit_factor", 0.0))
    if profit_factor < policy.min_profit_factor:
        failed_gates.append("PROFIT_FACTOR_GATE")
        reasons.append("PROFIT_FACTOR_BELOW_THRESHOLD")
    else:
        passed_gates.append("PROFIT_FACTOR_GATE")

    # Drawdown gate
    max_dd = float(metrics.get("max_drawdown", 0.0))
    if max_dd > policy.max_drawdown_pct:
        failed_gates.append("DRAWDOWN_GATE")
        reasons.append("DRAWDOWN_EXCEEDS_THRESHOLD")
    else:
        passed_gates.append("DRAWDOWN_GATE")

    # 3. Outcome classification
    if failed_gates:
        # Check if near miss (e.g. sample size passed, positive sharpe, but marginally below threshold)
        if "INSUFFICIENT_SAMPLE_SIZE" in reasons:
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
    seed_selection: str = "median",
) -> MultiSeedEvaluationResult:
    """Evaluate candidate across multiple seeds, strictly forbidding best-seed cherry-picking.

    Invariants:
    - EVAL-02-AC3: Selecting 'best' seed is strictly rejected.
    - Uses honest statistical aggregation (median, mean, or worst seed).
    """
    if not runs:
        raise ValueError("NO_RUNS_PROVIDED_FOR_EVALUATION")

    normalized_selection = seed_selection.strip().lower()
    if normalized_selection in ("best", "max", "highest", "cherry_pick"):
        raise ValueError(
            "BEST_SEED_SELECTION_FORBIDDEN: cherry-picking the best seed as finalist is strictly forbidden by EVAL-02."
        )

    if policy is None:
        policy = EvaluationPolicy()

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

    finalist_metric = {
        "sharpe_ratio": agg_sharpe,
        "profit_factor": agg_pf,
        "trade_count": agg_tc,
        "max_drawdown": agg_dd,
        "seed_count": len(runs),
    }

    # Evaluate using representative synthetic run record
    first_run = runs[0]
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

    return MultiSeedEvaluationResult(
        candidate_id=first_run.candidate_id,
        seed_runs=[r.run_id for r in runs],
        aggregation_method=normalized_selection,
        finalist_metric=finalist_metric,
        overall_outcome=eval_res.outcome,
    )
