"""C05 volatility breakout acceptance tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.contracts.decision import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c05 import c05_decide, load_c05_specification


def _rows(*, expansion: bool = True) -> pd.DataFrame:
    start = datetime(2024, 6, 1, tzinfo=UTC)
    rows = []
    for index in range(26):
        if index < 20:
            low, high = 100.0, 110.0
        elif index < 25:
            low, high = 100.0, 104.0
        elif expansion:
            low, high = 100.0, 112.0
        else:
            low, high = 100.0, 105.0
        rows.append(
            {
                "pair": "btc_idr",
                "decision_ts": start + timedelta(hours=index),
                "row_ready_at": start + timedelta(hours=index),
                "high": high,
                "low": low,
                "close": 111.0 if index == 25 and expansion else 103.0,
                "atr_14": 2.5,
                "eligible": True,
            }
        )
    return pd.DataFrame(rows)


def test_c05_01_valid_contract():
    spec = load_c05_specification()
    df = _rows()
    frame = create_decision_frame(df, as_of=df["decision_ts"].max())

    intents = c05_decide(frame, spec)

    assert len(intents) == 1
    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C05"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.desired_qty == Decimal("0.1")
    assert intent.stop_loss == Decimal("106.0")


def test_c05_01_contract_1_future_range_does_not_create_earlier_signal():
    df = _rows(expansion=False)
    future = df.iloc[[-1]].copy()
    future["decision_ts"] += timedelta(hours=1)
    future["row_ready_at"] += timedelta(hours=1)
    future["high"], future["low"], future["close"] = 112.0, 100.0, 111.0
    combined = pd.concat([df.iloc[:-1], future], ignore_index=True)
    visible_at_future = create_decision_frame(
        combined, as_of=combined["decision_ts"].iloc[-1].to_pydatetime()
    )
    assert len(c05_decide(visible_at_future, load_c05_specification())) == 1

    frame = create_decision_frame(
        combined, as_of=df["decision_ts"].iloc[-2].to_pydatetime()
    )

    assert c05_decide(frame, load_c05_specification()) == []


def test_c05_01_contract_2_expansion_gives_intent():
    df = _rows()
    frame = create_decision_frame(df, as_of=df["decision_ts"].max())

    assert len(c05_decide(frame, load_c05_specification())) == 1


def test_c05_01_contract_3_degenerate_range_abstains():
    df = _rows()
    df.loc[df.index[-1], ["high", "low"]] = 100.0
    frame = create_decision_frame(df, as_of=df["decision_ts"].max())

    assert c05_decide(frame, load_c05_specification()) == []
