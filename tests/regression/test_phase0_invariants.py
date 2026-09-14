"""Phase 0 public-behavior checkpoint; all exercised paths must stay offline."""

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
import requests

from indodax_api import WalletBalance, _parse_my_trades_v2
from paper_accounting import account_buy, account_sell, realized_pnl
from risk_manager import calculate_trading_plan
from signal_logic import MarketMode, SignalDecision
from signal_observer import SignalObserver, resolve_barriers
from ta_processor import TAResult

pytestmark = pytest.mark.no_network

_TRADE_FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "indodax" / "my_trades_v2.json"
)


def _bullish_decision() -> SignalDecision:
    return SignalDecision(
        pair="btc_idr",
        should_signal=True,
        score=0.8,
        score_pct=80,
        market_mode=MarketMode.BULL,
        ta_1h=TAResult(
            pair="btc_idr", timeframe="1h", candle_count=60,
            open=100_000.0, close=100_000.0, high=101_000.0, low=99_000.0,
            volume=10.0, ema_fast=100_500.0, ema_slow=99_500.0,
            stoch_k=30.0, stoch_d=25.0, stoch_k_prev=25.0, stoch_d_prev=20.0,
            macd_line=1.0, macd_signal=0.5, macd_hist=0.5, macd_hist_prev=0.25,
            bb_upper=102_000.0, bb_mid=100_000.0, bb_lower=98_000.0,
            atr=1_000.0, volume_ma=8.0, adx=30.0, adx_plus_di=25.0,
            adx_minus_di=15.0,
        ),
    )


def test_phase0_public_invariants_are_reconciled_and_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch missing Phase 0 aggregation, marker, or offline public contracts."""
    monkeypatch.setattr(
        requests.sessions.Session,
        "request",
        lambda *_args, **_kwargs: pytest.fail("Phase 0 regression made a network request"),
    )

    plan = calculate_trading_plan(
        _bullish_decision(),
        WalletBalance(500_000.0, 0.0, 500_000.0, {}),
    )
    assert plan is not None
    assert plan.risk_reward_ratio >= 2.0
    assert plan.max_risk_idr <= 10_000.0

    trade = _parse_my_trades_v2(json.loads(_TRADE_FIXTURE.read_text()), "aave_idr")[0]
    assert (
        trade.pair,
        trade.trade_id,
        trade.order_id,
        trade.price,
        trade.amount,
        trade.quote_amount,
        trade.commission,
        trade.commission_asset,
        trade.is_buyer,
        trade.is_maker,
        trade.timestamp_ms,
        trade.timestamp,
    ) == (
        "aave_idr",
        "72057594037936570",
        "aaveidr-limit-3568",
        1_564_455.0,
        0.1,
        156_445.5,
        468.0,
        "idr",
        False,
        False,
        1_723_442_692_520,
        1_723_442_692.52,
    )

    buy = account_buy(Decimal("100000"), Decimal("10000"), Decimal("0.002"))
    sell = account_sell(buy.base_qty, Decimal("11000"), Decimal("0.004"))
    assert (buy.cash_debit, buy.base_qty, sell.net_credit, realized_pnl(buy, sell)) == (
        Decimal("100000"), Decimal("9.98"), Decimal("109340.880"), Decimal("9340.880"),
    )

    observer = SignalObserver(db_path=tmp_path / "observations.db", clock=lambda: 1_001.0)
    observation_id = observer.record_candidate(
        pair="btc_idr", strategy="SNIPER", strategy_version="signal_logic_v1",
        score=0.82, passed=False, reason="score below gate",
        dataset_version="live_ohlcv_v1", runtime_version="ibs_runtime_v1",
    )
    with sqlite3.connect(tmp_path / "observations.db") as conn:
        intent_count = conn.execute(
            "SELECT COUNT(*) FROM signal_action_intents"
        ).fetchone()[0]
        shadow_status = conn.execute(
            "SELECT shadow_status FROM signal_observations WHERE id = ?",
            (observation_id,),
        ).fetchone()[0]
    assert intent_count == 0
    assert shadow_status == "NOT_OPENED"

    resolution = resolve_barriers(
        bar_high=112,
        bar_low=88,
        stop_loss=90,
        take_profit=110,
    )
    assert resolution is not None
    assert (resolution.reason, resolution.fill_price) == ("SL", 90)
