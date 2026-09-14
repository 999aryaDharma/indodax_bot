"""Pure point-in-time universe classification with explicit audit reasons."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from indodax_lab.contracts import QualityStatus

from .contracts import (
    ReasonCode,
    TierPolicy,
    UniverseDecision,
    UniverseMetrics,
    UniversePolicy,
    UniverseTier,
)


def classify_pair(metrics: UniverseMetrics, policy: UniversePolicy) -> UniverseDecision:
    """Pure point-in-time classification; no provider, network, clock, or filesystem calls."""
    cutoff = datetime.combine(metrics.as_of_date, time.max, tzinfo=UTC)
    cap_valid, cap_stale = _cap_is_valid(metrics, policy, cutoff)
    if cap_valid:
        tier = (
            UniverseTier.BIG_CAP
            if metrics.market_cap_rank <= policy.cap_rank_boundary
            else UniverseTier.SMALL_CAP
        )
        tier_policy = policy.big if tier is UniverseTier.BIG_CAP else policy.small
        cap_reasons: list[ReasonCode] = []
    else:
        tier = policy.fallback_tier
        tier_policy = policy.small
        cap_reasons = [ReasonCode.CAP_HISTORY_MISSING]
        if cap_stale:
            cap_reasons.append(ReasonCode.SOURCE_STALE)

    listing_age_days = (metrics.as_of_date - metrics.listed_at.date()).days
    gate_reasons = _liquidity_reasons(metrics, tier_policy, cutoff, listing_age_days)
    eligible = not gate_reasons
    decision_tier = tier if eligible else None
    market_cap_usd = metrics.market_cap_usd if cap_valid else None
    market_cap_rank = metrics.market_cap_rank if cap_valid else None
    cap_source_ts = metrics.cap_source_ts if cap_valid else None
    available_at = metrics.liquidity_available_at
    sources = [metrics.source]
    if cap_valid:
        available_at = max(available_at, metrics.cap_available_at)
        sources.append(metrics.cap_source)
    input_ids = sorted(
        {
            identity
            for identity in (
                metrics.source_input_id,
                metrics.cap_input_id,
                *metrics.additional_source_input_ids,
            )
            if identity
        }
    )

    return UniverseDecision(
        as_of_date=metrics.as_of_date,
        pair=metrics.pair,
        asset=metrics.asset,
        quote_asset=metrics.quote_asset,
        listed_at=metrics.listed_at,
        listing_age_days=listing_age_days,
        market_cap_usd=market_cap_usd,
        market_cap_rank=market_cap_rank,
        cap_source_ts=cap_source_ts,
        median_quote_volume_30d=metrics.median_quote_volume_30d,
        median_spread_bps_7d=metrics.median_spread_bps_7d,
        depth_10bps=metrics.depth_10bps,
        depth_50bps=metrics.depth_50bps,
        zero_volume_ratio_30d=metrics.zero_volume_ratio_30d,
        tier=decision_tier,
        eligible=eligible,
        reason_codes=tuple(cap_reasons + gate_reasons),
        available_at=available_at,
        source="+".join(sources),
        source_input_ids=tuple(input_ids),
    )


def _cap_is_valid(
    metrics: UniverseMetrics, policy: UniversePolicy, cutoff: datetime
) -> tuple[bool, bool]:
    complete = all(
        value is not None
        for value in (
            metrics.market_cap_usd,
            metrics.market_cap_rank,
            metrics.cap_source_ts,
            metrics.cap_available_at,
            metrics.cap_expires_at,
            metrics.cap_source,
            metrics.cap_input_id,
        )
    )
    if not complete or metrics.cap_source != policy.cap_source:
        return False, False
    if metrics.cap_source_ts > metrics.cap_available_at:
        return False, False
    if metrics.cap_source_ts > cutoff or metrics.cap_available_at > cutoff:
        return False, False
    expected_expiry = metrics.cap_available_at + timedelta(
        seconds=policy.cap_source_ttl_seconds
    )
    if metrics.cap_expires_at != expected_expiry:
        return False, cutoff > metrics.cap_expires_at
    if cutoff > metrics.cap_expires_at:
        return False, True
    return True, False


def _liquidity_reasons(
    metrics: UniverseMetrics,
    tier_policy: TierPolicy,
    cutoff: datetime,
    listing_age_days: int,
) -> list[ReasonCode]:
    reasons: list[ReasonCode] = []
    if listing_age_days < tier_policy.listing_age_days_min:
        reasons.append(ReasonCode.LISTING_TOO_YOUNG)
    if metrics.zero_volume_ratio_30d > tier_policy.zero_volume_ratio_30d_max:
        reasons.append(ReasonCode.ZERO_VOLUME_TOO_HIGH)
    if metrics.median_spread_bps_7d > tier_policy.median_spread_bps_7d_max:
        reasons.append(ReasonCode.SPREAD_TOO_WIDE)
    depth = metrics.depth_10bps if tier_policy.depth_band_bps == 10 else metrics.depth_50bps
    required_depth = metrics.simulated_order_quote * tier_policy.depth_to_order_multiple_min
    if depth < required_depth:
        reasons.append(ReasonCode.DEPTH_TOO_LOW)
    if metrics.quality_status is not QualityStatus.PASS:
        reasons.append(ReasonCode.DATA_QUALITY_FAIL)
    if not metrics.active:
        reasons.append(ReasonCode.PAIR_INACTIVE)
    if not metrics.tradable:
        reasons.append(ReasonCode.PAIR_UNTRADABLE)
    if metrics.liquidity_available_at > cutoff:
        reasons.append(ReasonCode.SOURCE_AFTER_CUTOFF)
    return reasons
