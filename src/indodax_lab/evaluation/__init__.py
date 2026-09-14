"""Evaluation and experiment lifecycle package (EVAL-01, EVAL-02, EVAL-03)."""

from indodax_lab.evaluation.gates import (
    EvaluationOutcome,
    EvaluationPolicy,
    EvaluationResult,
    MultiSeedEvaluationResult,
    evaluate_multi_seed_runs,
    evaluate_run,
)
from indodax_lab.evaluation.lifecycle import (
    CandidateFrozenError,
    CandidateLifecycleManager,
    CandidateNotFoundError,
    CandidateRecord,
    CandidateStage,
    ExposureAuditRecord,
    GateAlreadyOpenedError,
    InvalidTransitionError,
    LeaderboardEntry,
    TransitionRecord,
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
from indodax_lab.evaluation.tournament import (
    LiveProfitabilityClaimForbiddenError,
    TournamentCandidate,
    TournamentFollowUp,
    TournamentReport,
    run_wave1_tournament,
)

__all__ = [
    "CandidateFrozenError",
    "CandidateLifecycleManager",
    "CandidateNotFoundError",
    "CandidateRecord",
    "CandidateStage",
    "EvaluationOutcome",
    "EvaluationPolicy",
    "EvaluationResult",
    "ExperimentRegistry",
    "ExperimentRunRecord",
    "ExperimentRunStatus",
    "ExposureAuditRecord",
    "GateAlreadyOpenedError",
    "InvalidTransitionError",
    "LeaderboardEntry",
    "MultiSeedEvaluationResult",
    "TransitionRecord",
    "compute_deflated_sharpe_ratio",
    "compute_pbo",
    "evaluate_multi_seed_runs",
    "evaluate_run",
    # QA-01 Tournament
    "LiveProfitabilityClaimForbiddenError",
    "TournamentCandidate",
    "TournamentFollowUp",
    "TournamentReport",
    "run_wave1_tournament",
]
