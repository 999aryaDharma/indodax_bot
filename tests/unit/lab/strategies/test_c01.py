"""Unit tests for C01 Donchian breakout strategy (C01-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import DecisionFrame, StrategySpecification, create_decision_frame
from indodax_lab.strategies.c01 import c01_decide, load_c01_specification


def _build_test_bars(
    n_bars: int,
    base_price: float = 100000000.0,
    breakout_on_last: bool = True,
    volume_spike_on_last: bool = True,
    incomplete_last: bool = False,
) -> pd.DataFrame:
    """Generate causal test feature frame with N completed bars."""
    start_dt = datetime(2024, 6, 1, 0, 0, tzinfo=UTC)
    rows = []
    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        is_last = (i == n_bars - 1)

        if is_last and breakout_on_last:
            # Previous bars high is around 101m. Last bar closes at 103m.
            close_p = base_price * 1.03
            high_p = base_price * 1.04
        else:
            close_p = base_price * 1.00
            high_p = base_price * 1.01

        low_p = base_price * 0.99
        vol = 200.0 if (is_last and volume_spike_on_last) else 100.0

        if is_last and incomplete_last:
            close_p = None

        rows.append(
            {
                "pair": "btc_idr",
                "decision_ts": bar_dt,
                "row_ready_at": bar_dt,
                "close": close_p,
                "high": high_p,
                "low": low_p,
                "base_volume": vol,
                "atr_14": 1500000.0,
                "eligible": True if close_p is not None else False,
                "missing_feature_count": 0 if close_p is not None else 1,
                "reason_codes": (),
            }
        )

    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_c01_01_valid_contract():
    """C01-01-AC0: Kandidat C01 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama."""
    spec = load_c01_specification()
    assert spec.strategy_id == "C01"
    assert spec.family == "breakout"

    df = _build_test_bars(n_bars=25, breakout_on_last=True)
    as_of = df["decision_ts"].max()
    frame = create_decision_frame(df, as_of=as_of)

    intents = c01_decide(frame, spec)
    assert isinstance(intents, list)
    assert len(intents) == 1

    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C01"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.decision_ts == as_of
    assert intent.desired_qty > Decimal("0")
    assert intent.stop_loss is not None
    assert intent.limit_price is not None
    assert intent.stop_loss < intent.limit_price


def test_c01_01_contract_1():
    """C01-01-AC1: Current bar tidak ikut previous high."""
    spec = load_c01_specification()
    # 25 bars. Bars 0..23 have high = 101,000,000.
    # Bar 24 (current) has high = 105,000,000 and close = 102,000,000.
    # If current bar WERE included in previous high, threshold would be 105m and close 102m would NOT breakout.
    # Because current bar is NOT included, threshold is 101m and close 102m DOES breakout!
    df = _build_test_bars(n_bars=25, breakout_on_last=True)
    # Set current bar high very high
    df.loc[df.index[-1], "high"] = 105000000.0
    df.loc[df.index[-1], "close"] = 102000000.0

    as_of = df["decision_ts"].max()
    frame = create_decision_frame(df, as_of=as_of)

    intents = c01_decide(frame, spec)
    assert len(intents) == 1, "Breakout should be confirmed because current bar high must not be in threshold"
    assert intents[0].side == OrderSide.BUY


def test_c01_01_contract_2():
    """C01-01-AC2: Breakout confirmed menghasilkan LONG."""
    spec = load_c01_specification()

    # Case A: Confirmed breakout (close > previous high AND volume >= avg volume)
    df_breakout = _build_test_bars(n_bars=25, breakout_on_last=True, volume_spike_on_last=True)
    as_of = df_breakout["decision_ts"].max()
    frame_breakout = create_decision_frame(df_breakout, as_of=as_of)
    intents_long = c01_decide(frame_breakout, spec)
    assert len(intents_long) == 1
    assert intents_long[0].side == OrderSide.BUY

    # Case B: No breakout (close <= previous high)
    df_no_breakout = _build_test_bars(n_bars=25, breakout_on_last=False, volume_spike_on_last=True)
    frame_no_breakout = create_decision_frame(df_no_breakout, as_of=as_of)
    intents_none = c01_decide(frame_no_breakout, spec)
    assert len(intents_none) == 0, "No breakout should produce FLAT (empty intents)"

    # Case C: Price broke out but volume gate failed
    df_low_vol = _build_test_bars(n_bars=25, breakout_on_last=True, volume_spike_on_last=False)
    # Set volume well below average
    df_low_vol.loc[df_low_vol.index[-1], "base_volume"] = 10.0
    frame_low_vol = create_decision_frame(df_low_vol, as_of=as_of)
    intents_vol_fail = c01_decide(frame_low_vol, spec)
    assert len(intents_vol_fail) == 0, "Volume gate failure should produce FLAT (empty intents)"


def test_c01_01_contract_3():
    """C01-01-AC3: Incomplete bar menghasilkan FLAT."""
    spec = load_c01_specification()

    # Case A: Incomplete lookback window (only 10 bars when 20 required)
    df_short = _build_test_bars(n_bars=10, breakout_on_last=True)
    as_of_short = df_short["decision_ts"].max()
    frame_short = create_decision_frame(df_short, as_of=as_of_short)
    intents_short = c01_decide(frame_short, spec)
    assert len(intents_short) == 0, "Incomplete lookback window must produce FLAT"

    # Case B: Current bar is incomplete (eligible=False or missing values)
    df_incomplete = _build_test_bars(n_bars=25, incomplete_last=True)
    as_of_inc = df_incomplete["decision_ts"].max()
    frame_inc = create_decision_frame(df_incomplete, as_of=as_of_inc)
    intents_inc = c01_decide(frame_inc, spec)
    assert len(intents_inc) == 0, "Incomplete bar must produce FLAT"
