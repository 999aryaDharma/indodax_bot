"""Unit tests for S02 Squeeze expansion strategy (S02-01)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.strategies.base import create_decision_frame
from indodax_lab.strategies.s02 import load_s02_specification, s02_decide


def _build_s02_bars(
    as_of: datetime,
    n_bars: int = 25,
    scenario: str = "valid_expansion",
    pair: str = "btc_idr",
) -> pd.DataFrame:
    """Build causal feature frame with controlled squeeze and expansion dynamics.

    Scenarios:
    - 'valid_expansion': prior bars in tight squeeze, current bar expands with high volume and normal gap.
    - 'squeeze_only': all bars (including current) remain in tight squeeze without expansion.
    - 'expansion_no_volume': current bar expands above upper BB, but volume is low.
    - 'gap_over_chase_cap': current bar expands but price gaps up excessively (> max_chase_pct).
    """
    start_dt = as_of - timedelta(hours=n_bars - 1)
    rows = []
    base_price = 100000000.0

    for i in range(n_bars):
        bar_dt = start_dt + timedelta(hours=i)
        is_curr = i == n_bars - 1

        if not is_curr:
            # Squeeze regime: extremely tight price range so BB width < KC width
            p = base_price * (1.0 + 0.0002 * (1 if i % 2 == 0 else -1))
            high_p = p * 1.001
            low_p = p * 0.999
            vol = 100.0
            atr_val = 2000000.0  # Large ATR ensures KC width is wide relative to compressed BB
        else:
            atr_val = 2000000.0
            if scenario == "valid_expansion":
                # Clean expansion: price pops 2% with 2.5x volume
                p = base_price * 1.02
                high_p = p * 1.005
                low_p = p * 0.995
                vol = 300.0  # 3x average volume
            elif scenario == "squeeze_only":
                # Remains compressed
                p = base_price * (1.0 + 0.0002)
                high_p = p * 1.001
                low_p = p * 0.999
                vol = 100.0
            elif scenario == "expansion_no_volume":
                # Expands price but with weak volume
                p = base_price * 1.02
                high_p = p * 1.005
                low_p = p * 0.995
                vol = 80.0  # < average volume
            elif scenario == "gap_over_chase_cap":
                # Massive gap up (e.g. 7% gap when cap is 3%)
                p = base_price * 1.07
                high_p = p * 1.01
                low_p = p * 0.99
                vol = 500.0
            else:
                p = base_price
                high_p = p * 1.001
                low_p = p * 0.999
                vol = 100.0

        rows.append(
            {
                "pair": pair,
                "decision_ts": bar_dt,
                "row_ready_at": bar_dt,
                "close": p,
                "high": high_p,
                "low": low_p,
                "volume": vol,
                "base_volume": vol,
                "atr_14": atr_val,
                "eligible": True,
                "missing_feature_count": 0,
                "reason_codes": (),
            }
        )

    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def test_s02_01_valid_contract() -> None:
    """S02-01-AC0: Candidate S02 produces intent comparable with baseline on same judge."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s02_specification()

    df = _build_s02_bars(as_of, scenario="valid_expansion")
    frame = create_decision_frame(features=df, as_of=as_of)

    intents = s02_decide(frame, spec)
    assert len(intents) == 1
    intent = intents[0]
    assert isinstance(intent, SignalIntent)
    assert intent.side == OrderSide.BUY
    assert intent.pair == "btc_idr"
    assert intent.desired_qty == Decimal("0.1")
    assert intent.strategy_id == "S02"
    assert intent.limit_price is not None
    assert intent.stop_loss is not None
    assert intent.stop_loss < intent.limit_price


def test_s02_01_contract_1() -> None:
    """S02-01-AC1: Squeeze alone does not enter."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s02_specification()

    df = _build_s02_bars(as_of, scenario="squeeze_only")
    frame = create_decision_frame(features=df, as_of=as_of)

    intents = s02_decide(frame, spec)
    assert len(intents) == 0


def test_s02_01_contract_2() -> None:
    """S02-01-AC2: Expansion without volume is rejected."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s02_specification()

    df = _build_s02_bars(as_of, scenario="expansion_no_volume")
    frame = create_decision_frame(features=df, as_of=as_of)

    intents = s02_decide(frame, spec)
    assert len(intents) == 0


