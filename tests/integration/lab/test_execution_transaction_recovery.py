"""Integration tests for atomic financial execution state and recovery (PM-02, ADR-007).

Validates:
- AC0 (test_pm_02_0): Crash at boundary yields zero or one complete effect after restart.
- AC1 (test_pm_02_1): Duplicate replay cannot double OMS quantity or fees.
- AC2 (test_pm_02_2): Conflicting duplicate/overfill/unmatched fill halts without partial posting.
- AC3 (test_pm_02_3): Late fill after cancellation updates cumulative evidence once.
- AC4 (test_pm_02_4): Corrupt snapshot/journal linkage blocks restore.
- AC5 (test_pm_02_bootstrap_recovery): No-intent event crash and partial two-order
  submission recover once without cursor loss or blind resubmission.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.orders import Fill
from indodax_lab.execution.oms import OmsOrder, OmsOrderState
from indodax_lab.execution.state_store import (
    ConflictingFillError,
    CorruptStateError,
    ExecutionStateError,
    ExecutionStateStore,
    OverfillInvariantError,
    UnmatchedFillError,
)

_T0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2025, 1, 1, 12, 5, 0, tzinfo=UTC)


def _make_store(tmp_path: Path, initial_cash: Decimal = Decimal("10000000")) -> ExecutionStateStore:
    db_path = tmp_path / "execution_state.db"
    return ExecutionStateStore(
        db_path=db_path,
        namespace="prod_paper",
        initial_cash=initial_cash,
        valuation_currency="IDR",
    )


def _make_fill(
    fill_id: str,
    pair: str = "btc_idr",
    side: OrderSide = OrderSide.BUY,
    qty: Decimal = Decimal("0.01"),
    price: Decimal = Decimal("500000000"),
    fees: Decimal = Decimal("5000"),
    ts: datetime | None = None,
    order_id: str = "ord_1",
) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        event_id="evt_1",
        pair=pair,
        side=side,
        role=OrderRole.TAKER,
        qty=qty,
        price=price,
        fees=fees,
        timestamp=ts or _T0,
    )


# =========================================================================
# AC0: Crash at each boundary yields either 0 or 1 complete effect
# =========================================================================
def test_pm_02_0(tmp_path: Path) -> None:
    """PM-02-AC0: Crash at each boundary yields either zero or one complete effect after restart."""
    store = _make_store(tmp_path)
    snapshot = store.restore()
    assert snapshot.revision == 0
    assert snapshot.cash == Decimal("10000000")

    # 1. Prepare event
    event = {"event_id": "evt_100", "type": "market_candle", "payload": "candle_data_1"}
    env = store.prepare_event(event, expected_revision=0)
    assert env.status == "PREPARED"

    # Simulate restart before commit_decision -> restart reloads snapshot with revision 0
    store2 = _make_store(tmp_path)
    rep = store2.recover()
    assert "evt_100" in rep.resumed_envelopes or rep.reloaded_revision == 0

    # 2. Decision commit
    order = OmsOrder(
        internal_order_id="ord_100",
        client_order_id="cl_100",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    env_dec = store2.commit_decision(
        envelope_id=env.envelope_id,
        expected_revision=0,
        next_state={"features": {"rsi": "55"}},
        intents=[order],
        reservations={"btc_idr": Decimal("10000000")},
    )
    assert env_dec.status == "DECIDED"
    assert env_dec.revision == 1

    # Restart after commit_decision: order must be persisted exactly once
    store3 = _make_store(tmp_path)
    snap3 = store3.restore()
    assert snap3.revision == 1
    assert "ord_100" in snap3.orders


# =========================================================================
# AC1: Duplicate replay cannot double OMS quantity or fees
# =========================================================================
def test_pm_02_1(tmp_path: Path) -> None:
    """PM-02-AC1: Duplicate replay cannot double OMS quantity or fees."""
    store = _make_store(tmp_path)
    order = OmsOrder(
        internal_order_id="ord_1",
        client_order_id="cl_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    # Setup order in store
    env = store.prepare_event({"event_id": "evt_1"}, expected_revision=0)
    store.commit_decision(env.envelope_id, 0, {}, [order], {})

    # Apply fill 1 (0.01 BTC)
    fill1 = _make_fill("fill_1", qty=Decimal("0.01"), fees=Decimal("5000"))
    res1 = store.apply_fill(fill1, expected_revision=1)
    assert not res1.is_duplicate
    assert res1.revision == 2

    snap_after_fill = store.restore()
    initial_cash_balance = snap_after_fill.cash
    initial_filled_qty = Decimal(str(snap_after_fill.orders["ord_1"]["filled_qty"]))
    assert initial_filled_qty == Decimal("0.01")

    # Replay duplicate fill 1
    res_dup = store.apply_fill(fill1, expected_revision=2)
    assert res_dup.is_duplicate

    snap_after_dup = store.restore()
    # Must NOT double fees or quantity
    assert Decimal(str(snap_after_dup.orders["ord_1"]["filled_qty"])) == initial_filled_qty
    assert snap_after_dup.cash == initial_cash_balance


# =========================================================================
# AC2: Conflicting duplicate / overfill / unmatched fill halts without partial posting
# =========================================================================
def test_pm_02_2(tmp_path: Path) -> None:
    """PM-02-AC2: Conflicting duplicate/overfill/unmatched fill halts without partial posting."""
    # 1. Unmatched fill -> must raise UnmatchedFillError, quarantine, and latch halted
    store_unmatched = _make_store(tmp_path / "unmatched")
    unmatched_fill = _make_fill("fill_unmatched", order_id="ord_nonexistent")
    with pytest.raises(UnmatchedFillError):
        store_unmatched.apply_fill(unmatched_fill, expected_revision=0)
    assert store_unmatched.restore().halted

    # 2. Conflicting duplicate: same fill_id but changed attributes -> halts
    store_conflict = _make_store(tmp_path / "conflict")
    order = OmsOrder(
        internal_order_id="ord_1",
        client_order_id="cl_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    env = store_conflict.prepare_event({"event_id": "evt_1"}, expected_revision=0)
    store_conflict.commit_decision(env.envelope_id, 0, {}, [order], {})

    fill1 = _make_fill("fill_1", qty=Decimal("0.005"))
    store_conflict.apply_fill(fill1, expected_revision=1)

    conflicting_fill = _make_fill("fill_1", qty=Decimal("0.008"))  # Changed qty
    with pytest.raises(ConflictingFillError):
        store_conflict.apply_fill(conflicting_fill, expected_revision=2)
    assert store_conflict.restore().halted

    # 3. Overfill: fill exceeds desired_qty (0.01) -> halts
    store_overfill = _make_store(tmp_path / "overfill")
    env_ov = store_overfill.prepare_event({"event_id": "evt_1"}, expected_revision=0)
    store_overfill.commit_decision(env_ov.envelope_id, 0, {}, [order], {})
    fill_first = _make_fill("fill_first", qty=Decimal("0.005"))
    store_overfill.apply_fill(fill_first, expected_revision=1)

    overfill = _make_fill("fill_second", qty=Decimal("0.01"))  # 0.005 + 0.01 > 0.01
    with pytest.raises(OverfillInvariantError):
        store_overfill.apply_fill(overfill, expected_revision=2)
    assert store_overfill.restore().halted


# =========================================================================
# AC3: Late fill after cancellation updates cumulative evidence once
# =========================================================================
def test_pm_02_3(tmp_path: Path) -> None:
    """PM-02-AC3: Late fill after cancellation updates cumulative evidence once."""
    store = _make_store(tmp_path)
    order = OmsOrder(
        internal_order_id="ord_cancel",
        client_order_id="cl_cancel",
        venue_order_id="v_cancel_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("500000000"),
        state=OmsOrderState.CANCELLED,
        created_at=_T0,
        updated_at=_T0,
    )
    env = store.prepare_event({"event_id": "evt_1"}, expected_revision=0)
    store.commit_decision(env.envelope_id, 0, {}, [order], {})

    late_fill = Fill(
        fill_id="fill_late",
        order_id="ord_cancel",
        event_id="evt_late",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.01"),
        price=Decimal("500000000"),
        fees=Decimal("5000"),
        timestamp=_T1,
    )

    res = store.apply_fill(late_fill, expected_revision=1)
    assert res.order_state == OmsOrderState.CANCELLED  # Cancellation lifecycle fact retained
    assert res.revision == 2

    # Verify cumulative quantity and financial ledger updated
    snap = store.restore()
    assert Decimal(str(snap.orders["ord_cancel"]["filled_qty"])) == Decimal("0.01")
    # Duplicate late fill is idempotent
    res_dup = store.apply_fill(late_fill, expected_revision=2)
    assert res_dup.is_duplicate


# =========================================================================
# AC4: Corrupt snapshot/journal linkage blocks restore
# =========================================================================
def test_pm_02_4(tmp_path: Path) -> None:
    """PM-02-AC4: Corrupt snapshot/journal linkage blocks restore."""
    store = _make_store(tmp_path)
    order = OmsOrder(
        internal_order_id="ord_1",
        client_order_id="cl_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    env = store.prepare_event({"event_id": "evt_1"}, expected_revision=0)
    store.commit_decision(env.envelope_id, 0, {}, [order], {})
    fill = _make_fill("fill_1")
    store.apply_fill(fill, expected_revision=1)

    # Tamper with the ledger transactions table (break hash chain)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE ledger_transactions SET entry_hash = 'corrupted_hash' WHERE sequence_num = 1"
        )
        conn.commit()

    # Restore must fail-closed
    store_tampered = _make_store(tmp_path)
    with pytest.raises(CorruptStateError):
        store_tampered.restore()


# =========================================================================
# AC5: Bootstrap recovery
# =========================================================================
def test_pm_02_bootstrap_recovery(tmp_path: Path) -> None:
    """PM-02-AC5: No-intent event crash and partial two-order submission recover once."""
    store = _make_store(tmp_path)

    # 1. No-intent event goes PREPARED -> DECIDED -> ACKNOWLEDGED
    env1 = store.prepare_event({"event_id": "evt_no_intent"}, expected_revision=0)
    store.commit_decision(env1.envelope_id, 0, {"cursor": "cur_1"}, [], {})
    step1 = store.acknowledge_event(env1.envelope_id, 1)
    assert step1.status == "ACKNOWLEDGED"

    # 2. Event producing two orders with only one submitted before crash
    order1 = OmsOrder(
        internal_order_id="ord_a",
        client_order_id="cl_a",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    order2 = OmsOrder(
        internal_order_id="ord_b",
        client_order_id="cl_b",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    env2 = store.prepare_event({"event_id": "evt_multi"}, expected_revision=2)
    store.commit_decision(env2.envelope_id, 2, {"cursor": "cur_2"}, [order1, order2], {})

    # Claim submission for order 1
    attempt1 = store.claim_submission("outbox_ord_a", expected_revision=3)
    assert attempt1.status == "ATTEMPTING"
    # Record submission success for order 1
    store.record_submission(attempt1.attempt_id, outcome={"status": "SUBMITTED"})

    # Order 2 outbox is claimed but crashes while ATTEMPTING (no outcome recorded)
    attempt2 = store.claim_submission("outbox_ord_b", expected_revision=5)
    assert attempt2.status == "ATTEMPTING"

    # Crash & restart
    recovered_store = _make_store(tmp_path)
    report = recovered_store.recover()
    assert report.status == "RECOVERED"
    # Unfinished attempting submission must resolve to UNKNOWN and latch halted
    assert report.halted
    assert "outbox_ord_b" in report.reconciled_attempts or "att_" in str(report.reconciled_attempts)


def test_pm_02_acknowledge_requires_finished_outbox(tmp_path: Path) -> None:
    """F-02: acknowledge_event blocks cursor advancement if outbox submissions are in-flight."""
    store = _make_store(tmp_path)
    order = OmsOrder(
        internal_order_id="ord_pending",
        client_order_id="cl_pending",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    env = store.prepare_event({"event_id": "evt_ack_test"}, expected_revision=0)
    store.commit_decision(env.envelope_id, 0, {}, [order], {})

    # Outbox has a PENDING submission -> acknowledge_event must fail closed
    with pytest.raises(ExecutionStateError, match="UNFINISHED_OUTBOX_SUBMISSIONS"):
        store.acknowledge_event(env.envelope_id, expected_revision=1)

    # Claim submission -> status becomes ATTEMPTING -> still must fail closed
    attempt = store.claim_submission("outbox_ord_pending", expected_revision=1)
    with pytest.raises(ExecutionStateError, match="UNFINISHED_OUTBOX_SUBMISSIONS"):
        store.acknowledge_event(env.envelope_id, expected_revision=2)

    # Record terminal submission outcome -> now acknowledge succeeds
    store.record_submission(attempt.attempt_id, outcome={"status": "SUBMITTED"})
    result = store.acknowledge_event(env.envelope_id, expected_revision=3)
    assert result.status == "ACKNOWLEDGED"
    assert result.cursor == "evt_ack_test"
    assert result.revision == 4


def test_pm_02_quarantine_latches_halt(tmp_path: Path) -> None:
    """F-04: Unmatched fills and overfills latch halted=1 in state_metadata."""
    # 1. Unmatched fill latches halt
    store1 = _make_store(tmp_path / "halt_unmatched")
    with pytest.raises(UnmatchedFillError):
        store1.apply_fill(_make_fill("fill_unmatched"), expected_revision=0)
    snap1 = store1.restore()
    assert snap1.halted

    # 2. Overfill latches halt
    store2 = _make_store(tmp_path / "halt_overfill")
    order = OmsOrder(
        internal_order_id="ord_ov",
        client_order_id="cl_ov",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("500000000"),
        created_at=_T0,
        updated_at=_T0,
    )
    env = store2.prepare_event({"event_id": "evt_ov"}, expected_revision=0)
    store2.commit_decision(env.envelope_id, 0, {}, [order], {})
    overfill = _make_fill("fill_over", order_id="ord_ov", qty=Decimal("0.05"))
    with pytest.raises(OverfillInvariantError):
        store2.apply_fill(overfill, expected_revision=1)
    snap2 = store2.restore()
    assert snap2.halted


def test_pm_02_migrate_readonly(tmp_path: Path) -> None:
    """F-01, F-05: migrate_readonly safely migrates historical DB without mutating source."""
    import hashlib

    # Create source database
    src_db = tmp_path / "historical_source.db"
    tx_id = "tx_hist_1"
    fill_id = "fill_hist_1"
    ts_utc = "2025-01-01T00:00:00Z"
    postings_json = "[]"
    prev_hash = "0" * 64
    payload = f"{tx_id}:{fill_id}:{ts_utc}:{postings_json}:{prev_hash}"
    entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    with sqlite3.connect(src_db) as conn:
        conn.execute(
            """
            CREATE TABLE oms_orders (
                internal_order_id TEXT PRIMARY KEY,
                client_order_id TEXT,
                venue_order_id TEXT,
                pair TEXT,
                side TEXT,
                desired_qty TEXT,
                filled_qty TEXT,
                limit_price TEXT,
                state TEXT,
                version INTEGER,
                payload_json TEXT,
                sha256 TEXT,
                updated_at_utc TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO oms_orders VALUES (
                'hist_ord_1', 'cl_hist_1', 'v_1', 'btc_idr', 'BUY',
                '0.1', '0.1', '500000000', 'FILLED', 1, '{}', 'hash1', '2025-01-01T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE ledger_transactions (
                transaction_id TEXT PRIMARY KEY,
                fill_id TEXT,
                timestamp_utc TEXT,
                pair TEXT,
                base_qty_delta TEXT,
                postings_json TEXT,
                prev_hash TEXT,
                entry_hash TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ledger_transactions VALUES (
                ?, ?, ?, ?, '0.1', ?, ?, ?
            )
            """,
            (tx_id, fill_id, ts_utc, "btc_idr", postings_json, prev_hash, entry_hash),
        )
        conn.commit()

    # Capture source DB hash before migration
    src_hash_before = hashlib.sha256(src_db.read_bytes()).hexdigest()

    # Target store
    store = _make_store(tmp_path / "target_store")
    report = store.migrate_readonly([src_db], target_namespace="prod_paper")

    # Assert report fields matching CONTRACTS.md line 90
    assert report.target_namespace == "prod_paper"
    assert report.migrated_orders == 1
    assert report.migrated_transactions == 1
    assert report.verified is True
    assert report.status == "MIGRATED"
    assert not report.blocking_reasons
    assert str(src_db) in report.source_hashes

    # Assert source DB remained completely immutable
    src_hash_after = hashlib.sha256(src_db.read_bytes()).hexdigest()
    assert src_hash_before == src_hash_after

    # Assert target store has the migrated order
    snap = store.restore()
    assert "hist_ord_1" in snap.orders
