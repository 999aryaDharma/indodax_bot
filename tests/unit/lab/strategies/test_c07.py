"""Unit tests for C07 Bollinger RSI reversion strategy (C07-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.c07 import c07_decide, load_c07_specification


def _build_c07_features(
    as_of: datetime,
    bb_z: float = -2.2,
    bb_width: float = 0.05,
    rsi: float = 25.0,
    adx: float = 0.15,
    di_spread: float = -0.05,
    regime: str = "sideways",
    close: float = 100000000.0,
    pair: str = "btc_idr",
) -> pd.DataFrame:
    """Construct minimal causal feature row for C07 Bollinger RSI evaluation."""
    rows = [
        {
            "pair": pair,
            "decision_ts": as_of,
            "row_ready_at": as_of,
            "close": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "base_volume": 100.0,
            "atr_14": 1500000.0,
            "bb_z": bb_z,
            "bb_width": bb_width,
            "rsi_14": rsi,
            "adx_14": adx,
            "di_spread_14": di_spread,
            "regime": regime,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        }
    ]
    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_c07_01_valid_contract():
    """C07-01-AC0: Kandidat C07 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama."""
    spec = load_c07_specification()
    assert spec.strategy_id == "C07"
    assert spec.family == "mean_reversion"

    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    # Sideways, extreme oversold (bb_z <= -2.0, rsi <= 30)
    df = _build_c07_features(
        as_of=as_of,
        bb_z=-2.5,
        bb_width=0.04,
        rsi=22.0,
        adx=0.15,
        di_spread=-0.02,
        regime="sideways",
    )
    frame = create_decision_frame(df, as_of=as_of)

    intents = c07_decide(frame, spec)
    assert isinstance(intents, list)
    assert len(intents) == 1

    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.strategy_id == "C07"
    assert intent.pair == "btc_idr"
    assert intent.side == OrderSide.BUY
    assert intent.decision_ts == as_of
    assert intent.desired_qty > Decimal("0")
    assert intent.stop_loss is not None
    assert intent.limit_price is not None


def test_c07_01_contract_1():
    """C07-01-AC1: Strong downtrend menolak entry."""
    spec = load_c07_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # Extreme oversold in RSI and BB, BUT in strong downtrend (ADX high, DI spread strongly negative)
    df_downtrend = _build_c07_features(
        as_of=as_of,
        bb_z=-2.8,
        bb_width=0.08,
        rsi=18.0,
        adx=0.40,  # High trend strength
        di_spread=-0.35,  # Strong negative directional movement
        regime="downtrend",
    )
    frame = create_decision_frame(df_downtrend, as_of=as_of)

    intents = c07_decide(frame, spec)
    assert len(intents) == 0, "Strong downtrend knife-catch must be strictly rejected"


def test_c07_01_contract_2():
    """C07-01-AC2: Sideways oversold memberi bounded intent."""
    spec = load_c07_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # Valid sideways oversold condition
    df_sideways = _build_c07_features(
        as_of=as_of,
        bb_z=-2.1,
        bb_width=0.03,
        rsi=28.0,
        adx=0.12,  # Low ADX confirms sideways
        di_spread=0.01,
        regime="sideways",
    )
    frame = create_decision_frame(df_sideways, as_of=as_of)

    intents = c07_decide(frame, spec)
    assert len(intents) == 1, "Sideways oversold must trigger bounded entry intent"
    intent = intents[0]
    assert intent.side == OrderSide.BUY
    assert intent.stop_loss is not None, "Bounded intent must include risk stop-loss"


def test_c07_01_contract_3():
    """C07-01-AC3: Zero band width memberi abstain."""
    spec = load_c07_specification()
    as_of = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

    # Degenerate zero band width (flat market or zero volatility)
    df_zero_band = _build_c07_features(
        as_of=as_of,
        bb_z=-2.5,
        bb_width=0.0,  # Zero bandwidth
        rsi=20.0,
        adx=0.10,
        di_spread=0.0,
        regime="sideways",
    )
    frame = create_decision_frame(df_zero_band, as_of=as_of)

    intents = c07_decide(frame, spec)
    assert len(intents) == 0, "Zero band width must abstain (empty intents)"
