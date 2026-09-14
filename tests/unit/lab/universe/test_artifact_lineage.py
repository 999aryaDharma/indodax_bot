"""Strongly typed artifact-reference loader contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.universe.coingecko_adapter import (
    CoinGeckoAdapter,
    HttpResponse,
)
from indodax_lab.universe.lineage import (
    CapProviderResponseArtifactRef,
    ListingArtifactRef,
    ProfileArtifactRef,
    load_cap_provider_artifact,
    load_listing_artifact,
    load_materialization_profile,
    require_reference_type,
)

PHASE1_FIXTURES = Path(__file__).parents[3] / "fixtures" / "indodax" / "phase1"


class _Transport:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def get(self, _url, *, params, timeout):
        del params, timeout
        return HttpResponse(200, {"Content-Type": "application/json"}, self.body)


def test_cap_loader_rejects_forged_observation_over_genuine_provider_body(
    tmp_path: Path,
) -> None:
    """Classification facts must be reconstructed from body 100/rank 9, never caller values."""
    listing = load_listing_artifact(PHASE1_FIXTURES / "listing.json")
    body = json.dumps(
        [
            {
                "id": "bitcoin",
                "market_cap": 100,
                "market_cap_rank": 9,
                "last_updated": "2024-01-01T00:00:00Z",
            }
        ],
        separators=(",", ":"),
    ).encode()
    batch = CoinGeckoAdapter(
        transport=_Transport(body), data_root=tmp_path, ttl_seconds=60
    ).fetch_market_caps(
        asset_ids=("bitcoin",),
        as_of_date=date(2024, 1, 1),
        received_at=datetime(2024, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    forged = replace(
        batch,
        observations=(
            replace(
                batch.observations[0],
                market_cap_usd=Decimal("999999"),
                market_cap_rank=1,
            ),
        ),
    )

    with pytest.raises(ValueError, match="CAP_PROVIDER_BATCH_MISMATCH"):
        load_cap_provider_artifact(forged, listing)


def test_listing_loader_rejects_pair_component_and_provider_mapping_mismatch(
    tmp_path: Path,
) -> None:
    """A btc_idr label cannot carry eth/usd components under the bitcoin provider ID."""
    listing_path = tmp_path / "listing.json"
    listing_path.write_text(
        '{"pair":"btc_idr","base_asset_symbol":"eth","quote_asset_symbol":"usd",'
        '"provider_asset_id":"bitcoin","listed_at":"2020-01-01T00:00:00Z",'
        '"active":true,"tradable":true,"available_at":"2024-01-01T00:00:00Z"}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="LISTING_PAIR_COMPONENT_MISMATCH"):
        load_listing_artifact(listing_path)


def test_listing_and_profile_refs_are_loaded_from_exact_schema_valid_bytes(tmp_path: Path) -> None:
    listing_path = tmp_path / "listing.json"
    listing_path.write_text(
        '{"pair":"btc_idr","base_asset_symbol":"btc","quote_asset_symbol":"idr",'
        '"provider_asset_id":"bitcoin","listed_at":"2020-01-01T00:00:00Z",'
        '"active":true,"tradable":true,"available_at":"2024-01-01T00:00:00Z"}',
        encoding="utf-8",
    )
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "profile_id: phase1\ntrade_lookback_days: 1\nspread_lookback_days: 1\n"
        "depth_band_bps: 50\nsimulated_order_quote: '1000'\n",
        encoding="utf-8",
    )

    listing = load_listing_artifact(listing_path)
    profile = load_materialization_profile(profile_path)

    assert type(listing.reference) is ListingArtifactRef
    assert type(profile.reference) is ProfileArtifactRef
    assert listing.evidence.provider_asset_id == "bitcoin"
    assert listing.evidence.input_id in listing.reference.ids
    assert profile.profile.trade_lookback_days == 1


def test_pipeline_lineage_rejects_one_verified_artifact_type_in_another_field() -> None:
    """A listing reference cannot masquerade as a cap-provider response despite sha IDs."""
    with pytest.raises(TypeError, match="LINEAGE_TYPE_MISMATCH:cap"):
        require_reference_type(
            "cap", object.__new__(ListingArtifactRef), CapProviderResponseArtifactRef
        )


def test_reference_constructor_rejects_arbitrary_sha_strings() -> None:
    """Only schema/checksum-verifying loaders may mint a typed artifact reference."""
    identity = "sha256:" + "a" * 64
    with pytest.raises(TypeError, match="verified production loader"):
        ListingArtifactRef(
            ids=(identity,),
            pair="btc_idr",
            base_asset_symbol="btc",
            quote_asset_symbol="idr",
            provider_asset_id="bitcoin",
        )
