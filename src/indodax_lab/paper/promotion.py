"""Champion replacement gate and promotion registry (SHADOW-03).

Contract: sealed pass + >=90 days AND >=100 pooled closed forward trades + no policy breach -> versioned promotion.

Guarantees:
1. SHADOW-03-AC0: Challenger with sealed pass, >=90 days, and >=100 trades replaces champion.
2. SHADOW-03-AC1: >=100 trades in <90 days fails duration gate (InsufficientForwardDurationError).
3. SHADOW-03-AC2: >=90 days with <100 trades fails trade count gate (InsufficientForwardTradesError).
4. SHADOW-03-AC3: Challenger training/evaluation activities do not modify the active champion pointer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InsufficientForwardDurationError(ValueError):
    """Raised when candidate has insufficient forward evaluation days (minimum 90)."""


class InsufficientForwardTradesError(ValueError):
    """Raised when candidate has insufficient closed forward trades (minimum 100)."""


class UnsealedCandidatePromotionError(ValueError):
    """Raised when a candidate has not passed the sealed evaluation phase."""


class PolicyBreachPromotionError(ValueError):
    """Raised when a candidate has an unexcused risk policy breach in forward evaluation."""


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class ChallengerEvidence(BaseModel):
    """Audited evidence package for a challenger candidate requesting champion replacement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    candidate_version: str
    is_sealed_pass: bool
    forward_days: int
    closed_trades_count: int
    has_policy_breach: bool = False
    outperformance: bool = True


class PromotionDecision(BaseModel):
    """Audit record capturing the promotion verdict and resulting champion pointer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    promoted: bool
    reason: str
    champion_id: str
    champion_version: str
    promoted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# ChampionRegistry
# ---------------------------------------------------------------------------


class ChampionRegistry:
    """Authority managing champion pointer and enforcing the 90-day/100-trade gate."""

    def __init__(
        self,
        initial_champion_id: str,
        initial_champion_version: str,
        min_forward_days: int = 90,
        min_closed_trades: int = 100,
    ) -> None:
        self.active_champion_id: str = initial_champion_id
        self.active_champion_version: str = initial_champion_version
        self.min_forward_days: int = min_forward_days
        self.min_closed_trades: int = min_closed_trades
        self._challenger_activity_log: list[dict[str, Any]] = []

    def record_challenger_activity(self, candidate_id: str, action: str) -> None:
        """Record training or evaluation of a challenger without altering champion (SHADOW-03-AC3)."""
        self._challenger_activity_log.append(
            {
                "candidate_id": candidate_id,
                "action": action,
                "logged_at_utc": datetime.now(UTC),
            }
        )
        # Active champion pointer is strictly untouched

    def evaluate_promotion(self, challenger: ChallengerEvidence) -> PromotionDecision:
        """Evaluate a challenger against the champion replacement gate (SHADOW-03-AC0..AC3).

        Args:
            challenger: The ``ChallengerEvidence`` package.

        Returns:
            A ``PromotionDecision`` reflecting the atomic pointer update.

        Raises:
            UnsealedCandidatePromotionError: If candidate is not a sealed pass.
            InsufficientForwardDurationError: If forward evaluation duration < 90 days (AC1).
            InsufficientForwardTradesError: If closed forward trades count < 100 (AC2).
            PolicyBreachPromotionError: If candidate incurred any policy breach.
        """
        # Sealed pass gate
        if not challenger.is_sealed_pass:
            raise UnsealedCandidatePromotionError(
                f"UNSEALED_PROMOTION_FORBIDDEN: Candidate '{challenger.candidate_id}' "
                "has not passed the sealed test evaluation phase."
            )

        # AC1: 90-day duration gate
        if challenger.forward_days < self.min_forward_days:
            raise InsufficientForwardDurationError(
                f"INSUFFICIENT_FORWARD_DURATION: Candidate '{challenger.candidate_id}' "
                f"has {challenger.forward_days} forward days, but minimum {self.min_forward_days} "
                "days are required. Rapid trade generation does not satisfy this requirement (SHADOW-03-AC1)."
            )

        # AC2: 100 closed trades gate
        if challenger.closed_trades_count < self.min_closed_trades:
            raise InsufficientForwardTradesError(
                f"INSUFFICIENT_FORWARD_TRADES: Candidate '{challenger.candidate_id}' "
                f"has {challenger.closed_trades_count} closed trades, but minimum {self.min_closed_trades} "
                "trades are required. Long duration without sample size does not satisfy this requirement (SHADOW-03-AC2)."
            )

        # Policy breach gate
        if challenger.has_policy_breach:
            raise PolicyBreachPromotionError(
                f"POLICY_BREACH_FORBIDDEN: Candidate '{challenger.candidate_id}' "
                "incurred a policy breach during forward evaluation."
            )

        # AC0: All gates satisfied -> atomic champion pointer swap
        self.active_champion_id = challenger.candidate_id
        self.active_champion_version = challenger.candidate_version

        return PromotionDecision(
            promoted=True,
            reason=(
                f"CHAMPION_REPLACED: Challenger '{challenger.candidate_id}' v{challenger.candidate_version} "
                f"satisfied sealed pass, {challenger.forward_days} forward days (>={self.min_forward_days}), "
                f"and {challenger.closed_trades_count} closed trades (>={self.min_closed_trades})."
            ),
            champion_id=self.active_champion_id,
            champion_version=self.active_champion_version,
        )
