from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from indodax_lab.models.lob.queue_evidence import (
    QueueEvidence,
    QueueEvidencePolicy,
    queue_evidence_failure_reason,
)

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _policy() -> QueueEvidencePolicy:
    # Explicit test policy; no operational queue-age default is approved.
    return QueueEvidencePolicy(
        policy_id="queue-test",
        version="test-v1",
        approved_by="test-operator",
        approval_ref="TEST-QUEUE-APPROVAL",
        source_id="fixture-lob",
        source_version="fixture-v1",
        max_evidence_age_seconds=5,
    )


def _evidence(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "pair": "ALT_IDR",
        "event_at": NOW - timedelta(seconds=2),
        "available_at": NOW - timedelta(seconds=1),
        "observed_at": NOW - timedelta(milliseconds=500),
        "session_id": "session-1",
        "sequence_contiguous": True,
        "book_imbalance_l5": "0.2",
        "depth_bid_10bps_idr": "250000",
        "depth_ask_10bps_idr": "200000",
        "spread_bps": "15",
        "queue_ahead_base_qty": "3.25",
        "status": "known",
        "source_id": "fixture-lob",
        "source_version": "fixture-v1",
        "source_sha256": "a" * 64,
    }
    values.update(updates)
    return values


def test_s08_valid_queue_evidence_preserves_typed_lineage_and_units() -> None:
    evidence = QueueEvidence.model_validate(_evidence())

    assert evidence.contract_id == "lob_queue_v1"
    assert evidence.pair == "alt_idr"
    assert evidence.queue_ahead_base_qty == Decimal("3.25")
    assert queue_evidence_failure_reason(evidence, _policy(), decision_time=NOW) is None


def test_s08_default_queue_freshness_is_five_seconds_fail_closed() -> None:
    policy = QueueEvidencePolicy(
        policy_id="research-queue-freshness",
        version="1.0.0",
        approved_by="project-owner",
        approval_ref="CR-S08",
        source_id="fixture-lob",
        source_version="fixture-v1",
    )
    assert policy.max_evidence_age_seconds == Decimal("5")
    fresh = QueueEvidence.model_validate(
        _evidence(
            event_at=NOW - timedelta(seconds=7),
            available_at=NOW - timedelta(seconds=6),
            observed_at=NOW - timedelta(seconds=5),
        )
    )
    stale = QueueEvidence.model_validate(
        _evidence(
            event_at=NOW - timedelta(seconds=7),
            available_at=NOW - timedelta(seconds=6),
            observed_at=NOW - timedelta(milliseconds=5001),
        )
    )

    assert queue_evidence_failure_reason(fresh, policy, decision_time=NOW) is None
    assert queue_evidence_failure_reason(stale, policy, decision_time=NOW) == "QUEUE_EVIDENCE_STALE"


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"status": "unknown", "queue_ahead_base_qty": None}, "QUEUE_UNAVAILABLE"),
        ({"sequence_contiguous": False}, "QUEUE_SEQUENCE_INVALID"),
        (
            {
                "event_at": NOW - timedelta(seconds=8),
                "available_at": NOW - timedelta(seconds=7),
                "observed_at": NOW - timedelta(seconds=6),
            },
            "QUEUE_EVIDENCE_STALE",
        ),
        (
            {"observed_at": NOW + timedelta(seconds=1)},
            "QUEUE_EVIDENCE_NOT_CAUSAL",
        ),
    ],
)
def test_s08_unknown_stale_future_or_broken_queue_blocks_qualification(
    updates: dict[str, object], expected: str
) -> None:
    evidence = QueueEvidence.model_validate(_evidence(**updates))

    assert queue_evidence_failure_reason(evidence, _policy(), decision_time=NOW) == expected


def test_s08_missing_policy_or_evidence_blocks_queue_qualification() -> None:
    evidence = QueueEvidence.model_validate(_evidence())

    assert (
        queue_evidence_failure_reason(evidence, None, decision_time=NOW)
        == "QUEUE_POLICY_MISSING"
    )
    assert queue_evidence_failure_reason(None, _policy(), decision_time=NOW) == "QUEUE_UNAVAILABLE"


def test_s08_queue_evidence_requires_matching_pair_source_and_causal_book_event() -> None:
    assert (
        queue_evidence_failure_reason(
            QueueEvidence.model_validate(_evidence()),
            _policy(),
            decision_time=NOW,
            expected_pair="other_idr",
        )
        == "QUEUE_PAIR_MISMATCH"
    )
    wrong_source = QueueEvidence.model_validate(_evidence(source_version="other"))
    assert (
        queue_evidence_failure_reason(wrong_source, _policy(), decision_time=NOW)
        == "QUEUE_SOURCE_MISMATCH"
    )
    future_event = QueueEvidence.model_validate(
        _evidence(
            event_at=NOW + timedelta(seconds=1),
            available_at=NOW + timedelta(seconds=2),
            observed_at=NOW + timedelta(seconds=3),
        )
    )
    assert (
        queue_evidence_failure_reason(future_event, _policy(), decision_time=NOW)
        == "QUEUE_EVIDENCE_NOT_CAUSAL"
    )


def test_s08_queue_policy_requires_explicit_approval_and_freshness_limit() -> None:
    policy = _policy().model_dump()
    policy["max_evidence_age_seconds"] = None

    with pytest.raises(ValidationError):
        QueueEvidencePolicy.model_validate(policy)


@pytest.mark.parametrize("field", ["approved_by", "approval_ref", "policy_id", "source_id"])
def test_s08_queue_policy_rejects_blank_identity_and_approval(field: str) -> None:
    policy = _policy().model_dump()
    policy[field] = "   "

    with pytest.raises(ValidationError):
        QueueEvidencePolicy.model_validate(policy)


@pytest.mark.parametrize("session_id", ["", "   "])
def test_s08_known_evidence_rejects_blank_session_identity(session_id: str) -> None:
    with pytest.raises(ValidationError):
        QueueEvidence.model_validate(_evidence(session_id=session_id))


def test_s08_known_queue_evidence_requires_complete_causal_fields() -> None:
    with pytest.raises(ValidationError):
        QueueEvidence.model_validate(_evidence(sequence_contiguous=None))

    with pytest.raises(ValidationError):
        QueueEvidence.model_validate(_evidence(queue_ahead_base_qty=None))
