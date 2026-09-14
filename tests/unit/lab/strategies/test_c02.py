"""Unit tests for C02 EMA pullback strategy (C02-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c02 import c02_decide, load_c02_specification


def _build_c02_bars(
    as_of: datetime,
    regime: str = "uptrend",
    pullback_state: str = "recovered",
    pair: str = "btc_idr",
) -> pd.DataFrame:
    """Build causal feature bars with fast EMA (20) and slow EMA (50)."""
    # 2 bars: previous bar (t-1h) and current decision bar (t)
    t_prev = as_of - timedelta(hours=1)

    if regime == "uptrend":
        slow_ema = 100000000.0  # EMA 50
        fast_ema = 105000000.0  # EMA 20

        if pullback_state == "recovered":
            # Previous bar dipped below fast EMA (low <= 105m)
            prev_row = {
                "pair": pair,
                "decision_ts": t_prev,
                "row_ready_at": t_prev,
                "close": 104500000.0,
                "high": 106000000.0,
                "low": 104000000.0,  # dipped below fast_ema
                "base_volume": 100.0,
                "atr_14": 1500000.0,
                "ema_fast": fast_ema,
                "ema_slow": slow_ema,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
            # Current bar closed back above fast EMA (close > 105m)
            curr_row = {
                "pair": pair,
                "decision_ts": as_of,
                "row_ready_at": as_of,
                "close": 106000000.0,  # recovered above fast_ema
                "high": 106500000.0,
                "low": 105100000.0,
                "base_volume": 120.0,
                "atr_14": 1500000.0,
                "ema_fast": fast_ema,
                "ema_slow": slow_ema,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
        elif pullback_state == "unrecovered":
            # Previous bar dipped, current bar still below fast EMA
            prev_row = {
                "pair": pair,
                "decision_ts": t_prev,
                "row_ready_at": t_prev,
                "close": 104500000.0,
                "high": 105500000.0,
                "low": 104000000.0,
                "base_volume": 100.0,
                "atr_14": 1500000.0,
                "ema_fast": fast_ema,
                "ema_slow": slow_ema,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
            curr_row = {
                "pair": pair,
                "decision_ts": as_of,
                "row_ready_at": as_of,
                "close": 104800000.0,  # still below fast_ema 105m!
                "high": 105000000.0,
                "low": 104200000.0,
                "base_volume": 90.0,
                "atr_14": 1500000.0,
                "ema_fast": fast_ema,
                "ema_slow": slow_ema,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
        else:  # no pullback
            prev_row = {
                "pair": pair,
                "decision_ts": t_prev,
                "row_ready_at": t_prev,
                "close": 107000000.0,
                "high": 108000000.0,
                "low": 106500000.0,
                "base_volume": 100.0,
                "atr_14": 1500000.0,
                "ema_fast": fast_ema,
                "ema_slow": slow_ema,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
            curr_row = {
                "pair": pair,
                "decision_ts": as_of,
                "row_ready_at": as_of,
                "close": 108000000.0,
                "high": 108500000.0,
                "low": 107500000.0,
                "base_volume": 100.0,
                "atr_14": 1500000.0,
                "ema_fast": fast_ema,
                "ema_slow": slow_ema,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
    else:
        # Downtrend: EMA fast < EMA slow, price below slow EMA
        slow_ema = 100000000.0
        fast_ema = 95000000.0
        prev_row = {
            "pair": pair,
            "decision_ts": t_prev,
            "row_ready_at": t_prev,
            "close": 94000000.0,
            "high": 95000000.0,
            "low": 93000000.0,
            "base_volume": 100.0,
            "atr_14": 1500000.0,
            "ema_fast": fast_ema,
            "ema_slow": slow_ema,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        }
        curr_row = {
            "pair": pair,
            "decision_ts": as_of,
            "row_ready_at": as_of,
            "close": 96000000.0,  # Bounced above fast, but overall in downtrend!
            "high": 96500000.0,
            "low": 94500000.0,
            "base_volume": 100.0,
            "atr_14": 1500000.0,
            "ema_fast": fast_ema,
            "ema_slow": slow_ema,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        }

    df = pd.DataFrame([prev_row, curr_row])
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_c02_01_valid_contract():
    """C02-01-AC0: Kandidat C02 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama."""
    spec = load_c02_specification()
    assert spec.strategy_id == "C02"
    assert spec.family == "trend_pullback"

    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    df = _build_c02_bars(as_of=as_of, regime="uptrend", pullback_state="recovered")
    frame = create_decision_frame(df, as_of=as_of)

    intents = c02_decide(frame, spec)
    assert isinstance(intents, list)
    assert len(intents) == 1

    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C02"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.decision_ts == as_of
    assert intent.desired_qty > Decimal("0")
    assert intent.stop_loss is not None
    assert intent.limit_price is not None
    assert intent.stop_loss < intent.limit_price


def test_c02_01_contract_1():
    """C02-01-AC1: Downtrend menolak buy."""
    spec = load_c02_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # Market in downtrend: fast EMA < slow EMA and price < slow EMA
    df_downtrend = _build_c02_bars(as_of=as_of, regime="downtrend")
    frame = create_decision_frame(df_downtrend, as_of=as_of)

    intents = c02_decide(frame, spec)
    assert len(intents) == 0, "Downtrend must strictly reject buy intents"


def test_c02_01_contract_2():
    """C02-01-AC2: Pullback belum recovered tidak entry."""
    spec = load_c02_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # In uptrend, but price is still sitting below fast EMA (unrecovered pullback)
    df_unrecovered = _build_c02_bars(as_of=as_of, regime="uptrend", pullback_state="unrecovered")
    frame = create_decision_frame(df_unrecovered, as_of=as_of)

    intents = c02_decide(frame, spec)
    assert len(intents) == 0, "Pullback not yet recovered above fast EMA must not enter"


def test_c02_01_contract_3():
    """C02-01-AC3: Recovery closed bar memberi intent."""
    spec = load_c02_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # In uptrend, prior bar pulled back below fast EMA, and current closed bar closed back above fast EMA
    df_recovered = _build_c02_bars(as_of=as_of, regime="uptrend", pullback_state="recovered")
    frame = create_decision_frame(df_recovered, as_of=as_of)

    intents = c02_decide(frame, spec)
    assert len(intents) == 1, "Confirmed recovery bar must emit LONG intent"
    intent = intents[0]
    assert intent.side == OrderSide.BUY
    assert intent.limit_price == Decimal("106000000")
