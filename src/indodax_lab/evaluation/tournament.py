"""Wave 1 tournament checkpoint and multi-candidate evaluation (QA-01).

Contract: tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.

Guarantees:
1. QA-01-AC0: Tiny tournament evaluates candidate portfolio deterministically on common snapshot.
2. QA-01-AC1: Fixture produces and verifies all four lifecycle outcomes: INVALID_RUN, HARD_FAIL, NEAR_MISS, PASS.
3. QA-01-AC2: Follow-up actions map correctly to evaluation outcomes per JOB-03 repeat policy.
4. QA-01-AC3: Tournament report contains strict disclaimer and rejects real-market profitability claims.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.evaluation.gates import EvaluationOutcome


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LiveProfitabilityClaimForbiddenError(ValueError):
    """Raised when an attempt is made to claim live market profitability from CI tournament tests."""


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
    """
    # AC3: Forbid claims of real-market profitability
    if claim_live_profitability:
        raise LiveProfitabilityClaimForbiddenError(
            "LIVE_PROFITABILITY_CLAIM_FORBIDDEN: Tiny CI offline tournament results "
            "cannot be claimed as evidence of live market profitability (QA-01-AC3)."
        )

    evaluated_candidates: list[TournamentCandidate] = []
    follow_ups: list[TournamentFollowUp] = []

    for c in candidates:
        # AC1: Classify lifecycle outcome
        if not c.is_valid_run:
            outcome = EvaluationOutcome.INVALID_RUN
        elif c.sharpe < 0.0 or c.max_drawdown > 0.30:
            outcome = EvaluationOutcome.HARD_FAIL
        elif c.sharpe < 1.0 or c.max_drawdown > 0.10:
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
