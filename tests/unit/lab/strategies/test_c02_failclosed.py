"""Fail-closed regression for C02-01 (blocking review findings).

Unknown EMA/ATR must not convert to zero and pass the regime gate.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd

from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c02 import c02_decide, load_c02_specification


def _bars(as_of, drop=None):
    t_prev = as_of - timedelta(hours=1)

    def row(dt, close, low):
        return {
            "pair": "btc_idr",
            "decision_ts": dt,
            "row_ready_at": dt,
            "close": close,
            "high": close * 1.01,
            "low": low,
            "base_volume": 100.0,
            "atr_14": 1500000.0,
            "ema_fast": 105000000.0,
            "ema_slow": 100000000.0,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        }

    df = pd.DataFrame(
        [
            row(t_prev, 104500000.0, 104000000.0),
            row(as_of, 106000000.0, 105100000.0),
        ]
    )
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    if drop:
        df = df.drop(columns=list(drop))
    return df


def test_c02_missing_slow_ema_blocks_trade():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c02_specification()
    frame = create_decision_frame(_bars(as_of, drop=["ema_slow"]), as_of=as_of)
    assert c02_decide(frame, spec) == []


def test_c02_missing_fast_ema_blocks_trade():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c02_specification()
    frame = create_decision_frame(_bars(as_of, drop=["ema_fast"]), as_of=as_of)
    assert c02_decide(frame, spec) == []


def test_c02_missing_atr_blocks_trade():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c02_specification()
    frame = create_decision_frame(_bars(as_of, drop=["atr_14"]), as_of=as_of)
    assert c02_decide(frame, spec) == []
