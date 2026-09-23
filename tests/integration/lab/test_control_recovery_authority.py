"""Integration tests for recovery mode and durable operator risk governance (PM-03, FR-23).

Validates:
- AC0 (test_pm_03_0): All persisted modes restart into RECOVERY.
- AC1 (test_pm_03_1): Corrupt/missing risk state prevents active mode.
- AC2 (test_pm_03_2): Persistence failure leaves writes disabled.
- AC3 (test_pm_03_3): Reset with absent/stale evidence rejects.
- AC4 (test_pm_03_4): Reused or expired approval/reset token rejects.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.control.approval import (
    ManualApprovalStore,
    generate_approval_token,
)
from indodax_lab.control.mode import (
    CorruptModeJournalError,
    DurableModeStore,
    ExecutionMode,
    RecoveryReport,
    RecoveryService,
)
from indodax_lab.execution.oms import OmsOrder, OmsOrderState
from indodax_lab.risk.engine import HealthEvidence, RiskEngine

_T0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
_SECRET = b"test_risk_secret_key_32_bytes_pad"


def _make_order(order_id: str = "ord_test_1") -> OmsOrder:
    return OmsOrder(
        internal_order_id=order_id,
        client_order_id=f"cl_{order_id}",
        venue_order_id="v_1",
        pair="btc_idr",
        side="buy",
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("500000000"),
        state=OmsOrderState.NEW,
        created_at=_T0,
        updated_at=_T0,
    )


# =========================================================================
# AC0: All persisted modes restart into RECOVERY
# =========================================================================
def test_pm_03_0(tmp_path: Path) -> None:
    """PM-03-AC0: All persisted modes restart into RECOVERY; requested mode stored separately."""
    mode_path = tmp_path / "execution_mode.json"

    # 1. Test across all operational modes
    test_modes = [
        ExecutionMode.READ_ONLY,
        ExecutionMode.SHADOW,
        ExecutionMode.MANUAL_APPROVAL,
        ExecutionMode.AUTONOMOUS_LIMITED,
        ExecutionMode.DISABLED,
        ExecutionMode.HALTED,
    ]

    for mode in test_modes:
        store = DurableModeStore(path=mode_path, initial_mode=ExecutionMode.RECOVERY)
        if mode != ExecutionMode.RECOVERY:
            # Step-by-step valid transitions
            if mode == ExecutionMode.READ_ONLY:
                store.transition_to(ExecutionMode.READ_ONLY, reason="test", at=_T0)
            elif mode == ExecutionMode.SHADOW:
                store.transition_to(ExecutionMode.READ_ONLY, reason="step1", at=_T0)
                store.transition_to(ExecutionMode.SHADOW, reason="test", at=_T0)
            elif mode == ExecutionMode.MANUAL_APPROVAL:
                store.transition_to(ExecutionMode.READ_ONLY, reason="step1", at=_T0)
                store.transition_to(ExecutionMode.SHADOW, reason="step2", at=_T0)
                store.transition_to(ExecutionMode.MANUAL_APPROVAL, reason="test", at=_T0)
            elif mode == ExecutionMode.AUTONOMOUS_LIMITED:
                store.transition_to(ExecutionMode.READ_ONLY, reason="step1", at=_T0)
                store.transition_to(ExecutionMode.SHADOW, reason="step2", at=_T0)
                store.transition_to(ExecutionMode.MANUAL_APPROVAL, reason="step3", at=_T0)
                store.transition_to(ExecutionMode.AUTONOMOUS_LIMITED, reason="test", at=_T0)
            elif mode == ExecutionMode.HALTED:
                store.transition_to(ExecutionMode.HALTED, reason="test", at=_T0)
            elif mode == ExecutionMode.DISABLED:
                store.transition_to(ExecutionMode.DISABLED, reason="test", at=_T0)

        # Reboot / reload store from disk
        restarted_store = DurableModeStore(path=mode_path)

        # Invariant: Effective mode at boot is ALWAYS RECOVERY
        assert restarted_store.get_effective_mode() == ExecutionMode.RECOVERY
        assert restarted_store.get_mode() == ExecutionMode.RECOVERY

        # Invariant: Requested mode is stored separately
        assert restarted_store.get_requested_mode() == mode

        # Invariant: RecoveryService.restore() reports RECOVERY
        recovery_service = RecoveryService(mode_store=restarted_store)
        report = recovery_service.restore(namespace="prod_paper")
        assert isinstance(report, RecoveryReport)
        assert report.effective_mode == "RECOVERY"
        assert report.requested_mode == mode.value
        assert report.effective_state == "RECOVERY"


# =========================================================================
# AC1: Corrupt/missing risk state prevents active mode
# =========================================================================
def test_pm_03_1(tmp_path: Path) -> None:
    """PM-03-AC1: Corrupt/missing risk state prevents active mode."""
    mode_path = tmp_path / "execution_mode.json"
    throttle_path = tmp_path / "throttle_history.json"
    kill_switch_path = tmp_path / "emergency_kill_switch"

    DurableModeStore(path=mode_path, initial_mode=ExecutionMode.RECOVERY)

    # 1. Corrupt mode journal prevents transition to active mode
    with open(mode_path, encoding="utf-8") as f:
        data = json.load(f)
    # Tamper with journal hash
    data["journal"][0]["entry_hash"] = "tampered_hash_value"
    with open(mode_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    store_corrupted = DurableModeStore(path=mode_path)
    with pytest.raises(CorruptModeJournalError):
        store_corrupted.transition_to(ExecutionMode.READ_ONLY, reason="active_transition")

    # RecoveryService detects corrupted journal
    rec_service = RecoveryService(mode_store=store_corrupted)
    report = rec_service.restore(namespace="prod_paper")
    assert not report.journal_integrity_ok
    assert "CORRUPT_MODE_JOURNAL" in report.halt_reasons
    assert report.effective_state == "HALTED"

    # 2. Corrupted throttle/risk history prevents active mode in RiskEngine
    throttle_path.write_text("{corrupt_json: invalid", encoding="utf-8")
    risk_engine = RiskEngine(
        kill_switch_path=kill_switch_path,
        throttle_history_path=throttle_path,
    )
    assert not risk_engine.verify_risk_state_integrity()

    # RecoveryService with corrupt risk engine halts
    fresh_mode_store = DurableModeStore(
        path=tmp_path / "fresh_mode.json",
        initial_mode=ExecutionMode.RECOVERY,
    )
    rec_service_risk = RecoveryService(mode_store=fresh_mode_store, risk_engine=risk_engine)
    report_risk = rec_service_risk.restore(namespace="prod_paper")
    assert "CORRUPT_OR_MISSING_RISK_STATE" in report_risk.halt_reasons
    assert report_risk.effective_state == "HALTED"


# =========================================================================
# AC2: Persistence failure leaves writes disabled
# =========================================================================
def test_pm_03_2(tmp_path: Path) -> None:
    """PM-03-AC2: Persistence failure leaves writes disabled / in recovery."""
    mode_path = tmp_path / "unwritable_dir" / "execution_mode.json"

    store = DurableModeStore(path=mode_path, initial_mode=ExecutionMode.RECOVERY)
    assert store.get_mode() == ExecutionMode.RECOVERY

    # Make target directory unwritable / non-existent file path failure
    # Simulate persistence failure on transition_to
    import unittest.mock as mock

    with mock.patch.object(DurableModeStore, "_save", side_effect=OSError("Disk full / read-only")):
        with pytest.raises(RuntimeError, match="MODE_PERSISTENCE_FAILED"):
            store.transition_to(ExecutionMode.READ_ONLY, reason="test_transition")

    # State must NOT have advanced in memory; writes remain disabled
    assert store.get_mode() == ExecutionMode.RECOVERY
    assert store.get_effective_mode() == ExecutionMode.RECOVERY
    assert not store.get_mode().can_write_venue


# =========================================================================
# AC3: Reset with absent/stale evidence rejects
# =========================================================================
def test_pm_03_3(tmp_path: Path) -> None:
    """PM-03-AC3: Reset with absent/stale evidence rejects."""
    kill_switch_path = tmp_path / "emergency_kill_switch"
    risk_engine = RiskEngine(
        kill_switch_path=kill_switch_path,
        reset_confirmation_secret=_SECRET,
    )
    risk_engine.trigger_kill_switch("TEST_HALT")
    assert risk_engine.is_kill_switch_active

    # 1. Reset with absent evidence rejects
    with pytest.raises(ValueError, match="HEALTH_EVIDENCE_REQUIRED"):
        risk_engine.reset_kill_switch(
            operator_id="operator_1",
            reason="RECOVERY_ATTEMPT",
            evidence=None,
        )
    assert risk_engine.is_kill_switch_active

    # 2. Reset with stale evidence (> 300s old) rejects
    stale_time = _T0 - timedelta(seconds=301)
    stale_evidence = HealthEvidence(
        timestamp_utc=stale_time,
        reconciliation_healthy=True,
        unknown_orders_count=0,
        source="reconciliation_worker",
    )
    with pytest.raises(ValueError, match="HEALTH_EVIDENCE_STALE"):
        risk_engine.reset_kill_switch(
            operator_id="operator_1",
            reason="RECOVERY_ATTEMPT",
            evidence=stale_evidence,
            at=_T0,
        )
    assert risk_engine.is_kill_switch_active

    # 3. Reset with unhealthy reconciliation rejects
    fresh_unhealthy_evidence = HealthEvidence(
        timestamp_utc=_T0,
        reconciliation_healthy=False,
        unknown_orders_count=0,
        source="reconciliation_worker",
    )
    with pytest.raises(RuntimeError, match="CANNOT_RESET_KILL_SWITCH_UNHEALTHY_RECONCILIATION"):
        risk_engine.reset_kill_switch(
            operator_id="operator_1",
            reason="RECOVERY_ATTEMPT",
            evidence=fresh_unhealthy_evidence,
            at=_T0,
        )
    assert risk_engine.is_kill_switch_active

    # 4. Reset with unknown orders > 0 rejects
    fresh_unknown_orders_evidence = HealthEvidence(
        timestamp_utc=_T0,
        reconciliation_healthy=True,
        unknown_orders_count=2,
        source="reconciliation_worker",
    )
    with pytest.raises(RuntimeError, match="CANNOT_RESET_KILL_SWITCH_UNKNOWN_ORDERS_EXIST"):
        risk_engine.reset_kill_switch(
            operator_id="operator_1",
            reason="RECOVERY_ATTEMPT",
            evidence=fresh_unknown_orders_evidence,
            at=_T0,
        )
    assert risk_engine.is_kill_switch_active

    # 5. CLI clear without evidence rejects (no default healthy/zero fallback)
    from indodax_lab.cli import kill_switch

    ret_code = kill_switch.main(["--sentinel-path", str(kill_switch_path), "clear"])
    assert ret_code != 0
    assert risk_engine.is_kill_switch_active


# =========================================================================
# AC4: Reused or expired approval/reset token rejects
# =========================================================================
def test_pm_03_4(tmp_path: Path) -> None:
    """PM-03-AC4: Reused or expired approval/reset token rejects."""
    # 1. ManualApprovalStore: expired token rejects
    approval_store = ManualApprovalStore(
        persistence_path=tmp_path / "approvals.json",
        signing_secret=_SECRET,
    )
    order = _make_order("ord_approval_1")
    proposal = approval_store.propose(order, at=_T0, ttl_seconds=60)
    token = generate_approval_token(
        proposal_id=proposal.proposal_id,
        operator_id="op_alice",
        expires_at=proposal.expires_at,
        secret_key=_SECRET,
        nonce="nonce_123",
        action="APPROVE_PROPOSAL",
    )

    # Expired token rejects
    with pytest.raises(TimeoutError, match="PROPOSAL_EXPIRED"):
        approval_store.approve(
            proposal.proposal_id,
            operator_id="op_alice",
            at=_T0 + timedelta(seconds=61),  # Expired
            token=token,
            nonce="nonce_123",
        )

    # 2. Reused token/nonce rejects
    proposal2 = approval_store.propose(_make_order("ord_approval_2"), at=_T0, ttl_seconds=300)
    token2 = generate_approval_token(
        proposal_id=proposal2.proposal_id,
        operator_id="op_alice",
        expires_at=proposal2.expires_at,
        secret_key=_SECRET,
        nonce="nonce_456",
        action="APPROVE_PROPOSAL",
    )

    # First approval succeeds
    approved = approval_store.approve(
        proposal2.proposal_id,
        operator_id="op_alice",
        at=_T0 + timedelta(seconds=10),
        token=token2,
        nonce="nonce_456",
    )
    assert approved.status == "APPROVED"

    # Reusing same nonce/token for a new proposal must reject
    proposal3 = approval_store.propose(_make_order("ord_approval_3"), at=_T0, ttl_seconds=300)
    with pytest.raises(PermissionError, match="NONCE_ALREADY_USED"):
        approval_store.approve(
            proposal3.proposal_id,
            operator_id="op_alice",
            at=_T0 + timedelta(seconds=20),
            token=token2,
            nonce="nonce_456",
        )

    # 3. Kill switch reset token reuse rejects
    kill_switch_path = tmp_path / "emergency_kill_switch_ac4"
    risk_engine = RiskEngine(
        kill_switch_path=kill_switch_path,
        reset_confirmation_secret=_SECRET,
    )
    risk_engine.trigger_kill_switch("HALT_AC4")

    fresh_evidence = HealthEvidence(
        timestamp_utc=_T0,
        reconciliation_healthy=True,
        unknown_orders_count=0,
        source="reconciliation_worker",
    )

    token_reset = risk_engine.generate_reset_token(
        operator_id="op_bob",
        nonce="reset_nonce_789",
        expires_at=_T0 + timedelta(seconds=60),
    )

    # First reset with valid token succeeds
    risk_engine.reset_kill_switch(
        operator_id="op_bob",
        reason="DISARM_VALID",
        evidence=fresh_evidence,
        confirmation_token=token_reset,
        token_nonce="reset_nonce_789",
        at=_T0,
    )
    assert not risk_engine.is_kill_switch_active

    # Re-trip
    risk_engine.trigger_kill_switch("HALT_AGAIN")
    assert risk_engine.is_kill_switch_active

    # Reusing the reset token/nonce must reject
    with pytest.raises(PermissionError, match="NONCE_ALREADY_USED"):
        risk_engine.reset_kill_switch(
            operator_id="op_bob",
            reason="DISARM_REPLAY",
            evidence=fresh_evidence,
            confirmation_token=token_reset,
            token_nonce="reset_nonce_789",
            at=_T0 + timedelta(seconds=5),
        )
    assert risk_engine.is_kill_switch_active

    # 4. Expired kill switch reset token rejects
    token_expired = risk_engine.generate_reset_token(
        operator_id="op_bob",
        nonce="reset_nonce_expired_1",
        expires_at=_T0 + timedelta(seconds=10),
    )
    with pytest.raises(TimeoutError, match="RESET_TOKEN_EXPIRED"):
        risk_engine.reset_kill_switch(
            operator_id="op_bob",
            reason="DISARM_EXPIRED",
            evidence=fresh_evidence,
            confirmation_token=token_expired,
            token_nonce="reset_nonce_expired_1",
            at=_T0 + timedelta(seconds=15),
        )
    assert risk_engine.is_kill_switch_active
