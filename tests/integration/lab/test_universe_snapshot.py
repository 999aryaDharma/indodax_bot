"""Offline point-in-time universe adapter and snapshot integration tests."""

from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from indodax_lab.cli.build_universe import main
from indodax_lab.contracts import QualityStatus
from indodax_lab.universe.coingecko_adapter import (
    CoinGeckoAdapter,
    HttpResponse,
    ProviderUnavailableCode,
)
from indodax_lab.universe.contracts import UniverseMetrics, UniverseTier, load_universe_policy
from indodax_lab.universe.snapshot import build_daily_snapshot

AS_OF = date(2024, 1, 31)
AVAILABLE_AT = datetime(2024, 1, 31, 1, tzinfo=UTC)
CONFIG = Path(__file__).parents[3] / "configs" / "universe" / "default_v1.yaml"


def _sha(character: str) -> str:
    return f"sha256:{character * 64}"


def _metrics(pair: str, **changes: object) -> UniverseMetrics:
    asset = pair.split("_", maxsplit=1)[0]
    values: dict[str, object] = {
        "as_of_date": AS_OF,
        "pair": pair,
        "asset": asset,
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
        "liquidity_available_at": AVAILABLE_AT,
        "source": "indodax",
        "source_input_id": _sha("a"),
        "market_cap_usd": Decimal("1000000000"),
        "market_cap_rank": 10,
        "cap_source_ts": datetime(2024, 1, 31, tzinfo=UTC),
        "cap_available_at": AVAILABLE_AT,
        "cap_expires_at": datetime(2024, 2, 2, 1, tzinfo=UTC),
        "cap_source": "coingecko",
        "cap_input_id": _sha("b"),
    }
    values.update(changes)
    return UniverseMetrics(**values)


class FakeTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], float]] = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        return self.response


