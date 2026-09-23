"""
test_live_shadow_engine.py — Unit tests for LiveShadowEngine

Tests:
1. Time-valid fee accounting and conservative taker proxy semantics
2. Fixed fractional position sizing (1.5% risk capped at 25% cash)
3. Capacity limit enforcement (Max 2 concurrent positions)
4. State persistence and recovery from transactional SQLite checkpoint
5. Trailing stop and take profit trigger logic
"""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
import tempfile

import pandas as pd
import pytest

from indodax_lab.backtest.costs import CostScheduleTable, OrderRole, OrderSide
from indodax_lab.backtest.orders import Fill

from indodax_lab.paper.live_shadow_engine import (
    FEATURE_COLS,
    LiveShadowEngine,
    ShadowPosition,
)




def _seed_open_position(engine: LiveShadowEngine, pos: ShadowPosition) -> None:
    """Create a test position through the same double-entry boundary as runtime."""
    cash_debit = Decimal(str(pos.cash_debited))
    requested_fee = Decimal(str(pos.buy_fee_paid))
    requested_gross = cash_debit - requested_fee
    qty = (requested_gross / Decimal(str(pos.entry_price))).quantize(
        Decimal("0.00000001"),
        rounding=ROUND_DOWN,
    )
    gross = qty * Decimal(str(pos.entry_price))
    fee = cash_debit - gross
    pos.qty = float(qty)
    pos.buy_fee_paid = float(fee)
    fill = Fill(
        fill_id=f"seed-{pos.position_id}",
        order_id=f"seed-order-{pos.position_id}",
        event_id=f"seed-event-{pos.position_id}",
        pair=pos.pair,
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=qty,
        price=Decimal(str(pos.entry_price)),
        fees=fee,
        timestamp=datetime(2026, 9, 17, tzinfo=UTC),
        fee_components={"total": fee},
    )
    engine.ledger.process_fill(fill)
    engine.open_positions[pos.position_id] = pos
    engine._assert_accounting_consistency()


@pytest.fixture
def temp_engine():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = Path(tmp_dir) / "shadow_state.sqlite3"
        engine = LiveShadowEngine(
            state_file=state_file,
            initial_cash=Decimal("500000.00"),
            max_positions=2,
            fixed_risk_pct=0.015,
            max_cash_per_trade_pct=0.25,
            min_order_idr=Decimal("10000.00"),
        )
        engine.cost_table = CostScheduleTable(
            schedule_set_id="paper-test-fixture",
            version="1",
            intervals=tuple(
                interval.model_copy(update={"evidence_verified": True})
                for interval in engine.cost_table.intervals
            ),
        )
        yield engine


def test_initial_ledger_state(temp_engine):
    """Initial cash must be exact Rp 500,000 with 0 positions."""
    assert temp_engine.available_cash == Decimal("500000.00")
    assert len(temp_engine.open_positions) == 0
    assert len(temp_engine.closed_trades) == 0
    assert all(tx.is_balanced for tx in temp_engine.ledger.transactions)


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
    _seed_open_position(temp_engine, pos)
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
    assert recovered_engine.ledger.cash == Decimal("400000.00")
    assert all(tx.is_balanced for tx in recovered_engine.ledger.transactions)


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
    _seed_open_position(temp_engine, pos)

    # Live price hits 43,500,000 (above TP 43,000,000)
    live_prices = {"eth_idr": 43500000.0}
    closed = temp_engine.check_open_positions(live_prices)

    assert len(closed) == 1
    trade = closed[0]
    assert trade.exit_reason == "TAKE_PROFIT"
    assert trade.exit_price == 43000000.0

    # TP proxy is capped at the target (43m), never rewarded with the better 43.5m ticker.
    # Runtime sell cost is resolved point-in-time as taker, not assumed maker.
    assert trade.net_pnl > 6000.0
    assert len(temp_engine.open_positions) == 0
    assert temp_engine.available_cash > Decimal("506000.00")


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
    _seed_open_position(temp_engine, pos)

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
    _seed_open_position(temp_engine, pos)

    # Price rises to 42,000,000
    live_prices = {"eth_idr": 42000000.0}
    closed = temp_engine.check_open_positions(live_prices)
    assert len(closed) == 0

    # New trailing stop should be 42,000,000 - 2.0 * ATR (2,000,000) = 40,000,000 (Breakeven/Lock profit!)
    updated_pos = temp_engine.open_positions["pos_trail_test"]
    assert updated_pos.highest_price == 42000000.0
    assert updated_pos.stop_loss == 40000000.0



