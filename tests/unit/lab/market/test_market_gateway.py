"""Unit tests for the canonical MarketGateway, ClockGuard, and DataQualityGuard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from indodax_lab.contracts import CandleRecord, CanonicalPair, QualityStatus
from indodax_lab.market.clock import ClockGuard
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.market.health import MarketHealthState
from indodax_lab.market.quality import (
    DataQualityGuard,
    TickerSnapshot,
)

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def test_clock_guard_rejects_naive_timestamp() -> None:
    guard = ClockGuard()
    naive_dt = datetime(2026, 9, 21, 12, 0)
    with pytest.raises(ValueError, match="rejects naive timestamp"):
        guard.check_clock(naive_dt)


def test_clock_guard_detects_backwards_regression() -> None:
    guard = ClockGuard()
    t1 = NOW
    t2 = NOW - timedelta(seconds=10)

    r1 = guard.check_clock(t1)
    assert r1.is_safe is True

    r2 = guard.check_clock(t2)
    assert r2.is_safe is False
    assert r2.regression_detected is True
    assert r2.finding_code == "CLOCK_REGRESSION_DETECTED"


def test_clock_guard_detects_offset_exceeding_threshold() -> None:
    guard = ClockGuard(max_allowed_offset_ms=1000.0)
    t_local = NOW
    t_venue = NOW + timedelta(milliseconds=2500)

    report = guard.check_clock(t_local, reference_utc=t_venue)
    assert report.is_safe is False
    assert report.finding_code == "CLOCK_OFFSET_EXCEEDED"
    assert report.offset_ms == 2500.0


def test_data_quality_guard_rejects_non_positive_and_crossed_ticker() -> None:
    guard = DataQualityGuard()
    # Negative bid
    bad_ticker1 = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("-100"),
        ask=Decimal("1000"),
        last_price=Decimal("1000"),
        timestamp_utc=NOW,
    )
    res1 = guard.validate_ticker(bad_ticker1, as_of_utc=NOW)
    assert res1.is_valid is False
    assert "INVALID_BID_NON_POSITIVE" in res1.findings

    # Crossed market (ask < bid)
    bad_ticker2 = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1100"),
        ask=Decimal("1000"),
        last_price=Decimal("1050"),
        timestamp_utc=NOW,
    )
    res2 = guard.validate_ticker(bad_ticker2, as_of_utc=NOW)
    assert res2.is_valid is False
    assert "CROSSED_MARKET_ASK_LESS_THAN_BID" in res2.findings


def test_data_quality_guard_detects_stale_ticker() -> None:
    guard = DataQualityGuard(max_ticker_age_seconds=30.0)
    stale_ticker = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1000"),
        ask=Decimal("1010"),
        last_price=Decimal("1005"),
        timestamp_utc=NOW - timedelta(seconds=65),
    )
    res = guard.validate_ticker(stale_ticker, as_of_utc=NOW)
    assert res.is_valid is False
    assert any(f.startswith("STALE_TICKER_AGE") for f in res.findings)


def test_data_quality_guard_enforces_closed_bar_semantics() -> None:
    guard = DataQualityGuard()
    # Bar started 10m ago, 1h interval -> finishes in 50m (future/unclosed)
    open_ts = NOW - timedelta(minutes=10)
    close_ts = open_ts + timedelta(hours=1)
    unclosed_bar = CandleRecord(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        interval="1h",
        open_time=open_ts,
        close_time=close_ts,
        open=Decimal("1000"),
        high=Decimal("1050"),
        low=Decimal("990"),
        close=Decimal("1020"),
        base_volume=Decimal("5.5"),
        quote_volume=Decimal("5500"),
        is_closed=False,
        available_at=close_ts,
        source="indodax",
        ingested_at=NOW,
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )
    res = guard.validate_closed_bar(unclosed_bar, as_of_utc=NOW, interval_seconds=3600)
    assert res.is_valid is False
    assert "CANDLE_NOT_CLOSED_YET" in res.findings


def test_data_quality_guard_detects_duplicate_and_out_of_order_bars() -> None:
    guard = DataQualityGuard()
    t_open1 = NOW - timedelta(hours=3)
    t_close1 = t_open1 + timedelta(hours=1)
    bar1 = CandleRecord(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        interval="1h",
        open_time=t_open1,
        close_time=t_close1,
        open=Decimal("1000"),
        high=Decimal("1050"),
        low=Decimal("990"),
        close=Decimal("1020"),
        base_volume=Decimal("5.5"),
        quote_volume=Decimal("5500"),
        is_closed=True,
        available_at=t_close1,
        source="indodax",
        ingested_at=t_close1,
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )
    res1 = guard.validate_closed_bar(bar1, as_of_utc=NOW, interval_seconds=3600)
    assert res1.is_valid is True

    # Duplicate bar timestamp
    res_dup = guard.validate_closed_bar(bar1, as_of_utc=NOW, interval_seconds=3600)
    assert res_dup.is_valid is False
    assert "DUPLICATE_CANDLE_TIMESTAMP" in res_dup.findings

    # Out of order bar (older than bar1)
    t_open_older = NOW - timedelta(hours=4)
    t_close_older = t_open_older + timedelta(hours=1)
    bar_older = CandleRecord(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        interval="1h",
        open_time=t_open_older,
        close_time=t_close_older,
        open=Decimal("1000"),
        high=Decimal("1050"),
        low=Decimal("990"),
        close=Decimal("1020"),
        base_volume=Decimal("5.5"),
        quote_volume=Decimal("5500"),
        is_closed=True,
        available_at=t_close_older,
        source="indodax",
        ingested_at=t_close_older,
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )
    res_older = guard.validate_closed_bar(bar_older, as_of_utc=NOW, interval_seconds=3600)
    assert res_older.is_valid is False
    assert "OUT_OF_ORDER_CANDLE_TIMESTAMP" in res_older.findings


def test_market_gateway_produces_healthy_snapshot() -> None:
    gateway = MarketGateway()
    clean_ticker = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1000000000"),
        ask=Decimal("1000500000"),
        last_price=Decimal("1000200000"),
        timestamp_utc=NOW,
    )
    snapshot = gateway.get_market_snapshot(
        pair="btc_idr",
        as_of_utc=NOW,
        ticker_override=clean_ticker,
    )
    assert snapshot.health.state == MarketHealthState.HEALTHY
    assert snapshot.health.should_halt_new_orders is False
    assert snapshot.is_safe_for_trading is True
    assert snapshot.last_price == Decimal("1000200000")


def test_market_gateway_fails_closed_on_clock_unsafe() -> None:
    # Clock guard with tiny tolerance
    clock_guard = ClockGuard(max_allowed_offset_ms=500.0)
    gateway = MarketGateway(clock_guard=clock_guard)

    # First observe future time, then regression
    clock_guard.check_clock(NOW + timedelta(seconds=10))

    clean_ticker = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1000"),
        ask=Decimal("1005"),
        last_price=Decimal("1002"),
        timestamp_utc=NOW,
    )
    snapshot = gateway.get_market_snapshot(
        pair="btc_idr",
        as_of_utc=NOW,
        ticker_override=clean_ticker,
    )
    assert snapshot.health.state == MarketHealthState.CLOCK_UNSAFE
    assert snapshot.health.should_halt_new_orders is True
    assert snapshot.is_safe_for_trading is False
    assert "CLOCK_REGRESSION_DETECTED" in snapshot.health.findings


def test_market_gateway_fails_closed_on_stale_data() -> None:
    quality_guard = DataQualityGuard(max_ticker_age_seconds=10.0)
    gateway = MarketGateway(quality_guard=quality_guard)

    stale_ticker = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1000"),
        ask=Decimal("1005"),
        last_price=Decimal("1002"),
        timestamp_utc=NOW - timedelta(seconds=25),
    )
    snapshot = gateway.get_market_snapshot(
        pair="btc_idr",
        as_of_utc=NOW,
        ticker_override=stale_ticker,
    )
    assert snapshot.health.state == MarketHealthState.STALE
    assert snapshot.health.should_halt_new_orders is True
    assert snapshot.is_safe_for_trading is False
