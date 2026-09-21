"""Tests for RiskEngine operational, market health, and financial gates."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
from indodax_lab.market.health import MarketHealthState
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


@pytest.fixture
def sample_risk_engine(tmp_path: Path):
    policy = RiskPolicy(
        policy_id="pol_test",
        version="1.0",
        max_position_fraction=Decimal("0.25"),
        max_open_positions=3,
        min_order_notional=Decimal("10000"),
        max_drawdown_halt_fraction=Decimal("0.10"),
    )
    risk_manager = PortfolioRiskManager(
        policy=policy,
        initial_equity=Decimal("100000000"),
        start_time=NOW,
    )
    kill_switch_file = tmp_path / "emergency_kill_switch"
    return RiskEngine(
        risk_manager=risk_manager,
        max_orders_per_minute=3,
        kill_switch_path=kill_switch_file,
    )


def test_risk_engine_normal_approval_creates_oms_order(sample_risk_engine: RiskEngine) -> None:
    engine = sample_risk_engine
    intent = SignalIntent(
        intent_id="sig_norm",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("1000000000"),
    )

    assessment = engine.assess_intent(
        intent,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
    )

    assert assessment.approved
    assert assessment.approved_qty == Decimal("0.02")

    oms_order = engine.create_oms_order_from_assessment(
        intent,
        assessment,
        internal_order_id="int_order_1",
        client_order_id="cl_order_1",
        created_at=NOW,
    )

    assert oms_order.internal_order_id == "int_order_1"
    assert oms_order.desired_qty == Decimal("0.02")
    assert oms_order.pair == "btc_idr"


def test_risk_engine_programmatic_kill_switch(sample_risk_engine: RiskEngine) -> None:
    engine = sample_risk_engine
    intent = SignalIntent(
        intent_id="sig_ks",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("1000000000"),
    )

    engine.trigger_kill_switch("CRITICAL_VOLATILITY")
    assert engine.is_kill_switch_active

    assessment = engine.assess_intent(
        intent,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
    )
    assert not assessment.approved
    assert assessment.reason_code == "KILL_SWITCH_ACTIVE"

    # Reset kill switch
    engine.reset_kill_switch()
    assert not engine.is_kill_switch_active


def test_risk_engine_file_kill_switch(sample_risk_engine: RiskEngine) -> None:
    engine = sample_risk_engine
    assert engine.kill_switch_path is not None
    # Create file externally (operator intervention)
    engine.kill_switch_path.write_text("MANUAL_OPERATOR_HALT", encoding="utf-8")

    assert engine.is_kill_switch_active
    intent = SignalIntent(
        intent_id="sig_ks_file",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("1000000000"),
    )
    assessment = engine.assess_intent(
        intent,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
    )
    assert not assessment.approved
    assert assessment.reason_code == "KILL_SWITCH_ACTIVE"


def test_risk_engine_unsafe_market_health_blocks_buys(sample_risk_engine: RiskEngine) -> None:
    engine = sample_risk_engine
    intent = SignalIntent(
        intent_id="sig_unsafe",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("1000000000"),
    )

    assessment = engine.assess_intent(
        intent,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
        market_health=MarketHealthState.CLOCK_UNSAFE,
    )
    assert not assessment.approved
    assert assessment.reason_code == "MARKET_HEALTH_UNSAFE"


def test_risk_engine_rate_limit_throttle(sample_risk_engine: RiskEngine) -> None:
    engine = sample_risk_engine
    # Max orders per minute = 3
    for i in range(3):
        intent = SignalIntent(
            intent_id=f"sig_rate_{i}",
            decision_ts=NOW,
            pair="btc_idr",
            side=OrderSide.BUY,
            desired_qty=Decimal("0.001"),
            limit_price=Decimal("1000000000"),
        )
        res = engine.assess_intent(
            intent,
            current_equity=Decimal("100000000"),
            current_positions={},
            mark_prices={"btc_idr": Decimal("1000000000")},
            evaluation_time=NOW,
            available_cash=Decimal("100000000"),
        )
        assert res.approved

    # 4th order within same minute should be rejected
    fourth_intent = SignalIntent(
        intent_id="sig_rate_4",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("1000000000"),
    )
    fourth_res = engine.assess_intent(
        fourth_intent,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
    )
    assert not fourth_res.approved
    assert fourth_res.reason_code == "RATE_LIMIT_EXCEEDED"
