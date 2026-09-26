"""Fail-closed regression for C03-01 (blocking review findings).

Unknown ATR must not produce a stop==entry intent; degenerate
zero start price must abstain, not raise.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd

from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c03 import c03_decide, load_c03_specification


def _bars(as_of, n=25, base=100000000.0):
    start = as_of - timedelta(hours=n - 1)
    rows = []
    for i in range(n):
        dt = start + timedelta(hours=i)
        p = base * (1.0 + 0.005 * i + (0.001 if i % 2 == 0 else -0.001))
        rows.append(
            {
                "pair": "btc_idr",
                "decision_ts": dt,
                "row_ready_at": dt,
                "close": p,
                "high": p * 1.01,
                "low": p * 0.99,
                "base_volume": 100.0,
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


def test_c03_missing_atr_blocks_trade():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c03_specification()
    df = _bars(as_of).drop(columns=["atr_14"])
    frame = create_decision_frame(df, as_of=as_of)
    assert c03_decide(frame, spec) == []


def test_c03_zero_start_price_abstains_without_exception():
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c03_specification()
    df = _bars(as_of)
    df.loc[df.index[0], "close"] = 0.0
    frame = create_decision_frame(df, as_of=as_of)
    assert c03_decide(frame, spec) == []
