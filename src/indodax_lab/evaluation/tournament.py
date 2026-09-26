"""Wave 1 tournament checkpoint and multi-candidate evaluation (QA-01).

Contract: tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

Guarantees:
1. QA-01-AC0: Tiny tournament evaluates candidate portfolio deterministically on common snapshot.
2. QA-01-AC1: Fixture produces and verifies all four lifecycle outcomes: INVALID_RUN, HARD_FAIL, NEAR_MISS, PASS.
3. QA-01-AC2: Follow-up actions map correctly to evaluation outcomes per JOB-03 repeat policy.
4. QA-01-AC3: Tournament report contains strict disclaimer and rejects real-market profitability claims.
5. Fail-closed classification: unestimable or impossible candidate metrics classify
   ``INVALID_RUN`` (retryable) instead of falling through to ``PASS`` -> ``ADVANCE_TO_SHADOW``.
6. Identical-cost and non-empty portfolio guards enforce the QA-01-AC0 comparison contract.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.evaluation.gates import EvaluationOutcome


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LiveProfitabilityClaimForbiddenError(ValueError):
    """Raised when an attempt is made to claim live market profitability from CI tournament tests."""


class TournamentPortfolioInvalidError(ValueError):
    """Raised when a tournament portfolio violates the identical-cost / non-empty contract."""


# ---------------------------------------------------------------------------
# Classification thresholds (QA-01-AC1)
# ---------------------------------------------------------------------------

_HARD_FAIL_SHARPE = 0.0
_HARD_FAIL_MAX_DRAWDOWN = 0.30
_NEAR_MISS_SHARPE = 1.0
_NEAR_MISS_MAX_DRAWDOWN = 0.10


def _metric_defect(candidate: TournamentCandidate) -> str | None:
    """Return a machine-readable fail-closed defect token, or ``None`` when metrics are usable.

    ``None`` is *not* a safe classifier default: comparing NaN against a threshold is always
    ``False`` in Python, so a NaN metric silently satisfies every ``<``/``>`` check and would
    otherwise reach the ``PASS`` branch that maps to ``ADVANCE_TO_SHADOW``.
    """
    if not math.isfinite(candidate.sharpe):
        return "NON_FINITE_SHARPE"
    if not math.isfinite(candidate.max_drawdown):
        return "NON_FINITE_MAX_DRAWDOWN"
    if candidate.max_drawdown < 0.0:
        return "NEGATIVE_MAX_DRAWDOWN"
    if not math.isfinite(candidate.cost_basis):
        return "NON_FINITE_COST_BASIS"
    if candidate.cost_basis < 0.0:
        return "NEGATIVE_COST_BASIS"
    return None


def _validate_portfolio(candidates: list[TournamentCandidate]) -> None:
    """Enforce the QA-01-AC0 "identical snapshot/folds/costs" comparison contract."""
    if not candidates:
        raise TournamentPortfolioInvalidError(
            "EMPTY_TOURNAMENT_PORTFOLIO: Wave 1 tournament requires at least one candidate; "
            "a zero-candidate report must not satisfy a wave checkpoint."
        )
    cost_bases = {candidate.cost_basis for candidate in candidates}
    if len(cost_bases) > 1:
        raise TournamentPortfolioInvalidError(
            "COST_BASIS_NOT_IDENTICAL: tournament candidates must share one cost basis "
            f"(QA-01-AC0); got {sorted(cost_bases)}."
        )


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class TournamentCandidate(BaseModel):
    """A model or rule-based strategy candidate evaluated in the tournament."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    candidate_type: str  # "strategy" or "model"
    sharpe: float
    max_drawdown: float
    cost_basis: float = 0.004
    is_valid_run: bool = True
    outcome: EvaluationOutcome | None = None
    exclusion_reason: str | None = None


class TournamentFollowUp(BaseModel):
    """Actionable next step for a candidate resulting from tournament evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    outcome: EvaluationOutcome
    action: str
    allowed_to_retry: bool


class TournamentReport(BaseModel):
    """Comprehensive tournament evaluation summary and governance disclaimer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str
    candidates_evaluated: int
    results: list[TournamentCandidate]
    follow_ups: list[TournamentFollowUp]
    disclaimer: str = (
        "TINY_CI_DOES_NOT_CONSTITUTE_REAL_MARKET_PROFITABILITY_EVIDENCE: "
        "Results are generated from synthetic offline tournament fixtures "
        "and must not be used as evidence of live market profitability (QA-01-AC3)."
    )
    is_real_market_evidence: bool = False
    evaluated_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Tournament Runner
