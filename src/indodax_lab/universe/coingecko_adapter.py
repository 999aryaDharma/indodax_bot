"""Auditable injected CoinGecko market-cap adapter; no account or trading endpoints."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from indodax_lab.data.checksums import sha256_bytes
from indodax_lab.data.manifest import canonical_json_bytes
from indodax_lab.data.publication import publish_immutable_bytes, rollback_or_raise_indeterminate

COINGECKO_MARKETS_ENDPOINT = "https://api.coingecko.com/api/v3/coins/markets"
ADAPTER_POLICY_VERSION = "coingecko-current-v1"
_ASSET_ID = re.compile(r"^[a-z0-9-]+$")
_SAFE_HEADERS = frozenset({"content-type", "date", "etag", "last-modified", "retry-after"})
_WIRE_METADATA_FIELDS = {
    "wire_schema_version",
    "adapter_policy_version",
    "provider",
    "request_id",
    "request",
    "snapshot_as_of_date",
    "status_code",
    "response_headers",
    "body_sha256",
    "size_bytes",
    "source_timestamps",
    "available_at",
    "ttl_seconds",
    "expires_at",
    "response_id",
}
_HISTORICAL_AUDIT_FIELDS = {
    "audit_schema_version",
    "adapter_policy_version",
    "provider",
    "endpoint",
    "capability",
    "asset_ids",
    "requested_as_of_date",
    "available_at",
    "reason",
}


@dataclass(frozen=True)
class HttpResponse:
    """Complete public HTTP result passed by an injected transport."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    """Only external side effect required by the adapter."""

    def get(self, url: str, *, params: Mapping[str, object], timeout: float) -> HttpResponse: ...


class ProviderUnavailableCode(StrEnum):
    """Explicit non-numeric provider failure classifications."""

    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    HISTORICAL_UNSUPPORTED = "HISTORICAL_UNSUPPORTED"


@dataclass(frozen=True)
class ProviderUnavailable:
    """Auditable absence; numeric fields are deliberately always null."""

    asset_id: str
    code: ProviderUnavailableCode
    detail: str
    available_at: datetime
    source_input_id: str
    market_cap_usd: None = None
    market_cap_rank: None = None


@dataclass(frozen=True)
class CapObservation:
    """One parsed point-in-time market-cap observation."""

    asset_id: str
    market_cap_usd: Decimal
    market_cap_rank: int
    source_ts: datetime
    available_at: datetime
    ttl_seconds: int
    expires_at: datetime
    source: str
    source_input_id: str


@dataclass(frozen=True)
class CapWireArtifact:
    """Immutable raw response and metadata lineage."""

    request_id: str
    response_id: str
    body_path: Path
    metadata_path: Path
    available_at: datetime
    ttl_seconds: int


@dataclass(frozen=True)
class CapBatch:
    """Provider response split into typed observations and explicit absence records."""

    observations: tuple[CapObservation, ...]
    unavailable: tuple[ProviderUnavailable, ...]
    wire: CapWireArtifact | None
    audit_path: Path | None = None


class CoinGeckoAdapter:
    """Fetch public cap metadata through an injected, testable transport boundary."""

    def __init__(
        self,
        *,
        transport: HttpTransport,
        data_root: Path,
        ttl_seconds: int,
        timeout_seconds: float = 30.0,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("provider TTL must be positive")
        if timeout_seconds <= 0:
            raise ValueError("provider timeout must be positive")
        self._transport = transport
        self._data_root = Path(data_root)
        self._ttl_seconds = ttl_seconds
        self._timeout_seconds = timeout_seconds

    def fetch_market_caps(
        self, *, asset_ids: tuple[str, ...], as_of_date: date, received_at: datetime
    ) -> CapBatch:
        """Fetch, preserve raw bytes/availability/TTL, then parse without zero filling."""
        _require_utc(received_at, "received_at")
        if not asset_ids or len(set(asset_ids)) != len(asset_ids):
            raise ValueError("asset_ids must be non-empty and unique")
        if any(not _ASSET_ID.fullmatch(asset_id) for asset_id in asset_ids):
            raise ValueError("CoinGecko asset IDs must be lowercase slug values")
        ordered_ids = tuple(sorted(asset_ids))
        if as_of_date != received_at.date():
            return self._record_historical_unavailable(
                asset_ids=ordered_ids,
                as_of_date=as_of_date,
                received_at=received_at,
            )
        params: dict[str, object] = {
            "vs_currency": "usd",
            "ids": ",".join(ordered_ids),
        }
        response = self._transport.get(
            COINGECKO_MARKETS_ENDPOINT, params=params, timeout=self._timeout_seconds
        )
        if not isinstance(response.body, bytes):
            raise TypeError("provider response body must be bytes")
        parsed = _parse_json(response.body)
        source_timestamps = _source_timestamps(parsed)
        wire = self._publish_wire(
            asset_ids=ordered_ids,
            as_of_date=as_of_date,
            response=response,
            received_at=received_at,
            source_timestamps=source_timestamps,
        )
        return _reconstruct_current_wire(wire)

    def _record_historical_unavailable(
        self,
        *,
        asset_ids: tuple[str, ...],
        as_of_date: date,
        received_at: datetime,
    ) -> CapBatch:
        audit = {
            "audit_schema_version": "1.0.0",
            "adapter_policy_version": ADAPTER_POLICY_VERSION,
            "provider": "coingecko",
            "endpoint": COINGECKO_MARKETS_ENDPOINT,
            "capability": "CURRENT_ONLY",
            "asset_ids": list(asset_ids),
            "requested_as_of_date": as_of_date.isoformat(),
            "available_at": received_at.isoformat(),
            "reason": ProviderUnavailableCode.HISTORICAL_UNSUPPORTED,
        }
        audit_bytes = canonical_json_bytes(audit)
        audit_digest = sha256_bytes(audit_bytes)
        audit_id = f"sha256:{audit_digest}"
        audit_path = (
            self._data_root
            / "wire"
            / "source=coingecko"
            / "dataset=market_cap_unavailable"
            / f"as_of_date={as_of_date.isoformat()}"
            / f"audit={audit_digest}"
            / "unavailable.json"
        )
        publish_immutable_bytes(audit_path, audit_bytes)
        batch = CapBatch(
            observations=(),
            unavailable=tuple(
                ProviderUnavailable(
                    asset_id=asset_id,
                    code=ProviderUnavailableCode.HISTORICAL_UNSUPPORTED,
                    detail="CoinGecko /coins/markets is current-only",
                    available_at=received_at,
                    source_input_id=audit_id,
                )
                for asset_id in asset_ids
            ),
            wire=None,
            audit_path=audit_path,
        )
        return reconstruct_coingecko_batch(batch)

    def _publish_wire(
        self,
        *,
        asset_ids: tuple[str, ...],
        as_of_date: date,
        response: HttpResponse,
        received_at: datetime,
        source_timestamps: tuple[datetime, ...],
    ) -> CapWireArtifact:
        request = {
            "endpoint": COINGECKO_MARKETS_ENDPOINT,
            "asset_ids": list(asset_ids),
            "params": {"vs_currency": "usd", "ids": ",".join(asset_ids)},
        }
        request_id = f"sha256:{sha256_bytes(canonical_json_bytes(request))}"
        body_sha256 = sha256_bytes(response.body)
        safe_headers = {
            key.lower(): str(value)
            for key, value in response.headers.items()
            if key.lower() in _SAFE_HEADERS
        }
        metadata_without_id = {
            "wire_schema_version": "1.0.0",
            "adapter_policy_version": ADAPTER_POLICY_VERSION,
            "provider": "coingecko",
            "request_id": request_id,
            "request": request,
            "snapshot_as_of_date": as_of_date.isoformat(),
            "status_code": int(response.status_code),
            "response_headers": dict(sorted(safe_headers.items())),
            "body_sha256": body_sha256,
            "size_bytes": len(response.body),
            "source_timestamps": [timestamp.isoformat() for timestamp in source_timestamps],
            "available_at": received_at.isoformat(),
            "ttl_seconds": self._ttl_seconds,
            "expires_at": (received_at + timedelta(seconds=self._ttl_seconds)).isoformat(),
        }
        response_digest = sha256_bytes(canonical_json_bytes(metadata_without_id))
        response_id = f"sha256:{response_digest}"
        metadata = {**metadata_without_id, "response_id": response_id}
        directory = (
            self._data_root
            / "wire"
            / "source=coingecko"
            / "dataset=market_cap"
            / f"as_of_date={as_of_date.isoformat()}"
            / f"request={request_id.removeprefix('sha256:')}"
            / f"response={response_digest}"
        )
        body_path = directory / "body.json"
        metadata_path = directory / "metadata.json"
        body_new = publish_immutable_bytes(body_path, response.body)
        try:
            publish_immutable_bytes(metadata_path, canonical_json_bytes(metadata))
        except Exception:
            if body_new:
                rollback_or_raise_indeterminate(body_path, "cap wire metadata publication")
            raise
        return CapWireArtifact(
            request_id=request_id,
            response_id=response_id,
            body_path=body_path,
            metadata_path=metadata_path,
            available_at=received_at,
            ttl_seconds=self._ttl_seconds,
        )


def reconstruct_coingecko_batch(batch: CapBatch) -> CapBatch:
    """Rebuild all provider facts from verified immutable current or audit bytes."""
    if batch.wire is not None and batch.audit_path is None:
        reconstructed = _reconstruct_current_wire(batch.wire)
    elif batch.wire is None and batch.audit_path is not None:
        reconstructed = _reconstruct_historical_audit(batch.audit_path)
    else:
        raise ValueError("CAP_PROVIDER_ARTIFACT_INVALID")
    if (
        batch.observations != reconstructed.observations
        or batch.unavailable != reconstructed.unavailable
    ):
        raise ValueError(
            "CAP_PROVIDER_BATCH_MISMATCH: caller facts differ from verified provider bytes"
        )
    return reconstructed


def _reconstruct_current_wire(wire: CapWireArtifact) -> CapBatch:
    """Verify response metadata and hashes before parsing current-only market-cap bytes."""
    try:
        body = wire.body_path.read_bytes()
        metadata_bytes = wire.metadata_path.read_bytes()
        metadata = json.loads(metadata_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("CAP_PROVIDER_RESPONSE_INVALID") from error
    if (
        not isinstance(metadata, dict)
        or set(metadata) != _WIRE_METADATA_FIELDS
        or canonical_json_bytes(metadata) != metadata_bytes
    ):
        raise ValueError("CAP_PROVIDER_RESPONSE_INVALID")
    metadata_without_id = {
        key: value for key, value in metadata.items() if key != "response_id"
    }
    response_id = f"sha256:{sha256_bytes(canonical_json_bytes(metadata_without_id))}"
    request = metadata.get("request")
    if not isinstance(request, dict) or set(request) != {"endpoint", "asset_ids", "params"}:
        raise ValueError("CAP_PROVIDER_REQUEST_INVALID")
    asset_ids = request.get("asset_ids")
    params = request.get("params")
    if (
        not isinstance(asset_ids, list)
        or not asset_ids
        or any(not isinstance(asset_id, str) for asset_id in asset_ids)
        or asset_ids != sorted(set(asset_ids))
        or any(not _ASSET_ID.fullmatch(asset_id) for asset_id in asset_ids)
        or request.get("endpoint") != COINGECKO_MARKETS_ENDPOINT
        or not isinstance(params, dict)
        or params != {"vs_currency": "usd", "ids": ",".join(asset_ids)}
    ):
        raise ValueError("CAP_PROVIDER_REQUEST_INVALID")
    request_id = f"sha256:{sha256_bytes(canonical_json_bytes(request))}"
    body_sha256 = sha256_bytes(body)
    try:
        available_at = _parse_utc(str(metadata["available_at"]))
        snapshot_as_of_date = date.fromisoformat(str(metadata["snapshot_as_of_date"]))
        expires_at = _parse_utc(str(metadata["expires_at"]))
    except (TypeError, ValueError) as error:
        raise ValueError("CAP_PROVIDER_RESPONSE_INVALID") from error
    ttl_seconds = metadata.get("ttl_seconds")
    status_code = metadata.get("status_code")
    response_headers = metadata.get("response_headers")
    if (
        metadata.get("wire_schema_version") != "1.0.0"
        or metadata.get("adapter_policy_version") != ADAPTER_POLICY_VERSION
        or metadata.get("provider") != "coingecko"
        or metadata.get("request_id") != request_id
        or metadata.get("response_id") != response_id
        or metadata.get("body_sha256") != body_sha256
        or metadata.get("size_bytes") != len(body)
        or type(ttl_seconds) is not int
        or ttl_seconds <= 0
        or expires_at != available_at + timedelta(seconds=ttl_seconds)
        or snapshot_as_of_date != available_at.date()
        or type(status_code) is not int
        or not isinstance(response_headers, dict)
        or any(
            not isinstance(key, str)
            or key not in _SAFE_HEADERS
            or not isinstance(value, str)
            for key, value in response_headers.items()
        )
        or wire.request_id != request_id
        or wire.response_id != response_id
        or wire.available_at != available_at
        or wire.ttl_seconds != ttl_seconds
        or wire.body_path.name != "body.json"
        or wire.metadata_path.name != "metadata.json"
        or wire.body_path.parent != wire.metadata_path.parent
        or wire.body_path.parent.name != f"response={response_id.removeprefix('sha256:')}"
        or wire.body_path.parent.parent.name != f"request={request_id.removeprefix('sha256:')}"
    ):
        raise ValueError("CAP_PROVIDER_RESPONSE_INVALID")
    parsed = _parse_json(body)
    source_timestamps = metadata.get("source_timestamps")
    expected_source_timestamps = [
        timestamp.isoformat() for timestamp in _source_timestamps(parsed)
    ]
    if source_timestamps != expected_source_timestamps:
        raise ValueError("CAP_PROVIDER_RESPONSE_INVALID")
    verified_wire = CapWireArtifact(
        request_id=request_id,
        response_id=response_id,
        body_path=wire.body_path,
        metadata_path=wire.metadata_path,
        available_at=available_at,
        ttl_seconds=ttl_seconds,
    )
    return _cap_batch_from_response(
        tuple(asset_ids), status_code, parsed, verified_wire
    )


def _cap_batch_from_response(
    asset_ids: tuple[str, ...],
    status_code: int,
    parsed: object,
    wire: CapWireArtifact,
) -> CapBatch:
    if status_code == 429:
        return _unavailable_batch(
            asset_ids, ProviderUnavailableCode.RATE_LIMITED, "HTTP 429", wire
        )
    if status_code in {402, 403}:
        return _unavailable_batch(
            asset_ids,
            ProviderUnavailableCode.QUOTA_EXHAUSTED,
            f"HTTP {status_code}",
            wire,
        )
    if not 200 <= status_code < 300:
        return _unavailable_batch(
            asset_ids,
            ProviderUnavailableCode.PROVIDER_ERROR,
            f"HTTP {status_code}",
            wire,
        )
    if not isinstance(parsed, list):
        return _unavailable_batch(
            asset_ids,
            ProviderUnavailableCode.INVALID_RESPONSE,
            "response must be a JSON array",
            wire,
        )
    rows_by_id: dict[str, list[object]] = {asset_id: [] for asset_id in asset_ids}
    for row in parsed:
        if isinstance(row, dict) and row.get("id") in rows_by_id:
            rows_by_id[str(row["id"])].append(row)
    observations: list[CapObservation] = []
    unavailable: list[ProviderUnavailable] = []
    for asset_id in asset_ids:
        rows = rows_by_id[asset_id]
        if len(rows) != 1:
            code = (
                ProviderUnavailableCode.DATA_UNAVAILABLE
                if not rows
                else ProviderUnavailableCode.INVALID_RESPONSE
            )
            unavailable.append(
                ProviderUnavailable(
                    asset_id=asset_id,
                    code=code,
                    detail="expected exactly one provider row",
                    available_at=wire.available_at,
                    source_input_id=wire.response_id,
                )
            )
            continue
        try:
            observation = _observation(
                asset_id, rows[0], wire, ttl_seconds=wire.ttl_seconds
            )
        except (KeyError, TypeError, ValueError, InvalidOperation) as error:
            unavailable.append(
                ProviderUnavailable(
                    asset_id=asset_id,
                    code=ProviderUnavailableCode.INVALID_RESPONSE,
                    detail=str(error),
                    available_at=wire.available_at,
                    source_input_id=wire.response_id,
                )
            )
        else:
            observations.append(observation)
    return CapBatch(tuple(observations), tuple(unavailable), wire)


def _reconstruct_historical_audit(path: Path) -> CapBatch:
    try:
        audit_bytes = Path(path).read_bytes()
        audit = json.loads(audit_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("CAP_PROVIDER_HISTORICAL_AUDIT_INVALID") from error
    if (
        not isinstance(audit, dict)
        or set(audit) != _HISTORICAL_AUDIT_FIELDS
        or canonical_json_bytes(audit) != audit_bytes
    ):
        raise ValueError("CAP_PROVIDER_HISTORICAL_AUDIT_INVALID")
    asset_ids = audit.get("asset_ids")
    try:
        requested_date = date.fromisoformat(str(audit["requested_as_of_date"]))
        available_at = _parse_utc(str(audit["available_at"]))
    except (TypeError, ValueError) as error:
        raise ValueError("CAP_PROVIDER_HISTORICAL_AUDIT_INVALID") from error
    if (
        audit.get("audit_schema_version") != "1.0.0"
        or audit.get("adapter_policy_version") != ADAPTER_POLICY_VERSION
        or audit.get("provider") != "coingecko"
        or audit.get("endpoint") != COINGECKO_MARKETS_ENDPOINT
        or audit.get("capability") != "CURRENT_ONLY"
        or audit.get("reason") != ProviderUnavailableCode.HISTORICAL_UNSUPPORTED
        or requested_date == available_at.date()
        or not isinstance(asset_ids, list)
        or not asset_ids
        or any(not isinstance(asset_id, str) for asset_id in asset_ids)
        or asset_ids != sorted(set(asset_ids))
        or any(not _ASSET_ID.fullmatch(asset_id) for asset_id in asset_ids)
    ):
        raise ValueError("CAP_PROVIDER_HISTORICAL_AUDIT_INVALID")
    audit_id = f"sha256:{sha256_bytes(audit_bytes)}"
    return CapBatch(
        observations=(),
        unavailable=tuple(
            ProviderUnavailable(
                asset_id=asset_id,
                code=ProviderUnavailableCode.HISTORICAL_UNSUPPORTED,
                detail="CoinGecko /coins/markets is current-only",
                available_at=available_at,
                source_input_id=audit_id,
            )
            for asset_id in asset_ids
        ),
        wire=None,
        audit_path=Path(path),
    )


def _parse_json(body: bytes) -> object:
    try:
        return json.loads(body, parse_float=Decimal, parse_int=int)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _source_timestamps(parsed: object) -> tuple[datetime, ...]:
    if not isinstance(parsed, list):
        return ()
    timestamps: set[datetime] = set()
    for row in parsed:
        if not isinstance(row, dict):
            continue
        try:
            timestamps.add(_parse_utc(str(row["last_updated"])))
        except (KeyError, ValueError):
            continue
    return tuple(sorted(timestamps))


def _observation(
    asset_id: str, row: object, wire: CapWireArtifact, *, ttl_seconds: int
) -> CapObservation:
    if not isinstance(row, dict):
        raise TypeError("provider row must be an object")
    raw_cap = row["market_cap"]
    if isinstance(raw_cap, bool) or not isinstance(raw_cap, (int, Decimal)):
        raise TypeError("market_cap must be an exact JSON number")
    cap = Decimal(raw_cap)
    if cap <= 0:
        raise ValueError("market_cap must be positive; unavailable is not zero")
    rank = row["market_cap_rank"]
    if type(rank) is not int or rank <= 0:
        raise ValueError("market_cap_rank must be a positive integer")
    source_ts = _parse_utc(str(row["last_updated"]))
    if source_ts > wire.available_at:
        raise ValueError("source timestamp must not be after response availability")
    return CapObservation(
        asset_id=asset_id,
        market_cap_usd=cap,
        market_cap_rank=rank,
        source_ts=source_ts,
        available_at=wire.available_at,
        ttl_seconds=ttl_seconds,
        expires_at=wire.available_at + timedelta(seconds=ttl_seconds),
        source="coingecko",
        source_input_id=wire.response_id,
    )


def _unavailable_batch(
    asset_ids: tuple[str, ...],
    code: ProviderUnavailableCode,
    detail: str,
    wire: CapWireArtifact,
) -> CapBatch:
    return CapBatch(
        observations=(),
        unavailable=tuple(
            ProviderUnavailable(
                asset_id=asset_id,
                code=code,
                detail=detail,
                available_at=wire.available_at,
                source_input_id=wire.response_id,
            )
            for asset_id in asset_ids
        ),
        wire=wire,
    )


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    _require_utc(parsed, "source timestamp")
    return parsed.astimezone(UTC)


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be timezone-aware UTC")
