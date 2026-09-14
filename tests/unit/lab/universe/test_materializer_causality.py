"""Fail-closed causal consistency checks for universe materialization."""
# ruff: noqa: E501

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from indodax_lab.contracts import AggressorSide, CanonicalPair, QualityStatus, TradeEvent
from indodax_lab.data.bars import BarType, SilverBar
from indodax_lab.data.stream_protocol import BookEvent, BookSide
from indodax_lab.universe import (
    BarArtifactRef,
    BookArtifactRef,
    BronzeSnapshotArtifactRef,
    CandleQualityArtifactRef,
    CandleWireArtifactRef,
    CapEvidence,
    CapProviderResponseArtifactRef,
    GlobalTradeQualityArtifactRef,
    ListingArtifactRef,
    ListingEvidence,
    MaterializationProfile,
    PipelineLineageInputs,
    ProfileArtifactRef,
    TradeBatchArtifactRef,
    TradeWireArtifactRef,
    UniversePolicyArtifactRef,
    materialize_universe_metrics,
)

NOW = datetime(2024, 1, 1, 12, tzinfo=UTC)
IDENTITY = "sha256:" + "a" * 64


def _inputs():
    pair = "btc_idr"
    trade = TradeEvent(
        schema_version="1.0.0", pair=CanonicalPair(pair=pair), venue_symbol="BTCIDR",
        event_ts=NOW - timedelta(minutes=2), ingested_at=NOW - timedelta(minutes=1),
        available_at=NOW - timedelta(minutes=1), price=Decimal("100"), base_qty=Decimal("1"),
        quote_qty=Decimal("100"), source_event_id="trade-1", source="fixture",
        aggressor_side=AggressorSide.BUY, quality_status=QualityStatus.PASS, quality_flags=[],
    )
    bar = SilverBar(
        schema_version="1.0.0", bar_id=IDENTITY, pair=pair, bar_type=BarType.TIME,
        interval="1m", policy_id="fixture", availability_lag_microseconds=0,
        first_event_ts=trade.event_ts, last_event_ts=trade.event_ts,
        open_time=NOW - timedelta(minutes=2), close_time=NOW - timedelta(minutes=1),
        available_at=NOW - timedelta(minutes=1), open=Decimal("100"), high=Decimal("100"),
        low=Decimal("100"), close=Decimal("100"), base_volume=Decimal("1"),
        quote_volume=Decimal("100"), trade_count=1, buy_base_volume=Decimal("1"),
        sell_base_volume=Decimal(0), source_snapshot_id=IDENTITY, source="fixture",
        source_session_id="fixture", source_event_ids=("trade-1",),
        quality_status=QualityStatus.PASS, quality_flags=(),
    )
    books = tuple(
        BookEvent(
            schema_version="1.0.0", pair=CanonicalPair(pair=pair), venue_symbol="BTCIDR",
            event_ts=NOW - timedelta(minutes=2), ingested_at=NOW - timedelta(minutes=1),
            available_at=NOW - timedelta(minutes=1), book_session_id="fixture", sequence=1,
            event_type="SNAPSHOT", side=side, level=0, price=price, base_qty=Decimal("1"),
            quote_qty=price, source_event_id=f"book-{side.value}", source="fixture",
            quality_status=QualityStatus.PASS, quality_flags=[],
        )
        for side, price in ((BookSide.BID, Decimal("99")), (BookSide.ASK, Decimal("101")))
    )
    listing = ListingEvidence(
        pair, "btc", "idr", NOW - timedelta(days=10), True, True, NOW, IDENTITY,
        "bitcoin",
    )
    cap = CapEvidence(
        Decimal("1000000"), 1, NOW - timedelta(minutes=2), NOW - timedelta(minutes=1),
        NOW + timedelta(days=1), "fixture", IDENTITY, pair, "btc", "idr", "bitcoin",
    )
    profile = MaterializationProfile("fixture", 1, 1, 50, Decimal("10"))
    lineage = _lineage(profile)
    return listing, cap, (trade,), (bar,), books, lineage, profile


