"""C08 multi-timeframe confirmation acceptance tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c08 import c08_decide, load_c08_specification

AS_OF = datetime(2024, 6, 3, 12, 0, tzinfo=UTC)


def _frame(*, daily_closed=True, daily_age_hours=24):
    daily_ts = AS_OF - timedelta(hours=daily_age_hours)
    h4_ts = AS_OF - timedelta(hours=4)
    row = {
        "pair": "btc_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "daily_decision_ts": daily_ts,
        "daily_row_ready_at": daily_ts + timedelta(minutes=5),
        "daily_closed": daily_closed,
        "daily_close": 115.0,
        "daily_ema_fast": 112.0,
        "daily_ema_slow": 110.0,
        "four_hour_decision_ts": h4_ts,
        "four_hour_row_ready_at": h4_ts + timedelta(minutes=5),
        "four_hour_closed": True,
        "four_hour_close": 114.0,
        "four_hour_ema_fast": 112.0,
        "four_hour_ema_slow": 110.0,
        "close": 113.0,
        "lower_prev_20_high": 112.0,
        "atr_14": 2.5,
        "eligible": True,
    }
    return create_decision_frame(pd.DataFrame([row]), as_of=AS_OF)


def test_c08_01_valid_contract():
    intents = c08_decide(_frame(), load_c08_specification())

    assert len(intents) == 1
    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C08"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.desired_qty == Decimal("0.1")
    assert intent.stop_loss == Decimal("108.0")


def test_c08_01_contract_1_partial_daily_trend_is_rejected():
    assert c08_decide(_frame(daily_closed=False), load_c08_specification()) == []


def test_c08_01_contract_2_stale_higher_timeframe_abstains():
    assert c08_decide(_frame(daily_age_hours=37), load_c08_specification()) == []


def test_c08_01_contract_3_confirmed_alignment_gives_long():
    assert len(c08_decide(_frame(), load_c08_specification())) == 1
