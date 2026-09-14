"""Unit tests for S01 Liquidity screened breakout strategy (S01-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.s01 import c01_decide_s01 as s01_decide, load_s01_specification


def _build_s01_bars(
    as_of: datetime,
    n_bars: int = 25,
    breakout: bool = True,
    spread_bps: float | None = 15.0,
    depth: float | None = 1.0,
    pair: str = "btc_idr",
) -> pd.DataFrame:
    """Build causal feature frame for S01 with controllable breakout, spread, and depth."""
    start_dt = as_of - timedelta(hours=n_bars - 1)
    rows = []
    base_price = 100000000.0

    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        is_curr = i == n_bars - 1

        if is_curr and breakout:
            p = base_price * 1.10  # strong breakout above prior range
            high_p = p * 1.02
            vol = 500.0
        else:
            p = base_price * (1.0 + 0.001 * (i % 5))
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
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        }

        # Liquidity fields on current bar
        if is_curr:
            if spread_bps is not None:
                row["spread_bps"] = spread_bps
            if depth is not None:
                row["depth_50bps"] = depth

        rows.append(row)

    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_s01_01_valid_contract() -> None:
    """S01-01-AC0: Breakout with normal spread and sufficient depth produces valid intent."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s01_specification()

    df = _build_s01_bars(as_of, breakout=True, spread_bps=15.0, depth=1.0)
    frame = create_decision_frame(features=df, as_of=as_of)

    intents = s01_decide(frame, spec)
    assert len(intents) == 1
    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.side == OrderSide.BUY
    assert intent.pair == "btc_idr"
    assert intent.desired_qty == Decimal("0.1")
    assert intent.strategy_id == "S01"
    assert intent.limit_price is not None
    assert intent.stop_loss is not None
    assert intent.stop_loss < intent.limit_price


def test_s01_01_contract_1() -> None:
    """S01-01-AC1: Wide spread rejects breakout entry."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s01_specification()

    # Spread of 60 bps exceeds max_spread_bps of 30.0
    df = _build_s01_bars(as_of, breakout=True, spread_bps=60.0, depth=1.0)
    frame = create_decision_frame(features=df, as_of=as_of)

    intents = s01_decide(frame, spec)
    assert len(intents) == 0


def test_s01_01_contract_2() -> None:
    """S01-01-AC2: Insufficient depth restricts order size to available depth."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s01_specification()

    # Depth is 0.04 (< base_qty 0.1)
    df = _build_s01_bars(as_of, breakout=True, spread_bps=15.0, depth=0.04)
    frame = create_decision_frame(features=df, as_of=as_of)

    intents = s01_decide(frame, spec)
    assert len(intents) == 1
    intent = intents[0]
    assert intent.desired_qty == Decimal("0.04")


def test_s01_01_contract_3() -> None:
    """S01-01-AC3: Missing liquidity blocks trade."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s01_specification()

    # Case A: Missing spread_bps
    df_no_spread = _build_s01_bars(as_of, breakout=True, spread_bps=None, depth=1.0)
    frame_a = create_decision_frame(features=df_no_spread, as_of=as_of)
    assert len(s01_decide(frame_a, spec)) == 0

    # Case B: Missing depth
    df_no_depth = _build_s01_bars(as_of, breakout=True, spread_bps=15.0, depth=None)
    frame_b = create_decision_frame(features=df_no_depth, as_of=as_of)
    assert len(s01_decide(frame_b, spec)) == 0
