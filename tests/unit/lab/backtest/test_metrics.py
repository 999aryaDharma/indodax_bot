"""Unit tests for net-cost risk, performance, and capacity metrics (SIM-04)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest

from indodax_lab.backtest.ledger import AccountType, ResearchLedger
from indodax_lab.backtest.metrics import (
    CostStressMetrics,
    PerformanceMetrics,
    ProfitFactorResult,
    calculate_equity,
    compute_performance_metrics,
)
from indodax_lab.backtest.orders import Fill, OrderRole, OrderSide


BASE_TIME = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)


def _populate_sample_ledger(ledger: ResearchLedger) -> None:
    # 1. Buy 0.01 BTC at 500,000,000 with 5000 fee
    fill_buy = Fill(
        fill_id="fill-buy-1",
        order_id="ord-buy-1",
        event_id="evt-buy-1",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("500000000"),
        qty=Decimal("0.01"),
        fees=Decimal("5000"),
        timestamp=BASE_TIME,
    )
    ledger.process_fill(fill_buy)

    # 2. Sell 0.01 BTC at 550,000,000 with 5500 fee -> Gain 500,000 gross
    fill_sell = Fill(
        fill_id="fill-sell-1",
        order_id="ord-sell-1",
        event_id="evt-sell-1",
        pair="btc_idr",
        side=OrderSide.SELL,
        role=OrderRole.TAKER,
        price=Decimal("550000000"),
        qty=Decimal("0.01"),
        fees=Decimal("5500"),
        timestamp=BASE_TIME + timedelta(hours=2),
    )
    ledger.process_fill(fill_sell)

    # 3. Buy 0.01 BTC at 600,000,000 with 6000 fee
    fill_buy_2 = Fill(
        fill_id="fill-buy-2",
        order_id="ord-buy-2",
        event_id="evt-buy-2",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("600000000"),
        qty=Decimal("0.01"),
        fees=Decimal("6000"),
        timestamp=BASE_TIME + timedelta(days=1),
    )
    ledger.process_fill(fill_buy_2)

    # 4. Sell 0.01 BTC at 580,000,000 with 5800 fee -> Loss 200,000 gross
    fill_sell_2 = Fill(
        fill_id="fill-sell-2",
        order_id="ord-sell-2",
        event_id="evt-sell-2",
        pair="btc_idr",
        side=OrderSide.SELL,
        role=OrderRole.TAKER,
        price=Decimal("580000000"),
        qty=Decimal("0.01"),
        fees=Decimal("5800"),
        timestamp=BASE_TIME + timedelta(days=1, hours=2),
    )
    ledger.process_fill(fill_sell_2)


def test_sim_04_valid_contract() -> None:
    """SIM-04-AC0: Performance report computes metrics from ledger with cost stress and capacity bounds."""
    ledger = ResearchLedger(initial_cash=Decimal("10000000"))
    _populate_sample_ledger(ledger)

    equity_curve = [
        (BASE_TIME, Decimal("10000000")),
        (BASE_TIME + timedelta(hours=2), Decimal("10489500")),
        (BASE_TIME + timedelta(days=1, hours=2), Decimal("10277700")),
    ]

    metrics = compute_performance_metrics(
        ledger=ledger,
        equity_curve=equity_curve,
        rejected_orders=[{"order_id": "rej-1", "reason": "MAX_DRAWDOWN_HALT"}],
        spread_data={"btc_idr": Decimal("50000")},
    )

    # Invariants
    assert metrics.initial_cash == Decimal("10000000")
    assert metrics.ending_cash == Decimal("10277700")
    assert metrics.ending_equity == Decimal("10277700")

    # Gross: +500,000 - 200,000 = +300,000
    assert metrics.total_gross_pnl == Decimal("300000")
    # Fees: 5000 + 5500 + 6000 + 5800 = 22300
    assert metrics.total_fees_paid == Decimal("22300")
    # Net: 300,000 - 22,300 = 277,700
    assert metrics.total_net_pnl == Decimal("277700")

    # Profit factor: gross_profit 500,000 / gross_loss 200,000 = 2.5
    assert metrics.profit_factor.defined is True
    assert metrics.profit_factor.value == Decimal("2.5")

    # Trade counts
    assert metrics.trade_count == 2
    assert metrics.win_count == 1
    assert metrics.loss_count == 1
    assert metrics.win_rate == Decimal("0.5")

    # Stress testing: 1.5x and 2.0x
    assert metrics.stress_1_5x.multiplier == Decimal("1.5")
    assert metrics.stress_1_5x.stressed_fees == Decimal("22300") * Decimal("1.5")
    assert metrics.stress_1_5x.stressed_net_pnl == Decimal("300000") - (Decimal("22300") * Decimal("1.5"))

    assert metrics.stress_2_0x.multiplier == Decimal("2.0")
    assert metrics.stress_2_0x.stressed_fees == Decimal("22300") * Decimal("2.0")
    assert metrics.stress_2_0x.stressed_net_pnl == Decimal("300000") - (Decimal("22300") * Decimal("2.0"))

    # Breakdown by year and asset
    assert "2024" in metrics.by_year
    assert "btc_idr" in metrics.by_asset
    assert metrics.rejected_order_count == 1
    assert metrics.spread_status == "AVAILABLE"
    assert metrics.spread_cost == Decimal("50000")


def test_sim_04_contract_1() -> None:
    """SIM-04-AC1: No-trade and zero-loss PF produce well-reasoned undefined outcomes."""
    # Scenario A: No trades
    empty_ledger = ResearchLedger(initial_cash=Decimal("500000"))
    metrics_no_trade = compute_performance_metrics(ledger=empty_ledger)
    assert metrics_no_trade.trade_count == 0
    assert metrics_no_trade.profit_factor.defined is False
    assert metrics_no_trade.profit_factor.value is None
    assert metrics_no_trade.profit_factor.reason == "NO_TRADES"

    # Scenario B: Zero loss (all winning trades)
    win_ledger = ResearchLedger(initial_cash=Decimal("10000000"))
    fill_buy = Fill(
        fill_id="fill-buy-w",
        order_id="ord-buy-w",
        event_id="evt-buy-w",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("500000000"),
        qty=Decimal("0.01"),
        fees=Decimal("5000"),
        timestamp=BASE_TIME,
    )
    fill_sell = Fill(
        fill_id="fill-sell-w",
        order_id="ord-sell-w",
        event_id="evt-sell-w",
        pair="btc_idr",
        side=OrderSide.SELL,
        role=OrderRole.TAKER,
        price=Decimal("600000000"),
        qty=Decimal("0.01"),
        fees=Decimal("6000"),
        timestamp=BASE_TIME + timedelta(hours=1),
    )
    win_ledger.process_fill(fill_buy)
    win_ledger.process_fill(fill_sell)

    metrics_win = compute_performance_metrics(ledger=win_ledger)
    assert metrics_win.trade_count == 1
    assert metrics_win.profit_factor.defined is False
    assert metrics_win.profit_factor.value is None
    assert metrics_win.profit_factor.reason == "ZERO_LOSS"


def test_sim_04_contract_2() -> None:
    """SIM-04-AC2: Fee is not double-subtracted from net cash equity."""
    initial_cash = Decimal("10000000")
    ledger = ResearchLedger(initial_cash=initial_cash)

    # Buy asset: 5,000,000 gross + 5,000 fee
    fill_buy = Fill(
        fill_id="fill-buy-c2",
        order_id="ord-buy-c2",
        event_id="evt-buy-c2",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("500000000"),
        qty=Decimal("0.01"),
        fees=Decimal("5000"),
        timestamp=BASE_TIME,
    )
    ledger.process_fill(fill_buy)

    # Cash in ledger is 10,000,000 - 5,005,000 = 4,995,000
    assert ledger.cash == Decimal("4995000")

    # Mark price equals buy price -> marked asset value = 5,000,000
    mark_prices = {"btc_idr": Decimal("500000000")}
    marked_asset_value = Decimal("5000000")

    # Equity = Cash + Marked Asset Value = 4,995,000 + 5,000,000 = 9,995,000
    equity = calculate_equity(cash=ledger.cash, marked_asset_value=marked_asset_value)
    assert equity == Decimal("9995000")

    # Fee was already debited from cash. If subtracted again, it would be 9,990,000
    assert equity != Decimal("9995000") - Decimal("5000")

    # Total net PnL at mark equals Unrealized (0) - Fees Paid (5,000) = -5,000
    # Equity - Initial Cash = 9,995,000 - 10,000,000 = -5,000 (Exact match)
    assert equity - initial_cash == -Decimal("5000")


def test_sim_04_contract_3() -> None:
    """SIM-04-AC3: Missing spread is never reported as zero cost."""
    ledger = ResearchLedger(initial_cash=Decimal("10000000"))
    _populate_sample_ledger(ledger)

    # Pass None for spread_data
    metrics_missing_spread = compute_performance_metrics(
        ledger=ledger,
        spread_data=None,
    )

    # Must be None, NEVER Decimal("0")
    assert metrics_missing_spread.spread_cost is None
    assert metrics_missing_spread.spread_status == "MISSING_SPREAD"
    assert "MISSING_SPREAD: Cost and capacity estimate requires empirical spread data" in metrics_missing_spread.capacity_notes
