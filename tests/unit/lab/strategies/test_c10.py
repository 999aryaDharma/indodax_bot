"""Unit tests for C10 Regime ensemble strategy (C10-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c10 import c10_decide, load_c10_specification


def _build_c10_bars(
    as_of: datetime,
    n_bars: int = 25,
    regime: str | None = "trending",
    pair: str = "btc_idr",
) -> pd.DataFrame:
    """Build causal feature frame with breakout conditions and specified regime."""
    start_dt = as_of - timedelta(hours=n_bars - 1)
    rows = []
    base_price = 100000000.0

    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        is_curr = i == n_bars - 1

        if is_curr:
            # Donchian breakout condition: price breaks above prior high with volume
            p = base_price * 1.05
            high_p = p * 1.01
            vol = 500.0
        else:
            p = base_price * (1.0 + 0.001 * (i % 3))
            high_p = base_price * 1.02
            vol = 100.0

        row = {
            "pair": pair,
            "decision_ts": bar_dt,
            "row_ready_at": bar_dt,
            "close": p,
            "high": high_p,
            "low": p * 0.98,
            "volume": vol,
            "base_volume": vol,
            "atr_14": 1500000.0,
            "rsi_14": 25.0,  # oversold for C07
            "bb_lower": base_price * 1.06,  # close below lower band for C07 oversold
            "bb_upper": base_price * 1.08,
            "bb_bandwidth": 0.05,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        }
        if regime is not None:
            row["regime"] = regime

        rows.append(row)

    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_c10_01_valid_contract() -> None:
    """C10-01-AC0: Candidate C10 produces intent comparable with baseline on same judge."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c10_specification()

    # Case 1: Trending regime delegates to C01 Donchian breakout
    df_trend = _build_c10_bars(as_of, regime="trending")
    frame_trend = create_decision_frame(features=df_trend, as_of=as_of)
    intents_trend = c10_decide(frame_trend, spec)

    assert len(intents_trend) == 1
    intent = intents_trend[0]
    assert isinstance(intent, SignalIntent)
    assert intent.side == OrderSide.BUY
    assert intent.strategy_id == "C10"
    assert "C01" in intent.intent_id


def test_c10_01_contract_1() -> None:
    """C10-01-AC1: Unknown regime produces cash (empty intents)."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c10_specification()

    # Case A: Unknown string regime
    df_unknown = _build_c10_bars(as_of, regime="chaos_volatile_unrecognized")
    frame_unknown = create_decision_frame(features=df_unknown, as_of=as_of)
    assert len(c10_decide(frame_unknown, spec)) == 0

    # Case B: None / missing regime
    df_none = _build_c10_bars(as_of, regime=None)
    frame_none = create_decision_frame(features=df_none, as_of=as_of)
    assert len(c10_decide(frame_none, spec)) == 0


def test_c10_01_contract_2() -> None:
    """C10-01-AC2: Future regime change does not alter decision at as_of."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c10_specification()

    # Features up to as_of have 'trending'
    df_base = _build_c10_bars(as_of, regime="trending")
    frame_base = create_decision_frame(features=df_base, as_of=as_of)
    intents_base = c10_decide(frame_base, spec)
    assert len(intents_base) == 1

    # Add a future bar with regime 'chaos' at as_of + 1h
    future_bar = df_base.iloc[[-1]].copy()
    future_bar["decision_ts"] = as_of + timedelta(hours=1)
    future_bar["row_ready_at"] = as_of + timedelta(hours=1)
    future_bar["regime"] = "chaos"

    combined_df = pd.concat([df_base, future_bar], ignore_index=True)
    # create_decision_frame filters out future bars past as_of
    frame_with_future = create_decision_frame(features=combined_df, as_of=as_of)
    intents_with_future = c10_decide(frame_with_future, spec)

    # Output at as_of must be identical
    assert len(intents_with_future) == len(intents_base)
    assert intents_with_future[0].intent_id == intents_base[0].intent_id
    assert intents_with_future[0].limit_price == intents_base[0].limit_price


def test_c10_01_contract_3() -> None:
    """C10-01-AC3: Member version is recorded in intent."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_c10_specification()

    df_trend = _build_c10_bars(as_of, regime="trending")
    frame = create_decision_frame(features=df_trend, as_of=as_of)
    intents = c10_decide(frame, spec)

    assert len(intents) == 1
    intent = intents[0]
    # Check that member ID and version are explicitly recorded in intent_id
    assert "C01" in intent.intent_id
    assert "v1.0.0" in intent.intent_id or "1.0.0" in intent.intent_id
