"""Unit tests verifying candle gap detection and fail-closed non-positive price gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from indodax_lab.contracts import CandleRecord, CanonicalPair, QualityStatus
from indodax_lab.market.gateway import MarketGateway
from indodax_lab.market.health import MarketHealthReport, MarketHealthState
from indodax_lab.market.quality import DataQualityGuard, TickerSnapshot

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def _make_bar(
    start: datetime,
    end: datetime,
    pair: str = "btc_idr",
    interval: str = "1h",
) -> CandleRecord:
    canonical = CanonicalPair(pair=pair)
    return CandleRecord(
        schema_version="1.0.0",
        pair=canonical,
        venue_symbol="btcidr",
        interval=interval,
        open_time=start,
        close_time=end,
        open=Decimal("1000000000"),
        high=Decimal("1005000000"),
        low=Decimal("995000000"),
        close=Decimal("1002000000"),
        base_volume=Decimal("1.5"),
        quote_volume=Decimal("1500000000"),
        trade_count=100,
        is_closed=True,
        available_at=end,
        source="test",
        ingested_at=end,
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )


def test_quality_guard_detects_forward_interval_gap() -> None:
    guard = DataQualityGuard()

    # Bar 1: 08:00 to 09:00
    t0 = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
    bar_1 = _make_bar(t0, t1)
    res_1 = guard.validate_closed_bar(bar_1, as_of_utc=NOW)
    assert res_1.is_valid
    assert len(res_1.findings) == 0

    # Bar 2: Gap detected! 10:00 to 11:00 (missing 09:00 to 10:00)
    t2 = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    t3 = datetime(2026, 9, 21, 11, 0, tzinfo=UTC)
    bar_gap = _make_bar(t2, t3)
    res_2 = guard.validate_closed_bar(bar_gap, as_of_utc=NOW + timedelta(hours=2))
    assert not res_2.is_valid
    assert any("MISSING_CANDLE_INTERVAL_GAP" in f for f in res_2.findings)


def test_market_health_report_is_clean_rejects_invalid_and_crossed_prices() -> None:
    # 1. Non-positive last price finding
    report_last_bad = MarketHealthReport(
        pair="btc_idr",
        state=MarketHealthState.HEALTHY,
        as_of_utc=NOW,
        findings=("INVALID_LAST_PRICE_NON_POSITIVE",),
    )
    assert report_last_bad.is_clean is False
    assert report_last_bad.should_halt_new_orders is True

    # 2. Non-positive bid
    report_bid_bad = MarketHealthReport(
        pair="btc_idr",
        state=MarketHealthState.DEGRADED,
        as_of_utc=NOW,
        findings=("INVALID_BID_NON_POSITIVE",),
    )
    assert report_bid_bad.is_clean is False
    assert report_bid_bad.should_halt_new_orders is True

    # 3. Crossed book
    report_crossed = MarketHealthReport(
        pair="btc_idr",
        state=MarketHealthState.HEALTHY,
        as_of_utc=NOW,
        findings=("CROSSED_MARKET_ASK_LESS_THAN_BID",),
    )
    assert report_crossed.is_clean is False
    assert report_crossed.should_halt_new_orders is True


def test_market_gateway_snapshot_with_zero_price_is_unsafe() -> None:
    gateway = MarketGateway()
    ticker = TickerSnapshot(
        pair="btc_idr",
        bid=Decimal("1000000000"),
        ask=Decimal("1001000000"),
        last_price=Decimal("0"),  # Zero price!
        timestamp_utc=NOW,
    )

    snapshot = gateway.get_market_snapshot("btc_idr", as_of_utc=NOW, ticker_override=ticker)
    assert snapshot.health.should_halt_new_orders is True
    assert snapshot.is_safe_for_trading is False
    assert "INVALID_LAST_PRICE_NON_POSITIVE" in snapshot.health.findings
