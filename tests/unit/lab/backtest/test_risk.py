"""Portfolio risk, position sizing, and circuit breaker contract tests (SIM-02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import Position
from indodax_lab.backtest.risk import (
    PortfolioRiskManager,
    RiskAssessmentResult,
    RiskPolicy,
)


BASE_TS = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def default_policy() -> RiskPolicy:
    return RiskPolicy(
        policy_id="core_risk_v1",
        version="1.0.0",
        max_position_fraction=Decimal("0.20"),  # Max 20% of equity per position
        max_open_positions=3,
        min_order_notional=Decimal("10000"),    # 10,000 IDR min notional
        max_daily_loss_fraction=Decimal("0.05"), # 5% daily loss limit
        max_weekly_loss_fraction=Decimal("0.10"),# 10% weekly loss limit
        max_drawdown_halt_fraction=Decimal("0.15"), # 15% drawdown halts portfolio
    )


def test_sim_02_valid_contract(default_policy: RiskPolicy) -> None:
    """SIM-02-AC0: Sizing menghormati modal bersama, exposure dan batas rugi sebelum order dibuat."""
    risk_manager = PortfolioRiskManager(
        policy=default_policy,
        initial_equity=Decimal("1000000"),
        start_time=BASE_TS,
    )

    # Strategy requests 0.001 BTC @ 500_000_000 IDR = 500_000 IDR (50% of equity)
    intent = SignalIntent(
        intent_id="intent-01",
        decision_ts=BASE_TS,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
    )

    # Risk manager caps position size to max_position_fraction (20% of 1,000,000 = 200,000 IDR)
    result = risk_manager.assess_order(
        intent=intent,
        current_equity=Decimal("1000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("500000000")},
        evaluation_time=BASE_TS,
        available_cash=Decimal("1000000"),
    )

    assert result.approved is True
    assert result.reason_code == "APPROVED"
    assert result.approved_notional == Decimal("200000")
    # Approved qty = 200_000 / 500_000_000 = 0.0004 BTC
    assert result.approved_qty == Decimal("0.0004")


def test_sim_02_contract_1(default_policy: RiskPolicy) -> None:
    """SIM-02-AC1: Size di bawah minimum ditolak bukan dibulatkan naik."""
    risk_manager = PortfolioRiskManager(
        policy=default_policy,
        initial_equity=Decimal("1000000"),
        start_time=BASE_TS,
    )

    # Strategy requests 0.00001 BTC @ 500_000_000 IDR = 5,000 IDR (< min_order_notional 10,000 IDR)
    intent = SignalIntent(
        intent_id="intent-small",
        decision_ts=BASE_TS,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.00001"),
    )

    result = risk_manager.assess_order(
        intent=intent,
        current_equity=Decimal("1000000"),
        current_positions={},
        mark_prices={"btc_idr": Decimal("500000000")},
        evaluation_time=BASE_TS,
        available_cash=Decimal("1000000"),
    )

    # Must be REJECTED, NEVER rounded up to 10,000 IDR
    assert result.approved is False
    assert result.approved_qty == Decimal("0")
    assert result.reason_code == "BELOW_MIN_SIZE_REJECTED"


def test_sim_02_contract_2(default_policy: RiskPolicy) -> None:
    """SIM-02-AC2: Daily dan weekly loss memasukkan unrealized PnL."""
    risk_manager = PortfolioRiskManager(
        policy=default_policy,
        initial_equity=Decimal("1000000"),
        start_time=BASE_TS,
    )

    # We hold 0.001 BTC bought at 500_000_000 IDR (cost basis 500_000 IDR)
    # Cash is 500_000 IDR.
    # Now BTC crashes to 440_000_000 IDR.
    # Unrealized position value = 0.001 * 440_000_000 = 440_000 IDR.
    # Total equity = 500_000 (cash) + 440_000 (unrealized mark) = 940_000 IDR.
    # Daily loss = (1_000_000 - 940_000) / 1_000_000 = 6% loss (> max_daily_loss 5%).
    positions = {
        "btc_idr": Position(pair="btc_idr", base_qty=Decimal("0.001"), cost_basis=Decimal("500000"))
    }
    mark_prices = {"btc_idr": Decimal("440000000"), "eth_idr": Decimal("50000000")}

    new_intent = SignalIntent(
        intent_id="intent-during-crash",
        decision_ts=BASE_TS + timedelta(hours=4),
        pair="eth_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.002"),
    )

    result = risk_manager.assess_order(
        intent=new_intent,
        current_equity=Decimal("940000"),
        current_positions=positions,
        mark_prices=mark_prices,
        evaluation_time=BASE_TS + timedelta(hours=4),
        available_cash=Decimal("500000"),
    )

    # Must reject due to daily loss breach that incorporates unrealized loss
    assert result.approved is False
    assert result.reason_code == "CIRCUIT_BREAKER_DAILY_LOSS"


def test_sim_02_contract_3(default_policy: RiskPolicy, tmp_path: Path) -> None:
    """SIM-02-AC3: Drawdown halt tidak hilang setelah restart."""
    risk_manager = PortfolioRiskManager(
        policy=default_policy,
        initial_equity=Decimal("1000000"),
        start_time=BASE_TS,
    )

    # Equity experiences severe drawdown from peak of 1,000,000 to 830,000 (17% DD > 15% halt limit)
    mark_prices = {"btc_idr": Decimal("500000000")}
    intent = SignalIntent(
        intent_id="intent-before-restart",
        decision_ts=BASE_TS + timedelta(days=2),
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
    )

    result = risk_manager.assess_order(
        intent=intent,
        current_equity=Decimal("830000"),
        current_positions={},
        mark_prices=mark_prices,
        evaluation_time=BASE_TS + timedelta(days=2),
        available_cash=Decimal("830000"),
    )
    assert result.approved is False
    assert result.reason_code == "CIRCUIT_BREAKER_DRAWDOWN_HALT"
    assert risk_manager.is_halted is True

    # Persist state to disk
    state_path = tmp_path / "risk_state.json"
    risk_manager.save_to_json(state_path)

    # Simulate restart by instantiating fresh risk manager from persisted state
    restarted_risk_manager = PortfolioRiskManager.load_from_json(state_path)

    # Even if market appears to recover slightly to 840,000, the drawdown halt MUST PERSIST
    subsequent_intent = SignalIntent(
        intent_id="intent-after-restart",
        decision_ts=BASE_TS + timedelta(days=3),
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.0001"),
    )
    result_after_restart = restarted_risk_manager.assess_order(
        intent=subsequent_intent,
        current_equity=Decimal("840000"),
        current_positions={},
        mark_prices=mark_prices,
        evaluation_time=BASE_TS + timedelta(days=3),
        available_cash=Decimal("840000"),
    )

    assert restarted_risk_manager.is_halted is True
    assert result_after_restart.approved is False
    assert result_after_restart.reason_code == "CIRCUIT_BREAKER_DRAWDOWN_HALT"
