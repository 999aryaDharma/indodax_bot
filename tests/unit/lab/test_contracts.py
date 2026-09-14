from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from indodax_lab.contracts import CandleRecord, CanonicalPair, QualityStatus, TradeEvent


def test_canonical_pair_rejects_venue_symbol_in_core_validation():
    """Removing canonical-ID validation would let a venue identity leak into core data."""
    with pytest.raises(ValidationError):
        CanonicalPair(pair="BTCIDR")


def test_adapter_constructor_normalizes_venue_symbol_to_canonical_pair():
    """Changing the explicit adapter conversion would produce the wrong internal pair ID."""
    pair = CanonicalPair.from_venue_symbol("BTCIDR")

    assert pair.pair == "btc_idr"


def test_candle_record_rejects_timezone_naive_datetime():
    """Removing UTC validation would permit ambiguous event timestamps into candle data."""
    with pytest.raises(ValidationError):
        CandleRecord(
            schema_version="1.0.0",
            pair=CanonicalPair(pair="btc_idr"),
            venue_symbol="BTCIDR",
            interval="1h",
            open_time=datetime(2026, 8, 12, 10, 0),
            close_time=datetime(2026, 8, 12, 11, 0, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            base_volume=Decimal("1.5"),
            is_closed=True,
            available_at=datetime(2026, 8, 12, 11, 0, tzinfo=UTC),
            source="indodax",
            ingested_at=datetime(2026, 8, 12, 11, 0, tzinfo=UTC),
            quality_status=QualityStatus.PASS,
            quality_flags=[],
        )


def test_candle_record_keeps_decimal_prices_without_float_conversion():
    """Accepting binary floats would lose the Decimal source-of-truth invariant."""
    start = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        CandleRecord(
            schema_version="1.0.0",
            pair=CanonicalPair(pair="btc_idr"),
            venue_symbol="BTCIDR",
            interval="1h",
            open_time=start,
            close_time=start + timedelta(hours=1),
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            base_volume=1.5,
            is_closed=True,
            available_at=start + timedelta(hours=1),
            source="indodax",
            ingested_at=start + timedelta(hours=1),
            quality_status=QualityStatus.PASS,
            quality_flags=[],
        )


def test_trade_event_keeps_venue_symbol_as_separate_source_identity():
    """Collapsing source identity into the pair would lose the adapter-facing symbol."""
    event_ts = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    trade = TradeEvent(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        event_ts=event_ts,
        ingested_at=event_ts + timedelta(seconds=1),
        available_at=event_ts + timedelta(seconds=1),
        price=Decimal("1000000000.12"),
        base_qty=Decimal("0.00000123"),
        quote_qty=Decimal("1230.0001476"),
        source_event_id="trade-42",
        source="indodax",
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )

    assert trade.pair.pair == "btc_idr"
    assert trade.venue_symbol == "BTCIDR"


def test_trade_event_keeps_explicit_aggressor_side():
    """Dropping aggressor-side data would make signed trade-flow features impossible."""
    event_ts = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    trade = TradeEvent(
        schema_version="1.0.0",
        pair=CanonicalPair(pair="btc_idr"),
        venue_symbol="BTCIDR",
        event_ts=event_ts,
        ingested_at=event_ts + timedelta(seconds=1),
        available_at=event_ts + timedelta(seconds=1),
        price=Decimal("100"),
        base_qty=Decimal("0.1"),
        quote_qty=Decimal("10"),
        source_event_id="trade-43",
        source="indodax",
        aggressor_side="BUY",
        quality_status=QualityStatus.PASS,
        quality_flags=[],
    )

    assert trade.aggressor_side == "BUY"


def test_trade_event_requires_clock_anomaly_flag_for_pre_event_ingestion():
    """Removing the anomaly gate would silently accept impossible source clock ordering."""
    event_ts = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        TradeEvent(
            schema_version="1.0.0",
            pair=CanonicalPair(pair="btc_idr"),
            venue_symbol="BTCIDR",
            event_ts=event_ts,
            ingested_at=event_ts - timedelta(seconds=1),
            available_at=event_ts,
            price=Decimal("100"),
            base_qty=Decimal("0.1"),
            quote_qty=Decimal("10"),
            source_event_id="trade-44",
            source="indodax",
            quality_status=QualityStatus.WARN,
            quality_flags=[],
        )


def test_candle_record_requires_explicit_schema_version():
    """Removing candle schema lineage would make immutable datasets impossible to interpret."""
    start = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        CandleRecord(
            pair=CanonicalPair(pair="btc_idr"),
            venue_symbol="BTCIDR",
            interval="1h",
            open_time=start,
            close_time=start + timedelta(hours=1),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            base_volume=Decimal("1.5"),
            is_closed=True,
            available_at=start + timedelta(hours=1),
            source="indodax",
            ingested_at=start + timedelta(hours=1),
            quality_status=QualityStatus.PASS,
            quality_flags=[],
        )


def test_trade_event_requires_explicit_schema_version():
    """Removing trade schema lineage would make immutable datasets impossible to interpret."""
    event_ts = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        TradeEvent(
            pair=CanonicalPair(pair="btc_idr"),
            venue_symbol="BTCIDR",
            event_ts=event_ts,
            ingested_at=event_ts + timedelta(seconds=1),
            available_at=event_ts + timedelta(seconds=1),
            price=Decimal("100"),
            base_qty=Decimal("0.1"),
            quote_qty=Decimal("10"),
            source_event_id="trade-45",
            source="indodax",
            quality_status=QualityStatus.PASS,
            quality_flags=[],
        )


@pytest.mark.parametrize("interval", ["1M", "banana", " 1h"])
def test_candle_record_rejects_non_contract_intervals(interval):
    """Relaxing the interval allowlist would fragment canonical candle partitions."""
    start = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        CandleRecord(
            schema_version="1.0.0",
            pair=CanonicalPair(pair="btc_idr"),
            venue_symbol="BTCIDR",
            interval=interval,
            open_time=start,
            close_time=start + timedelta(hours=1),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("90"),
            close=Decimal("105"),
            base_volume=Decimal("1.5"),
            is_closed=True,
            available_at=start + timedelta(hours=1),
            source="indodax",
            ingested_at=start + timedelta(hours=1),
            quality_status=QualityStatus.PASS,
            quality_flags=[],
        )
