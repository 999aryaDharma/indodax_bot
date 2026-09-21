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
        available_cash=Decimal("100000000"),
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
