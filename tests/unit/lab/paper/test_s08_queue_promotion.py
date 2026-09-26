from datetime import UTC, datetime

import pytest

from indodax_lab.models.lob.queue_evidence import QueueEvidencePolicy, QueueQualificationReport
from indodax_lab.paper.promotion import (
    ChallengerEvidence,
    ChampionRegistry,
    PromotionApproval,
    QueueEvidencePromotionError,
)

NOW = datetime.now(UTC)


def _queue_report(**updates: object) -> QueueQualificationReport:
    values: dict[str, object] = {
        "report_id": "run-1",
        "candidate_id": "s08",
        "candidate_version": "1.0.0",
        "policy": QueueEvidencePolicy(
            policy_id="queue-age",
            version="1",
            approved_by="test-operator",
            approval_ref="TEST-QUEUE-APPROVAL",
            source_id="lob-feed",
            source_version="lob-v1",
            max_evidence_age_seconds=5,
        ),
        "report_sha256": "b" * 64,
        "sample_count": 120,
        "unavailable_count": 0,
        "stale_count": 0,
        "future_count": 0,
        "sequence_invalid_count": 0,
        "max_observed_age_seconds": "4.5",
    }
    values.update(updates)
    return QueueQualificationReport.model_validate(values)


def _evidence(**updates: object) -> ChallengerEvidence:
    values: dict[str, object] = {
        "candidate_id": "s08",
        "candidate_version": "1.0.0",
        "evidence_id": "eval-1",
        "evaluated_at_utc": NOW,
        "is_sealed_pass": True,
        "forward_days": 100,
        "closed_trades_count": 120,
        "has_policy_breach": False,
        "outperformance": True,
        "execution_contract": "lob_queue_v1",
    }
    values.update(updates)
    return ChallengerEvidence.model_validate(values)


def _approval(evidence: ChallengerEvidence) -> PromotionApproval:
    return PromotionApproval(
        approver_id="reviewer",
        approved_at_utc=NOW,
        evidence_id=evidence.evidence_id,
        evidence_digest=evidence.evidence_digest(),
        reason="test",
    )


@pytest.mark.parametrize(
    ("report", "reason"),
    [
        (None, "QUEUE_QUALIFICATION_MISSING"),
        (_queue_report(unavailable_count=1), "QUEUE_EVIDENCE_INCOMPLETE"),
        (_queue_report(stale_count=1), "QUEUE_EVIDENCE_INCOMPLETE"),
        (_queue_report(future_count=1), "QUEUE_EVIDENCE_INCOMPLETE"),
        (_queue_report(sequence_invalid_count=1), "QUEUE_SEQUENCE_INVALID"),
        (_queue_report(max_observed_age_seconds="6"), "QUEUE_EVIDENCE_STALE"),
        (_queue_report(candidate_id="other"), "QUEUE_CANDIDATE_MISMATCH"),
    ],
)
def test_s08_promotion_rejects_missing_or_invalid_queue_report(report, reason: str) -> None:
    evidence = _evidence(queue_qualification=report)
    registry = ChampionRegistry("baseline", "1")

    with pytest.raises(QueueEvidencePromotionError, match=reason):
        registry.evaluate_promotion(evidence, _approval(evidence))

    assert registry.active_champion_id == "baseline"


def test_s08_promotion_accepts_approved_complete_queue_report() -> None:
    evidence = _evidence(queue_qualification=_queue_report())
    registry = ChampionRegistry("baseline", "1")

    result = registry.evaluate_promotion(evidence, _approval(evidence))

    assert result.promoted is True
    assert registry.active_champion_id == "s08"


def test_s08_queue_report_is_bound_to_promotion_digest() -> None:
    evidence = _evidence(queue_qualification=_queue_report())
    approval = _approval(evidence)
    changed = evidence.model_copy(
        update={"queue_qualification": _queue_report(report_sha256="c" * 64)}
    )

    with pytest.raises(ValueError, match="PROMOTION_APPROVAL_EVIDENCE_MISMATCH"):
        ChampionRegistry("baseline", "1").evaluate_promotion(changed, approval)


def test_s08_queue_qualification_report_rejects_blank_identity() -> None:
    with pytest.raises(ValueError):
        _queue_report(candidate_id="   ")
