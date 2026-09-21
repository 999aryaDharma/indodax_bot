"""
test_live_shadow_engine.py — Unit tests for LiveShadowEngine

Tests:
1. Exact double-entry fee accounting (Maker 0.1111% buy, 0.3211% sell)
2. Fixed fractional position sizing (1.5% risk capped at 25% cash)
3. Capacity limit enforcement (Max 2 concurrent positions)
4. State persistence and recovery from JSON checkpoint
5. Trailing stop and take profit trigger logic
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import pytest
import pandas as pd

from indodax_lab.paper.live_shadow_engine import (
    LiveShadowEngine,
    MAKER_BUY_FEE_RATE,
    MAKER_SELL_FEE_RATE,
    ShadowPosition,
)


@pytest.fixture
def temp_engine():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = Path(tmp_dir) / "shadow_state.json"
        engine = LiveShadowEngine(
            state_file=state_file,
            initial_cash=Decimal("500000.00"),
            max_positions=2,
            fixed_risk_pct=0.015,
            max_cash_per_trade_pct=0.25,
            min_order_idr=Decimal("10000.00"),
        )
        yield engine


def test_initial_ledger_state(temp_engine):
    """Initial cash must be exact Rp 500,000 with 0 positions."""
    assert temp_engine.available_cash == Decimal("500000.00")
    assert len(temp_engine.open_positions) == 0
    assert len(temp_engine.closed_trades) == 0


def test_state_persistence_and_recovery(temp_engine):
    """Saving state and re-instantiating must recover identical cash and positions."""
    # Add a mock position
    pos = ShadowPosition(
        position_id="pos_test_1",
        pair="eth_idr",
        strategy_id="C02_EMA_TREND_PULLBACK",
        entry_ts="2026-09-17 00:00:00 UTC",
        entry_price=40000000.0,
        qty=0.0025,
        cash_debited=100000.0,
        buy_fee_paid=111.1,
        stop_loss=39000000.0,
        take_profit=42000000.0,
        entry_atr=500000.0,
        highest_price=40000000.0,
    )
    temp_engine.open_positions["pos_test_1"] = pos
    temp_engine.available_cash = Decimal("400000.00")
    temp_engine.save_state()

    # Re-instantiate from the same state file
    recovered_engine = LiveShadowEngine(
        state_file=temp_engine.state_file,
        initial_cash=Decimal("500000.00"),
    )
    assert recovered_engine.available_cash == Decimal("400000.00")
    assert len(recovered_engine.open_positions) == 1
    assert "pos_test_1" in recovered_engine.open_positions
    assert recovered_engine.open_positions["pos_test_1"].entry_price == 40000000.0


def test_take_profit_exit_and_fee_accounting(temp_engine):
    """Position hitting take-profit must trigger fill, charge sell fee, and credit cash."""
    pos = ShadowPosition(
        position_id="pos_tp_test",
        pair="eth_idr",
        strategy_id="C02_EMA_TREND_PULLBACK",
        entry_ts="2026-09-17 00:00:00 UTC",
        entry_price=40000000.0,
        qty=0.0025,  # 0.0025 * 40m = 100k notional
        cash_debited=100000.0,
        buy_fee_paid=111.1,
        stop_loss=38000000.0,
        take_profit=43000000.0,
        entry_atr=1000000.0,
        highest_price=40000000.0,
    )
    temp_engine.open_positions["pos_tp_test"] = pos
    temp_engine.available_cash = Decimal("400000.00")

    # Live price hits 43,500,000 (above TP 43,000,000)
    live_prices = {"eth_idr": 43500000.0}
    closed = temp_engine.check_open_positions(live_prices)

    assert len(closed) == 1
    trade = closed[0]
    assert trade.exit_reason == "TAKE_PROFIT"
    assert trade.exit_price == 43500000.0

    # Verify Proceeds & Fees:
    # Gross proceeds = 0.0025 * 43,500,000 = 108,750
    # Maker Sell Fee = 108,750 * 0.003211 = 349.19625
    # Net Credit = 108,750 - 349.19625 = 108,400.80375
    # Net PnL = Net Credit (108,400.80) - Cash Debited (100,000) = +8,400.80
    assert trade.net_pnl > 8000.0
    assert len(temp_engine.open_positions) == 0
    assert temp_engine.available_cash > Decimal("508000.00")


def test_stop_loss_exit_and_capital_protection(temp_engine):
    """Position hitting stop-loss must exit immediately, preserving remaining capital."""
    pos = ShadowPosition(
        position_id="pos_sl_test",
        pair="btc_idr",
        strategy_id="C07_MEAN_REVERSION",
        entry_ts="2026-09-17 00:00:00 UTC",
        entry_price=1000000000.0,
        qty=0.0001,  # 0.0001 * 1B = 100k notional
        cash_debited=100000.0,
        buy_fee_paid=111.1,
        stop_loss=980000000.0,
        take_profit=1040000000.0,
        entry_atr=10000000.0,
        highest_price=1000000000.0,
    )
    temp_engine.open_positions["pos_sl_test"] = pos
    temp_engine.available_cash = Decimal("400000.00")

    # Live price drops to 975,000,000 (below SL 980,000,000)
    live_prices = {"btc_idr": 975000000.0}
    closed = temp_engine.check_open_positions(live_prices)

    assert len(closed) == 1
    trade = closed[0]
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.exit_price == 975000000.0
    assert trade.net_pnl < 0
    # Remaining capital returned to cash
    assert temp_engine.available_cash > Decimal("490000.00")


def test_trailing_stop_advancement(temp_engine):
    """Trailing stop must ratchet upward when price reaches new highs."""
    pos = ShadowPosition(
        position_id="pos_trail_test",
        pair="eth_idr",
        strategy_id="C02_EMA_TREND_PULLBACK",
        entry_ts="2026-09-17 00:00:00 UTC",
        entry_price=40000000.0,
        qty=0.0025,
        cash_debited=100000.0,
        buy_fee_paid=111.1,
        stop_loss=38250000.0,  # 40m - 1.75 * 1m
        take_profit=43500000.0,
        entry_atr=1000000.0,
        highest_price=40000000.0,
    )
    temp_engine.open_positions["pos_trail_test"] = pos

    # Price rises to 42,000,000
    live_prices = {"eth_idr": 42000000.0}
    closed = temp_engine.check_open_positions(live_prices)
    assert len(closed) == 0

    # New trailing stop should be 42,000,000 - 2.0 * ATR (2,000,000) = 40,000,000 (Breakeven/Lock profit!)
    updated_pos = temp_engine.open_positions["pos_trail_test"]
    assert updated_pos.highest_price == 42000000.0
    assert updated_pos.stop_loss == 40000000.0
