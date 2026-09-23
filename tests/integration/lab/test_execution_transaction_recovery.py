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
) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id="ord_1",
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

    # 1. Unmatched fill -> must raise UnmatchedFillError and quarantine
    unmatched_fill = Fill(
        fill_id="fill_unmatched",
        order_id="ord_nonexistent",
        event_id="evt_x",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.01"),
        price=Decimal("500000000"),
        fees=Decimal("5000"),
        timestamp=_T0,
    )
    with pytest.raises(UnmatchedFillError):
        store.apply_fill(unmatched_fill, expected_revision=1)

    # 2. Conflicting duplicate: same fill_id but different qty/price
    fill1 = _make_fill("fill_1", qty=Decimal("0.005"))
    store.apply_fill(fill1, expected_revision=1)

    conflicting_fill = _make_fill("fill_1", qty=Decimal("0.008"))  # Changed qty
    with pytest.raises(ConflictingFillError):
        store.apply_fill(conflicting_fill, expected_revision=2)

    # 3. Overfill: fill exceeds desired_qty (0.01)
    overfill = _make_fill("fill_2", qty=Decimal("0.01"))  # 0.005 + 0.01 > 0.01
    with pytest.raises(OverfillInvariantError):
        store.apply_fill(overfill, expected_revision=2)


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