def _materialize(**updates):
    listing, cap, trades, bars, books, lineage, profile = _inputs()
    values = {"listing": listing, "cap": cap, "trades": trades, "bars": bars, "books": books}
    values.update(updates)
    return materialize_universe_metrics(
        as_of_date=date(2024, 1, 1), build_cutoff=NOW,
        lineage=lineage, **values,
    )


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"cap": lambda cap: CapEvidence(cap.market_cap_usd, cap.market_cap_rank, cap.source_ts, cap.available_at, cap.expires_at, cap.source, cap.input_id, "eth_idr", "eth", "idr", cap.provider_asset_id)}, "CAP_ASSET_IDENTITY_MISMATCH"),
        ({"trades": lambda rows: (rows[0].model_copy(update={"pair": CanonicalPair(pair="eth_idr")}),)}, "canonical pair and assets"),
        ({"bars": lambda rows: (rows[0].model_copy(update={"pair": "eth_idr"}),)}, "canonical pair and assets"),
        ({"books": lambda rows: (rows[0].model_copy(update={"pair": CanonicalPair(pair="eth_idr")}), *rows[1:])}, "canonical pair and assets"),
        ({"listing": lambda row: ListingEvidence("eth_idr", "eth", "idr", row.listed_at, True, True, row.available_at, IDENTITY, row.provider_asset_id)}, "LINEAGE_LISTING_ARTIFACT_MISMATCH"),
    ],
)
def test_materializer_rejects_wrong_pair_inputs(update, message):
    values = _inputs()
    names = ("listing", "cap", "trades", "bars", "books", "lineage", "profile")
    kwargs = dict(zip(names, values, strict=True))
    for name, factory in update.items():
        kwargs[name] = factory(kwargs[name])
    with pytest.raises(ValueError, match=message):
        _materialize(**{key: kwargs[key] for key in ("listing", "cap", "trades", "bars", "books")})


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"trades": lambda rows: (rows[0].model_copy(update={"available_at": NOW + timedelta(days=1)}),)}, "after cutoff"),
        ({"bars": lambda rows: (rows[0].model_copy(update={"available_at": NOW + timedelta(days=1)}),)}, "after cutoff"),
        ({"books": lambda rows: (rows[0].model_copy(update={"available_at": NOW + timedelta(days=1)}), *rows[1:])}, "after cutoff"),
        ({"listing": lambda row: ListingEvidence(row.pair, row.asset, row.quote_asset, row.listed_at, True, True, NOW + timedelta(days=1), IDENTITY, row.provider_asset_id)}, "after cutoff"),
        ({"cap": lambda cap: CapEvidence(cap.market_cap_usd, cap.market_cap_rank, NOW + timedelta(days=1), NOW, cap.expires_at, cap.source, cap.input_id, cap.pair, cap.asset, cap.quote_asset, cap.provider_asset_id)}, "source timestamp"),
    ],
)
def test_materializer_rejects_future_or_impossible_availability(update, message):
    values = _inputs()
    names = ("listing", "cap", "trades", "bars", "books", "lineage", "profile")
    kwargs = dict(zip(names, values, strict=True))
    for name, factory in update.items():
        kwargs[name] = factory(kwargs[name])
    with pytest.raises(ValueError, match=message):
        _materialize(**{key: kwargs[key] for key in ("listing", "cap", "trades", "bars", "books")})


