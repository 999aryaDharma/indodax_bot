"""TDD RED tests for feature_replay adapter — FASE 6 (C01_MTF backtest pipeline).

These tests MUST fail before implementation of
src/indodax_lab/backtest/feature_replay.py exists.

Invariants tested:
  - No future leakage: as_of strictly enforced
  - Closed-bar semantics: signal only on closed bar
  - No bfill / no ffill injection
  - as-of join is backward-only
  - available_at wajib sudah tersedia sebelum decision_ts
  - context 1h tidak boleh dipakai sebelum available
  - execution signal 5m dilakukan pada next 5m open
  - missing feature/context fails closed (tidak netral)
  - Decimal di semua numeric
  - Timezone-aware UTC di semua timestamp
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from indodax_lab.backtest.feature_replay import (
    FeatureReplayAdapter,
    FeatureReplayConfig,
    load_bars_from_parquet,
    validate_no_future_leakage,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

BASE_5M = datetime(2021, 1, 4, 0, 0, 0, tzinfo=UTC)  # Monday open
INTERVAL_5M = timedelta(minutes=5)
INTERVAL_1H = timedelta(hours=1)


def _make_5m_feature_row(
    decision_ts: datetime,
    pair: str = "btc_idr",
    close: float = 500_000_000.0,
    row_ready_at: datetime | None = None,
    eligible: bool = True,
) -> dict:
    if row_ready_at is None:
        row_ready_at = decision_ts  # available at bar close (historical-availability)
    return {
        "pair": pair,
        "decision_ts": decision_ts,
        "row_ready_at": row_ready_at,
        "eligible": eligible,
        "close_5m": Decimal(str(close)),
        "high_5m": Decimal(str(close * 1.001)),
        "low_5m": Decimal(str(close * 0.999)),
        "base_volume_5m": Decimal("10.0"),
        "atr_14_5m": Decimal("1000000"),
    }


def _make_1h_feature_row(
    decision_ts: datetime,
    pair: str = "btc_idr",
    close: float = 500_000_000.0,
    row_ready_at: datetime | None = None,
    eligible: bool = True,
) -> dict:
    if row_ready_at is None:
        row_ready_at = decision_ts
    return {
        "pair": pair,
        "decision_ts": decision_ts,
        "row_ready_at": row_ready_at,
        "eligible": eligible,
        "close_1h": Decimal(str(close)),
        "btc_log_ret_1_1h": Decimal("0.005"),
    }


def _make_signal_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


def _make_context_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["pair", "decision_ts", "row_ready_at", "eligible", "close_1h", "btc_log_ret_1_1h"]
        )
    df = pd.DataFrame(rows)
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    df["row_ready_at"] = pd.to_datetime(df["row_ready_at"], utc=True)
    return df


# ---------------------------------------------------------------------------
# TEST 1: FeatureReplayConfig validates required fields
# ---------------------------------------------------------------------------

def test_fr01_config_requires_pair():
    """FR-01: Config must reject empty pair."""
    with pytest.raises((ValueError, TypeError)):
        FeatureReplayConfig(pair="", signal_interval="5m", context_interval="1h")


# ---------------------------------------------------------------------------
# TEST 2: validate_no_future_leakage raises on row_ready_at > decision_ts
# ---------------------------------------------------------------------------

def test_fr02_future_leakage_detected():
    """FR-02: row_ready_at > decision_ts is future leakage and must be rejected."""
    decision_ts = BASE_5M
    row_ready_at = BASE_5M + timedelta(minutes=10)  # future
    rows = [_make_5m_feature_row(decision_ts, row_ready_at=row_ready_at)]
    df = _make_signal_df(rows)
    with pytest.raises(ValueError, match="FUTURE_LEAKAGE"):
        validate_no_future_leakage(df)


# ---------------------------------------------------------------------------
# TEST 3: validate_no_future_leakage passes when row_ready_at == decision_ts
# ---------------------------------------------------------------------------

def test_fr03_no_leakage_when_ready_at_eq_decision():
    """FR-03: row_ready_at == decision_ts is valid (closed bar = available at close_time)."""
    rows = [_make_5m_feature_row(BASE_5M, row_ready_at=BASE_5M)]
    df = _make_signal_df(rows)
    # Must not raise
    validate_no_future_leakage(df)


# ---------------------------------------------------------------------------
# TEST 4: FeatureReplayAdapter.build_decision_frame returns only eligible rows
# ---------------------------------------------------------------------------

def test_fr04_ineligible_rows_excluded():
    """FR-04: Rows with eligible=False are excluded from DecisionFrame."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h",
                                   require_context=False),
    )
    rows = [
        _make_5m_feature_row(BASE_5M, eligible=True),
        _make_5m_feature_row(BASE_5M + INTERVAL_5M, eligible=False),
    ]
    signal_df = _make_signal_df(rows)
    frame = adapter.build_decision_frame(
        signal_rows=signal_df,
        context_rows=pd.DataFrame(),
        as_of=BASE_5M + INTERVAL_5M,
    )
    # Only 1 eligible row should be present
    assert len(frame.features) == 1
    assert (frame.features["eligible"] == True).all()


