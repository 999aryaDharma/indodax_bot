"""Evaluation and experiment lifecycle package (EVAL-01, EVAL-02)."""

from indodax_lab.evaluation.gates import (
    EvaluationOutcome,
    EvaluationPolicy,
    EvaluationResult,
    MultiSeedEvaluationResult,
    evaluate_multi_seed_runs,
    evaluate_run,
)
from indodax_lab.evaluation.registry import (
    ExperimentRegistry,
    ExperimentRunRecord,
    ExperimentRunStatus,
)
from indodax_lab.evaluation.statistics import (
    compute_deflated_sharpe_ratio,
    compute_pbo,
)

__all__ = [
    "ExperimentRegistry",
    "ExperimentRunRecord",
    "ExperimentRunStatus",
    "EvaluationOutcome",
    "EvaluationPolicy",
    "EvaluationResult",
    "MultiSeedEvaluationResult",
    "evaluate_run",
    "evaluate_multi_seed_runs",
    "compute_deflated_sharpe_ratio",
    "compute_pbo",
]