def test_s02_01_contract_3() -> None:
    """S02-01-AC3: Gap above chase cap is rejected."""
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s02_specification()

    df = _build_s02_bars(as_of, scenario="gap_over_chase_cap")
    frame = create_decision_frame(features=df, as_of=as_of)

    intents = s02_decide(frame, spec)
    assert len(intents) == 0


def test_s02_bands_self_referential_regression() -> None:
    """REGRESSION: Current bar included in band calculation (self-referential).
    
    The code uses `curr_window = p_df.iloc[-lookback_bars:]` which includes
    the current decision bar. Expansion check should use PRIOR window only,
    like `prev_bb_upper` from prior_window.
    """
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    spec = load_s02_specification()
    
    # Build a scenario where prior window was in squeeze, 
    # but current bar expansion would fail if current bar contaminates bands
    start_dt = as_of - timedelta(hours=24)
    rows = []
    base_price = 100000000.0
    
    # 24 prior bars: tight squeeze
    for i in range(24):
        bar_dt = start_dt + timedelta(hours=i)
        p = base_price * (1.0 + 0.0001 * (1 if i % 2 == 0 else -1))
        rows.append({
            "pair": "btc_idr",
            "decision_ts": bar_dt,
            "row_ready_at": bar_dt,
            "close": p,
            "high": p * 1.001,
            "low": p * 0.999,
            "volume": 100.0,
            "base_volume": 100.0,
            "atr_14": 2000000.0,
            "eligible": True,
            "missing_feature_count": 0,
            "reason_codes": (),
        })
    
    # Current bar: expands significantly above prior high
    curr_dt = start_dt + timedelta(hours=24)
    rows.append({
        "pair": "btc_idr",
        "decision_ts": curr_dt,
        "row_ready_at": curr_dt,
        "close": base_price * 1.02,  # 2% expansion (under 3% chase cap)
        "high": base_price * 1.025,
        "low": base_price * 1.015,
        "volume": 500.0,  # High volume
        "base_volume": 500.0,
        "atr_14": 2000000.0,
        "eligible": True,
        "missing_feature_count": 0,
        "reason_codes": (),
    })
    
    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    frame = create_decision_frame(features=df, as_of=as_of)
    
    intents = s02_decide(frame, spec)
    # Should still detect expansion correctly - using prior_window only
    # This test ensures we don't regress to self-referential bands
    assert len(intents) == 1, "Valid expansion should be detected using prior bands only"


@pytest.mark.parametrize("case", ["missing", "zero", "nan"])
def test_s02_missing_or_invalid_volume_abstains(case: str) -> None:
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    df = _build_s02_bars(as_of, scenario="valid_expansion")
    if case == "missing":
        df = df.drop(columns=["base_volume", "volume"])
    elif case == "zero":
        df.loc[:, ["base_volume", "volume"]] = 0.0
    else:
        df.loc[df.index[-1], ["base_volume", "volume"]] = float("nan")

    assert s02_decide(create_decision_frame(df, as_of), load_s02_specification()) == []


@pytest.mark.parametrize("atr", [float("nan"), 100000000.0])
def test_s02_invalid_or_unbounded_atr_abstains(atr: float) -> None:
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    df = _build_s02_bars(as_of, scenario="valid_expansion")
    df.loc[df.index[-1], "atr_14"] = atr

    assert s02_decide(create_decision_frame(df, as_of), load_s02_specification()) == []


@pytest.mark.parametrize("problem", ["stale", "gap"])
def test_s02_stale_or_discontinuous_lookback_abstains(problem: str) -> None:
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    df = _build_s02_bars(as_of, scenario="valid_expansion")
    if problem == "stale":
        df.loc[:, ["decision_ts", "row_ready_at"]] -= timedelta(hours=1)
    else:
        df.loc[df.index[-2], ["decision_ts", "row_ready_at"]] -= timedelta(hours=1)

    assert s02_decide(create_decision_frame(df, as_of), load_s02_specification()) == []


@pytest.mark.parametrize("problem", ["missing_close", "infinite_atr"])
def test_s02_incomplete_lookback_abstains(problem: str) -> None:
    as_of = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    df = _build_s02_bars(as_of, scenario="valid_expansion")
    if problem == "missing_close":
        df.loc[df.index[-10], "close"] = float("nan")
    else:
        df.loc[df.index[-2], "atr_14"] = float("inf")

    assert s02_decide(create_decision_frame(df, as_of), load_s02_specification()) == []
