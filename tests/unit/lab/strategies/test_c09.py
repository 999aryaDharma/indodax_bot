"""C09 VWAP deviation reversion acceptance tests."""

from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c09 import c09_decide, load_c09_specification

AS_OF = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)


def _frame(*, deviation=-0.03, slope=0.1, volume=100.0):
    row = {
        "pair": "btc_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "close": 100.0,
        "atr_14": 2.0,
        "base_volume": volume,
        "vwap_dev_24_1h": deviation,
        "ema20_slope_5_1h": slope,
        "adx_14_1h": 0.2,
        "eligible": True,
    }
    return create_decision_frame(pd.DataFrame([row]), as_of=AS_OF)


def test_c09_01_valid_contract():
    intents = c09_decide(_frame(), load_c09_specification())

    assert len(intents) == 1
    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C09"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.desired_qty == Decimal("0.1")
    assert intent.stop_loss == Decimal("97.0")


def test_c09_01_contract_1_zero_denominator_abstains():
    assert c09_decide(_frame(deviation=float("nan")), load_c09_specification()) == []


def test_c09_01_contract_2_falling_price_trend_abstains():
    assert c09_decide(_frame(slope=-0.01), load_c09_specification()) == []


def test_c09_01_contract_3_missing_volume_does_not_become_zero():
    assert c09_decide(_frame(volume=None), load_c09_specification()) == []
