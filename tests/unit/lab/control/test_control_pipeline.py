"""Tests for control plane execution modes, manual approval, and unified pipeline."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
from indodax_lab.control.approval import ManualApprovalStore, ProposalStatus
from indodax_lab.control.mode import AutonomousLimits, ExecutionMode
from indodax_lab.control.pipeline import TradingPipeline
from indodax_lab.execution.fake_venue import DeterministicFakeVenue
from indodax_lab.execution.oms import OmsOrderState
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.order_router import OrderRouter
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.market.quality import TickerSnapshot
from indodax_lab.portfolio.constructor import PortfolioConstructor
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


@pytest.fixture
def pipeline_fixture(tmp_path: Path):
    gateway = MarketGateway()
    ticker = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("999900000"),
        ask=Decimal("1000100000"),
        last_price=Decimal("1000000000"),
        timestamp_utc=NOW,
        high_24h=Decimal("1010000000"),
        low_24h=Decimal("990000000"),
        volume_24h=Decimal("10.0"),
    )

    constructor = PortfolioConstructor()

    risk_policy = RiskPolicy(
        policy_id="pol_1",
        version="1.0",
        max_position_fraction=Decimal("0.50"),
        max_open_positions=3,
        min_order_notional=Decimal("10000"),
    )
    risk_manager = PortfolioRiskManager(
        policy=risk_policy,
        initial_equity=Decimal("100000000"),
        start_time=NOW,
    )
    risk_engine = RiskEngine(risk_manager=risk_manager)

    oms_store = OmsStore(tmp_path / "oms.sqlite3")
    fake_venue = DeterministicFakeVenue()
    order_router = OrderRouter(oms_store=oms_store, venue=fake_venue)

    approval_store = ManualApprovalStore()
    autonomous_limits = AutonomousLimits(
        max_single_order_notional=Decimal("500000"),  # 500,000 IDR limit
        allowed_pairs=("btc_idr",),
    )

    pipeline = TradingPipeline(
        mode=ExecutionMode.READ_ONLY,
        gateway=gateway,
        constructor=constructor,
        risk_engine=risk_engine,
        oms_store=oms_store,
        order_router=order_router,
        approval_store=approval_store,
        autonomous_limits=autonomous_limits,
        estimated_fee_rate=Decimal("0.003"),
        fee_precision=8,
        quantity_precision=8,
    )

    return pipeline, fake_venue, oms_store, approval_store, risk_engine, ticker


def test_pipeline_disabled_mode_skips(pipeline_fixture) -> None:
    pipeline, _, oms_store, _, _, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.DISABLED)

    intent = SignalIntent(
        intent_id="sig_dis",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )

    report = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert report.mode == ExecutionMode.DISABLED
    assert report.approved_count == 0
    assert len(oms_store.load_nonterminal_orders()) == 0


def test_pipeline_read_only_mode_does_not_write_or_persist(pipeline_fixture) -> None:
    pipeline, _, oms_store, _, _, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.READ_ONLY)

    intent = SignalIntent(
        intent_id="sig_ro",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )

    report = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert report.mode == ExecutionMode.READ_ONLY
    assert report.approved_count == 1
    assert len(report.submitted_orders) == 0
    assert len(oms_store.load_nonterminal_orders()) == 0


def test_pipeline_shadow_mode_routes_to_venue(pipeline_fixture) -> None:
    pipeline, fake_venue, _, _, _, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)

    intent = SignalIntent(
        intent_id="sig_shadow",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )

    report = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert report.mode == ExecutionMode.SHADOW
    assert len(report.submitted_orders) == 1
    submitted = report.submitted_orders[0]
    assert submitted.state == OmsOrderState.ACKNOWLEDGED
    assert submitted.venue_order_id in fake_venue.orders


def test_pipeline_step_uses_typed_state_and_fee_aware_sizing(pipeline_fixture) -> None:
    pipeline, _, _, _, _, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.max_risk_amount_by_strategy = {"agent-c07": Decimal("4000")}
    intent = SignalIntent(
        intent_id="sig_fee_aware",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.2"),
        limit_price=Decimal("1000000000"),
        stop_loss=Decimal("990000000"),
        time_in_force="GTC",
        strategy_id="agent-c07",
    )

    report = pipeline.step(
        [intent], current_positions={}, available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"), now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert len(report.submitted_orders) == 1
    order = report.submitted_orders[0]
    assert order.time_in_force == "GTC"
    notional = order.desired_qty * Decimal("1000000000")
    fee = (notional * Decimal("0.003")).quantize(Decimal("0.00000001"))
    exit_fee = (
        order.desired_qty * Decimal("990000000") * Decimal("0.003")
    ).quantize(Decimal("0.00000001"))
    stop_risk = order.desired_qty * Decimal("10000000") + fee + exit_fee
    assert stop_risk <= Decimal("4000")


def test_pipeline_blocks_unmapped_strategy_when_stop_risk_policy_is_active(
    pipeline_fixture,
) -> None:
    pipeline, _, _, _, _, ticker = pipeline_fixture
    pipeline.max_risk_amount_by_strategy = {"agent-c07": Decimal("4000")}
    intent = SignalIntent(
        intent_id="sig_unmapped", decision_ts=NOW, pair="btc_idr", side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"), limit_price=Decimal("1000000000"),
        stop_loss=Decimal("990000000"), strategy_id="unknown-agent",
    )

    report = pipeline.step(
        [intent], current_positions={}, available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"), now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert report.approved_count == 0
    assert report.rejected_reasons == ("btc_idr:MISSING_STRATEGY_RISK_POLICY",)


def test_pipeline_pending_proposal_reserves_cash_until_decision(pipeline_fixture) -> None:
    pipeline, _, _, _, _, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.set_mode(ExecutionMode.MANUAL_APPROVAL)
    intent = SignalIntent(
        intent_id="sig_reserve",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
        stop_loss=Decimal("990000000"),
        strategy_id="agent-c07",
    )
    first = pipeline.step(
        [intent], current_positions={}, available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"), now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )
    assert len(first.pending_proposals) == 1

    free_cash = Decimal("99899700")
    empty = pipeline.step(
        [], current_positions={}, available_cash=free_cash,
        current_equity=Decimal("100000000"), now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )
    assert empty.rejected_reasons == ()

    second = pipeline.step(
        [intent], current_positions={}, available_cash=free_cash,
        current_equity=Decimal("100000000"), now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert second.approved_count == 1
    assert second.rejected_reasons == ()


def test_pipeline_without_current_fee_evidence_blocks_buy(pipeline_fixture) -> None:
    pipeline, _, _, _, _, ticker = pipeline_fixture
    pipeline.estimated_fee_rate = None
    intent = SignalIntent(
        intent_id="sig_no_fee", decision_ts=NOW, pair="btc_idr", side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"), limit_price=Decimal("1000000000"),
    )

    report = pipeline.step(
        [intent], current_positions={}, available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"), now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert report.approved_count == 0
    assert report.rejected_reasons == ("btc_idr:COST_AND_PRECISION_REQUIRED",)


def test_pipeline_manual_approval_queues_proposal(pipeline_fixture) -> None:
    pipeline, _, _, approval_store, _, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.set_mode(ExecutionMode.MANUAL_APPROVAL)

    intent = SignalIntent(
        intent_id="sig_manual",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )

    report = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert len(report.pending_proposals) == 1
    proposal = report.pending_proposals[0]
    assert proposal.status == ProposalStatus.PENDING

    # Operator approves proposal
    approved = approval_store.approve(
        proposal.proposal_id,
        operator_id="operator_arya",
        at=NOW + timedelta(seconds=10),
    )
    assert approved.status == ProposalStatus.APPROVED
    assert approved.decided_by == "operator_arya"


def test_pipeline_autonomous_limited_success_and_breach(pipeline_fixture) -> None:
    pipeline, _, _, _, risk_engine, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.set_mode(ExecutionMode.MANUAL_APPROVAL)
    pipeline.set_mode(ExecutionMode.AUTONOMOUS_LIMITED)

    # 1. Order within limit (0.0001 BTC * 1e9 = 100,000 IDR <= 500,000 limit)
    intent_valid = SignalIntent(
        intent_id="sig_auton_ok",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )
    report_ok = pipeline.step(
        [intent_valid],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )
    assert len(report_ok.submitted_orders) == 1
    assert not report_ok.kill_switch_triggered

    # 2. Order exceeding limit (0.001 BTC * 1e9 = 1,000,000 IDR > 500,000 limit)
    intent_breach = SignalIntent(
        intent_id="sig_auton_breach",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("1000000000"),
    )
    report_breach = pipeline.step(
        [intent_breach],
        current_positions={},
        available_cash=Decimal("99899700"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )
    assert report_breach.kill_switch_triggered
    assert risk_engine.is_kill_switch_active


def test_pipeline_autonomous_limited_uncertain_submit_trips_kill_switch(
    pipeline_fixture,
) -> None:
    pipeline, fake_venue, _, _, risk_engine, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.set_mode(ExecutionMode.MANUAL_APPROVAL)
    pipeline.set_mode(ExecutionMode.AUTONOMOUS_LIMITED)

    # Configure fake venue to time out after write -> transitions to UNKNOWN
    fake_venue.submit_scenario = "TIMEOUT_AFTER"

    intent = SignalIntent(
        intent_id="sig_auton_timeout",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )
    report = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
    )

    assert report.kill_switch_triggered
    assert risk_engine.is_kill_switch_active
    assert len(report.submitted_orders) == 1
    assert report.submitted_orders[0].state == OmsOrderState.UNKNOWN


def test_pipeline_autonomous_daily_loss_limit_trips_kill_switch(
    pipeline_fixture,
) -> None:
    pipeline, _, _, _, risk_engine, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.set_mode(ExecutionMode.MANUAL_APPROVAL)
    pipeline.set_mode(ExecutionMode.AUTONOMOUS_LIMITED)

    intent = SignalIntent(
        intent_id="sig_loss",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )

    # Exceed autonomous max_daily_loss_notional (default 1,000,000)
    report = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("95000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
        cumulative_daily_loss=Decimal("1500000"),
    )

    assert report.kill_switch_triggered
    assert risk_engine.is_kill_switch_active
    assert "DAILY_LOSS_LIMIT_EXCEEDED" in report.rejected_reasons


def test_pipeline_reconciliation_pre_write_gate(pipeline_fixture) -> None:
    from indodax_lab.execution.reconciliation import (
        ReconciliationIssue,
        ReconciliationReport,
        ReconciliationStatus,
    )

    pipeline, _, _, _, _, ticker = pipeline_fixture
    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.set_mode(ExecutionMode.MANUAL_APPROVAL)

    intent = SignalIntent(
        intent_id="sig_rec_gate",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
    )

    # 1. Stale reconciliation report (> 120s) blocks venue writes
    stale_report = ReconciliationReport(
        status=ReconciliationStatus.HEALTHY,
        evaluated_at=NOW - timedelta(seconds=130),
        issues=(),
    )
    report = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
        reconciliation_report=stale_report,
    )
    assert "RECONCILIATION_STALE" in report.rejected_reasons

    # 2. Unhealthy reconciliation report blocks venue writes
    unhealthy_report = ReconciliationReport(
        status=ReconciliationStatus.HALT_NEW_ORDERS,
        evaluated_at=NOW,
        issues=(ReconciliationIssue(code="CASH_MISMATCH", detail="diff"),),
    )
    report2 = pipeline.step(
        [intent],
        current_positions={},
        available_cash=Decimal("100000000"),
        current_equity=Decimal("100000000"),
        now=NOW,
        ticker_overrides={"btc_idr": ticker},
        reconciliation_report=unhealthy_report,
    )
    assert "RECONCILIATION_UNHEALTHY" in report2.rejected_reasons


def test_pipeline_recover_and_promote(pipeline_fixture) -> None:
    from indodax_lab.execution.reconciliation import (
        ReconciliationReport,
        ReconciliationStatus,
    )

    pipeline, _, _, _, risk_engine, _ = pipeline_fixture
    pipeline.set_mode(ExecutionMode.HALTED)
    assert pipeline.mode == ExecutionMode.HALTED

    # 1. Kill switch active blocks promotion
    risk_engine.trigger_kill_switch("TEST_HALT")
    with pytest.raises(RuntimeError, match="CANNOT_PROMOTE_WHILE_KILL_SWITCH_ACTIVE"):
        pipeline.recover_and_promote(ExecutionMode.READ_ONLY)

    risk_engine.reset_kill_switch(
        operator_id="operator_test",
        reason="RECOVERED",
        reconciliation_healthy=True,
        unknown_orders_count=0,
    )

    # 2. Unhealthy reconciliation blocks promotion
    bad_report = ReconciliationReport(
        status=ReconciliationStatus.HALT_NEW_ORDERS,
        evaluated_at=NOW,
        issues=(),
    )
    with pytest.raises(RuntimeError, match="CANNOT_PROMOTE_WITH_UNHEALTHY_RECONCILIATION"):
        pipeline.recover_and_promote(ExecutionMode.READ_ONLY, reconciliation_report=bad_report)

    # 3. Successful promotion from HALTED -> RECOVERY -> READ_ONLY -> SHADOW
    clean_report = ReconciliationReport(
        status=ReconciliationStatus.HEALTHY,
        evaluated_at=NOW,
        issues=(),
    )
    promoted_mode = pipeline.recover_and_promote(
        ExecutionMode.SHADOW,
        now=NOW,
        reconciliation_report=clean_report,
    )
    assert promoted_mode == ExecutionMode.SHADOW
    assert pipeline.mode == ExecutionMode.SHADOW


def test_pipeline_execute_approved_proposal_with_hmac_and_risk_recheck(
    pipeline_fixture,
) -> None:
    from indodax_lab.control.approval import generate_approval_token
    from indodax_lab.execution.oms import OmsOrder

    pipeline, fake_venue, oms_store, _, risk_engine, ticker = pipeline_fixture
    secret = b"topsecret_approval_key"
    approval_store = ManualApprovalStore(signing_secret=secret)
    pipeline.approval_store = approval_store

    pipeline.set_mode(ExecutionMode.SHADOW)
    pipeline.set_mode(ExecutionMode.MANUAL_APPROVAL)

    order = OmsOrder(
        internal_order_id="ord_hmac_1",
        client_order_id="cl_hmac_1",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
        limit_price=Decimal("1000000000"),
        created_at=NOW,
        updated_at=NOW,
    )
    oms_store.create_order(order, event_id="evt_init_ord_hmac_1")
    proposal = approval_store.propose(order, at=NOW, ttl_seconds=300)

    # Operator signs approval with valid HMAC token
    token = generate_approval_token(proposal.proposal_id, "op_alice", proposal.expires_at, secret)
    approval_store.approve(
        proposal.proposal_id,
        operator_id="op_alice",
        at=NOW + timedelta(seconds=1),
        token=token,
    )

    from indodax_lab.control.authority import MissingEvidenceError

    pipeline.max_risk_amount_by_strategy = {"agent-c07": Decimal("4000")}
    with pytest.raises(MissingEvidenceError, match="MISSING_APPROVED_INTENT_RISK_LINEAGE"):
        pipeline.execute_approved_proposal(
            proposal.proposal_id,
            now=NOW + timedelta(seconds=2),
            market_snapshot=pipeline.gateway.get_market_snapshot(
                pair="btc_idr", as_of_utc=NOW + timedelta(seconds=2), ticker_override=ticker
            ),
            available_cash=Decimal("99899700"),
            current_equity=Decimal("100000000"),
        )
    pipeline.max_risk_amount_by_strategy = {}

    clean_snapshot = pipeline.gateway.get_market_snapshot(
        pair="btc_idr", as_of_utc=NOW + timedelta(seconds=2), ticker_override=ticker
    )

    # 1. Proposal executes successfully with live risk check
    submitted = pipeline.execute_approved_proposal(
        proposal.proposal_id,
        now=NOW + timedelta(seconds=2),
        market_snapshot=clean_snapshot,
        available_cash=Decimal("99899700"),
        current_equity=Decimal("100000000"),
    )
    assert submitted.internal_order_id == "ord_hmac_1"

    # 2. Risk check failure rejects execution fail-closed
    order_huge = OmsOrder(
        internal_order_id="ord_hmac_huge",
        client_order_id="cl_hmac_huge",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("100.0"),  # 100 BTC >> 100M IDR cash
        limit_price=Decimal("1000000000"),
        created_at=NOW,
        updated_at=NOW,
    )
    prop_huge = approval_store.propose(order_huge, at=NOW, ttl_seconds=300)
    token_huge = generate_approval_token(
        prop_huge.proposal_id, "op_alice", prop_huge.expires_at, secret
    )
    approval_store.approve(
        prop_huge.proposal_id,
        operator_id="op_alice",
        at=NOW + timedelta(seconds=1),
        token=token_huge,
    )

    expected_err = "POST_APPROVAL_RISK_REJECTED:INSUFFICIENT_CASH_OR_CAPACITY"
    with pytest.raises(RuntimeError, match=expected_err):
        pipeline.execute_approved_proposal(
            prop_huge.proposal_id,
            now=NOW + timedelta(seconds=2),
            market_snapshot=clean_snapshot,
            available_cash=Decimal("399700"),
            current_equity=Decimal("100000000"),
        )