# ---------------------------------------------------------------------------
# TEST 5: as_of strictly excludes rows with decision_ts > as_of
# ---------------------------------------------------------------------------

def test_fr05_as_of_future_rows_excluded():
    """FR-05: Rows with decision_ts > as_of must be excluded (no future leakage)."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h",
                                   require_context=False),
    )
    future_ts = BASE_5M + timedelta(hours=1)
    rows = [
        _make_5m_feature_row(BASE_5M),           # valid
        _make_5m_feature_row(future_ts),          # future — must be excluded
    ]
    signal_df = _make_signal_df(rows)
    frame = adapter.build_decision_frame(
        signal_rows=signal_df,
        context_rows=pd.DataFrame(),
        as_of=BASE_5M,
    )
    assert len(frame.features) == 1
    assert pd.to_datetime(frame.features.iloc[0]["decision_ts"], utc=True) == BASE_5M


# ---------------------------------------------------------------------------
# TEST 6: Context row not available at signal time raises / fails closed
# ---------------------------------------------------------------------------

def test_fr06_future_context_fails_closed():
    """FR-06: Context with row_ready_at > signal decision_ts must fail closed."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h"),
    )
    signal_ts = BASE_5M
    # context bar decision_ts is BEFORE signal but not yet available (row_ready_at in future)
    context_decision = BASE_5M - INTERVAL_1H
    context_ready = BASE_5M + timedelta(minutes=30)  # not ready yet at signal time
    signal_rows = _make_signal_df([_make_5m_feature_row(signal_ts)])
    context_rows = _make_context_df([
        _make_1h_feature_row(context_decision, row_ready_at=context_ready)
    ])
    with pytest.raises(ValueError):
        adapter.build_decision_frame(
            signal_rows=signal_rows,
            context_rows=context_rows,
            as_of=signal_ts,
        )


# ---------------------------------------------------------------------------
# TEST 7: Context available before signal time is correctly attached
# ---------------------------------------------------------------------------

def test_fr07_valid_context_attached():
    """FR-07: Context available before signal time is correctly attached via as-of join."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h"),
    )
    signal_ts = BASE_5M + INTERVAL_1H  # one hour in
    context_ts = BASE_5M              # 1h context closed at BASE, available at BASE
    signal_rows = _make_signal_df([_make_5m_feature_row(signal_ts)])
    context_rows = _make_context_df([_make_1h_feature_row(context_ts, row_ready_at=BASE_5M)])
    frame = adapter.build_decision_frame(
        signal_rows=signal_rows,
        context_rows=context_rows,
        as_of=signal_ts,
    )
    assert not frame.features.empty
    assert "btc_idr" in frame.eligible_pairs


# ---------------------------------------------------------------------------
# TEST 8: No bfill — missing context must not be silently filled
# ---------------------------------------------------------------------------

def test_fr08_missing_context_no_bfill():
    """FR-08: Missing 1h context must not be silently bfilled or assumed neutral."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h"),
    )
    # Signal at T=0 but no context rows at all
    signal_rows = _make_signal_df([_make_5m_feature_row(BASE_5M)])
    context_rows = _make_context_df([])  # empty context
    with pytest.raises(ValueError):
        adapter.build_decision_frame(
            signal_rows=signal_rows,
            context_rows=context_rows,
            as_of=BASE_5M,
        )


