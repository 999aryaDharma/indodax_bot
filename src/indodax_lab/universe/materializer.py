"""Offline materialization of universe inputs from auditable market artifacts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal

from indodax_lab.contracts import QualityStatus, TradeEvent
from indodax_lab.data.bars import SilverBar
from indodax_lab.data.stream_protocol import BookEvent, BookSide

from .contracts import UniverseMetrics
from .lineage import CapEvidence, ListingEvidence, PipelineLineageInputs


def materialize_universe_metrics(
    *,
    as_of_date: date,
    build_cutoff: datetime,
    listing: ListingEvidence,
    cap: CapEvidence,
    trades: Iterable[TradeEvent],
    bars: Iterable[SilverBar],
    books: Iterable[BookEvent],
    lineage: PipelineLineageInputs,
) -> UniverseMetrics:
    """Derive metrics with sorted, deduplicated immutable upstream lineage.

    Callers supply identities for the durable artifacts that produced the
    decoded records (wire, sentry decisions, manifests, and policies).  They
    are carried into the universe decision in canonical lexical order; the
    eventual universe snapshot ID is deliberately excluded to avoid recursion.
    """
    _require_utc(build_cutoff, "BUILD_CUTOFF_INVALID")
    cutoff = build_cutoff
    profile = lineage.profile.profile
    if profile is None:
        raise ValueError("LINEAGE_PROFILE_MISSING")
    trades = tuple(sorted(trades, key=lambda row: (row.event_ts, row.source_event_id)))
    bars = tuple(sorted(bars, key=lambda row: (row.open_time, row.bar_id)))
    books = tuple(sorted(books, key=lambda row: (row.event_ts, row.sequence, row.side, row.level)))
    if not trades or not bars or not books:
        raise ValueError("materializer requires non-empty trade, bar, and book inputs")
    if any(row.quality_status is not QualityStatus.PASS for row in trades):
        raise ValueError("materializer requires PASS trades")
    if any(row.quality_status is not QualityStatus.PASS for row in bars):
        raise ValueError("materializer requires PASS bars")
    if any(row.quality_status is not QualityStatus.PASS for row in books):
        raise ValueError("materializer requires PASS book rows")
    if listing.input_id not in lineage.listing.ids:
        raise ValueError("LINEAGE_LISTING_ARTIFACT_MISMATCH")
    if cap.input_id not in lineage.cap.ids:
        raise ValueError("LINEAGE_CAP_ARTIFACT_MISMATCH")
    if listing.pair != f"{listing.base_asset_symbol}_{listing.quote_asset_symbol}":
        raise ValueError("LISTING_PAIR_COMPONENT_MISMATCH")
    if (
        listing.pair != lineage.listing.pair
        or listing.base_asset_symbol != lineage.listing.base_asset_symbol
        or listing.quote_asset_symbol != lineage.listing.quote_asset_symbol
        or listing.provider_asset_id != lineage.listing.provider_asset_id
    ):
        raise ValueError("LINEAGE_LISTING_ARTIFACT_MISMATCH")
    if cap.pair != f"{cap.base_asset_symbol}_{cap.quote_asset_symbol}":
        raise ValueError("CAP_PAIR_COMPONENT_MISMATCH")
    if (
        cap.pair != listing.pair
        or cap.base_asset_symbol != listing.base_asset_symbol
        or cap.quote_asset_symbol != listing.quote_asset_symbol
        or cap.provider_asset_id != listing.provider_asset_id
    ):
        raise ValueError("CAP_ASSET_IDENTITY_MISMATCH")
    if (
        cap.pair != lineage.cap.pair
        or cap.base_asset_symbol != lineage.cap.base_asset_symbol
        or cap.quote_asset_symbol != lineage.cap.quote_asset_symbol
        or cap.provider_asset_id != lineage.cap.provider_asset_id
    ):
        raise ValueError("LINEAGE_CAP_ARTIFACT_MISMATCH")
    target_pair = listing.pair
    if (
        cap.pair != target_pair
        or any(row.pair.pair != target_pair for row in trades)
        or any(row.pair != target_pair for row in bars)
        or any(row.pair.pair != target_pair for row in books)
    ):
        raise ValueError(
            "INPUT_PAIR_MISMATCH: materializer inputs must use one canonical pair and assets"
        )
    if listing.listed_at > listing.available_at:
        raise ValueError(
            "LISTING_CAUSAL_ORDER: listing source timestamp is after availability"
        )
    if cap.source_ts > cap.available_at:
        raise ValueError("CAP_CAUSAL_ORDER: cap source timestamp is after availability")
    if any(row.event_ts > row.available_at for row in trades):
        raise ValueError("TRADE_CAUSAL_ORDER: trade event timestamp is after availability")
    if any(row.event_ts > row.available_at for row in books):
        raise ValueError("BOOK_CAUSAL_ORDER: book event timestamp is after availability")
    if any(
        not (
            row.first_event_ts
            <= row.last_event_ts
            <= row.close_time
            <= row.available_at
        )
        for row in bars
    ):
        raise ValueError(
            "BAR_CAUSAL_ORDER: expected first_event_ts <= last_event_ts "
            "<= close_time <= available_at"
        )
    trade_sources = {row.source for row in trades}
    if len(trade_sources) != 1 or any(row.source not in trade_sources for row in bars):
        raise ValueError("BAR_PROVIDER_MISMATCH: bars and trades must use one source provider")
    if any(row.source_snapshot_id != lineage.bronze_snapshot_id for row in bars):
        raise ValueError("BAR_SNAPSHOT_MISMATCH: bar source snapshot does not match lineage")
    _require_utc_before_cutoff(
        (
            listing.listed_at,
            listing.available_at,
            cap.source_ts,
            cap.available_at,
            *(row.event_ts for row in trades),
            *(row.available_at for row in trades),
            *(row.first_event_ts for row in bars),
            *(row.last_event_ts for row in bars),
            *(row.close_time for row in bars),
            *(row.available_at for row in bars),
            *(row.event_ts for row in books),
            *(row.available_at for row in books),
        ),
        cutoff,
    )
    daily_quote = _daily_quote_volume(trades, as_of_date, profile.trade_lookback_days)
    spreads, depth_10bps, depth_50bps = _book_metrics(books, cutoff)
    if len(spreads) < profile.spread_lookback_days:
        raise ValueError("materializer does not have complete spread lookback")
    bar_ids = tuple(sorted({row.bar_id for row in bars if row.available_at <= cutoff}))
    if not bar_ids:
        raise ValueError("materializer bars are unavailable at cutoff")
    if bar_ids != lineage.bars.bar_ids:
        raise ValueError("LINEAGE_BAR_ID_MISMATCH")
    source_ids = lineage.canonical_ids()
    trade_batch_id = lineage.trade_batches[0].batch_id
    return UniverseMetrics(
        as_of_date=as_of_date,
        pair=listing.pair,
        asset=listing.asset,
        quote_asset=listing.quote_asset,
        listed_at=listing.listed_at,
        active=listing.active,
        tradable=listing.tradable,
        median_quote_volume_30d=_median(daily_quote),
        median_spread_bps_7d=_median(spreads),
        depth_10bps=depth_10bps,
        depth_50bps=depth_50bps,
        simulated_order_quote=profile.simulated_order_quote,
        zero_volume_ratio_30d=(
            Decimal(sum(value == 0 for value in daily_quote)) / Decimal(len(daily_quote))
        ),
        quality_status=QualityStatus.PASS,
        liquidity_available_at=max(
            [row.available_at for row in trades]
            + [row.available_at for row in bars]
            + [row.available_at for row in books]
        ),
        source="public-trades+public-book+listing",
        source_input_id=trade_batch_id,
        additional_source_input_ids=source_ids,
        market_cap_usd=cap.market_cap_usd,
        market_cap_rank=cap.market_cap_rank,
        cap_source_ts=cap.source_ts,
        cap_available_at=cap.available_at,
        cap_expires_at=cap.expires_at,
        cap_source=cap.source,
        cap_input_id=cap.input_id,
    )


def _daily_quote_volume(
    trades: tuple[TradeEvent, ...], as_of_date: date, days: int
) -> list[Decimal]:
    if days <= 0:
        raise ValueError("trade lookback must be positive")
    first = as_of_date - timedelta(days=days - 1)
    by_day: defaultdict[date, Decimal] = defaultdict(Decimal)
    for trade in trades:
        if first <= trade.event_ts.date() <= as_of_date:
            by_day[trade.event_ts.date()] += trade.quote_qty
    return [by_day[first + timedelta(days=index)] for index in range(days)]


def _book_metrics(
    books: tuple[BookEvent, ...], cutoff: datetime
) -> tuple[list[Decimal], Decimal, Decimal]:
    snapshots: defaultdict[tuple[datetime, int], list[BookEvent]] = defaultdict(list)
    for book in books:
        if book.available_at <= cutoff:
            snapshots[(book.event_ts, book.sequence)].append(book)
    spreads: list[Decimal] = []
    depths_10: list[Decimal] = []
    depths_50: list[Decimal] = []
    for rows in snapshots.values():
        asks = [row for row in rows if row.side is BookSide.ASK]
        bids = [row for row in rows if row.side is BookSide.BID]
        if not asks or not bids:
            continue
        best_ask = min(asks, key=lambda row: row.price)
        best_bid = max(bids, key=lambda row: row.price)
        midpoint = (best_ask.price + best_bid.price) / Decimal(2)
        if midpoint <= 0:
            continue
        spreads.append((best_ask.price - best_bid.price) / midpoint * Decimal(10_000))
        depths_10.append(_depth(rows, midpoint, Decimal(10)))
        depths_50.append(_depth(rows, midpoint, Decimal(50)))
    if not spreads:
        raise ValueError("materializer has no complete public book")
    return spreads, _median(depths_10), _median(depths_50)


def _depth(rows: Iterable[BookEvent], midpoint: Decimal, bps: Decimal) -> Decimal:
    limit = midpoint * (Decimal(1) + bps / Decimal(10_000))
    lower = midpoint * (Decimal(1) - bps / Decimal(10_000))
    return sum(
        (row.quote_qty for row in rows if lower <= row.price <= limit), Decimal(0)
    )


def _median(values: Iterable[Decimal]) -> Decimal:
    rows = sorted(values)
    if not rows:
        raise ValueError("median needs a value")
    middle = len(rows) // 2
    return rows[middle] if len(rows) % 2 else (rows[middle - 1] + rows[middle]) / Decimal(2)


def _require_utc_before_cutoff(values: Iterable[datetime], cutoff: datetime) -> None:
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0) for value in values):
        raise ValueError("INPUT_NOT_UTC: materializer input is not UTC")
    if any(value > cutoff for value in values):
        raise ValueError("INPUT_AFTER_BUILD_CUTOFF: materializer input is after cutoff")


def _require_utc(value: datetime, code: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{code}: timestamp must use UTC")