@pytest.mark.parametrize(
    ("update", "code"),
    [
        (
            {"trades": lambda rows: (rows[0].model_copy(update={"available_at": rows[0].event_ts - timedelta(microseconds=1)}),)},
            "TRADE_CAUSAL_ORDER",
        ),
        (
            {"books": lambda rows: (rows[0].model_copy(update={"available_at": rows[0].event_ts - timedelta(microseconds=1)}), *rows[1:])},
            "BOOK_CAUSAL_ORDER",
        ),
        (
            {"bars": lambda rows: (rows[0].model_copy(update={"last_event_ts": rows[0].close_time + timedelta(microseconds=1)}),)},
            "BAR_CAUSAL_ORDER",
        ),
        (
            {"bars": lambda rows: (rows[0].model_copy(update={"available_at": rows[0].close_time - timedelta(microseconds=1)}),)},
            "BAR_CAUSAL_ORDER",
        ),
        (
            {"bars": lambda rows: (rows[0].model_copy(update={"source": "another-provider"}),)},
            "BAR_PROVIDER_MISMATCH",
        ),
        (
            {"listing": lambda row: ListingEvidence(row.pair, row.asset, row.quote_asset, NOW + timedelta(seconds=1), True, True, NOW, IDENTITY, row.provider_asset_id)},
            "LISTING_CAUSAL_ORDER",
        ),
        (
            {"cap": lambda cap: CapEvidence(cap.market_cap_usd, cap.market_cap_rank, NOW + timedelta(seconds=1), NOW, cap.expires_at, cap.source, cap.input_id, cap.pair, cap.asset, cap.quote_asset, cap.provider_asset_id)},
            "CAP_CAUSAL_ORDER",
        ),
        (
            {"trades": lambda rows: (rows[0].model_copy(update={"available_at": NOW + timedelta(hours=1)}),)},
            "INPUT_AFTER_BUILD_CUTOFF",
        ),
    ],
)
def test_materializer_enforces_stable_causal_failure_codes(update, code):
    """Every causal edge is checked against the caller's fixed cutoff with a stable code."""
    listing, cap, trades, bars, books, _lineage, _profile = _inputs()
    values = {"listing": listing, "cap": cap, "trades": trades, "bars": bars, "books": books}
    for name, factory in update.items():
        values[name] = factory(values[name])

    with pytest.raises(ValueError, match=code):
        _materialize(**values)


def _lineage(profile: MaterializationProfile) -> PipelineLineageInputs:
    """Typed value-object doubles isolate causal checks from artifact-loader integration tests."""
    candle_wire = _ref(CandleWireArtifactRef, ids=(IDENTITY,))
    bronze = _ref(BronzeSnapshotArtifactRef, ids=(IDENTITY,), snapshot_id=IDENTITY)
    candle_quality = _ref(
        CandleQualityArtifactRef,
        ids=(IDENTITY,),
        snapshot_id=IDENTITY,
        decision_id=IDENTITY,
    )
    trade_wire = _ref(TradeWireArtifactRef, ids=(IDENTITY,), batch_id=IDENTITY)
    trade_batch = _ref(TradeBatchArtifactRef, ids=(IDENTITY,), batch_id=IDENTITY)
    trade_quality = _ref(
        GlobalTradeQualityArtifactRef,
        ids=(IDENTITY,),
        batch_ids=(IDENTITY,),
        decision_id=IDENTITY,
    )
    bars = _ref(
        BarArtifactRef,
        ids=(IDENTITY,),
        output_id=IDENTITY,
        manifest_id=IDENTITY,
        config_id=IDENTITY,
        bar_ids=(IDENTITY,),
        source_snapshot_id=IDENTITY,
        trade_batch_ids=(IDENTITY,),
        trade_decision_id=IDENTITY,
        candle_decision_id=IDENTITY,
    )
    book = _ref(BookArtifactRef, ids=(IDENTITY,), batch_id=IDENTITY)
    listing = _ref(
        ListingArtifactRef,
        ids=(IDENTITY,),
        pair="btc_idr",
        base_asset_symbol="btc",
        quote_asset_symbol="idr",
        provider_asset_id="bitcoin",
    )
    cap = _ref(
        CapProviderResponseArtifactRef,
        ids=(IDENTITY,),
        pair="btc_idr",
        base_asset_symbol="btc",
        quote_asset_symbol="idr",
        provider_asset_id="bitcoin",
    )
    profile_ref = _ref(
        ProfileArtifactRef, ids=(IDENTITY,), profile_id=profile.profile_id, profile=profile
    )
    policy = _ref(UniversePolicyArtifactRef, ids=(IDENTITY,), policy_version="fixture")
    return PipelineLineageInputs(
        candle_wires=(candle_wire,),
        bronze_snapshot=bronze,
        candle_quality=candle_quality,
        trade_wires=(trade_wire,),
        trade_batches=(trade_batch,),
        global_trade_quality=trade_quality,
        bars=bars,
        book=book,
        listing=listing,
        cap=cap,
        profile=profile_ref,
        universe_policy=policy,
    )


def _ref(cls, **values):
    reference = object.__new__(cls)
    for field, value in values.items():
        object.__setattr__(reference, field, value)
    return reference
