"""Verified, strongly typed references for Phase 1 upstream artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import InitVar, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

import yaml

from indodax_lab.contracts import CanonicalPair, QualityStatus, TradeEvent
from indodax_lab.data.bars import SilverBar, load_time_bar_config
from indodax_lab.data.checksums import sha256_bytes, sha256_file
from indodax_lab.data.manifest import canonical_json_bytes, read_manifest, snapshot_manifest_path
from indodax_lab.data.parquet_store import CANDLE_SCHEMA_IDENTITY
from indodax_lab.data.quality import POLICY_VERSION as CANDLE_POLICY_VERSION
from indodax_lab.data.sentry import require_approved_snapshot_decision
from indodax_lab.data.stream_protocol import BookEvent
from indodax_lab.data.trade_sentry import (
    POLICY_VERSION as TRADE_POLICY_VERSION,
)
from indodax_lab.data.trade_sentry import (
    require_existing_approved_trade_decision,
)

from .coingecko_adapter import (
    CapBatch,
    ProviderUnavailableCode,
    reconstruct_coingecko_batch,
)
from .contracts import LoadedUniversePolicy, load_universe_policy

_IDENTITY = re.compile(r"^sha256:[0-9a-f]{64}$")
_VERIFIED = object()
_T = TypeVar("_T")


@dataclass(frozen=True)
class ListingEvidence:
    """One immutable offline listing observation with provider asset identity."""

    pair: str
    base_asset_symbol: str
    quote_asset_symbol: str
    listed_at: datetime
    active: bool
    tradable: bool
    available_at: datetime
    input_id: str
    provider_asset_id: str

    @property
    def base_asset(self) -> str:
        return self.base_asset_symbol

    @property
    def asset(self) -> str:
        return self.base_asset_symbol

    @property
    def quote_asset(self) -> str:
        return self.quote_asset_symbol


@dataclass(frozen=True)
class CapEvidence:
    """One immutable market-cap observation bound to a listing identity."""

    market_cap_usd: Decimal
    market_cap_rank: int
    source_ts: datetime
    available_at: datetime
    expires_at: datetime
    source: str
    input_id: str
    pair: str
    base_asset_symbol: str
    quote_asset_symbol: str
    provider_asset_id: str

    @property
    def base_asset(self) -> str:
        return self.base_asset_symbol

    @property
    def asset(self) -> str:
        return self.base_asset_symbol

    @property
    def quote_asset(self) -> str:
        return self.quote_asset_symbol


@dataclass(frozen=True)
class MaterializationProfile:
    """Explicit lookbacks loaded from exact versioned configuration bytes."""

    profile_id: str
    trade_lookback_days: int
    spread_lookback_days: int
    depth_band_bps: int
    simulated_order_quote: Decimal


@dataclass(frozen=True)
class _Reference:
    ids: tuple[str, ...]
    _token: InitVar[object] = None

    def __post_init__(self, _token: object) -> None:
        if _token is not _VERIFIED:
            raise TypeError("artifact references must come from a verified production loader")
        if not self.ids or len(self.ids) != len(set(self.ids)):
            raise ValueError("artifact reference identities must be non-empty and unique")
        if any(not _IDENTITY.fullmatch(value) for value in self.ids):
            raise ValueError("artifact reference identities must be canonical sha256 IDs")


@dataclass(frozen=True)
class CandleWireArtifactRef(_Reference):
    checkpoint_path: Path = Path()


@dataclass(frozen=True)
class BronzeSnapshotArtifactRef(_Reference):
    snapshot_id: str = ""
    manifest_path: Path = Path()


@dataclass(frozen=True)
class CandleQualityArtifactRef(_Reference):
    snapshot_id: str = ""
    decision_id: str = ""


@dataclass(frozen=True)
class TradeWireArtifactRef(_Reference):
    batch_id: str = ""
    wire_id: str = ""
    body_path: Path = Path()
    metadata_path: Path = Path()


@dataclass(frozen=True)
class TradeBatchArtifactRef(_Reference):
    batch_id: str = ""
    path: Path = Path()


@dataclass(frozen=True)
class GlobalTradeQualityArtifactRef(_Reference):
    batch_ids: tuple[str, ...] = ()
    decision_id: str = ""


@dataclass(frozen=True)
class BarArtifactRef(_Reference):
    output_id: str = ""
    manifest_id: str = ""
    config_id: str = ""
    bar_ids: tuple[str, ...] = ()
    source_snapshot_id: str = ""
    trade_batch_ids: tuple[str, ...] = ()
    trade_decision_id: str = ""
    candle_decision_id: str = ""


@dataclass(frozen=True)
class BookArtifactRef(_Reference):
    batch_id: str = ""


@dataclass(frozen=True)
class ListingArtifactRef(_Reference):
    pair: str = ""
    base_asset_symbol: str = ""
    quote_asset_symbol: str = ""
    provider_asset_id: str = ""

    @property
    def base_asset(self) -> str:
        return self.base_asset_symbol

    @property
    def quote_asset(self) -> str:
        return self.quote_asset_symbol


@dataclass(frozen=True)
class CapProviderResponseArtifactRef(_Reference):
    pair: str = ""
    base_asset_symbol: str = ""
    quote_asset_symbol: str = ""
    provider_asset_id: str = ""


@dataclass(frozen=True)
class ProfileArtifactRef(_Reference):
    profile_id: str = ""
    profile: MaterializationProfile | None = None


@dataclass(frozen=True)
class UniversePolicyArtifactRef(_Reference):
    policy_version: str = ""


@dataclass(frozen=True)
class LoadedListingArtifact:
    reference: ListingArtifactRef
    evidence: ListingEvidence


@dataclass(frozen=True)
class LoadedCapProviderArtifact:
    reference: CapProviderResponseArtifactRef
    evidence: CapEvidence


@dataclass(frozen=True)
class LoadedMaterializationProfile:
    reference: ProfileArtifactRef
    profile: MaterializationProfile


@dataclass(frozen=True)
class LoadedUniversePolicyArtifact:
    reference: UniversePolicyArtifactRef
    loaded: LoadedUniversePolicy


@dataclass(frozen=True)
class LoadedTradeArtifacts:
    wires: tuple[TradeWireArtifactRef, ...]
    batches: tuple[TradeBatchArtifactRef, ...]
    quality: GlobalTradeQualityArtifactRef
    trades: tuple[TradeEvent, ...]


@dataclass(frozen=True)
class LoadedBarArtifact:
    reference: BarArtifactRef
    bars: tuple[SilverBar, ...]


@dataclass(frozen=True)
class LoadedBookArtifact:
    reference: BookArtifactRef
    books: tuple[BookEvent, ...]


@dataclass(frozen=True)
class PipelineLineageInputs:
    """Every named upstream class, verified and impossible to substitute by type."""

    candle_wires: tuple[CandleWireArtifactRef, ...]
    bronze_snapshot: BronzeSnapshotArtifactRef
    candle_quality: CandleQualityArtifactRef
    trade_wires: tuple[TradeWireArtifactRef, ...]
    trade_batches: tuple[TradeBatchArtifactRef, ...]
    global_trade_quality: GlobalTradeQualityArtifactRef
    bars: BarArtifactRef
    book: BookArtifactRef
    listing: ListingArtifactRef
    cap: CapProviderResponseArtifactRef
    profile: ProfileArtifactRef
    universe_policy: UniversePolicyArtifactRef

    def __post_init__(self) -> None:
        _require_ref_tuple("candle_wires", self.candle_wires, CandleWireArtifactRef)
        require_reference_type("bronze_snapshot", self.bronze_snapshot, BronzeSnapshotArtifactRef)
        require_reference_type("candle_quality", self.candle_quality, CandleQualityArtifactRef)
        _require_ref_tuple("trade_wires", self.trade_wires, TradeWireArtifactRef)
        _require_ref_tuple("trade_batches", self.trade_batches, TradeBatchArtifactRef)
        require_reference_type(
            "global_trade_quality", self.global_trade_quality, GlobalTradeQualityArtifactRef
        )
        require_reference_type("bars", self.bars, BarArtifactRef)
        require_reference_type("book", self.book, BookArtifactRef)
        require_reference_type("listing", self.listing, ListingArtifactRef)
        require_reference_type("cap", self.cap, CapProviderResponseArtifactRef)
        require_reference_type("profile", self.profile, ProfileArtifactRef)
        require_reference_type("universe_policy", self.universe_policy, UniversePolicyArtifactRef)
        if self.profile.profile is None:
            raise ValueError("LINEAGE_PROFILE_MISSING")
        batch_ids = tuple(item.batch_id for item in self.trade_batches)
        if batch_ids != self.global_trade_quality.batch_ids:
            raise ValueError("LINEAGE_TRADE_QUALITY_MISMATCH")
        if {item.batch_id for item in self.trade_wires} != set(batch_ids):
            raise ValueError("LINEAGE_TRADE_WIRE_MISMATCH")
        if self.candle_quality.snapshot_id != self.bronze_snapshot.snapshot_id:
            raise ValueError("LINEAGE_CANDLE_QUALITY_MISMATCH")
        if self.bars.source_snapshot_id != self.bronze_snapshot.snapshot_id:
            raise ValueError("LINEAGE_BAR_SNAPSHOT_MISMATCH")
        if self.bars.trade_batch_ids != batch_ids:
            raise ValueError("LINEAGE_BAR_BATCH_MISMATCH")
        if self.bars.trade_decision_id != self.global_trade_quality.decision_id:
            raise ValueError("LINEAGE_BAR_TRADE_QUALITY_MISMATCH")
        if self.bars.candle_decision_id != self.candle_quality.decision_id:
            raise ValueError("LINEAGE_BAR_CANDLE_QUALITY_MISMATCH")
        if self.listing.pair != (
            f"{self.listing.base_asset_symbol}_{self.listing.quote_asset_symbol}"
        ):
            raise ValueError("LINEAGE_LISTING_COMPONENT_MISMATCH")
        if (
            self.listing.pair != self.cap.pair
            or self.listing.base_asset_symbol != self.cap.base_asset_symbol
            or self.listing.quote_asset_symbol != self.cap.quote_asset_symbol
            or self.listing.provider_asset_id != self.cap.provider_asset_id
        ):
            raise ValueError("LINEAGE_CAP_ASSET_MISMATCH")

    @property
    def bronze_snapshot_id(self) -> str:
        return self.bronze_snapshot.snapshot_id

    def canonical_ids(self) -> tuple[str, ...]:
        references: tuple[_Reference, ...] = (
            *self.candle_wires,
            self.bronze_snapshot,
            self.candle_quality,
            *self.trade_wires,
            *self.trade_batches,
            self.global_trade_quality,
            self.bars,
            self.book,
            self.listing,
            self.cap,
            self.profile,
            self.universe_policy,
        )
        return tuple(sorted({identity for reference in references for identity in reference.ids}))


def require_reference_type(field: str, value: object, expected: type[_T]) -> _T:
    """Reject semantic substitution even when two artifacts carry valid sha256 IDs."""
    if type(value) is not expected:
        raise TypeError(f"LINEAGE_TYPE_MISMATCH:{field}")
    return value


def load_listing_artifact(path: Path) -> LoadedListingArtifact:
    raw = Path(path).read_bytes()
    try:
        row = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("LISTING_ARTIFACT_INVALID") from error
    required = {
        "pair",
        "base_asset_symbol",
        "quote_asset_symbol",
        "provider_asset_id",
        "listed_at",
        "active",
        "tradable",
        "available_at",
    }
    if not isinstance(row, dict) or set(row) != required:
        raise ValueError("LISTING_ARTIFACT_SCHEMA_INVALID")
    string_fields = (
        "pair",
        "base_asset_symbol",
        "quote_asset_symbol",
        "provider_asset_id",
        "listed_at",
        "available_at",
    )
    if any(type(row[field]) is not str for field in string_fields):
        raise ValueError("LISTING_ARTIFACT_SCHEMA_INVALID")
    pair = str(row["pair"])
    base_asset_symbol = str(row["base_asset_symbol"])
    quote_asset_symbol = str(row["quote_asset_symbol"])
    try:
        CanonicalPair(pair=pair)
        CanonicalPair(pair=f"{base_asset_symbol}_{quote_asset_symbol}")
    except ValueError as error:
        raise ValueError("LISTING_PAIR_COMPONENT_MISMATCH") from error
    if pair != f"{base_asset_symbol}_{quote_asset_symbol}":
        raise ValueError("LISTING_PAIR_COMPONENT_MISMATCH")
    provider_asset_id = str(row["provider_asset_id"])
    if not re.fullmatch(r"[a-z0-9-]+", provider_asset_id):
        raise ValueError("LISTING_PROVIDER_ASSET_ID_INVALID")
    if type(row["active"]) is not bool or type(row["tradable"]) is not bool:
        raise ValueError("LISTING_ARTIFACT_SCHEMA_INVALID")
    listed_at = _utc(str(row["listed_at"]), "LISTING_ARTIFACT_INVALID")
    available_at = _utc(str(row["available_at"]), "LISTING_ARTIFACT_INVALID")
    identity = _bytes_id(raw)
    evidence = ListingEvidence(
        pair=pair,
        base_asset_symbol=base_asset_symbol,
        quote_asset_symbol=quote_asset_symbol,
        listed_at=listed_at,
        active=row["active"],
        tradable=row["tradable"],
        available_at=available_at,
        input_id=identity,
        provider_asset_id=provider_asset_id,
    )
    reference = ListingArtifactRef(
        ids=(identity,),
        pair=evidence.pair,
        base_asset_symbol=evidence.base_asset_symbol,
        quote_asset_symbol=evidence.quote_asset_symbol,
        provider_asset_id=evidence.provider_asset_id,
        _token=_VERIFIED,
    )
    return LoadedListingArtifact(reference, evidence)


def load_materialization_profile(path: Path) -> LoadedMaterializationProfile:
    raw = Path(path).read_bytes()
    try:
        row = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise ValueError("PROFILE_ARTIFACT_INVALID") from error
    required = {
        "profile_id",
        "trade_lookback_days",
        "spread_lookback_days",
        "depth_band_bps",
        "simulated_order_quote",
    }
    if not isinstance(row, dict) or set(row) != required:
        raise ValueError("PROFILE_ARTIFACT_SCHEMA_INVALID")
    profile = MaterializationProfile(
        profile_id=str(row["profile_id"]),
        trade_lookback_days=int(row["trade_lookback_days"]),
        spread_lookback_days=int(row["spread_lookback_days"]),
        depth_band_bps=int(row["depth_band_bps"]),
        simulated_order_quote=Decimal(str(row["simulated_order_quote"])),
    )
    if min(
        profile.trade_lookback_days,
        profile.spread_lookback_days,
        profile.depth_band_bps,
    ) <= 0 or profile.simulated_order_quote <= 0:
        raise ValueError("PROFILE_ARTIFACT_INVALID")
    identity = _bytes_id(raw)
    reference = ProfileArtifactRef(
        ids=(identity,), profile_id=profile.profile_id, profile=profile, _token=_VERIFIED
    )
    return LoadedMaterializationProfile(reference, profile)


def load_universe_policy_artifact(path: Path) -> LoadedUniversePolicyArtifact:
    loaded = load_universe_policy(path)
    reference = UniversePolicyArtifactRef(
        ids=(loaded.source_id,),
        policy_version=loaded.policy.policy_version,
        _token=_VERIFIED,
    )
    return LoadedUniversePolicyArtifact(reference, loaded)


def load_candle_wire_artifact(data_root: Path, checkpoint_path: Path) -> CandleWireArtifactRef:
    root = Path(data_root).resolve()
    checkpoint_path = _contained(root, checkpoint_path)
    raw = checkpoint_path.read_bytes()
    try:
        checkpoint = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("CANDLE_CHECKPOINT_INVALID") from error
    if not isinstance(checkpoint, dict) or checkpoint.get("checkpoint_version") != "1.0.0":
        raise ValueError("CANDLE_CHECKPOINT_INVALID")
    without_checksum = {
        key: value for key, value in checkpoint.items() if key != "checkpoint_sha256"
    }
    if checkpoint.get("checkpoint_sha256") != sha256_bytes(canonical_json_bytes(without_checksum)):
        raise ValueError("CANDLE_CHECKPOINT_CHECKSUM_MISMATCH")
    body = _contained(root, root / str(checkpoint["wire_body_path"]))
    metadata = _contained(root, root / str(checkpoint["wire_metadata_path"]))
    body_digest = sha256_file(body)
    metadata_digest = sha256_file(metadata)
    if body_digest != checkpoint.get("wire_body_sha256") or metadata_digest != checkpoint.get(
        "wire_metadata_sha256"
    ):
        raise ValueError("CANDLE_WIRE_CHECKSUM_MISMATCH")
    metadata_row = json.loads(metadata.read_text(encoding="utf-8"))
    if (
        not isinstance(metadata_row, dict)
        or metadata_row.get("wire_schema_version") != "1.0.0"
        or metadata_row.get("body_sha256") != body_digest
        or metadata_row.get("request_id") != checkpoint.get("wire_request_id")
        or metadata_row.get("request_id")
        != _mapping_id(metadata_row.get("request"), "CANDLE_WIRE_REQUEST_INVALID")
    ):
        raise ValueError("CANDLE_WIRE_SCHEMA_INVALID")
    json.loads(body.read_text(encoding="utf-8"))
    ids = (
        str(checkpoint["wire_request_id"]),
        f"sha256:{body_digest}",
        f"sha256:{metadata_digest}",
        _bytes_id(raw),
    )
    return CandleWireArtifactRef(
        ids=tuple(sorted(set(ids))), checkpoint_path=checkpoint_path, _token=_VERIFIED
    )


def load_bronze_snapshot_artifact(
    data_root: Path, snapshot_id: str
) -> BronzeSnapshotArtifactRef:
    root = Path(data_root).resolve()
    manifest_path = _contained(root, snapshot_manifest_path(root, snapshot_id))
    manifest = read_manifest(manifest_path)
    if (
        manifest.get("dataset_snapshot_id") != snapshot_id
        or manifest.get("dataset") != "bronze_candles_v1"
        or manifest.get("manifest_version") != "1.0.0"
        or manifest.get("schema_identity") != CANDLE_SCHEMA_IDENTITY
    ):
        raise ValueError("BRONZE_MANIFEST_INVALID")
    partition_ids: list[str] = []
    partitions = manifest.get("partitions")
    if not isinstance(partitions, list) or not partitions:
        raise ValueError("BRONZE_MANIFEST_INVALID")
    for partition in partitions:
        if (
            not isinstance(partition, dict)
            or partition.get("schema_identity") != CANDLE_SCHEMA_IDENTITY
        ):
            raise ValueError("BRONZE_MANIFEST_INVALID")
        path = _contained(root, root / str(partition["path"]))
        digest = sha256_file(path)
        if digest != partition.get("sha256") or path.stat().st_size != partition.get("size_bytes"):
            raise ValueError("BRONZE_PARTITION_CHECKSUM_MISMATCH")
        partition_ids.append(f"sha256:{digest}")
    ids = (snapshot_id, _bytes_id(manifest_path.read_bytes()), *partition_ids)
    return BronzeSnapshotArtifactRef(
        ids=tuple(sorted(set(ids))),
        snapshot_id=snapshot_id,
        manifest_path=manifest_path,
        _token=_VERIFIED,
    )


def load_candle_quality_artifact(
    data_root: Path, bronze: BronzeSnapshotArtifactRef
) -> CandleQualityArtifactRef:
    require_reference_type("bronze_snapshot", bronze, BronzeSnapshotArtifactRef)
    decision = require_approved_snapshot_decision(data_root, bronze.snapshot_id)
    decision_id = f"sha256:{decision.record_sha256}"
    policy_id = _mapping_id(
        {"policy_version": CANDLE_POLICY_VERSION}, "CANDLE_POLICY_INVALID"
    )
    return CandleQualityArtifactRef(
        ids=tuple(sorted((decision_id, policy_id))),
        snapshot_id=bronze.snapshot_id,
        decision_id=decision_id,
        _token=_VERIFIED,
    )


def load_trade_artifacts(
    data_root: Path, batch_paths: tuple[Path, ...], decision_path: Path
) -> LoadedTradeArtifacts:
    root = Path(data_root).resolve()
    decision = require_existing_approved_trade_decision(root, batch_paths, decision_path)
    batches: list[TradeBatchArtifactRef] = []
    wires: list[TradeWireArtifactRef] = []
    for path, digest in zip(decision.batch_paths, decision.batch_sha256s, strict=True):
        batch_id = f"sha256:{digest}"
        batches.append(
            TradeBatchArtifactRef(
                ids=(batch_id,), batch_id=batch_id, path=path, _token=_VERIFIED
            )
        )
    for wire, batch_digest in zip(
        decision.wire_artifacts, decision.wire_batch_sha256s, strict=True
    ):
        batch_id = f"sha256:{batch_digest}"
        wires.append(
            TradeWireArtifactRef(
                ids=wire.identity_ids,
                batch_id=batch_id,
                wire_id=wire.link.wire_id,
                body_path=wire.link.body_path,
                metadata_path=wire.link.metadata_path,
                _token=_VERIFIED,
            )
        )
    decision_id = f"sha256:{decision.record_sha256}"
    policy_id = _mapping_id({"policy_version": TRADE_POLICY_VERSION}, "TRADE_POLICY_INVALID")
    quality = GlobalTradeQualityArtifactRef(
        ids=tuple(sorted((decision_id, policy_id))),
        batch_ids=tuple(item.batch_id for item in batches),
        decision_id=decision_id,
        _token=_VERIFIED,
    )
    return LoadedTradeArtifacts(tuple(wires), tuple(batches), quality, decision.events)


def load_bar_artifact(
    data_root: Path, output_id: str, config_path: Path
) -> LoadedBarArtifact:
    root = Path(data_root).resolve()
    manifest_path = _contained(root, root / "snapshots" / output_id / "manifest.json")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    required = {
        "dataset",
        "manifest_version",
        "schema_version",
        "bars_output_id",
        "source_snapshot_id",
        "source_quality",
        "trade_input",
        "row_count",
        "threshold_lineage",
        "partition",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or manifest.get("dataset") != "silver_bars_v1"
        or manifest.get("manifest_version") != "1.0.0"
        or manifest.get("schema_version") != "1.0.0"
        or manifest.get("bars_output_id") != output_id
    ):
        raise ValueError("BAR_MANIFEST_INVALID")
    partition = manifest.get("partition")
    if not isinstance(partition, dict):
        raise ValueError("BAR_MANIFEST_INVALID")
    artifact_path = _contained(root, root / str(partition.get("path")))
    payload_bytes = artifact_path.read_bytes()
    if (
        _bytes_id(payload_bytes) != output_id
        or sha256_bytes(payload_bytes) != partition.get("sha256")
        or len(payload_bytes) != partition.get("size_bytes")
    ):
        raise ValueError("BAR_OUTPUT_CHECKSUM_MISMATCH")
    payload = json.loads(payload_bytes, parse_float=Decimal)
    if canonical_json_bytes(payload) != payload_bytes or payload.get("dataset") != "silver_bars_v1":
        raise ValueError("BAR_OUTPUT_SCHEMA_INVALID")
    loaded_config = load_time_bar_config(config_path)
    if (
        payload.get("config_source_id") != loaded_config.source_id
        or payload.get("config_id") != loaded_config.config.config_id
        or payload.get("source_snapshot_id") != manifest.get("source_snapshot_id")
    ):
        raise ValueError("BAR_CONFIG_OR_SNAPSHOT_MISMATCH")
    encoded_bars = payload.get("bars")
    if not isinstance(encoded_bars, list) or len(encoded_bars) != manifest.get("row_count"):
        raise ValueError("BAR_ROW_COUNT_MISMATCH")
    bars = tuple(_silver_bar(row) for row in encoded_bars)
    if any(_expected_bar_id(bar) != bar.bar_id for bar in bars):
        raise ValueError("BAR_ID_MISMATCH")
    trade_input = manifest.get("trade_input")
    source_quality = manifest.get("source_quality")
    if not isinstance(trade_input, dict) or not isinstance(source_quality, dict):
        raise ValueError("BAR_LINEAGE_INVALID")
    batch_rows = trade_input.get("batches")
    if not isinstance(batch_rows, list) or not batch_rows:
        raise ValueError("BAR_LINEAGE_INVALID")
    trade_batch_ids = tuple(f"sha256:{row['sha256']}" for row in batch_rows)
    trade_decision_id = f"sha256:{trade_input['quality_sha256']}"
    candle_decision_id = f"sha256:{source_quality['record_sha256']}"
    manifest_id = _bytes_id(manifest_bytes)
    bar_ids = tuple(sorted(bar.bar_id for bar in bars))
    ids = (output_id, manifest_id, loaded_config.source_id, *bar_ids)
    reference = BarArtifactRef(
        ids=tuple(sorted(set(ids))),
        output_id=output_id,
        manifest_id=manifest_id,
        config_id=loaded_config.source_id,
        bar_ids=bar_ids,
        source_snapshot_id=str(manifest["source_snapshot_id"]),
        trade_batch_ids=trade_batch_ids,
        trade_decision_id=trade_decision_id,
        candle_decision_id=candle_decision_id,
        _token=_VERIFIED,
    )
    return LoadedBarArtifact(reference, bars)


def load_book_artifact(data_root: Path, batch_path: Path) -> LoadedBookArtifact:
    root = Path(data_root).resolve()
    path = _contained(root, batch_path)
    content = path.read_bytes()
    digest = sha256_bytes(content)
    if path.name != f"batch={digest}.jsonl":
        raise ValueError("BOOK_BATCH_CHECKSUM_MISMATCH")
    books: list[BookEvent] = []
    wire_ids: set[str] = set()
    for raw_line in content.splitlines():
        row = json.loads(raw_line)
        if not isinstance(row, dict) or row.get("kind") != "BOOK":
            raise ValueError("BOOK_BATCH_SCHEMA_INVALID")
        if isinstance(row.get("payload"), dict):
            wire_ids.add(_mapping_id(row["payload"], "BOOK_WIRE_INVALID"))
        encoded = row.get("events")
        if not isinstance(encoded, list):
            raise ValueError("BOOK_BATCH_SCHEMA_INVALID")
        books.extend(_book_event(event) for event in encoded)
    if not books or any(book.quality_status is not QualityStatus.PASS for book in books):
        raise ValueError("BOOK_BATCH_NOT_PASS")
    batch_id = f"sha256:{digest}"
    reference = BookArtifactRef(
        ids=tuple(sorted({batch_id, *wire_ids})), batch_id=batch_id, _token=_VERIFIED
    )
    return LoadedBookArtifact(reference, tuple(books))


def load_cap_provider_artifact(
    batch: CapBatch, listing: LoadedListingArtifact
) -> LoadedCapProviderArtifact:
    require_reference_type("listing", listing.reference, ListingArtifactRef)
    reconstructed = reconstruct_coingecko_batch(batch)
    if reconstructed.wire is None:
        if any(
            row.code is ProviderUnavailableCode.HISTORICAL_UNSUPPORTED
            for row in reconstructed.unavailable
        ):
            raise ValueError("CAP_PROVIDER_HISTORICAL_UNSUPPORTED")
        raise ValueError("CAP_PROVIDER_RESPONSE_UNAVAILABLE")
    if len(reconstructed.observations) != 1 or reconstructed.unavailable:
        raise ValueError("CAP_PROVIDER_RESPONSE_UNAVAILABLE")
    wire = reconstructed.wire
    body = wire.body_path.read_bytes()
    metadata_bytes = wire.metadata_path.read_bytes()
    observation = reconstructed.observations[0]
    if (
        observation.asset_id != listing.evidence.provider_asset_id
        or observation.source_input_id != wire.response_id
    ):
        raise ValueError("CAP_ASSET_IDENTITY_MISMATCH")
    evidence = CapEvidence(
        market_cap_usd=observation.market_cap_usd,
        market_cap_rank=observation.market_cap_rank,
        source_ts=observation.source_ts,
        available_at=observation.available_at,
        expires_at=observation.expires_at,
        source=observation.source,
        input_id=observation.source_input_id,
        pair=listing.evidence.pair,
        base_asset_symbol=listing.evidence.base_asset_symbol,
        quote_asset_symbol=listing.evidence.quote_asset_symbol,
        provider_asset_id=observation.asset_id,
    )
    ids = (
        wire.request_id,
        wire.response_id,
        _bytes_id(body),
        _bytes_id(metadata_bytes),
    )
    reference = CapProviderResponseArtifactRef(
        ids=tuple(sorted(set(ids))),
        pair=listing.evidence.pair,
        base_asset_symbol=listing.evidence.base_asset_symbol,
        quote_asset_symbol=listing.evidence.quote_asset_symbol,
        provider_asset_id=observation.asset_id,
        _token=_VERIFIED,
    )
    return LoadedCapProviderArtifact(reference, evidence)


def _require_ref_tuple(field: str, values: tuple[object, ...], expected: type[_T]) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"LINEAGE_EMPTY:{field}")
    for value in values:
        require_reference_type(field, value, expected)


def _contained(root: Path, path: Path) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("ARTIFACT_PATH_OUTSIDE_DATA_ROOT") from error
    return resolved


def _bytes_id(content: bytes) -> str:
    return f"sha256:{sha256_bytes(content)}"


def _mapping_id(value: object, code: str) -> str:
    if not isinstance(value, dict):
        raise ValueError(code)
    return _bytes_id(canonical_json_bytes(value))


def _utc(value: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as error:
        raise ValueError(code) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(code)
    return parsed.astimezone(UTC)


def _book_event(row: object) -> BookEvent:
    if not isinstance(row, dict):
        raise ValueError("BOOK_BATCH_SCHEMA_INVALID")
    converted = dict(row)
    for field in ("price", "base_qty", "quote_qty"):
        converted[field] = Decimal(str(converted[field]))
    return BookEvent.model_validate(converted)


def _silver_bar(row: object) -> SilverBar:
    if not isinstance(row, dict):
        raise ValueError("BAR_OUTPUT_SCHEMA_INVALID")
    converted = dict(row)
    for field in (
        "open",
        "high",
        "low",
        "close",
        "base_volume",
        "quote_volume",
        "buy_base_volume",
        "sell_base_volume",
        "threshold_value",
    ):
        if converted.get(field) is not None:
            converted[field] = Decimal(str(converted[field]))
    return SilverBar.model_validate(converted)


def _expected_bar_id(bar: SilverBar) -> str:
    identity = {
        "schema_version": bar.schema_version,
        "pair": bar.pair,
        "bar_type": bar.bar_type.value,
        "interval": bar.interval,
        "threshold_config_id": bar.threshold_config_id,
        "threshold_value": str(bar.threshold_value) if bar.threshold_value is not None else None,
        "threshold_provenance": bar.threshold_provenance,
        "threshold_source": bar.threshold_artifact_id or "FIXED",
        "threshold_artifact_version": bar.threshold_artifact_version,
        "threshold_train_end": (
            bar.threshold_train_end.isoformat() if bar.threshold_train_end else None
        ),
        "threshold_available_at": (
            bar.threshold_available_at.isoformat() if bar.threshold_available_at else None
        ),
        "policy_id": bar.policy_id,
        "availability_lag_microseconds": bar.availability_lag_microseconds,
        "open_time": bar.open_time.isoformat(),
        "close_time": bar.close_time.isoformat(),
        "source_snapshot_id": bar.source_snapshot_id,
        "source": bar.source,
        "source_session_id": bar.source_session_id,
        "source_event_ids": list(bar.source_event_ids),
        "boundary_direction": bar.boundary_direction,
    }
    return _mapping_id(identity, "BAR_ID_INVALID")