# ---------------------------------------------------------------------------


def run_wave1_tournament(
    candidates: list[TournamentCandidate],
    snapshot_id: str,
    claim_live_profitability: bool = False,
    evaluated_at_utc: datetime | None = None,
) -> TournamentReport:
    """Execute a deterministic offline tournament across multiple candidates.

    Args:
        candidates: List of ``TournamentCandidate`` items to evaluate.
        snapshot_id: Identifier of the immutable data snapshot used for evaluation.
        claim_live_profitability: If True, raises ``LiveProfitabilityClaimForbiddenError`` (QA-01-AC3).

    Returns:
        A ``TournamentReport`` with outcomes and follow-ups.

    Raises:
        LiveProfitabilityClaimForbiddenError: If ``claim_live_profitability`` is True (QA-01-AC3).
        TournamentPortfolioInvalidError: If the portfolio is empty or mixes cost bases (QA-01-AC0).
    """
    # AC3: Forbid claims of real-market profitability
    if claim_live_profitability:
        raise LiveProfitabilityClaimForbiddenError(
            "LIVE_PROFITABILITY_CLAIM_FORBIDDEN: Tiny CI offline tournament results "
            "cannot be claimed as evidence of live market profitability (QA-01-AC3)."
        )

    # AC0: identical cost basis, and a tournament must actually evaluate something
    _validate_portfolio(candidates)

    evaluated_candidates: list[TournamentCandidate] = []
    follow_ups: list[TournamentFollowUp] = []

    for c in candidates:
        # AC1: Classify lifecycle outcome (fail closed on unestimable metrics)
        if not c.is_valid_run:
            outcome = EvaluationOutcome.INVALID_RUN
            exclusion_reason: str | None = "RUN_NOT_VALID"
        elif (exclusion_reason := _metric_defect(c)) is not None:
            outcome = EvaluationOutcome.INVALID_RUN
        elif c.sharpe < _HARD_FAIL_SHARPE or c.max_drawdown > _HARD_FAIL_MAX_DRAWDOWN:
            outcome = EvaluationOutcome.HARD_FAIL
        elif c.sharpe < _NEAR_MISS_SHARPE or c.max_drawdown > _NEAR_MISS_MAX_DRAWDOWN:
            outcome = EvaluationOutcome.NEAR_MISS
        else:
            outcome = EvaluationOutcome.PASS

        evaluated_c = TournamentCandidate(
            candidate_id=c.candidate_id,
            candidate_type=c.candidate_type,
            sharpe=c.sharpe,
            max_drawdown=c.max_drawdown,
            cost_basis=c.cost_basis,
            is_valid_run=c.is_valid_run,
            outcome=outcome,
            exclusion_reason=exclusion_reason,
        )
        evaluated_candidates.append(evaluated_c)

        # AC2: Map follow-up action according to JOB-03 policy
        if outcome == EvaluationOutcome.PASS:
            action = "ADVANCE_TO_SHADOW"
            allowed_to_retry = False
        elif outcome == EvaluationOutcome.HARD_FAIL:
            action = "BLOCK_RETRIES"
            allowed_to_retry = False
        elif outcome == EvaluationOutcome.NEAR_MISS:
            action = "REQUIRE_NEW_VERSION"
            allowed_to_retry = True
        else:  # INVALID_RUN
            action = "RETRY_WITH_BACKOFF"
            allowed_to_retry = True

        follow_ups.append(
            TournamentFollowUp(
                candidate_id=c.candidate_id,
                outcome=outcome,
                action=action,
                allowed_to_retry=allowed_to_retry,
            )
        )

    kwargs = {"evaluated_at_utc": evaluated_at_utc} if evaluated_at_utc is not None else {}
    return TournamentReport(
        snapshot_id=snapshot_id,
        candidates_evaluated=len(evaluated_candidates),
        results=evaluated_candidates,
        follow_ups=follow_ups,
        is_real_market_evidence=False,
        **kwargs,
    )
