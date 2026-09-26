"""Tests for SHADOW-01: Auditable forward paper decisions.

RED tests written before implementation.

Contract: frozen candidate + live available features -> immutable prediction/decision with paper intent only.

AC boundaries:
- AC0: Forward forecast and risk decision stored before outcome; no callback selection bias.
- AC1: Telegram failure does NOT delete/void the decision (decision is persisted first).
- AC2: Stale data or model hash mismatch rejects entry fail-closed.
- AC3: Manual intent is not treated as ground truth (paper-only intent flag preserved).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.paper.contracts import (
    ForwardDecision,
    ForwardDecisionStatus,
    ManualIntentRecord,
    ModelMismatchError,
    PaperDecisionStore,
    StaleDataError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_decision(
    decision_id: str = "dec_001",
    candidate_id: str = "cand_001",
    bundle_hash: str = "abc123",
    snapshot_id: str = "snap_20260901",
    feature_snapshot_age_seconds: float = 30.0,
    max_staleness_seconds: float = 300.0,
    probability: float = 0.72,
    action: str = "ENTER",
    is_manual_intent: bool = False,
) -> ForwardDecision:
    """Build a minimal ForwardDecision fixture."""
    return ForwardDecision(
        decision_id=decision_id,
        candidate_id=candidate_id,
        bundle_hash=bundle_hash,
        snapshot_id=snapshot_id,
        feature_snapshot_age_seconds=feature_snapshot_age_seconds,
        max_staleness_seconds=max_staleness_seconds,
        probability=probability,
        action=action,
        is_manual_intent=is_manual_intent,
        decided_at_utc=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# AC0: Forward decision stored before outcome; immutable; no callback selection bias
# ---------------------------------------------------------------------------

def test_shadow_01_valid_contract():
    """SHADOW-01-AC0: ForwardDecision stored in PaperDecisionStore before outcome is known."""
    decision = _make_decision()
    store = PaperDecisionStore()

    record = store.record_decision(decision)

    assert record.status == ForwardDecisionStatus.PENDING, (
        "Freshly recorded decision must be PENDING (outcome not yet known)"
    )
    assert record.decision_id == decision.decision_id
    assert record.decided_at_utc is not None

    # Decision is retrievable by ID (immutable)
    retrieved = store.get_decision(decision.decision_id)
    assert retrieved is not None
    assert retrieved.decision_id == decision.decision_id
    assert retrieved.status == ForwardDecisionStatus.PENDING


# ---------------------------------------------------------------------------
# AC1: Telegram failure does NOT delete/void the decision
# ---------------------------------------------------------------------------

def test_shadow_01_contract_1():
    """SHADOW-01-AC1: If Telegram notification fails, the stored decision is preserved."""
    decision = _make_decision(decision_id="dec_telegram_fail")
    store = PaperDecisionStore()

    # Record decision first
    store.record_decision(decision)

    # Simulate Telegram notification failure
    telegram_error = RuntimeError("TELEGRAM_SEND_FAILED: connection timeout")
    store.notify_telegram(
        decision_id=decision.decision_id,
        telegram_error=telegram_error,
    )

    # Decision must still be present and PENDING — not deleted or voided
    retrieved = store.get_decision(decision.decision_id)
    assert retrieved is not None, "Decision must survive Telegram failure"
    assert retrieved.status == ForwardDecisionStatus.PENDING, (
        "Decision status must not change to VOIDED/FAILED due to Telegram error"
    )
    assert retrieved.telegram_notified is False, (
        "telegram_notified should be False when notification failed"
    )


# ---------------------------------------------------------------------------
# AC2: Stale data or model hash mismatch rejects entry
# ---------------------------------------------------------------------------

def test_shadow_01_contract_2():
    """SHADOW-01-AC2: Stale feature snapshot rejects entry; model hash mismatch rejects entry."""
    store = PaperDecisionStore()

    # Sub-case A: Feature data too stale (age > max_staleness)
    stale_decision = _make_decision(
        decision_id="dec_stale",
        feature_snapshot_age_seconds=400.0,  # exceeds max_staleness_seconds=300
        max_staleness_seconds=300.0,
    )
    with pytest.raises(StaleDataError):
        store.record_decision(stale_decision)

    # Sub-case B: Model bundle hash mismatch
    # Decision declares bundle_hash="abc123" but store is configured with "expected_xyz"
    mismatched_decision = _make_decision(
        decision_id="dec_mismatch",
        bundle_hash="WRONG_HASH",
    )
    with pytest.raises(ModelMismatchError):
        store.record_decision(
            mismatched_decision,
            expected_bundle_hash="abc123",
        )


# ---------------------------------------------------------------------------
# AC3: Manual intent is not treated as ground truth (paper intent only)
# ---------------------------------------------------------------------------

def test_shadow_01_contract_3():
    """SHADOW-01-AC3: Manual intent decisions are stored as paper-only intent, not ground truth."""
    # Manual intent decision (human override)
    manual_decision = _make_decision(
        decision_id="dec_manual",
        is_manual_intent=True,
        action="ENTER",
    )
    store = PaperDecisionStore()
    record = store.record_decision(manual_decision)

    # Must be stored, but flagged as manual intent (not auto)
    assert record.is_manual_intent is True, "Manual intent flag must be preserved"
    assert record.status == ForwardDecisionStatus.PENDING

    # Retrieving and checking that manual intent cannot be promoted to ground truth
    retrieved = store.get_decision(manual_decision.decision_id)
    assert retrieved.is_manual_intent is True

    # Cannot mark manual intent as authoritative ground truth
    with pytest.raises(ValueError, match="MANUAL_INTENT_NOT_GROUND_TRUTH"):
        store.mark_as_ground_truth(manual_decision.decision_id)


# ---------------------------------------------------------------------------
# Edge case: Same decision_id cannot be recorded twice (idempotency guard)
# ---------------------------------------------------------------------------

def test_shadow_01_idempotent_guard():
    """Edge case: Recording the same decision_id twice raises an error (no duplicate entries)."""
    decision = _make_decision(decision_id="dec_dup")
    store = PaperDecisionStore()
    store.record_decision(decision)

    with pytest.raises(ValueError, match="DUPLICATE_DECISION_ID"):
        store.record_decision(decision)


def test_shadow_01_hash_wired_to_bundle_registry():
    """Registry hash wiring rejects mismatched bundle without explicit expected hash."""
    store = PaperDecisionStore(bundle_registry={"cand_001": "abc123"})
    ok_record = store.record_decision(_make_decision(decision_id="dec_ok"))
    assert ok_record.status == ForwardDecisionStatus.PENDING
    with pytest.raises(ModelMismatchError):
        store.record_decision(_make_decision(decision_id="dec_bad", bundle_hash="WRONG_HASH"))


def test_shadow_01_persisted_recovery(tmp_path):
    """Decisions survive process restart via SQLite snapshot with duplicate guard intact."""
    store = PaperDecisionStore(bundle_registry={"cand_001": "abc123"})
    store.record_decision(_make_decision(decision_id="dec_persist"))
    db_path = tmp_path / "decisions.sqlite3"
    store.save_snapshot(db_path)

    restored = PaperDecisionStore.load_snapshot(db_path, bundle_registry={"cand_001": "abc123"})
    retrieved = restored.get_decision("dec_persist")
    assert retrieved is not None
    assert retrieved.status == ForwardDecisionStatus.PENDING
    assert retrieved.bundle_hash == "abc123"
    with pytest.raises(ValueError, match="DUPLICATE_DECISION_ID"):
        restored.record_decision(_make_decision(decision_id="dec_persist"))


def test_shadow_01_corrupt_snapshot_fails_closed(tmp_path):
    """Tampered persistence fails closed instead of loading silently."""
    import sqlite3

    store = PaperDecisionStore()
    store.record_decision(_make_decision(decision_id="dec_tamper"))
    db_path = tmp_path / "decisions.sqlite3"
    store.save_snapshot(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE forward_decisions SET record_json = '{}' WHERE decision_id = 'dec_tamper'")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ValueError, match="CORRUPT"):
        PaperDecisionStore.load_snapshot(db_path)
