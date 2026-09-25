"""Unit tests for ManualApprovalStore HMAC authorization
and TradingPipeline execute_approved_proposal.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.control.approval import (
    ManualApprovalStore,
    ProposalStatus,
    generate_approval_token,
    verify_approval_token,
)
from indodax_lab.control.authority import ExecutionSnapshot
from indodax_lab.control.mode import ExecutionMode
from indodax_lab.control.pipeline import TradingPipeline
from indodax_lab.execution.fake_venue import FakeVenueAdapter
from indodax_lab.execution.oms import OmsOrderState, OmsStateMachine, OmsStore
from indodax_lab.execution.order_router import OrderRouter
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.market.quality import TickerSnapshot
from indodax_lab.portfolio.constructor import PortfolioConstructor
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
SECRET_KEY = b"institutional_super_secret_hmac_key"


def test_manual_approval_hmac_token_verification(tmp_path: Path) -> None:
    store_file = tmp_path / "approvals.json"
    store = ManualApprovalStore(
        persistence_path=store_file,
        signing_secret=SECRET_KEY,
    )

    order = OmsStateMachine.create(
        internal_order_id="ord_hmac_test",
        client_order_id="cl_hmac_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    prop = store.propose(order, at=NOW, ttl_seconds=300)

    # 1. Approval without token fails closed
    with pytest.raises(PermissionError, match="MISSING_APPROVAL_TOKEN"):
        store.approve(
            prop.proposal_id,
            operator_id="operator_alice",
            at=NOW,
        )

    # 2. Approval with invalid token fails closed
    with pytest.raises(PermissionError, match="INVALID_APPROVAL_TOKEN"):
        store.approve(
            prop.proposal_id,
            operator_id="operator_alice",
            at=NOW,
            token="invalid_hex_token_12345",
        )

    # 3. Generate correct token
    valid_token = generate_approval_token(
        proposal_id=prop.proposal_id,
        operator_id="operator_alice",
        expires_at=prop.expires_at,
        secret_key=SECRET_KEY,
    )
    assert verify_approval_token(
        valid_token,
        prop.proposal_id,
        "operator_alice",
        prop.expires_at,
        SECRET_KEY,
    )

    # 4. Approval succeeds with valid token
    approved = store.approve(
        prop.proposal_id,
        operator_id="operator_alice",
        at=NOW,
        token=valid_token,
    )
    assert approved.status == ProposalStatus.APPROVED
    assert approved.decided_by == "operator_alice"
    assert approved.approval_token == valid_token


def test_trading_pipeline_execute_approved_proposal(tmp_path: Path) -> None:
    venue = FakeVenueAdapter()
    oms_store = OmsStore(tmp_path / "oms.db")
    router = OrderRouter(oms_store=oms_store, venue=venue)
    store = ManualApprovalStore(persistence_path=tmp_path / "approvals.json")

    risk_engine = MagicMock(spec=RiskEngine)
    risk_engine.is_kill_switch_active = False

    pipeline = TradingPipeline(
        mode=ExecutionMode.MANUAL_APPROVAL,
        gateway=MarketGateway(),
        constructor=MagicMock(spec=PortfolioConstructor),
        risk_engine=risk_engine,
        oms_store=oms_store,
        order_router=router,
        approval_store=store,
        estimated_fee_rate=Decimal("0.003"),
        fee_precision=8,
        quantity_precision=8,
    )

    order = OmsStateMachine.create(
        internal_order_id="ord_pipe_exec",
        client_order_id="cl_pipe_exec_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
    )
    oms_store.create_order(order, event_id="evt_init_ord_pipe_exec")
    other_order = OmsStateMachine.create(
        internal_order_id="ord_other_pending",
        client_order_id="cl_other_pending",
        pair="eth_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("1000000"),
        created_at=NOW,
    )
    oms_store.create_order(other_order, event_id="evt_init_ord_other_pending")
    prop = store.propose(order, at=NOW, ttl_seconds=300)

    # Attempting execution before operator approval fails
    with pytest.raises(ValueError, match="PROPOSAL_NOT_APPROVED"):
        pipeline.execute_approved_proposal(prop.proposal_id, at=NOW)

    # Operator approves proposal
    store.approve(prop.proposal_id, operator_id="operator_arya", at=NOW)

    # Execute approved proposal with market snapshot matching limit price
    ticker = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("999000000"),
        ask=Decimal("1000000000"),
        last_price=Decimal("1000000000"),
        timestamp_utc=NOW,
    )
    gateway = MarketGateway()
    snapshot = gateway.get_market_snapshot("btc_idr", as_of_utc=NOW, ticker_override=ticker)
    execution_snapshot = ExecutionSnapshot(
        snapshot_id="snap_manual_execution",
        created_at=NOW,
        ledger_revision=3,
        oms_revision=4,
        risk_revision=2,
        available_cash=Decimal("4977929970"),
        current_equity=Decimal("5000000000"),
        positions={"eth_idr": Decimal("2")},
        mark_prices={"btc_idr": Decimal("1000000000"), "eth_idr": Decimal("1000000")},
        cash_reservations={
            "ord_pipe_exec": Decimal("20060000"),
            "ord_other_pending": Decimal("10030"),
        },
        reconciliation_scope="btc_idr",
        reconciliation_time=NOW,
    )

    result_order = pipeline.execute_approved_proposal(
        prop.proposal_id,
        at=NOW,
        market_snapshot=snapshot,
        execution_snapshot=execution_snapshot,
    )

    # Order was acknowledged/filled via router
    assert result_order.state in (OmsOrderState.ACKNOWLEDGED, OmsOrderState.FILLED)
    assert result_order.internal_order_id == "ord_pipe_exec"

    # Loaded order in OMS store exists and is saved
    saved_order = oms_store.load_order("ord_pipe_exec")
    assert saved_order is not None
    assert saved_order.state == result_order.state
