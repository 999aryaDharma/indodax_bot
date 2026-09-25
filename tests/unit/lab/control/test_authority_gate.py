"""Unit tests for PM-01 authoritative fail-closed pre-write gate.

Covers acceptance criteria:
- PM-01-AC0: No report or portfolio snapshot means zero venue writes (test_pm_01_0)
- PM-01-AC1: Wrong scope or future timestamp cannot pass freshness (test_pm_01_1)
- PM-01-AC2: Changed cash/positions/price after approval requires fresh
  rejection/reapproval (test_pm_01_2)
- PM-01-AC3: Unknown orders block new exposure (test_pm_01_3)
- PM-01-AC4: Direct real-writer call without valid permit fails (test_pm_01_4)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.identity import ArtifactRef
from indodax_lab.control.approval import (
    ManualApprovalStore,
    PendingProposal,
    ProposalStatus,
)
from indodax_lab.control.authority import (
    AuthorityGate,
    ExecutionSnapshot,
    FutureEvidenceError,
    MissingEvidenceError,
    ReapprovalRequiredError,
    StaleEvidenceError,
    UnhealthyEvidenceError,
    UnknownOrdersError,
    WritePermit,
    WrongScopeError,
    compute_order_digest,
)
from indodax_lab.control.mode import ExecutionMode
from indodax_lab.control.pipeline import TradingPipeline
from indodax_lab.execution.fake_venue import FakeVenueAdapter
from indodax_lab.execution.oms import OmsOrder, OmsOrderState, OmsStateMachine, OmsStore
from indodax_lab.execution.order_router import OrderRouter
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.portfolio.constructor import PortfolioConstructor
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)
RELEASE_REF = ArtifactRef(
    kind="candidate",
    id="release-cand-001",
    version="v1.0.0",
    sha256="a" * 64,
)


def make_test_order(
    internal_id: str = "ord_test_1",
    pair: str = "btc_idr",
    side: OrderSide = OrderSide.BUY,
    qty: Decimal = Decimal("0.01"),
    limit_price: Decimal = Decimal("1000000000"),
) -> OmsOrder:
    return OmsStateMachine.create(
        internal_order_id=internal_id,
        client_order_id=f"cl_{internal_id}",
        pair=pair,
        side=side,
        desired_qty=qty,
        limit_price=limit_price,
        created_at=NOW,
    )


def make_valid_snapshot(
    now: datetime = NOW,
    scope: str = "btc_idr",
    unknown_count: int = 0,
    cash: Decimal = Decimal("100000000"),
    equity: Decimal = Decimal("100000000"),
    positions: dict[str, Decimal] | None = None,
    mark_prices: dict[str, Decimal] | None = None,
    cash_reservations: dict[str, Decimal] | None = None,
    rec_healthy: bool = True,
    rec_time: datetime | None = None,
    clock_healthy: bool = True,
    market_healthy: bool = True,
) -> ExecutionSnapshot:
    return ExecutionSnapshot(
        snapshot_id="snap_test_001",
        created_at=now,
        ledger_revision=42,
        oms_revision=108,
        risk_revision=1,
        available_cash=cash,
        current_equity=equity,
        positions=positions if positions is not None else {"btc_idr": Decimal("0.5")},
        mark_prices=mark_prices if mark_prices is not None else {"btc_idr": Decimal("1000000000")},
        cash_reservations=cash_reservations or {},
        market_healthy=market_healthy,
        clock_healthy=clock_healthy,
        reconciliation_healthy=rec_healthy,
        reconciliation_scope=scope,
        reconciliation_time=rec_time if rec_time is not None else now,
        unknown_orders_count=unknown_count,
    )


# =========================================================================
# PM-01-AC0: No report or portfolio snapshot means zero venue writes
# =========================================================================
def test_pm_01_0(tmp_path: Path) -> None:
    """PM-01-AC0: No report or portfolio snapshot means zero venue writes."""
    gate = AuthorityGate()
    order = make_test_order()

    # 1. None execution snapshot raises MissingEvidenceError
    with pytest.raises(MissingEvidenceError, match="MISSING_EXECUTION_SNAPSHOT"):
        gate.authorize(
            order=order,
            execution_snapshot=None,  # type: ignore[arg-type]
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # 2. In TradingPipeline: with require_execution_snapshot=True, missing snapshot
    # in venue-writing mode means zero submitted orders and no venue writes.
    venue = FakeVenueAdapter()
    oms_store = OmsStore(tmp_path / "oms.db")
    router = OrderRouter(oms_store=oms_store, venue=venue, require_permit=True)
    approval_store = ManualApprovalStore()
    risk_engine = MagicMock(spec=RiskEngine)
    risk_engine.is_kill_switch_active = False

    pipeline = TradingPipeline(
        mode=ExecutionMode.MANUAL_APPROVAL,
        gateway=MarketGateway(),
        constructor=MagicMock(spec=PortfolioConstructor),
        risk_engine=risk_engine,
        oms_store=oms_store,
        order_router=router,
        approval_store=approval_store,
        authority_gate=gate,
        require_execution_snapshot=True,
    )

    prop = approval_store.propose(order, at=NOW, ttl_seconds=300)
    approval_store.approve(prop.proposal_id, operator_id="op_admin", at=NOW)

    # Calling execute_approved_proposal without execution_snapshot fails closed: zero venue writes
    with pytest.raises(MissingEvidenceError, match="MISSING_EXECUTION_SNAPSHOT"):
        pipeline.execute_approved_proposal(
            prop.proposal_id,
            now=NOW,
            execution_snapshot=None,
        )
    # Venue received 0 orders
    assert len(venue.orders) == 0


# =========================================================================
# PM-01-AC1: Wrong scope or future timestamp cannot pass freshness
# =========================================================================
def test_pm_01_1() -> None:
    """PM-01-AC1: Wrong scope or future timestamp cannot pass freshness."""
    gate = AuthorityGate(max_reconciliation_age_seconds=120.0)
    order = make_test_order(pair="btc_idr")

    # 1. Wrong scope: snapshot covers 'eth_idr', order is 'btc_idr'
    snap_wrong_scope = make_valid_snapshot(scope="eth_idr")
    with pytest.raises(WrongScopeError, match="WRONG_RECONCILIATION_SCOPE"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_wrong_scope,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # 2. Future timestamp: reconciliation_time is in the future relative to now
    snap_future = make_valid_snapshot(rec_time=NOW + timedelta(seconds=60))
    with pytest.raises(FutureEvidenceError, match="FUTURE_RECONCILIATION_TIMESTAMP"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_future,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # 3. Future snapshot created_at
    snap_future_created = make_valid_snapshot(now=NOW + timedelta(seconds=60), rec_time=NOW)
    with pytest.raises(FutureEvidenceError, match="FUTURE_SNAPSHOT_TIMESTAMP"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_future_created,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # 4. Stale reconciliation: age > 120s
    snap_stale = make_valid_snapshot(rec_time=NOW - timedelta(seconds=121))
    with pytest.raises(StaleEvidenceError, match="STALE_RECONCILIATION_EVIDENCE"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_stale,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # 5. Unhealthy reconciliation
    snap_unhealthy_rec = make_valid_snapshot(rec_healthy=False)
    with pytest.raises(UnhealthyEvidenceError, match="RECONCILIATION_UNHEALTHY"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_unhealthy_rec,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # 6. Unhealthy clock / market
    snap_bad_clock = make_valid_snapshot(clock_healthy=False)
    with pytest.raises(UnhealthyEvidenceError, match="CLOCK_UNHEALTHY"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_bad_clock,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )


# =========================================================================
# PM-01-AC2: Changed cash/positions/price after approval requires fresh
# rejection/reapproval
# =========================================================================
def test_pm_01_2() -> None:
    """PM-01-AC2: Changed state requires fresh reapproval."""
    gate = AuthorityGate(max_slippage_bps=100)
    order = make_test_order(
        pair="btc_idr",
        side=OrderSide.BUY,
        qty=Decimal("0.05"),  # 0.05 BTC * 1,000,000,000 = 50,000,000 IDR
        limit_price=Decimal("1000000000"),
    )

    approval = PendingProposal(
        proposal_id="prop_001",
        order=order,
        created_at=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(seconds=290),
        status=ProposalStatus.APPROVED,
        decided_at=NOW - timedelta(seconds=5),
        decided_by="operator_bob",
    )

    # 1. Changed order quantity vs approved order requires reapproval
    order_changed_qty = make_test_order(qty=Decimal("0.06"))
    with pytest.raises(ReapprovalRequiredError, match="APPROVAL_QUANTITY_CHANGED"):
        gate.authorize(
            order=order_changed_qty,
            execution_snapshot=make_valid_snapshot(cash=Decimal("100000000")),
            release_ref=RELEASE_REF,
            approval=approval,
            now=NOW,
        )

    # 2. Cash decreased after approval: cash is only 30M IDR, order requires 50M IDR
    snap_low_cash = make_valid_snapshot(cash=Decimal("30000000"))
    with pytest.raises(ReapprovalRequiredError, match="INSUFFICIENT_CASH_AFTER_APPROVAL"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_low_cash,
            release_ref=RELEASE_REF,
            approval=approval,
            now=NOW,
        )

    # A snapshot may release only the exact approved order's own reserved cash.
    fully_reserved_snapshot = make_valid_snapshot(
        cash=Decimal("0"),
        cash_reservations={order.internal_order_id: Decimal("50000000")},
    )
    permit = gate.authorize(
        order=order,
        execution_snapshot=fully_reserved_snapshot,
        release_ref=RELEASE_REF,
        approval=approval,
        now=NOW,
    )
    assert permit.order_internal_id == order.internal_order_id

    # 3. For a SELL order: position decreased after approval
    sell_order = make_test_order(
        pair="btc_idr",
        side=OrderSide.SELL,
        qty=Decimal("0.5"),
    )
    sell_approval = PendingProposal(
        proposal_id="prop_sell_001",
        order=sell_order,
        created_at=NOW - timedelta(seconds=10),
        expires_at=NOW + timedelta(seconds=290),
        status=ProposalStatus.APPROVED,
        decided_at=NOW - timedelta(seconds=5),
        decided_by="operator_bob",
    )
    # Positions now has only 0.2 BTC (less than 0.5 BTC approved)
    snap_low_position = make_valid_snapshot(positions={"btc_idr": Decimal("0.2")})
    with pytest.raises(ReapprovalRequiredError, match="INSUFFICIENT_POSITION_AFTER_APPROVAL"):
        gate.authorize(
            order=sell_order,
            execution_snapshot=snap_low_position,
            release_ref=RELEASE_REF,
            approval=sell_approval,
            now=NOW,
        )

    # 4. Market price moved beyond allowable slippage (> 100 bps)
    # Order limit price is 1,000,000,000; mark price moved to 1,020,000,000 (200 bps diff)
    snap_high_slippage = make_valid_snapshot(
        mark_prices={"btc_idr": Decimal("1020000000")},
    )
    with pytest.raises(ReapprovalRequiredError, match="PRICE_SLIPPAGE_EXCEEDED_AFTER_APPROVAL"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_high_slippage,
            release_ref=RELEASE_REF,
            approval=approval,
            now=NOW,
        )

    # 5. Approval expired
    expired_approval = PendingProposal(
        proposal_id="prop_exp",
        order=order,
        created_at=NOW - timedelta(seconds=400),
        expires_at=NOW - timedelta(seconds=100),  # expired
        status=ProposalStatus.APPROVED,
        decided_at=NOW - timedelta(seconds=350),
        decided_by="operator_bob",
    )
    with pytest.raises(ReapprovalRequiredError, match="APPROVAL_EXPIRED"):
        gate.authorize(
            order=order,
            execution_snapshot=make_valid_snapshot(),
            release_ref=RELEASE_REF,
            approval=expired_approval,
            now=NOW,
        )


# =========================================================================
# PM-01-AC3: Unknown orders block new exposure
# =========================================================================
def test_pm_01_3() -> None:
    """PM-01-AC3: Unknown orders block new exposure."""
    gate = AuthorityGate()
    order = make_test_order()

    # When unknown_orders_count > 0 in execution snapshot, authorization fails closed immediately
    snap_with_unknown = make_valid_snapshot(unknown_count=1)
    with pytest.raises(UnknownOrdersError, match="UNKNOWN_ORDERS_BLOCK_EXPOSURE"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_with_unknown,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # With multiple unknown orders: also blocks
    snap_many_unknown = make_valid_snapshot(unknown_count=5)
    with pytest.raises(UnknownOrdersError, match="UNKNOWN_ORDERS_BLOCK_EXPOSURE"):
        gate.authorize(
            order=order,
            execution_snapshot=snap_many_unknown,
            release_ref=RELEASE_REF,
            approval=None,
            now=NOW,
        )

    # With zero unknown orders: passes and produces valid permit
    snap_zero_unknown = make_valid_snapshot(unknown_count=0)
    permit = gate.authorize(
        order=order,
        execution_snapshot=snap_zero_unknown,
        release_ref=RELEASE_REF,
        approval=None,
        now=NOW,
    )
    assert isinstance(permit, WritePermit)
    assert permit.order_internal_id == order.internal_order_id


# =========================================================================
# PM-01-AC4: Direct real-writer call without valid permit fails
# =========================================================================
def test_pm_01_4(tmp_path: Path) -> None:
    """PM-01-AC4: Direct real-writer call without valid permit fails."""
    venue = FakeVenueAdapter()
    oms_store = OmsStore(tmp_path / "oms.db")
    # OrderRouter with permit enforcement enabled
    router = OrderRouter(oms_store=oms_store, venue=venue, require_permit=True)

    order = make_test_order(internal_id="ord_permit_test")
    oms_store.create_order(order, event_id=f"evt_init_{order.internal_order_id}")
    gate = AuthorityGate()
    snapshot = make_valid_snapshot()

    # 1. Direct submit_order without permit fails
    with pytest.raises(PermissionError, match="MISSING_WRITE_PERMIT"):
        router.submit_order(order, now=NOW)

    # 2. Direct cancel_order without permit fails
    with pytest.raises(PermissionError, match="MISSING_WRITE_PERMIT"):
        router.cancel_order(order, now=NOW)

    # 3. Submit with expired permit fails
    expired_permit = WritePermit(
        permit_id="perm_expired",
        order_internal_id=order.internal_order_id,
        order_digest=compute_order_digest(order),
        candidate_ref=str(RELEASE_REF),
        snapshot_digest=snapshot.compute_digest(),
        action="SUBMIT",
        created_at=NOW - timedelta(seconds=60),
        expires_at=NOW - timedelta(seconds=10),
    )
    with pytest.raises(PermissionError, match="PERMIT_EXPIRED"):
        router.submit_order(order, permit=expired_permit, now=NOW)

    # 4. Submit with permit issued for different order fails
    other_order = make_test_order(internal_id="ord_other_999")
    oms_store.create_order(other_order, event_id=f"evt_init_{other_order.internal_order_id}")
    mismatched_permit = gate.authorize(
        order=other_order,
        execution_snapshot=snapshot,
        release_ref=RELEASE_REF,
        approval=None,
        now=NOW,
    )
    with pytest.raises(PermissionError, match="PERMIT_ORDER_MISMATCH"):
        router.submit_order(order, permit=mismatched_permit, now=NOW)

    # 5. Valid permit allows exactly one submission (single-use)
    valid_permit = gate.authorize(
        order=order,
        execution_snapshot=snapshot,
        release_ref=RELEASE_REF,
        approval=None,
        now=NOW,
    )
    submitted = router.submit_order(order, permit=valid_permit, now=NOW)
    assert submitted.state in (OmsOrderState.ACKNOWLEDGED, OmsOrderState.FILLED)

    # Re-using the exact same permit for a second submission fails closed (single-use)
    with pytest.raises(PermissionError, match="PERMIT_ALREADY_USED"):
        router.submit_order(order, permit=valid_permit, now=NOW)

    # 6. Cancel permit authorization and single-use
    cancel_permit = gate.authorize_cancel(
        order=submitted,
        execution_snapshot=snapshot,
        release_ref=RELEASE_REF,
        now=NOW + timedelta(seconds=1),
    )
    assert cancel_permit.action == "CANCEL"
    # Calling submit with a CANCEL permit fails
    with pytest.raises(PermissionError, match="PERMIT_ACTION_MISMATCH"):
        router.submit_order(submitted, permit=cancel_permit, now=NOW + timedelta(seconds=1))