def test_fake_provider_persists_raw_lineage_and_preserves_decimal_integer_types(tmp_path):
    """Coercing provider failures/money to zero/float would corrupt cap classification."""
    body = json.dumps(
        [
            {
                "id": "bitcoin",
                "market_cap": 12345678901234567890,
                "market_cap_rank": 1,
                "last_updated": "2024-01-31T00:00:00Z",
            }
        ]
    ).encode()
    transport = FakeTransport(HttpResponse(200, {"Content-Type": "application/json"}, body))
    adapter = CoinGeckoAdapter(
        transport=transport,
        data_root=tmp_path,
        ttl_seconds=172800,
    )

    batch = adapter.fetch_market_caps(
        asset_ids=("bitcoin",), as_of_date=AS_OF, received_at=AVAILABLE_AT
    )

    assert len(batch.observations) == 1
    observation = batch.observations[0]
    assert observation.market_cap_usd == Decimal("12345678901234567890")
    assert isinstance(observation.market_cap_usd, Decimal)
    assert observation.market_cap_rank == 1
    assert type(observation.market_cap_rank) is int
    assert observation.source_ts == datetime(2024, 1, 31, tzinfo=UTC)
    assert observation.available_at == AVAILABLE_AT
    assert observation.ttl_seconds == 172800
    assert observation.source_input_id == batch.wire.response_id
    assert batch.unavailable == ()
    assert batch.wire.body_path.read_bytes() == body
    metadata = json.loads(batch.wire.metadata_path.read_text(encoding="utf-8"))
    assert metadata["adapter_policy_version"] == "coingecko-current-v1"
    assert metadata["available_at"] == "2024-01-31T01:00:00+00:00"
    assert metadata["ttl_seconds"] == 172800
    assert metadata["source_timestamps"] == ["2024-01-31T00:00:00+00:00"]
    claimed_response_id = metadata.pop("response_id")
    canonical_metadata = json.dumps(
        metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    assert claimed_response_id == f"sha256:{hashlib.sha256(canonical_metadata).hexdigest()}"
    assert transport.calls == [
        (
            "https://api.coingecko.com/api/v3/coins/markets",
            {"vs_currency": "usd", "ids": "bitcoin"},
            30.0,
        )
    ]


def test_current_only_provider_never_queries_current_markets_for_a_historical_date(tmp_path):
    """Sending an ignored date to current markets would misrepresent today's cap as historical."""
    transport = FakeTransport(HttpResponse(200, {}, b"[]"))
    adapter = CoinGeckoAdapter(
        transport=transport,
        data_root=tmp_path,
        ttl_seconds=172800,
    )

    batch = adapter.fetch_market_caps(
        asset_ids=("bitcoin",),
        as_of_date=date(2020, 1, 1),
        received_at=AVAILABLE_AT,
    )

    assert transport.calls == []
    assert batch.observations == ()
    assert len(batch.unavailable) == 1
    assert batch.unavailable[0].code is ProviderUnavailableCode.HISTORICAL_UNSUPPORTED
    assert batch.unavailable[0].market_cap_usd is None
    assert batch.wire is None
    assert batch.audit_path is not None and batch.audit_path.is_file()
    audit = json.loads(batch.audit_path.read_text(encoding="utf-8"))
    assert audit["capability"] == "CURRENT_ONLY"
    assert audit["adapter_policy_version"] == "coingecko-current-v1"
    assert audit["requested_as_of_date"] == "2020-01-01"
    assert audit["available_at"] == "2024-01-31T01:00:00+00:00"
    assert audit["reason"] == "HISTORICAL_UNSUPPORTED"


def test_provider_rejects_source_timestamp_after_response_availability(tmp_path):
    """Accepting future source time would violate causal point-in-time availability."""
    body = json.dumps(
        [
            {
                "id": "bitcoin",
                "market_cap": 100,
                "market_cap_rank": 1,
                "last_updated": "2024-01-31T01:00:00.000001Z",
            }
        ]
    ).encode()
    adapter = CoinGeckoAdapter(
        transport=FakeTransport(HttpResponse(200, {}, body)),
        data_root=tmp_path,
        ttl_seconds=172800,
    )

    batch = adapter.fetch_market_caps(
        asset_ids=("bitcoin",), as_of_date=AS_OF, received_at=AVAILABLE_AT
    )

    assert batch.observations == ()
    assert batch.unavailable[0].code is ProviderUnavailableCode.INVALID_RESPONSE
    assert batch.unavailable[0].market_cap_usd is None


def test_safe_header_variation_produces_distinct_immutable_response_identity(tmp_path):
    """Hashing only the body would put different persisted metadata under one response ID."""
    body = json.dumps(
        [
            {
                "id": "bitcoin",
                "market_cap": 100,
                "market_cap_rank": 1,
                "last_updated": "2024-01-31T00:00:00Z",
            }
        ]
    ).encode()
    first = CoinGeckoAdapter(
        transport=FakeTransport(HttpResponse(200, {"ETag": '"v1"'}, body)),
        data_root=tmp_path,
        ttl_seconds=172800,
    ).fetch_market_caps(asset_ids=("bitcoin",), as_of_date=AS_OF, received_at=AVAILABLE_AT)
    second = CoinGeckoAdapter(
        transport=FakeTransport(HttpResponse(200, {"ETag": '"v2"'}, body)),
        data_root=tmp_path,
        ttl_seconds=172800,
    ).fetch_market_caps(asset_ids=("bitcoin",), as_of_date=AS_OF, received_at=AVAILABLE_AT)

    assert first.wire is not None and second.wire is not None
    assert first.wire.response_id != second.wire.response_id
    assert first.wire.metadata_path != second.wire.metadata_path
    assert json.loads(first.wire.metadata_path.read_text())["response_headers"] == {
        "etag": '"v1"'
    }
    assert json.loads(second.wire.metadata_path.read_text())["response_headers"] == {
        "etag": '"v2"'
    }


def test_rate_quota_and_provider_errors_are_explicit_unavailable_never_zero(tmp_path):
    """Mapping an HTTP error to numeric zero would fabricate a cap observation."""
    for index, (status, code) in enumerate(
        [
            (429, ProviderUnavailableCode.RATE_LIMITED),
            (403, ProviderUnavailableCode.QUOTA_EXHAUSTED),
            (503, ProviderUnavailableCode.PROVIDER_ERROR),
        ]
    ):
        root = tmp_path / str(index)
        adapter = CoinGeckoAdapter(
            transport=FakeTransport(HttpResponse(status, {}, b'{"error":"unavailable"}')),
            data_root=root,
            ttl_seconds=172800,
        )

        batch = adapter.fetch_market_caps(
            asset_ids=("bitcoin",), as_of_date=AS_OF, received_at=AVAILABLE_AT
        )

        assert batch.observations == ()
        assert len(batch.unavailable) == 1
        assert batch.unavailable[0].code is code
        assert batch.unavailable[0].market_cap_usd is None
        assert batch.unavailable[0].market_cap_rank is None
        assert batch.wire.body_path.read_bytes() == b'{"error":"unavailable"}'


def test_snapshot_retains_delisted_and_new_pairs_and_is_content_addressed(tmp_path):
    """Filtering against today's listing set would erase historical delisted decisions."""
    loaded = load_universe_policy(CONFIG)
    inputs = (
        _metrics("delisted_idr"),
        _metrics("new_idr", listed_at=datetime(2024, 1, 15, tzinfo=UTC)),
    )

    first = build_daily_snapshot(
        data_root=tmp_path,
        metrics=inputs,
        policy=loaded.policy,
        policy_source_id=loaded.source_id,
    )
    replay = build_daily_snapshot(
        data_root=tmp_path,
        metrics=tuple(reversed(inputs)),
        policy=loaded.policy,
        policy_source_id=loaded.source_id,
    )

    assert first.universe_snapshot_id == replay.universe_snapshot_id
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", first.universe_snapshot_id)
    assert [decision.pair for decision in first.decisions] == ["delisted_idr", "new_idr"]
    assert first.decisions[0].eligible is True
    assert first.decisions[1].eligible is False
    assert first.data_path == replay.data_path
    assert first.manifest_path == replay.manifest_path
    assert len(list(tmp_path.rglob("universe.jsonl"))) == 1
    assert len(list(tmp_path.rglob("manifest.json"))) == 1
    assert tmp_path.resolve() in first.data_path.resolve().parents
    assert ".." not in first.data_path.relative_to(tmp_path).parts
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["policy"] == {
        "policy_version": "universe-v1",
        "source_id": loaded.source_id,
    }
    assert manifest["row_count"] == 2
    rows = [json.loads(line) for line in first.data_path.read_text().splitlines()]
    assert rows[0]["pair"] == "delisted_idr"
    assert rows[0]["tier"] == "BIG_CAP"
    assert rows[1]["pair"] == "new_idr"
    assert rows[1]["eligible"] is False


def test_current_or_late_cap_never_labels_past_and_raw_input_changes_snapshot_id(tmp_path):
    """Ignoring cap availability or raw lineage would enable lookahead and ID collisions."""
    loaded = load_universe_policy(CONFIG)
    current_cap = _metrics(
        "btc_idr",
        cap_source_ts=datetime(2024, 8, 1, tzinfo=UTC),
        cap_available_at=datetime(2024, 8, 1, tzinfo=UTC),
        cap_input_id=_sha("c"),
    )
    changed_raw = current_cap.model_copy(update={"cap_input_id": _sha("d")})

    first = build_daily_snapshot(
        data_root=tmp_path,
        metrics=(current_cap,),
        policy=loaded.policy,
        policy_source_id=loaded.source_id,
    )
    changed = build_daily_snapshot(
        data_root=tmp_path,
        metrics=(changed_raw,),
        policy=loaded.policy,
        policy_source_id=loaded.source_id,
    )

    assert first.decisions[0].tier is UniverseTier.LIQUIDITY_ONLY
    assert first.decisions[0].market_cap_usd is None
    assert first.decisions[0].cap_source_ts is None
    assert first.universe_snapshot_id != changed.universe_snapshot_id


def test_cli_dry_run_is_offline_and_creates_no_output_root(tmp_path):
    """A planning command must not contact a provider or publish partial artifacts."""
    loaded = load_universe_policy(CONFIG)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps([_metrics("btc_idr").model_dump(mode="json")]), encoding="utf-8"
    )
    output_root = tmp_path / "must-not-exist"
    stdout = io.StringIO()

    exit_code = main(
        [
            "--as-of-date",
            "2024-01-31",
            "--config",
            str(CONFIG),
            "--metrics",
            str(metrics_path),
            "--data-root",
            str(output_root),
            "--dry-run",
        ],
        stdout=stdout,
    )

    assert exit_code == 0
    assert stdout.getvalue().startswith("rows=1 eligible=1 snapshot_id=sha256:")
    assert loaded.source_id in stdout.getvalue()
    assert not output_root.exists()
