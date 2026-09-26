"""Regression tests for SHADOW-03 review findings (ops-shadow batch).

Findings covered (spec: docs/specs/14-shadow-portfolios-and-promotion.md):

- S03-F1 (Critical): the "sufficient quality" gate is unenforced *and* fails open.
  ``ChallengerEvidence.outperformance`` defaulted to ``True`` and
  ``ChampionRegistry.evaluate_promotion`` never read it, so a challenger that
  demonstrably does NOT outperform the champion was still promoted.
- S03-F2 (Critical): promotion required no explicit recorded human approval. The
  champion pointer was swapped purely from an in-memory evidence object, so any
  caller holding a hand-built object could replace the live champion.
- S03-F3 (Critical): the evidence carried no provenance fingerprint or evaluation
  timestamp, so a forged or stale evaluation record could drive a promotion.
- S03-F4 (Important): ``PromotionDecision`` stored no previous champion, so a
  promotion was irreversible. Spec 14 requires "Promotion stores previous/current
  bundle IDs and can roll back only to compatible verified model/schema".

Isolation: every test is in-memory only. No filesystem, no network, no real
ledger, no live credentials, no real orders.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from indodax_lab.paper.promotion import (
    ChallengerEvidence,
    ChampionRegistry,
    InsufficientQualityPromotionError,
    MissingPromotionApprovalError,
    NoPromotedChampionError,
    PromotionApproval,
    SelfApprovedPromotionError,
    StalePromotionEvidenceError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _registry() -> ChampionRegistry:
    return ChampionRegistry(
        initial_champion_id="champion_m01",
        initial_champion_version="1.0.0",
    )


def _qualifying_evidence(
    candidate_id: str = "challenger_m02",
    *,
    outperformance: bool = True,
    evaluated_at_utc: datetime | None = None,
) -> ChallengerEvidence:
    """Evidence satisfying the day/trade/sealed gates plus the quality verdict."""
    return ChallengerEvidence(
        candidate_id=candidate_id,
        candidate_version="2.0.0",
        evidence_id=f"eval-{candidate_id}",
        evaluated_at_utc=evaluated_at_utc or datetime.now(UTC),
        is_sealed_pass=True,
        forward_days=95,
        closed_trades_count=120,
        has_policy_breach=False,
        outperformance=outperformance,
    )


def _approval_for(evidence: ChallengerEvidence, approver_id: str = "reviewer_ops") -> PromotionApproval:
    return PromotionApproval(
        approver_id=approver_id,
        approved_at_utc=datetime.now(UTC),
        evidence_id=evidence.evidence_id,
        evidence_digest=evidence.evidence_digest(),
        reason="Reviewed sealed pass, forward window, trade count and cost schedule.",
    )


# ---------------------------------------------------------------------------
# S03-F1: the quality gate must be enforced and must fail closed
# ---------------------------------------------------------------------------


def test_shadow_03_underperforming_challenger_is_not_promoted() -> None:
    """S03-F1: a challenger that does not outperform must never become champion."""
    registry = _registry()
    evidence = _qualifying_evidence(outperformance=False)
    approval = _approval_for(evidence)

    with pytest.raises(InsufficientQualityPromotionError):
        registry.evaluate_promotion(evidence, approval)

    assert registry.active_champion_id == "champion_m01", (
        "An underperforming challenger must not replace the champion"
    )
    assert registry.active_champion_version == "1.0.0"


def test_shadow_03_evidence_without_quality_verdict_cannot_be_constructed() -> None:
    """S03-F1: the quality verdict has no default, so it cannot fail open."""
    payload = _qualifying_evidence().model_dump()
    del payload["outperformance"]

    with pytest.raises(Exception) as excinfo:
        ChallengerEvidence(**payload)

    assert "outperformance" in str(excinfo.value)


# ---------------------------------------------------------------------------
# S03-F2: an explicit, recorded human approval is mandatory
# ---------------------------------------------------------------------------


def test_shadow_03_promotion_requires_explicit_human_approval() -> None:
    """S03-F2: passing the numeric gates alone must not swap the champion pointer."""
    registry = _registry()
    evidence = _qualifying_evidence()

    with pytest.raises(MissingPromotionApprovalError):
        registry.evaluate_promotion(evidence)

    assert registry.active_champion_id == "champion_m01", (
        "Champion replacement must require an explicit, recorded human approval"
    )


def test_shadow_03_challenger_owner_cannot_approve_own_promotion() -> None:
    """S03-F2: the proposer is not the final approver."""
    registry = _registry()
    evidence = _qualifying_evidence(candidate_id="challenger_m02")
    approval = _approval_for(evidence, approver_id="challenger_m02")

    with pytest.raises(SelfApprovedPromotionError):
        registry.evaluate_promotion(evidence, approval)

    assert registry.active_champion_id == "champion_m01"


def test_shadow_03_approved_promotion_still_succeeds() -> None:
    """Positive control: a fully approved, fully evidenced promotion goes through."""
    registry = _registry()
    evidence = _qualifying_evidence()
    approval = _approval_for(evidence)

    decision = registry.evaluate_promotion(evidence, approval)

    assert decision.promoted is True
    assert registry.active_champion_id == "challenger_m02"
    assert registry.active_champion_version == "2.0.0"


# ---------------------------------------------------------------------------
# S03-F3: forged / stale evidence must be refused
# ---------------------------------------------------------------------------


def test_shadow_03_stale_evaluation_record_is_refused() -> None:
    """S03-F3: a long-expired evaluation record must not drive a promotion."""
    registry = _registry()
    evidence = _qualifying_evidence(
        evaluated_at_utc=datetime.now(UTC) - timedelta(days=400),
    )
    approval = _approval_for(evidence)

    with pytest.raises(StalePromotionEvidenceError):
        registry.evaluate_promotion(evidence, approval)

    assert registry.active_champion_id == "champion_m01"


def test_shadow_03_approval_for_different_evidence_is_refused() -> None:
    """S03-F3: an approval signed for another evidence digest must not be reusable."""
    registry = _registry()
    evidence = _qualifying_evidence()
    other = _qualifying_evidence(candidate_id="challenger_m03")
    approval = _approval_for(other)

    with pytest.raises(StalePromotionEvidenceError):
        registry.evaluate_promotion(evidence, approval)

    assert registry.active_champion_id == "champion_m01"


def test_shadow_03_evidence_digest_changes_with_content() -> None:
    """S03-F3: the fingerprint must actually bind the evaluated content."""
    base = _qualifying_evidence()
    tampered = base.model_copy(update={"closed_trades_count": 500})

    assert tampered.evidence_digest() != base.evidence_digest()


# ---------------------------------------------------------------------------
# S03-F4: the previous champion must be recorded so promotion is reversible
# ---------------------------------------------------------------------------


def test_shadow_03_promotion_records_previous_champion() -> None:
    """S03-F4: the decision must carry the previous champion identity."""
    registry = _registry()
    evidence = _qualifying_evidence()
    decision = registry.evaluate_promotion(evidence, _approval_for(evidence))

    assert decision.previous_champion_id == "champion_m01"
    assert decision.previous_champion_version == "1.0.0"
    assert decision.approved_by == "reviewer_ops"


def test_shadow_03_promotion_can_be_rolled_back() -> None:
    """S03-F4: a recorded promotion can be reverted to the compatible prior bundle."""
    registry = _registry()
    evidence = _qualifying_evidence()
    registry.evaluate_promotion(evidence, _approval_for(evidence))
    assert registry.active_champion_id == "challenger_m02"

    rolled_back = registry.rollback_last_promotion()

    assert rolled_back.champion_id == "challenger_m02"
    assert registry.active_champion_id == "champion_m01"
    assert registry.active_champion_version == "1.0.0"


def test_shadow_03_rollback_without_promotion_fails_closed() -> None:
    """S03-F4: a rollback with nothing recorded is refused, not a silent no-op."""
    registry = _registry()

    with pytest.raises(NoPromotedChampionError):
        registry.rollback_last_promotion()
