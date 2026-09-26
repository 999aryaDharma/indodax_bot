"""Fail-closed regression for C01-01 (blocking review findings).

Unknown volume/ATR must not convert to zero and pass the gate.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd

from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c01 import c01_decide, load_c01_specification


def _bars(as_of, n=25, base=100000000.0):
    start = as_of - timedelta(hours=n - 1)
    rows = []
    for i in range(n):
        dt = start + timedelta(hours=i)
        last = i == n - 1
        close = base * 1.03 if last else base
        high = base * 1.04 if last else base * 1.01
        rows.append(
            {
                "pair": "btc_idr",
                "decision_ts": dt,
                "row_ready_at": dt,
                "close": close,
                "high": high,
                "low": base * 0.99,
                "base_volume": 200.0 if last else 100.0,
                "atr_14": 1500000.0,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
        )
    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_c01_missing_volume_blocks_trade():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c01_specification()
    df = _bars(as_of).drop(columns=["base_volume"])
    frame = create_decision_frame(df, as_of=as_of)
    assert c01_decide(frame, spec) == []


def test_c01_zero_avg_volume_blocks_trade():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c01_specification()
    df = _bars(as_of)
    df["base_volume"] = 0.0
    frame = create_decision_frame(df, as_of=as_of)
    assert c01_decide(frame, spec) == []


def test_c01_missing_atr_blocks_trade():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c01_specification()
    df = _bars(as_of).drop(columns=["atr_14"])
    frame = create_decision_frame(df, as_of=as_of)
    assert c01_decide(frame, spec) == []