# ---------------------------------------------------------------------------
# TEST 9: Pair mismatch in context rejected
# ---------------------------------------------------------------------------

def test_fr09_pair_mismatch_context_rejected():
    """FR-09: Context from different pair must not be attached to signal."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h"),
    )
    signal_rows = _make_signal_df([_make_5m_feature_row(BASE_5M, pair="btc_idr")])
    context_rows = _make_context_df([
        _make_1h_feature_row(BASE_5M - INTERVAL_1H, pair="eth_idr", row_ready_at=BASE_5M - INTERVAL_1H)
    ])
    with pytest.raises(ValueError):
        adapter.build_decision_frame(
            signal_rows=signal_rows,
            context_rows=context_rows,
            as_of=BASE_5M,
        )


# ---------------------------------------------------------------------------
# TEST 10: Non-UTC timestamp in signal rows rejected
# ---------------------------------------------------------------------------

def test_fr10_naive_timestamp_rejected():
    """FR-10: Naive (non-UTC) timestamps in feature rows must be rejected."""
    # Build a DataFrame that has naive datetime objects in object dtype columns
    naive_ts = datetime(2021, 1, 4, 0, 0, 0)  # no tzinfo
    df = pd.DataFrame([{
        "pair": "btc_idr",
        "decision_ts": naive_ts,
        "row_ready_at": naive_ts,
        "eligible": True,
    }])
    # decision_ts column is object dtype with a naive datetime — must be rejected
    with pytest.raises(ValueError):
        validate_no_future_leakage(df)


# ---------------------------------------------------------------------------
# TEST 11: load_bars_from_parquet returns MarketBar objects
# ---------------------------------------------------------------------------

def test_fr11_load_bars_from_parquet_returns_market_bars(tmp_path):
    """FR-11: load_bars_from_parquet must return a list of MarketBar."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from indodax_lab.backtest.events import MarketBar

    ts0 = BASE_5M
    ts1 = BASE_5M + INTERVAL_5M
    table = pa.table({
        "open_time": [ts0, ts1],
        "close_time": [ts0 + INTERVAL_5M, ts1 + INTERVAL_5M],
        "open": ["500000000", "501000000"],
        "high": ["502000000", "503000000"],
        "low":  ["498000000", "499000000"],
        "close": ["501000000", "502000000"],
        "base_volume": ["1.0", "1.1"],
        "quote_volume": ["500000000", "501000000"],
    })
    parquet_path = tmp_path / "test_bars.parquet"
    pq.write_table(table, parquet_path)

    bars = load_bars_from_parquet(parquet_path, pair="btc_idr")
    assert len(bars) == 2
    assert all(isinstance(b, MarketBar) for b in bars)
    assert all(b.pair == "btc_idr" for b in bars)
    # Timestamps must be UTC-aware
    assert all(b.open_time.tzinfo is not None for b in bars)


# ---------------------------------------------------------------------------
# TEST 12: load_bars_from_parquet sorts bars by open_time ascending
# ---------------------------------------------------------------------------

