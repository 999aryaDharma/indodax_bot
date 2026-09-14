"""Unit tests for triple barrier outcome labels (LABEL-02)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
import pytest

from indodax_lab.labels.triple_barrier import (
    BarrierTouch,
    TripleBarrierConfig,
    TripleBarrierLabel,
    build_triple_barrier_label,
    compute_concurrency_weights,
)


def _make_bar(
    open_time: datetime,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    pair: str = "btc_idr",
) -> dict[str, Any]:
    return {
        "pair": pair,
        "open_time": open_time,
        "close_time": open_time + timedelta(hours=1),
        "open": Decimal(str(open_p)),
        "high": Decimal(str(high_p)),
        "low": Decimal(str(low_p)),
        "close": Decimal(str(close_p)),
        "base_volume": Decimal("10"),
        "quote_volume": Decimal("10000000"),
    }


def test_label_02_valid_contract():
    """LABEL-02-AC0: Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap."""
    decision_ts = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)
    config = TripleBarrierConfig(
        label_set_id="triple_barrier",
        version="1.0.0",
        pt_multiplier=Decimal("2.0"),
        sl_multiplier=Decimal("1.5"),
        vertical_horizon=timedelta(hours=4),
    )

    # Volatility is 1% (0.01)
    # Entry at 10:00 bar open = 100,000,000
    # Upper barrier = 100,000,000 * (1 + 2.0 * 0.01) = 102,000,000
    # Lower barrier = 100,000,000 * (1 - 1.5 * 0.01) = 98,500,000
    # Vertical horizon = 10:00 + 4h = 14:00
    bars = [
        _make_bar(datetime(2024, 6, 1, 10, 0, tzinfo=UTC), 100000000, 100500000, 99500000, 100000000),
        _make_bar(datetime(2024, 6, 1, 11, 0, tzinfo=UTC), 100000000, 101000000, 99800000, 100800000),
        # Upper barrier touched at 12:00 (high = 102,500,000 >= 102,000,000)
        _make_bar(datetime(2024, 6, 1, 12, 0, tzinfo=UTC), 100800000, 102500000, 100500000, 102200000),
        _make_bar(datetime(2024, 6, 1, 13, 0, tzinfo=UTC), 102200000, 103000000, 101900000, 102800000),
        _make_bar(datetime(2024, 6, 1, 14, 0, tzinfo=UTC), 102800000, 103500000, 102500000, 103000000),
    ]

    label = build_triple_barrier_label(
        sample_id="s1",
        pair="btc_idr",
        decision_ts=decision_ts,
        decision_volatility=Decimal("0.01"),
        bars=bars,
        config=config,
    )

    assert label.status == "VALID"
    assert label.first_touch == BarrierTouch.UPPER
    assert label.outcome == 1
    assert label.entry_price == Decimal("100000000")
    assert label.upper_barrier == Decimal("102000000")
    assert label.lower_barrier == Decimal("98500000")
    assert label.label_end_ts == datetime(2024, 6, 1, 13, 0, tzinfo=UTC)  # close of 12:00 bar
    assert label.mfe is not None and label.mfe > Decimal("0")
    assert label.mae is not None and label.mae >= Decimal("0")


def test_label_02_contract_1():
    """LABEL-02-AC1: Dua barrier dalam candle sama memilih lower."""
    decision_ts = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)
    config = TripleBarrierConfig(
        label_set_id="triple_barrier",
        version="1.0.0",
        pt_multiplier=Decimal("2.0"),
        sl_multiplier=Decimal("1.5"),
        vertical_horizon=timedelta(hours=4),
    )

    # Volatility is 1% -> Upper = 102m, Lower = 98.5m
    # At 11:00 bar, both high >= 102m and low <= 98.5m occur
    bars = [
        _make_bar(datetime(2024, 6, 1, 10, 0, tzinfo=UTC), 100000000, 100500000, 99500000, 100000000),
        # Wild candle touching BOTH upper and lower
        _make_bar(datetime(2024, 6, 1, 11, 0, tzinfo=UTC), 100000000, 103000000, 97000000, 100000000),
        _make_bar(datetime(2024, 6, 1, 12, 0, tzinfo=UTC), 100000000, 101000000, 99500000, 100500000),
    ]

    label = build_triple_barrier_label(
        sample_id="s_both",
        pair="btc_idr",
        decision_ts=decision_ts,
        decision_volatility=Decimal("0.01"),
        bars=bars,
        config=config,
    )

    # Conservative risk assumption: Must choose LOWER barrier
    assert label.status == "VALID"
    assert label.first_touch == BarrierTouch.LOWER
    assert label.outcome == -1
    assert label.label_end_ts == datetime(2024, 6, 1, 12, 0, tzinfo=UTC)


def test_label_02_contract_2():
    """LABEL-02-AC2: Volatilitas masa depan tidak menggeser barrier."""
    decision_ts = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)
    config = TripleBarrierConfig(
        label_set_id="triple_barrier",
        version="1.0.0",
        pt_multiplier=Decimal("2.0"),
        sl_multiplier=Decimal("1.5"),
        vertical_horizon=timedelta(hours=4),
    )

    # Fixed decision-time volatility = 0.01
    bars = [
        _make_bar(datetime(2024, 6, 1, 10, 0, tzinfo=UTC), 100000000, 100500000, 99500000, 100000000),
        # Subsequent bars exhibit massive volatility, but barrier must remain frozen
        _make_bar(datetime(2024, 6, 1, 11, 0, tzinfo=UTC), 100000000, 101500000, 99000000, 101000000),
        _make_bar(datetime(2024, 6, 1, 12, 0, tzinfo=UTC), 101000000, 102100000, 100500000, 101800000),
    ]

    label = build_triple_barrier_label(
        sample_id="s_future_vol",
        pair="btc_idr",
        decision_ts=decision_ts,
        decision_volatility=Decimal("0.01"),
        bars=bars,
        config=config,
    )

    # Barriers must stay exactly at 102,000,000 and 98,500,000 regardless of post-entry volatility
    assert label.upper_barrier == Decimal("102000000")
    assert label.lower_barrier == Decimal("98500000")
    # And 102,100,000 touches the frozen 102,000,000 barrier at 12:00
    assert label.first_touch == BarrierTouch.UPPER
    assert label.outcome == 1


def test_label_02_contract_3():
    """LABEL-02-AC3: Missing exit data menghasilkan censored/excluded status."""
    decision_ts = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)
    config = TripleBarrierConfig(
        label_set_id="triple_barrier",
        version="1.0.0",
        pt_multiplier=Decimal("2.0"),
        sl_multiplier=Decimal("1.5"),
        vertical_horizon=timedelta(hours=4),  # Horizon reaches 14:00
    )

    # Bars terminate prematurely at 11:00 without touching upper or lower barrier
    bars = [
        _make_bar(datetime(2024, 6, 1, 10, 0, tzinfo=UTC), 100000000, 100500000, 99500000, 100000000),
        _make_bar(datetime(2024, 6, 1, 11, 0, tzinfo=UTC), 100000000, 100800000, 99800000, 100200000),
    ]

    label = build_triple_barrier_label(
        sample_id="s_missing",
        pair="btc_idr",
        decision_ts=decision_ts,
        decision_volatility=Decimal("0.01"),
        bars=bars,
        config=config,
    )

    # Incomplete vertical horizon without early touch must be EXCLUDED / CENSORED, never 0
    assert label.status == "EXCLUDED"
    assert label.outcome is None
    assert label.first_touch is None
    assert label.exclusion_reason == "INCOMPLETE_BARS_BEFORE_VERTICAL_BARRIER"


def test_label_02_concurrency_weights():
    """Test calculation of concurrency weights across overlapping label intervals."""
    # Label 1: active 10:00 to 14:00
    l1 = TripleBarrierLabel(
        sample_id="s1",
        label_set_id="tb",
        label_version="1.0.0",
        pair="btc_idr",
        decision_ts=datetime(2024, 6, 1, 10, 0, tzinfo=UTC),
        entry_ts=datetime(2024, 6, 1, 10, 0, tzinfo=UTC),
        label_end_ts=datetime(2024, 6, 1, 14, 0, tzinfo=UTC),
        first_touch=BarrierTouch.VERTICAL,
        outcome=0,
    )
    # Label 2: active 12:00 to 15:00 (overlaps with Label 1 between 12:00 and 14:00)
    l2 = TripleBarrierLabel(
        sample_id="s2",
        label_set_id="tb",
        label_version="1.0.0",
        pair="btc_idr",
        decision_ts=datetime(2024, 6, 1, 12, 0, tzinfo=UTC),
        entry_ts=datetime(2024, 6, 1, 12, 0, tzinfo=UTC),
        label_end_ts=datetime(2024, 6, 1, 15, 0, tzinfo=UTC),
        first_touch=BarrierTouch.VERTICAL,
        outcome=0,
    )

    weights = compute_concurrency_weights([l1, l2])
    assert "s1" in weights and "s2" in weights
    # Since they overlap, each has concurrency > 1, so weight < 1.0
    assert weights["s1"] < Decimal("1.0")
    assert weights["s2"] < Decimal("1.0")
