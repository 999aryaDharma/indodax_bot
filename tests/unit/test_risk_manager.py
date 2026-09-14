from indodax_api import WalletBalance
from risk_manager import calculate_trading_plan
from signal_logic import MarketMode, SignalDecision
from ta_processor import TAResult


def _bullish_decision() -> SignalDecision:
    return SignalDecision(
        pair="btc_idr",
        should_signal=True,
        score=0.8,
        score_pct=80,
        market_mode=MarketMode.BULL,
        ta_1h=TAResult(
            pair="btc_idr",
            timeframe="1h",
            candle_count=60,
            open=100_000.0,
            close=100_000.0,
            high=101_000.0,
            low=99_000.0,
            volume=10.0,
            ema_fast=100_500.0,
            ema_slow=99_500.0,
            stoch_k=30.0,
            stoch_d=25.0,
            stoch_k_prev=25.0,
            stoch_d_prev=20.0,
            macd_line=1.0,
            macd_signal=0.5,
            macd_hist=0.5,
            macd_hist_prev=0.25,
            bb_upper=102_000.0,
            bb_mid=100_000.0,
            bb_lower=98_000.0,
            atr=1_000.0,
            volume_ma=8.0,
            adx=30.0,
            adx_plus_di=25.0,
            adx_minus_di=15.0,
        ),
    )


def test_bullish_plan_meets_rr_gate_without_exceeding_risk_limit() -> None:
    balance = WalletBalance(
        idr_available=500_000.0,
        idr_on_order=0.0,
        idr_total=500_000.0,
        crypto_balances={},
    )

    plan = calculate_trading_plan(_bullish_decision(), balance)

    assert plan is not None
    assert plan.risk_reward_ratio >= 2.0
    assert plan.max_risk_idr <= 10_000.0
