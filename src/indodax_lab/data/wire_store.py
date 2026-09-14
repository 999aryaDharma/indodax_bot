"""Append-only raw HTTP response storage for deterministic parser replay."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit

from .checksums import sha256_bytes
from .manifest import ImmutableContentConflictError, canonical_json_bytes
from .publication import (
    fsync_directory,
    publish_immutable_bytes,
    rollback_or_raise_indeterminate,
)

_SAFE_RESPONSE_HEADERS = frozenset(
    {"content-type", "date", "etag", "last-modified", "retry-after", "x-request-id"}
)


@dataclass(frozen=True)
class WireRequest:
    """Credential-free identity of one public candle history request."""

    endpoint: str
    pair: str
    venue_symbol: str
    interval: str
    start_epoch: int
    end_epoch: int

    def audit_dict(self) -> dict[str, object]:
        """Return the only request fields allowed to cross the wire audit boundary."""
        parsed = urlsplit(self.endpoint)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("wire endpoint must not contain credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("wire endpoint must not contain query data")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.path:
            raise ValueError("wire endpoint must be an absolute HTTP URL")
        return {
            "endpoint": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
            "pair": self.pair,
            "venue_symbol": self.venue_symbol,
            "interval": self.interval,
            "start_epoch": self.start_epoch,
            "end_epoch": self.end_epoch,
            "epoch_unit": "seconds",
        }


@dataclass(frozen=True)
class WireArtifact:
    """Paths and immutable identity of one safely persisted wire response."""

    request_id: str
    body_sha256: str
    metadata_sha256: str
    status_code: int
    body_path: Path
    metadata_path: Path
    received_at: datetime


class WireStore:
    """Persist raw body bytes before any status, JSON, or candle validation."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)

    def write_response(
        self,
        *,
        request: WireRequest,
        status_code: int,
        headers: Mapping[str, str],
        body: bytes,
        received_at: datetime,
    ) -> WireArtifact:
        """Publish one request response without ever replacing prior audit bytes."""
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware UTC")
        if received_at.utcoffset().total_seconds() != 0:
            raise ValueError("received_at must use UTC")
        if not isinstance(body, bytes):
            raise TypeError("wire body must be bytes")

        request_audit = request.audit_dict()
        request_digest = sha256_bytes(canonical_json_bytes(request_audit))
        request_id = f"sha256:{request_digest}"
        event_date = datetime.fromtimestamp(request.start_epoch, tz=UTC).date().isoformat()
        directory = (
            self._data_root
            / "wire"
            / "source=indodax"
            / "dataset=candles"
            / f"event_date={event_date}"
            / f"request={request_digest}"
        )
        body_path = directory / "body.json"
        metadata_path = directory / "metadata.json"
        body_checksum = sha256_bytes(body)
        safe_headers = {
            key.lower(): str(value)
            for key, value in headers.items()
            if key.lower() in _SAFE_RESPONSE_HEADERS
        }
        metadata = {
            "wire_schema_version": "1.0.0",
            "request_id": request_id,
            "request": request_audit,
            "status_code": int(status_code),
            "response_headers": dict(sorted(safe_headers.items())),
            "body_sha256": body_checksum,
            "size_bytes": len(body),
            "received_at": received_at.astimezone(UTC).isoformat(),
        }

        metadata_bytes = canonical_json_bytes(metadata)
        if body_path.exists() or metadata_path.exists():
            return self._reuse_existing(
                body_path=body_path,
                metadata_path=metadata_path,
                body=body,
                metadata=metadata,
            )

        body_published_new = False
        try:
            body_published_new = _publish_immutable(body_path, body)
            _publish_immutable(metadata_path, metadata_bytes)
        except Exception:
            if body_published_new:
                _rollback_or_raise_indeterminate(body_path, "wire metadata publication")
            raise
        return WireArtifact(
            request_id=request_id,
            body_sha256=body_checksum,
            metadata_sha256=sha256_bytes(metadata_bytes),
            status_code=int(status_code),
            body_path=body_path,
            metadata_path=metadata_path,
            received_at=received_at.astimezone(UTC),
        )

    @staticmethod
    def _reuse_existing(
        *, body_path: Path, metadata_path: Path, body: bytes, metadata: dict[str, object]
    ) -> WireArtifact:
        if not body_path.is_file() or not metadata_path.is_file():
            raise ImmutableContentConflictError("wire response is only partially published")
        existing_body = body_path.read_bytes()
        try:
            existing_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ImmutableContentConflictError("wire metadata cannot be validated") from error
        if not isinstance(existing_metadata, dict):
            raise ImmutableContentConflictError("wire metadata must be an object")
        comparable_existing = {
            key: value for key, value in existing_metadata.items() if key != "received_at"
        }
        comparable_new = {key: value for key, value in metadata.items() if key != "received_at"}
        if existing_body != body or comparable_existing != comparable_new:
            raise ImmutableContentConflictError(
                f"immutable wire request already contains different content: {body_path.parent}"
            )
        try:
            original_received_at = datetime.fromisoformat(str(existing_metadata["received_at"]))
        except (KeyError, ValueError) as error:
            raise ImmutableContentConflictError("wire received_at cannot be validated") from error
        _fsync_directory(body_path.parent)
        return WireArtifact(
            request_id=str(existing_metadata["request_id"]),
            body_sha256=str(existing_metadata["body_sha256"]),
            metadata_sha256=sha256_bytes(metadata_path.read_bytes()),
            status_code=int(existing_metadata["status_code"]),
            body_path=body_path,
            metadata_path=metadata_path,
            received_at=original_received_at,
        )


def _publish_immutable(path: Path, content: bytes) -> bool:
    return publish_immutable_bytes(path, content, fsync_directory_fn=_fsync_directory)


def _fsync_directory(path: Path) -> None:
    fsync_directory(path)


def _rollback_or_raise_indeterminate(path: Path, operation: str) -> None:
    rollback_or_raise_indeterminate(
        path, operation, fsync_directory_fn=_fsync_directory
    )


SAFE_RESPONSE_HEADERS = MappingProxyType({name: True for name in _SAFE_RESPONSE_HEADERS})
"""Read-only documentation of response headers admitted to wire metadata."""
