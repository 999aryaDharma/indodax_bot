"""Immutable public-trade wire artifacts replayed through the canonical parser."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from indodax_lab.contracts import CanonicalPair, TradeEvent

from .checksums import sha256_bytes
from .manifest import canonical_json_bytes
from .publication import publish_immutable_bytes, rollback_or_raise_indeterminate
from .stream_protocol import InvalidPublicStreamMessage, parse_public_message

TRADE_WIRE_SCHEMA_VERSION = "1.0.0"
TRADE_PARSER_POLICY_VERSION = "indodax-public-trade-v1"
_IDENTITY = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_LINK_FIELDS = {
    "wire_id",
    "body_path",
    "body_sha256",
    "metadata_path",
    "metadata_sha256",
}
_METADATA_FIELDS = {
    "wire_schema_version",
    "parser_policy_version",
    "source",
    "kind",
    "expected_pair",
    "received_at",
    "channel",
    "offset",
    "body_sha256",
    "size_bytes",
    "wire_id",
}


@dataclass(frozen=True)
class TradeWireArtifactLink:
    """Serializable link carried by one durable public-stream TRADE record."""

    wire_id: str
    body_path: Path
    body_sha256: str
    metadata_path: Path
    metadata_sha256: str

    def to_record(self, data_root: Path) -> dict[str, object]:
        root = Path(data_root).resolve()
        return {
            "wire_id": self.wire_id,
            "body_path": self.body_path.resolve().relative_to(root).as_posix(),
            "body_sha256": self.body_sha256,
            "metadata_path": self.metadata_path.resolve().relative_to(root).as_posix(),
            "metadata_sha256": self.metadata_sha256,
        }


@dataclass(frozen=True)
class VerifiedTradeWireArtifact:
    """Verified exact bytes plus canonical events derived by Task 11 parsing."""

    link: TradeWireArtifactLink
    events: tuple[TradeEvent, ...]
    channel: str
    offset: int
    expected_pair: str
    received_at: datetime

    @property
    def identity_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    self.link.wire_id,
                    f"sha256:{self.link.body_sha256}",
                    f"sha256:{self.link.metadata_sha256}",
                }
            )
        )


def persist_trade_wire_artifact(
    data_root: Path,
    *,
    body: bytes,
    received_at: datetime,
    expected_pair: str,
    channel: str,
    offset: int,
) -> TradeWireArtifactLink:
    """Persist exact received bytes and strict metadata without claiming they parse."""
    if not isinstance(body, bytes):
        raise TypeError("trade wire body must be bytes")
    received_at = _require_utc(received_at, "TRADE_WIRE_RECEIVED_AT_INVALID")
    CanonicalPair(pair=expected_pair)
    if channel != f"market:trade-activity-{expected_pair.replace('_', '')}":
        raise ValueError("TRADE_WIRE_CHANNEL_MISMATCH")
    if type(offset) is not int or offset < 0:
        raise ValueError("TRADE_WIRE_OFFSET_INVALID")
    body_sha256 = sha256_bytes(body)
    metadata_without_id = {
        "wire_schema_version": TRADE_WIRE_SCHEMA_VERSION,
        "parser_policy_version": TRADE_PARSER_POLICY_VERSION,
        "source": "indodax_public_websocket",
        "kind": "TRADE",
        "expected_pair": expected_pair,
        "received_at": received_at.isoformat(),
        "channel": channel,
        "offset": offset,
        "body_sha256": body_sha256,
        "size_bytes": len(body),
    }
    wire_id = f"sha256:{sha256_bytes(canonical_json_bytes(metadata_without_id))}"
    metadata = {**metadata_without_id, "wire_id": wire_id}
    metadata_bytes = canonical_json_bytes(metadata)
    metadata_sha256 = sha256_bytes(metadata_bytes)
    directory = (
        Path(data_root)
        / "wire"
        / "source=indodax"
        / "dataset=public-trade-message"
        / f"wire={wire_id.removeprefix('sha256:')}"
    )
    body_path = directory / "body.json"
    metadata_path = directory / "metadata.json"
    body_new = publish_immutable_bytes(body_path, body)
    try:
        publish_immutable_bytes(metadata_path, metadata_bytes)
    except Exception:
        if body_new:
            rollback_or_raise_indeterminate(body_path, "trade wire metadata publication")
        raise
    return TradeWireArtifactLink(
        wire_id=wire_id,
        body_path=body_path,
        body_sha256=body_sha256,
        metadata_path=metadata_path,
        metadata_sha256=metadata_sha256,
    )


def load_trade_wire_artifact(
    data_root: Path, encoded_link: object
) -> VerifiedTradeWireArtifact:
    """Verify immutable bytes/metadata first, then derive canonical events from the body."""
    root = Path(data_root).resolve()
    link_row = _mapping(encoded_link, "TRADE_WIRE_REFERENCE_INVALID")
    if set(link_row) != _LINK_FIELDS:
        raise ValueError("TRADE_WIRE_REFERENCE_INVALID")
    wire_id = str(link_row["wire_id"])
    body_sha256 = str(link_row["body_sha256"])
    metadata_sha256 = str(link_row["metadata_sha256"])
    if (
        not _IDENTITY.fullmatch(wire_id)
        or not _DIGEST.fullmatch(body_sha256)
        or not _DIGEST.fullmatch(metadata_sha256)
    ):
        raise ValueError("TRADE_WIRE_REFERENCE_INVALID")
    body_path = _contained(root, root / str(link_row["body_path"]))
    metadata_path = _contained(root, root / str(link_row["metadata_path"]))
    if (
        body_path.name != "body.json"
        or metadata_path.name != "metadata.json"
        or body_path.parent != metadata_path.parent
        or body_path.parent.name != f"wire={wire_id.removeprefix('sha256:')}"
    ):
        raise ValueError("TRADE_WIRE_REFERENCE_INVALID")
    try:
        body = body_path.read_bytes()
        metadata_bytes = metadata_path.read_bytes()
    except OSError as error:
        raise ValueError("TRADE_WIRE_ARTIFACT_UNAVAILABLE") from error
    if sha256_bytes(body) != body_sha256 or sha256_bytes(metadata_bytes) != metadata_sha256:
        raise ValueError("TRADE_WIRE_CHECKSUM_MISMATCH")
    try:
        metadata = json.loads(metadata_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("TRADE_WIRE_METADATA_INVALID") from error
    if (
        not isinstance(metadata, dict)
        or set(metadata) != _METADATA_FIELDS
        or canonical_json_bytes(metadata) != metadata_bytes
    ):
        raise ValueError("TRADE_WIRE_METADATA_INVALID")
    metadata_without_id = {key: value for key, value in metadata.items() if key != "wire_id"}
    expected_wire_id = f"sha256:{sha256_bytes(canonical_json_bytes(metadata_without_id))}"
    if (
        metadata.get("wire_id") != wire_id
        or expected_wire_id != wire_id
        or metadata.get("wire_schema_version") != TRADE_WIRE_SCHEMA_VERSION
        or metadata.get("parser_policy_version") != TRADE_PARSER_POLICY_VERSION
        or metadata.get("source") != "indodax_public_websocket"
        or metadata.get("kind") != "TRADE"
        or metadata.get("body_sha256") != body_sha256
        or metadata.get("size_bytes") != len(body)
    ):
        raise ValueError("TRADE_WIRE_METADATA_INVALID")
    expected_pair = str(metadata["expected_pair"])
    try:
        CanonicalPair(pair=expected_pair)
        received_at = _parse_utc(str(metadata["received_at"]))
    except ValueError as error:
        raise ValueError("TRADE_WIRE_METADATA_INVALID") from error
    expected_channel = f"market:trade-activity-{expected_pair.replace('_', '')}"
    if metadata.get("channel") != expected_channel:
        raise ValueError("TRADE_WIRE_CHANNEL_MISMATCH")
    offset = metadata.get("offset")
    if type(offset) is not int or offset < 0:
        raise ValueError("TRADE_WIRE_OFFSET_INVALID")
    try:
        payload = json.loads(body)
        parsed = parse_public_message(
            payload,
            ingested_at=received_at,
            expected_pair=expected_pair,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        InvalidPublicStreamMessage,
        ValueError,
    ) as error:
        raise ValueError("TRADE_WIRE_PAYLOAD_INVALID") from error
    if (
        parsed.kind != "TRADE"
        or parsed.channel != expected_channel
        or parsed.channel != metadata["channel"]
        or parsed.offset != offset
        or not parsed.trades
    ):
        raise ValueError("TRADE_WIRE_PAYLOAD_INVALID")
    link = TradeWireArtifactLink(
        wire_id=wire_id,
        body_path=body_path,
        body_sha256=body_sha256,
        metadata_path=metadata_path,
        metadata_sha256=metadata_sha256,
    )
    return VerifiedTradeWireArtifact(
        link=link,
        events=parsed.trades,
        channel=parsed.channel,
        offset=offset,
        expected_pair=expected_pair,
        received_at=received_at,
    )


def _mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return value


def _contained(root: Path, path: Path) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("TRADE_WIRE_PATH_OUTSIDE_DATA_ROOT") from error
    return resolved


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    return _require_utc(parsed, "TRADE_WIRE_RECEIVED_AT_INVALID")


def _require_utc(value: datetime, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(code)
    return value.astimezone(UTC)
