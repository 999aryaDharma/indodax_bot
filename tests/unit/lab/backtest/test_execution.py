"""Conservative execution simulator contract tests (SIM-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest

from indodax_lab.backtest.costs import (
    CostScheduleInterval,
    CostScheduleTable,
    OrderRole,
    OrderSide,
)
from indodax_lab.backtest.events import ExecutionResult, ExecutionStatus, MarketBar, SignalIntent
from indodax_lab.backtest.execution import ConservativeExecutionSimulator


BASE_TS = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_cost_table() -> CostScheduleTable:
    intervals = (
        CostScheduleInterval(
            schedule_id="indodax_2024_buy",
            market="spot_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            valid_from=datetime(2024, 1, 1, tzinfo=UTC),
            valid_to=None,
            service_fee_rate=Decimal("0.002111"),
            tax_rate=Decimal("0.001100"),
            exchange_fee_rate=Decimal("0.000200"),
            min_notional=Decimal("10000"),
            precision=0,
            sources=("PMK 68",),
        ),
        CostScheduleInterval(
            schedule_id="indodax_2024_buy_maker",
            market="spot_idr",
            side=OrderSide.BUY,
            role=OrderRole.MAKER,
            valid_from=datetime(2024, 1, 1, tzinfo=UTC),
            valid_to=None,
            service_fee_rate=Decimal("0.000000"),
            tax_rate=Decimal("0.001100"),
            exchange_fee_rate=Decimal("0.000200"),
            min_notional=Decimal("10000"),
            precision=0,
            sources=("PMK 68",),
        ),
        CostScheduleInterval(
            schedule_id="indodax_2024_sell",
            market="spot_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            valid_from=datetime(2024, 1, 1, tzinfo=UTC),
            valid_to=None,
            service_fee_rate=Decimal("0.002111"),
            tax_rate=Decimal("0.001000"),
            exchange_fee_rate=Decimal("0.000200"),
            min_notional=Decimal("10000"),
            precision=0,
            sources=("PMK 68",),
        ),
    )
    return CostScheduleTable(
        schedule_set_id="test_indodax",
        version="1.0.0",
        intervals=intervals,
    )


def test_sim_01_valid_contract(sample_cost_table: CostScheduleTable) -> None:
    """SIM-01-AC0: Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis."""
    simulator = ConservativeExecutionSimulator(cost_schedule_table=sample_cost_table)

    # Decision made at end of 00:00-01:00 bar (decision_ts = 01:00)
    intent = SignalIntent(
        intent_id="intent-001",
        decision_ts=BASE_TS + timedelta(hours=1),
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        role_preference=OrderRole.TAKER,
        strategy_id="strat-alpha",
    )

    # Next bar is 01:00-02:00
    next_bar = MarketBar(
        pair="btc_idr",
        open_time=BASE_TS + timedelta(hours=1),
        close_time=BASE_TS + timedelta(hours=2),
        open=Decimal("500000000"),
        high=Decimal("505000000"),
        low=Decimal("498000000"),
        close=Decimal("502000000"),
        base_volume=Decimal("1.0"),  # Ample volume
        open_liquidity_base_volume=Decimal("1.0"),
        open_liquidity_available_at=BASE_TS + timedelta(hours=1),
        quote_volume=Decimal("500000000"),
    )

    result = simulator.simulate_execution(intent, next_bar)

    assert result.status == ExecutionStatus.FILLED
    assert result.filled_qty == Decimal("0.001")
    assert result.fill_price == Decimal("500000000")  # Next-bar open price
    assert result.fill is not None
    assert result.fill.timestamp == next_bar.open_time
    assert result.fill.fees > Decimal("0")
    # Gross = 0.001 * 500_000_000 = 500_000 IDR
    # Total rate = 0.002111 + 0.001100 + 0.000200 = 0.003411
    # Expected fee = 500_000 * 0.003411 = 1705.5 -> 1706 IDR (quantized to precision 0)
    assert result.fill.fees == Decimal("1706")


def test_sim_01_contract_1(sample_cost_table: CostScheduleTable) -> None:
    """SIM-01-AC1: Same-close execution ditolak."""
    simulator = ConservativeExecutionSimulator(cost_schedule_table=sample_cost_table)

    decision_ts = BASE_TS + timedelta(hours=1)
    intent = SignalIntent(
        intent_id="intent-lookahead",
        decision_ts=decision_ts,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
    )

    # Attempting to execute on the same bar that closed at decision_ts
    same_bar = MarketBar(
        pair="btc_idr",
        open_time=BASE_TS,
        close_time=decision_ts,
        open=Decimal("495000000"),
        high=Decimal("502000000"),
        low=Decimal("494000000"),
        close=Decimal("500000000"),
        base_volume=Decimal("1.0"),
        quote_volume=Decimal("500000000"),
    )

    result = simulator.simulate_execution(intent, same_bar)

    # Must reject same-close / past bar execution
    assert result.status == ExecutionStatus.REJECTED
    assert result.fill is None
    assert result.filled_qty == Decimal("0")
    assert result.reason_code == "SAME_CLOSE_EXECUTION_FORBIDDEN"


def test_sim_01_contract_2(sample_cost_table: CostScheduleTable) -> None:
    """SIM-01-AC2: Insufficient depth dan min-size menghasilkan reject atau partial."""
    # Max 10% participation rate
    simulator = ConservativeExecutionSimulator(
        cost_schedule_table=sample_cost_table,
        max_participation_rate=Decimal("0.10"),
    )

    # Case A: Min notional rejection
    # Desired qty 0.00001 BTC @ 500_000_000 IDR = 5,000 IDR (< min_notional 10,000 IDR)
    small_intent = SignalIntent(
        intent_id="intent-too-small",
        decision_ts=BASE_TS + timedelta(hours=1),
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.00001"),
    )
    bar = MarketBar(
        pair="btc_idr",
        open_time=BASE_TS + timedelta(hours=1),
        close_time=BASE_TS + timedelta(hours=2),
        open=Decimal("500000000"),
        high=Decimal("502000000"),
        low=Decimal("498000000"),
        close=Decimal("501000000"),
        base_volume=Decimal("10.0"),
        open_liquidity_base_volume=Decimal("10.0"),
        open_liquidity_available_at=BASE_TS + timedelta(hours=1),
        quote_volume=Decimal("5000000000"),
    )
    result_small = simulator.simulate_execution(small_intent, bar)
    assert result_small.status == ExecutionStatus.REJECTED
    assert result_small.reason_code == "MIN_NOTIONAL_VIOLATION"

    # Case B: Insufficient depth produces PARTIAL fill
    # Desired qty: 0.1 BTC. Bar base_volume: 0.5 BTC. Max 10% depth = 0.05 BTC.
    large_intent = SignalIntent(
        intent_id="intent-large",
        decision_ts=BASE_TS + timedelta(hours=1),
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.10"),
    )
    thin_bar = MarketBar(
        pair="btc_idr",
        open_time=BASE_TS + timedelta(hours=1),
        close_time=BASE_TS + timedelta(hours=2),
        open=Decimal("500000000"),
        high=Decimal("502000000"),
        low=Decimal("498000000"),
        close=Decimal("501000000"),
        base_volume=Decimal("0.5"),  # 10% is 0.05 BTC
        open_liquidity_base_volume=Decimal("0.5"),
        open_liquidity_available_at=BASE_TS + timedelta(hours=1),
        quote_volume=Decimal("250000000"),
    )
    result_partial = simulator.simulate_execution(large_intent, thin_bar)
    assert result_partial.status == ExecutionStatus.PARTIAL
    assert result_partial.filled_qty == Decimal("0.05")
    assert result_partial.remaining_qty == Decimal("0.05")
    assert result_partial.reason_code == "PARTIAL_DEPTH"
    assert result_partial.fill is not None
    assert result_partial.fill.qty == Decimal("0.05")


def test_sim_01_contract_3(sample_cost_table: CostScheduleTable) -> None:
    """SIM-01-AC3: Limit touch tidak otomatis maker fill."""
    simulator = ConservativeExecutionSimulator(
        cost_schedule_table=sample_cost_table,
        require_trade_through_for_maker=True,
    )

    # Buy limit order at 498_000_000 IDR
    limit_intent = SignalIntent(
        intent_id="intent-maker-touch",
        decision_ts=BASE_TS + timedelta(hours=1),
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.001"),
        limit_price=Decimal("498000000"),
        role_preference=OrderRole.MAKER,
    )

    # Bar where low EQUALS limit_price (limit touch, but no trade through)
    touch_bar = MarketBar(
        pair="btc_idr",
        open_time=BASE_TS + timedelta(hours=1),
        close_time=BASE_TS + timedelta(hours=2),
        open=Decimal("500000000"),
        high=Decimal("505000000"),
        low=Decimal("498000000"),  # Exact touch!
        close=Decimal("502000000"),
        base_volume=Decimal("1.0"),
        quote_volume=Decimal("500000000"),
    )

    # In conservative execution, touching the limit price alone MUST NOT fill
    result_touch = simulator.simulate_execution(limit_intent, touch_bar)
    assert result_touch.status == ExecutionStatus.REJECTED
    assert result_touch.reason_code == "LIMIT_TOUCH_NO_FILL"

    # Bar where low is STRICTLY LESS than limit_price (trade through)
    trade_through_bar = MarketBar(
        pair="btc_idr",
        open_time=BASE_TS + timedelta(hours=1),
        close_time=BASE_TS + timedelta(hours=2),
        open=Decimal("500000000"),
        high=Decimal("505000000"),
        low=Decimal("497000000"),  # Strict trade-through!
        close=Decimal("502000000"),
        base_volume=Decimal("1.0"),
        quote_volume=Decimal("500000000"),
    )
    result_fill = simulator.simulate_execution(limit_intent, trade_through_bar)
    assert result_fill.status == ExecutionStatus.FILLED
    assert result_fill.fill is not None
    assert result_fill.fill.role == OrderRole.MAKER
    assert result_fill.fill.price == Decimal("498000000")
