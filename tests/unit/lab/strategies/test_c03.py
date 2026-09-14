"""Unit tests for C03 Time series momentum strategy (C03-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c03 import c03_decide, load_c03_specification


def _build_c03_bars(
    as_of: datetime,
    n_bars: int = 25,
    trend: str = "positive",
    zero_volatility: bool = False,
    pair: str = "btc_idr",
) -> pd.DataFrame:
    """Build causal feature frame with controlled momentum and volatility."""
    start_dt = as_of - timedelta(hours=n_bars - 1)
    rows = []
    base_price = 100000000.0

    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        if zero_volatility:
            p = base_price
        elif trend == "positive":
            # Rising price with some noise
            p = base_price * (1.0 + 0.005 * i + (0.001 if i % 2 == 0 else -0.001))
        elif trend == "negative":
            # Falling price
            p = base_price * (1.0 - 0.005 * i)
        else:
            p = base_price

        rows.append(
            {
                "pair": pair,
                "decision_ts": bar_dt,
                "row_ready_at": bar_dt,
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


def test_c03_01_valid_contract():
    """C03-01-AC0: Kandidat C03 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama."""
    spec = load_c03_specification()
    assert spec.strategy_id == "C03"
    assert spec.family == "time_series_momentum"

    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    df = _build_c03_bars(as_of=as_of, n_bars=25, trend="positive")
    frame = create_decision_frame(df, as_of=as_of)

    intents = c03_decide(frame, spec)
    assert isinstance(intents, list)
    assert len(intents) == 1

    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C03"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.decision_ts == as_of
    assert intent.desired_qty > Decimal("0")
    assert intent.stop_loss is not None
    assert intent.limit_price is not None


def test_c03_01_contract_1():
    """C03-01-AC1: Negative momentum tetap cash."""
    spec = load_c03_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # Negative lookback return -> price falling
    df_negative = _build_c03_bars(as_of=as_of, n_bars=25, trend="negative")
    frame = create_decision_frame(df_negative, as_of=as_of)

    intents = c03_decide(frame, spec)
    assert len(intents) == 0, "Negative momentum must remain 100% cash (empty intents)"


def test_c03_01_contract_2():
    """C03-01-AC2: Zero volatility memberi reject."""
    spec = load_c03_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # Completely flat price -> zero realized return volatility
    df_zero_vol = _build_c03_bars(as_of=as_of, n_bars=25, zero_volatility=True)
    frame = create_decision_frame(df_zero_vol, as_of=as_of)

    intents = c03_decide(frame, spec)
    assert len(intents) == 0, "Zero volatility must reject / abstain without dividing by zero"


def test_c03_01_contract_3():
    """C03-01-AC3: Future return tidak mengubah sizing."""
    spec = load_c03_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    df = _build_c03_bars(as_of=as_of, n_bars=25, trend="positive")
    frame_as_is = create_decision_frame(df, as_of=as_of)
    intents_1 = c03_decide(frame_as_is, spec)
    assert len(intents_1) == 1
    size_1 = intents_1[0].desired_qty

    # Add a future bar with explosive return
    future_row = {
        "pair": "btc_idr",
        "decision_ts": as_of + timedelta(hours=1),
        "row_ready_at": as_of + timedelta(hours=1),
        "close": 200000000.0,
        "high": 205000000.0,
        "low": 195000000.0,
        "base_volume": 1000.0,
        "atr_14": 1500000.0,
        "eligible": True,
        "missing_feature_count": 0,
        "reason_codes": (),
    }
    df_with_future = pd.concat([df, pd.DataFrame([future_row])], ignore_index=True)
    df_with_future["decision_ts"] = pd.to_datetime(df_with_future["decision_ts"], utc=True)
    df_with_future["row_ready_at"] = pd.to_datetime(df_with_future["row_ready_at"], utc=True)

    # Decision frame filtered to as_of must insulate sizing from future bar
    frame_with_future = create_decision_frame(df_with_future, as_of=as_of)
    intents_2 = c03_decide(frame_with_future, spec)
    assert len(intents_2) == 1
    size_2 = intents_2[0].desired_qty

    assert size_1 == size_2, "Future return must not leak into or alter sizing"
