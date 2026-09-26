"""C06 directional trend strength acceptance tests."""

from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c06 import c06_decide, load_c06_specification

AS_OF = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)


def _frame(*, adx=0.4, di_spread=0.2, atr=2.5):
    row = {
        "pair": "btc_idr",
        "decision_ts": AS_OF,
        "row_ready_at": AS_OF,
        "close": 100.0,
        "atr_14": atr,
        "adx_14": adx,
        "di_spread_14": di_spread,
        "eligible": True,
    }
    return create_decision_frame(pd.DataFrame([row]), as_of=AS_OF)


def test_c06_01_valid_contract():
    spec = load_c06_specification()

    intents = c06_decide(_frame(), spec)

    assert len(intents) == 1
    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C06"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.desired_qty == Decimal("0.1")
    assert intent.stop_loss == Decimal("95.0")


def test_c06_01_contract_1_high_adx_negative_di_does_not_buy():
    assert c06_decide(_frame(adx=0.8, di_spread=-0.2), load_c06_specification()) == []


def test_c06_01_contract_2_incomplete_warmup_abstains():
    assert c06_decide(_frame(adx=float("nan")), load_c06_specification()) == []


def test_c06_01_contract_3_threshold_equality_is_deterministic():
    spec = load_c06_specification()

    assert len(c06_decide(_frame(adx=0.25, di_spread=0.01), spec)) == 1
    assert c06_decide(_frame(adx=0.25, di_spread=0.0), spec) == []
