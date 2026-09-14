"""Pure point-in-time universe eligibility tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from indodax_lab.contracts import QualityStatus
from indodax_lab.universe.contracts import (
    ReasonCode,
    TierPolicy,
    UniverseMetrics,
    UniversePolicy,
    UniverseTier,
    load_universe_policy,
)
from indodax_lab.universe.eligibility import classify_pair

AS_OF = date(2024, 1, 31)
CUTOFF = datetime(2024, 1, 31, 23, 59, 59, 999999, tzinfo=UTC)


def _sha(character: str) -> str:
    return f"sha256:{character * 64}"


def _policy() -> UniversePolicy:
    return UniversePolicy(
        policy_version="universe-v1",
        cap_rank_boundary=100,
        cap_source="coingecko",
        cap_source_ttl_seconds=172800,
        fallback_tier=UniverseTier.LIQUIDITY_ONLY,
        big=TierPolicy(
            listing_age_days_min=180,
            zero_volume_ratio_30d_max=Decimal("0.02"),
            median_spread_bps_7d_max=Decimal("75"),
            depth_band_bps=50,
            depth_to_order_multiple_min=Decimal("20"),
        ),
        small=TierPolicy(
            listing_age_days_min=180,
            zero_volume_ratio_30d_max=Decimal("0.05"),
            median_spread_bps_7d_max=Decimal("150"),
            depth_band_bps=50,
            depth_to_order_multiple_min=Decimal("10"),
        ),
    )


def _metrics(**changes: object) -> UniverseMetrics:
    values: dict[str, object] = {
        "as_of_date": AS_OF,
        "pair": "btc_idr",
        "asset": "btc",
        "quote_asset": "idr",
        "listed_at": datetime(2020, 1, 1, tzinfo=UTC),
        "active": True,
        "tradable": True,
        "median_quote_volume_30d": Decimal("1000000000"),
        "median_spread_bps_7d": Decimal("50"),
        "depth_10bps": Decimal("25000"),
        "depth_50bps": Decimal("25000"),
        "simulated_order_quote": Decimal("1000"),
        "zero_volume_ratio_30d": Decimal("0.01"),
        "quality_status": QualityStatus.PASS,
        "liquidity_available_at": datetime(2024, 1, 31, 1, tzinfo=UTC),
        "source": "indodax",
        "source_input_id": _sha("a"),
        "market_cap_usd": Decimal("1000000000000"),
        "market_cap_rank": 10,
        "cap_source_ts": datetime(2024, 1, 31, 0, tzinfo=UTC),
        "cap_available_at": datetime(2024, 1, 31, 1, tzinfo=UTC),
        "cap_expires_at": datetime(2024, 2, 2, 1, tzinfo=UTC),
        "cap_source": "coingecko",
        "cap_input_id": _sha("b"),
    }
    values.update(changes)
    return UniverseMetrics(**values)


def test_point_in_time_rank_boundary_selects_big_or_small_liquidity_policy():
    """Using one liquidity policy for both rank sides would misclassify boundary assets."""
    big = classify_pair(_metrics(), _policy())
    small = classify_pair(
        _metrics(
            market_cap_rank=101,
            zero_volume_ratio_30d=Decimal("0.04"),
            median_spread_bps_7d=Decimal("120"),
            depth_50bps=Decimal("10000"),
        ),
        _policy(),
    )

    assert (big.eligible, big.tier, big.reason_codes) == (True, UniverseTier.BIG_CAP, ())
    assert (small.eligible, small.tier, small.reason_codes) == (
        True,
        UniverseTier.SMALL_CAP,
        (),
    )


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"listed_at": datetime(2023, 10, 1, tzinfo=UTC)}, ReasonCode.LISTING_TOO_YOUNG),
        ({"zero_volume_ratio_30d": Decimal("0.021")}, ReasonCode.ZERO_VOLUME_TOO_HIGH),
        ({"median_spread_bps_7d": Decimal("75.01")}, ReasonCode.SPREAD_TOO_WIDE),
        ({"depth_50bps": Decimal("19999")}, ReasonCode.DEPTH_TOO_LOW),
        ({"quality_status": QualityStatus.FAIL}, ReasonCode.DATA_QUALITY_FAIL),
        ({"active": False}, ReasonCode.PAIR_INACTIVE),
        ({"tradable": False}, ReasonCode.PAIR_UNTRADABLE),
        (
            {"liquidity_available_at": datetime(2024, 2, 1, tzinfo=UTC)},
            ReasonCode.SOURCE_AFTER_CUTOFF,
        ),
    ],
)
def test_each_fail_closed_gate_emits_a_stable_reason_code(changes, reason):
    """Dropping a gate or its audit code would silently admit an invalid pair."""
    decision = classify_pair(_metrics(**changes), _policy())

    assert decision.eligible is False
    assert decision.tier is None
    assert reason in decision.reason_codes


def test_missing_historical_cap_falls_back_without_becoming_small_cap():
    """Treating absent cap as rank zero or infinity would invent a cap label."""
    decision = classify_pair(
        _metrics(
            market_cap_usd=None,
            market_cap_rank=None,
            cap_source_ts=None,
            cap_available_at=None,
            cap_expires_at=None,
            cap_source=None,
            cap_input_id=None,
        ),
        _policy(),
    )

    assert decision.eligible is True
    assert decision.tier is UniverseTier.LIQUIDITY_ONLY
    assert decision.reason_codes == (ReasonCode.CAP_HISTORY_MISSING,)
    assert decision.market_cap_usd is None
    assert decision.market_cap_rank is None


@pytest.mark.parametrize(
    "cap_changes",
    [
        {
            "cap_source_ts": datetime(2024, 8, 1, tzinfo=UTC),
            "cap_available_at": datetime(2024, 8, 1, tzinfo=UTC),
        },
        {"cap_available_at": datetime(2024, 2, 1, tzinfo=UTC)},
    ],
)
def test_future_or_late_current_cap_never_backfills_a_past_snapshot(cap_changes):
    """Allowing a post-cutoff payload would introduce point-in-time lookahead."""
    decision = classify_pair(_metrics(**cap_changes), _policy())

    assert decision.eligible is True
    assert decision.tier is UniverseTier.LIQUIDITY_ONLY
    assert ReasonCode.CAP_HISTORY_MISSING in decision.reason_codes
    assert decision.market_cap_usd is None
    assert decision.cap_source_ts is None
    assert decision.available_at <= CUTOFF


def test_stale_cap_is_audited_and_only_liquidity_can_classify_the_pair():
    """An expired provider observation must not retain a big/small label."""
    decision = classify_pair(
        _metrics(
            cap_source_ts=datetime(2024, 1, 1, tzinfo=UTC),
            cap_available_at=datetime(2024, 1, 1, tzinfo=UTC),
            cap_expires_at=datetime(2024, 1, 3, tzinfo=UTC),
        ),
        _policy(),
    )

    assert decision.eligible is True
    assert decision.tier is UniverseTier.LIQUIDITY_ONLY
    assert decision.reason_codes == (
        ReasonCode.CAP_HISTORY_MISSING,
        ReasonCode.SOURCE_STALE,
    )


def test_cap_expiry_boundary_is_inclusive_and_derived_from_availability():
    """Recomputing TTL from source time would reject a delayed but unexpired response."""
    policy = _policy().model_copy(update={"cap_source_ttl_seconds": 2})
    available_at = CUTOFF.replace(second=57, microsecond=999999)
    at_expiry = classify_pair(
        _metrics(
            cap_source_ts=datetime(2024, 1, 1, tzinfo=UTC),
            cap_available_at=available_at,
            cap_expires_at=CUTOFF,
        ),
        policy,
    )
    expired = classify_pair(
        _metrics(
            cap_source_ts=datetime(2024, 1, 1, tzinfo=UTC),
            cap_available_at=available_at,
            cap_expires_at=CUTOFF.replace(microsecond=999998),
        ),
        policy,
    )

    assert (at_expiry.eligible, at_expiry.tier, at_expiry.reason_codes) == (
        True,
        UniverseTier.BIG_CAP,
        (),
    )
    assert (expired.eligible, expired.tier, expired.reason_codes) == (
        True,
        UniverseTier.LIQUIDITY_ONLY,
        (ReasonCode.CAP_HISTORY_MISSING, ReasonCode.SOURCE_STALE),
    )


def test_causally_impossible_cap_source_timestamp_is_not_classified():
    """A provider fact cannot exist before its claimed source event occurs."""
    decision = classify_pair(
        _metrics(
            cap_source_ts=datetime(2024, 1, 31, 2, tzinfo=UTC),
            cap_available_at=datetime(2024, 1, 31, 1, tzinfo=UTC),
        ),
        _policy(),
    )

    assert decision.eligible is True
    assert decision.tier is UniverseTier.LIQUIDITY_ONLY
    assert decision.reason_codes == (ReasonCode.CAP_HISTORY_MISSING,)
    assert decision.cap_source_ts is None


def test_newly_listed_pair_stays_in_decisions_but_is_ineligible():
    """Filtering before classification would erase the anti-survivorship audit row."""
    decision = classify_pair(
        _metrics(pair="new_idr", asset="new", listed_at=datetime(2024, 1, 1, tzinfo=UTC)),
        _policy(),
    )

    assert decision.pair == "new_idr"
    assert decision.listing_age_days == 30
    assert decision.eligible is False
    assert ReasonCode.LISTING_TOO_YOUNG in decision.reason_codes


def test_default_yaml_enforces_documented_boundary_behavior():
    """Weakening any documented default boundary would admit a literal over-limit input."""
    config = Path(__file__).parents[4] / "configs" / "universe" / "default_v1.yaml"
    loaded = load_universe_policy(config)

    at_big_limits = classify_pair(
        _metrics(
            zero_volume_ratio_30d=Decimal("0.02"),
            median_spread_bps_7d=Decimal("75"),
            depth_50bps=Decimal("20000"),
        ),
        loaded.policy,
    )
    over_big_limits = classify_pair(
        _metrics(
            zero_volume_ratio_30d=Decimal("0.0201"),
            median_spread_bps_7d=Decimal("75.1"),
            depth_50bps=Decimal("19999"),
        ),
        loaded.policy,
    )

    assert at_big_limits.eligible is True
    assert over_big_limits.reason_codes == (
        ReasonCode.ZERO_VOLUME_TOO_HIGH,
        ReasonCode.SPREAD_TOO_WIDE,
        ReasonCode.DEPTH_TOO_LOW,
    )
    assert loaded.source_id.startswith("sha256:")


@pytest.mark.parametrize(
    "yaml_text",
    [
        """policy_version: universe-v1
cap_rank_boundary: 100
cap_source: coingecko
cap_source_ttl_seconds: 86400
fallback_tier: LIQUIDITY_ONLY
unknown_field: true
big: &tier
  listing_age_days_min: 180
  zero_volume_ratio_30d_max: '0.02'
  median_spread_bps_7d_max: '75'
  depth_band_bps: 50
  depth_to_order_multiple_min: '20'
small: *tier
""",
        """policy_version: universe-v1
cap_rank_boundary: 0
cap_source: coingecko
cap_source_ttl_seconds: -1
fallback_tier: LIQUIDITY_ONLY
big: &tier
  listing_age_days_min: -1
  zero_volume_ratio_30d_max: '1.1'
  median_spread_bps_7d_max: '0'
  depth_band_bps: 25
  depth_to_order_multiple_min: '0'
small: *tier
""",
    ],
)
def test_unknown_fields_and_invalid_thresholds_fail_closed(tmp_path, yaml_text):
    """Ignoring config mistakes would create an unaudited eligibility policy."""
    config = tmp_path / "policy.yaml"
    config.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_universe_policy(config)