def test_missing_model_fails_closed(temp_engine):
    """A missing model must never become a neutral 0.50 probability."""
    temp_engine.models.clear()
    temp_engine.metadata.clear()
    features = pd.Series({name: 0.0 for name in [
        "log_ret_1", "log_ret_6", "log_ret_24", "atr_pct_14",
        "ema_ratio_20_50", "dist_ema_200", "bb_z", "bb_width",
        "rsi_14", "adx_14", "vol_z_20",
    ]})
    assert temp_engine.predict_probability("btc_idr", features) is None


def test_bars_held_advances_only_on_new_closed_bar(temp_engine):
    """Polling the same closed 1h candle repeatedly must not age a position."""
    pos = ShadowPosition(
        position_id="pos_clock_test",
        pair="eth_idr",
        strategy_id="C02_EMA_TREND_PULLBACK",
        entry_ts="2026-09-17 00:00:00 UTC",
        entry_price=40000000.0,
        qty=0.0025,
        cash_debited=100000.0,
        buy_fee_paid=100.0,
        stop_loss=35000000.0,
        take_profit=50000000.0,
        entry_atr=1000000.0,
        highest_price=40000000.0,
        last_bar_timestamp=100,
    )
    _seed_open_position(temp_engine, pos)
    prices = {"eth_idr": 40500000.0}

    same_bar = {"eth_idr": pd.DataFrame([{"timestamp": 100}])}
    temp_engine.check_open_positions(prices, same_bar)
    temp_engine.check_open_positions(prices, same_bar)
    assert temp_engine.open_positions[pos.position_id].bars_held == 0

    next_bar = {"eth_idr": pd.DataFrame([{"timestamp": 200}])}
    temp_engine.check_open_positions(prices, next_bar)
    assert temp_engine.open_positions[pos.position_id].bars_held == 1



def _market_frame(latest_start: datetime) -> pd.DataFrame:
    timestamps = [
        int((latest_start - timedelta(hours=199 - index)).timestamp())
        for index in range(200)
    ]
    prices = [100_000_000.0 + index * 10_000.0 for index in range(200)]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices,
            "high": [price * 1.001 for price in prices],
            "low": [price * 0.999 for price in prices],
            "close": prices,
            "base_volume": [1.0 + (index % 7) for index in range(200)],
        }
    )


def test_model_metadata_schema_mismatch_fails_closed(temp_engine):
    pair = "btc_idr"
    temp_engine.models[pair] = object()
    temp_engine.metadata[pair] = {
        "feature_means": {FEATURE_COLS[0]: 0.0},
        "feature_stds": {FEATURE_COLS[0]: 1.0},
        "calibration": {"a": 1.0, "b": 0.0},
    }
    features = pd.Series({name: 0.0 for name in FEATURE_COLS})

    assert temp_engine.predict_probability(pair, features) is None


def test_missing_live_ticker_rejects_entry_before_model(temp_engine):
    latest_start = datetime.now(UTC) - timedelta(minutes=70)
    frame = _market_frame(latest_start)

    results = temp_engine.evaluate_market_scan({}, {"btc_idr": frame})

    assert len(results) == 1
    assert results[0]["action"] == "REJECT_MARKET_DATA_UNAVAILABLE"


def test_stale_closed_bar_rejects_entry_before_model(temp_engine):
    latest_start = datetime.now(UTC) - timedelta(hours=4)
    frame = _market_frame(latest_start)

    results = temp_engine.evaluate_market_scan(
        {"btc_idr": 102_000_000.0},
        {"btc_idr": frame},
    )

    assert len(results) == 1
    assert results[0]["action"] == "REJECT_STALE_MARKET_DATA"


def test_legacy_json_checkpoint_requires_explicit_migration(tmp_path):
    state_file = tmp_path / "shadow_state.sqlite3"
    state_file.with_suffix(".json").write_text("{}", encoding="utf-8")

    with pytest.raises(
        RuntimeError,
        match="LEGACY_SHADOW_JSON_STATE_REQUIRES_EXPLICIT_MIGRATION",
    ):
        LiveShadowEngine(
            state_file=state_file,
            initial_cash=Decimal("500000.00"),
        )
