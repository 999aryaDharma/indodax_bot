"""Unit tests for RiskEngine reset governance, confirmation tokens, and throttle persistence."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
from indodax_lab.risk.engine import RiskEngine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
RESET_SECRET = b"risk_engine_super_secret_reset_hmac_key"


@pytest.fixture
def risk_policy() -> RiskPolicy:
    return RiskPolicy(
        policy_id="pol_gov",
        version="1.0",
        max_position_fraction=Decimal("0.25"),
        max_open_positions=3,
        min_order_notional=Decimal("10000"),
        max_drawdown_halt_fraction=Decimal("0.10"),
    )


def test_risk_engine_reset_requires_healthy_reconciliation_and_zero_unknown(
    tmp_path: Path, risk_policy: RiskPolicy
) -> None:
    risk_manager = PortfolioRiskManager(
        policy=risk_policy,
        initial_equity=Decimal("100000000"),
        start_time=NOW,
    )
    ks_path = tmp_path / "emergency_kill_switch"
    engine = RiskEngine(risk_manager=risk_manager, kill_switch_path=ks_path)

    engine.trigger_kill_switch("DISASTER_TRIGGER")
    assert engine.is_kill_switch_active

    # 1. Reset fails if reconciliation is unhealthy
    with pytest.raises(RuntimeError, match="CANNOT_RESET_KILL_SWITCH_UNHEALTHY_RECONCILIATION"):
        engine.reset_kill_switch(
            operator_id="operator_arya",
            reason="SYSTEM_RECOVERED",
            reconciliation_healthy=False,
            unknown_orders_count=0,
        )
    assert engine.is_kill_switch_active

    # 2. Reset fails if unknown orders exist
    with pytest.raises(RuntimeError, match="CANNOT_RESET_KILL_SWITCH_UNKNOWN_ORDERS_EXIST:2"):
        engine.reset_kill_switch(
            operator_id="operator_arya",
            reason="SYSTEM_RECOVERED",
            reconciliation_healthy=True,
            unknown_orders_count=2,
        )
    assert engine.is_kill_switch_active

    # 3. Reset fails if operator_id is blank
    with pytest.raises(ValueError, match="OPERATOR_ID_REQUIRED"):
        engine.reset_kill_switch(
            operator_id="",
            reason="SYSTEM_RECOVERED",
            reconciliation_healthy=True,
            unknown_orders_count=0,
        )

    # 3b. Reset fails if reason is blank
    with pytest.raises(ValueError, match="RESET_REASON_REQUIRED"):
        engine.reset_kill_switch(
            operator_id="operator_arya",
            reason="",
            reconciliation_healthy=True,
            unknown_orders_count=0,
        )

    # 4. Successful reset when conditions are healthy
    engine.reset_kill_switch(
        operator_id="operator_arya",
        reason="SYSTEM_RECOVERED",
        reconciliation_healthy=True,
        unknown_orders_count=0,
    )
    assert not engine.is_kill_switch_active


def test_risk_engine_reset_confirmation_token_verification(
    tmp_path: Path, risk_policy: RiskPolicy
) -> None:
    risk_manager = PortfolioRiskManager(
        policy=risk_policy,
        initial_equity=Decimal("100000000"),
        start_time=NOW,
    )
    ks_path = tmp_path / "emergency_kill_switch"
    engine = RiskEngine(
        risk_manager=risk_manager,
        kill_switch_path=ks_path,
        reset_confirmation_secret=RESET_SECRET,
    )

    engine.trigger_kill_switch("EMERGENCY_HALT")

    # Missing token fails closed
    with pytest.raises(PermissionError, match="CONFIRMATION_TOKEN_REQUIRED"):
        engine.reset_kill_switch(
            operator_id="operator_arya",
            reason="SYSTEM_RECOVERED",
            reconciliation_healthy=True,
            unknown_orders_count=0,
        )

    # Invalid token fails closed
    with pytest.raises(PermissionError, match="INVALID_CONFIRMATION_TOKEN"):
        engine.reset_kill_switch(
            operator_id="operator_arya",
            reason="SYSTEM_RECOVERED",
            reconciliation_healthy=True,
            unknown_orders_count=0,
            confirmation_token="bad_token",
        )

    # Valid token succeeds
    expected_token = hmac.new(
        RESET_SECRET,
        b"RESET_KILL_SWITCH:operator_arya",
        hashlib.sha256,
    ).hexdigest()

    engine.reset_kill_switch(
        operator_id="operator_arya",
        reason="SYSTEM_RECOVERED",
        reconciliation_healthy=True,
        unknown_orders_count=0,
        confirmation_token=expected_token,
    )
    assert not engine.is_kill_switch_active


def test_risk_engine_throttle_history_persistence(tmp_path: Path, risk_policy: RiskPolicy) -> None:
    risk_manager = PortfolioRiskManager(
        policy=risk_policy,
        initial_equity=Decimal("100000000"),
        start_time=NOW,
    )
    throttle_file = tmp_path / "throttle_history.json"

    engine_1 = RiskEngine(
        risk_manager=risk_manager,
        max_orders_per_minute=2,
        throttle_history_path=throttle_file,
    )

    # Assess intent 1
    intent_1 = SignalIntent(
        intent_id="intent_1",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("1000000000"),
    )
    res_1 = engine_1.assess_intent(
        intent_1,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
    )
    assert res_1.approved
    assert throttle_file.exists()

    # Create new RiskEngine instance pointing to same file (simulating restart)
    engine_2 = RiskEngine(
        risk_manager=risk_manager,
        max_orders_per_minute=2,
        throttle_history_path=throttle_file,
    )
    assert len(engine_2._order_timestamps) == 1

    # Second order approved
    intent_2 = SignalIntent(
        intent_id="intent_2",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("1000000000"),
    )
    res_2 = engine_2.assess_intent(
        intent_2,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
    )
    assert res_2.approved

    # Third order rejected by persistent throttle
    intent_3 = SignalIntent(
        intent_id="intent_3",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("1000000000"),
    )
    res_3 = engine_2.assess_intent(
        intent_3,
        current_equity=Decimal("100000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("1000000000")},
        evaluation_time=NOW,
        available_cash=Decimal("100000000"),
    )
    assert not res_3.approved
    assert res_3.reason_code == "RATE_LIMIT_EXCEEDED"