def test_fr12_bars_sorted_ascending(tmp_path):
    """FR-12: Bars must be sorted by open_time ascending (deterministic replay order)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    ts0 = BASE_5M
    ts1 = BASE_5M + INTERVAL_5M
    # Write in reverse order
    table = pa.table({
        "open_time": [ts1, ts0],
        "close_time": [ts1 + INTERVAL_5M, ts0 + INTERVAL_5M],
        "open": ["501000000", "500000000"],
        "high": ["503000000", "502000000"],
        "low":  ["499000000", "498000000"],
        "close": ["502000000", "501000000"],
        "base_volume": ["1.1", "1.0"],
        "quote_volume": ["501000000", "500000000"],
    })
    parquet_path = tmp_path / "test_bars_unsorted.parquet"
    pq.write_table(table, parquet_path)

    bars = load_bars_from_parquet(parquet_path, pair="btc_idr")
    assert bars[0].open_time < bars[1].open_time


# ---------------------------------------------------------------------------
# TEST 13: execution_timing=next_bar_open => strategy_fn called at bar.available_at (close_time)
#          and intent.decision_ts == bar.available_at (not bar.open_time)
# ---------------------------------------------------------------------------

def test_fr13_signal_decision_ts_is_bar_available_at():
    """FR-13: For closed-bar signals, decision_ts must equal bar.available_at (close_time)."""
    from indodax_lab.backtest.events import MarketBar, SignalIntent
    from indodax_lab.backtest.costs import OrderSide

    bar = MarketBar(
        pair="btc_idr",
        open_time=BASE_5M,
        close_time=BASE_5M + INTERVAL_5M,
        open=Decimal("500000000"),
        high=Decimal("502000000"),
        low=Decimal("498000000"),
        close=Decimal("501000000"),
        base_volume=Decimal("1.0"),
        quote_volume=Decimal("500000000"),
    )
    # bar.available_at defaults to close_time
    intent = SignalIntent(
        intent_id="test-001",
        decision_ts=bar.available_at,  # must equal close_time
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.1"),
        strategy_id="C01_MTF",
    )
    assert intent.decision_ts == bar.close_time
    assert intent.decision_ts == bar.available_at


# ---------------------------------------------------------------------------
# TEST 14: FeatureReplayAdapter.build_decision_frame raises if as_of is naive
# ---------------------------------------------------------------------------

def test_fr14_naive_as_of_rejected():
    """FR-14: Naive as_of timestamp must be rejected by build_decision_frame."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h"),
    )
    naive_as_of = datetime(2021, 1, 4, 0, 0, 0)  # no tzinfo
    with pytest.raises(ValueError):
        adapter.build_decision_frame(
            signal_rows=pd.DataFrame(),
            context_rows=pd.DataFrame(),
            as_of=naive_as_of,
        )


# ---------------------------------------------------------------------------
# TEST 15: FeatureReplayAdapter returns empty frame for warmup period
# ---------------------------------------------------------------------------

def test_fr15_warmup_rows_produce_no_eligible_pairs():
    """FR-15: Warmup rows (eligible=False) produce no eligible pairs in DecisionFrame."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h"),
    )
    rows = [_make_5m_feature_row(BASE_5M, eligible=False)]
    signal_df = _make_signal_df(rows)
    frame = adapter.build_decision_frame(
        signal_rows=signal_df,
        context_rows=pd.DataFrame(),
        as_of=BASE_5M,
    )
    assert len(frame.eligible_pairs) == 0


# ---------------------------------------------------------------------------
# TEST 16: Context strictly before signal required (as-of backward only)
# ---------------------------------------------------------------------------

def test_fr16_context_strictly_backward_only():
    """FR-16: Future context (context_ts > signal_ts) must be rejected (backward-only)."""
    adapter = FeatureReplayAdapter(
        config=FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h"),
    )
    signal_ts = BASE_5M
    future_context_ts = BASE_5M + INTERVAL_1H  # context AFTER signal — forbidden
    signal_rows = _make_signal_df([_make_5m_feature_row(signal_ts)])
    context_rows = _make_context_df([
        _make_1h_feature_row(future_context_ts, row_ready_at=future_context_ts)
    ])
    with pytest.raises(ValueError):
        adapter.build_decision_frame(
            signal_rows=signal_rows,
            context_rows=context_rows,
            as_of=signal_ts,
        )


# ---------------------------------------------------------------------------
# TEST 17: FeatureReplayConfig immutable — cannot change interval after creation
# ---------------------------------------------------------------------------

def test_fr17_config_immutable():
    """FR-17: FeatureReplayConfig must be immutable (frozen) once created."""
    cfg = FeatureReplayConfig(pair="btc_idr", signal_interval="5m", context_interval="1h")
    with pytest.raises((AttributeError, TypeError)):
        cfg.pair = "eth_idr"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TEST 18: validate_no_future_leakage raises on missing row_ready_at column
# ---------------------------------------------------------------------------

def test_fr18_missing_row_ready_at_column_rejected():
    """FR-18: DataFrame without row_ready_at column must be rejected by validate_no_future_leakage."""
    df = pd.DataFrame([{"pair": "btc_idr", "decision_ts": BASE_5M, "eligible": True}])
    df["decision_ts"] = pd.to_datetime(df["decision_ts"], utc=True)
    with pytest.raises(ValueError, match="row_ready_at"):
        validate_no_future_leakage(df)
