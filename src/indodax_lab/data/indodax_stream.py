"""Bounded, append-only persistence and injected transport lifecycle for public streams."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from indodax_lab.contracts import CanonicalPair

from .book_recovery import BookRecoveryCoordinator, QuarantinedGap
from .checksums import sha256_bytes
from .manifest import canonical_json_bytes
from .publication import ensure_directory_tree, fsync_directory, publish_immutable_bytes
from .stream_protocol import (
    BookSessionProtocol,
    InvalidPublicStreamMessage,
    StreamState,
    parse_public_message,
)
from .trade_wire import persist_trade_wire_artifact


def _publish_immutable(path: Path, content: bytes) -> bool:
    return publish_immutable_bytes(path, content)


class StreamTransportClosed(ConnectionError):
    """The public transport closed normally or abnormally and may be reconnected."""


class AppendOnlyStreamWriter:
    """Keep at most one bounded batch in memory and checkpoint only durable offsets."""

    def __init__(self, data_root: Path, *, max_batch_size: int = 1_000) -> None:
        if max_batch_size <= 0:
            raise ValueError("max_batch_size must be positive")
        self._data_root = Path(data_root)
        self._max_batch_size = max_batch_size
        self._pending: list[tuple[dict[str, object], int, str]] = []
        self.checkpoint_path = self._data_root / "checkpoints" / "public_market_stream.json"

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def max_batch_size(self) -> int:
        return self._max_batch_size

    @property
    def data_root(self) -> Path:
        return self._data_root

    def append(
        self,
        record: Mapping[str, object],
        *,
        acknowledged_offset: int,
        checkpoint_key: str = "public",
    ) -> Path | None:
        """Append one detached record and flush synchronously at the configured bound."""
        if acknowledged_offset < 0:
            raise ValueError("acknowledged_offset must be non-negative")
        if not checkpoint_key:
            raise ValueError("checkpoint_key must not be empty")
        if len(self._pending) >= self._max_batch_size:
            self.flush()
        self._pending.append((dict(record), acknowledged_offset, checkpoint_key))
        if len(self._pending) == self._max_batch_size:
            return self.flush()
        return None

    def flush(self) -> Path | None:
        """Publish immutable JSONL, then atomically advance the durable checkpoint."""
        if not self._pending:
            return None
        lines = b"".join(
            canonical_json_bytes(record) + b"\n" for record, _, _ in self._pending
        )
        digest = sha256_bytes(lines)
        batch_path = (
            self._data_root
            / "wire"
            / "source=indodax"
            / "dataset=public-market-stream"
            / f"batch={digest}.jsonl"
        )
        _publish_immutable(batch_path, lines)
        acknowledged_offsets = self._read_acknowledged_offsets()
        for _, offset, key in self._pending:
            acknowledged_offsets[key] = offset
        checkpoint = {
            "checkpoint_version": "1.0.0",
            "dataset": "public-market-stream",
            "last_acknowledged_offset": self._pending[-1][1],
            "acknowledged_offsets": dict(sorted(acknowledged_offsets.items())),
            "batch_sha256": digest,
            "batch_path": batch_path.relative_to(self._data_root).as_posix(),
        }
        _atomic_replace(self.checkpoint_path, canonical_json_bytes(checkpoint))
        self._pending.clear()
        return batch_path

    def _read_acknowledged_offsets(self) -> dict[str, int]:
        if not self.checkpoint_path.exists():
            return {}
        try:
            existing = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            offsets = existing["acknowledged_offsets"]
            if not isinstance(offsets, dict):
                raise ValueError
            return {str(key): int(value) for key, value in offsets.items()}
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("existing stream checkpoint is invalid") from error


def _atomic_replace(path: Path, content: bytes) -> None:
    """Flush a temporary file and atomically replace the mutable latest checkpoint."""
    ensure_directory_tree(path.parent)
    partial = path.parent / f".{uuid.uuid4().hex}.partial"
    try:
        with partial.open("xb") as sink:
            sink.write(content)
            sink.flush()
            os.fsync(sink.fileno())
        os.replace(partial, path)
        fsync_directory(path.parent)
    finally:
        try:
            partial.unlink()
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class CollectorConfig:
    """Credential-free public stream settings with explicit lifecycle bounds."""

    endpoint: str
    pair: str
    public_token: str
    heartbeat_timeout: float = 30.0
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    jitter_fraction: float = 0.2

    def __post_init__(self) -> None:
        if not self.endpoint.startswith("wss://"):
            raise ValueError("public stream endpoint must use wss://")
        CanonicalPair(pair=self.pair)
        if not self.public_token:
            raise ValueError("documented public static token is required")
        if self.heartbeat_timeout <= 0 or self.backoff_base <= 0:
            raise ValueError("heartbeat timeout and backoff base must be positive")
        if self.backoff_max < self.backoff_base:
            raise ValueError("backoff_max must not be below backoff_base")
        if not 0 <= self.jitter_fraction <= 1:
            raise ValueError("jitter_fraction must be between zero and one")


class PublicTransport(Protocol):
    """Small fakeable boundary around a public WebSocket connection."""

    async def send(self, message: str) -> None: ...

    async def receive(self, *, timeout: float) -> str | bytes: ...

    async def close(self) -> None: ...


Connector = Callable[[str], Awaitable[PublicTransport]]
Clock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]
Monotonic = Callable[[], float]


class PublicMarketCollector:
    """Reconnectable public-only collector with bounded durable publication."""

    def __init__(
        self,
        *,
        config: CollectorConfig,
        writer: AppendOnlyStreamWriter,
        protocol: BookSessionProtocol,
        connector: Connector,
        clock: Clock,
        sleeper: Sleeper,
        random_value: Callable[[], float],
        monotonic: Monotonic = time.monotonic,
        request_id_factory: Callable[[], int] = lambda: 4,
    ) -> None:
        self._config = config
        self._writer = writer
        self._protocol = protocol
        self._connector = connector
        self._clock = clock
        self._sleeper = sleeper
        self._random_value = random_value
        self._monotonic = monotonic
        self._recovery = BookRecoveryCoordinator(
            protocol, request_id_factory=request_id_factory
        )
        self._stopping = False
        self._transport: PublicTransport | None = None
        self._pending_quarantine: QuarantinedGap | None = None
        self._connection_healthy = False

    def request_stop(self) -> None:
        """Stop accepting new messages; the run loop will flush and close."""
        self._stopping = True

    async def shutdown(self) -> None:
        """Stop intake, durably flush the stable batch, then wake a blocked receive."""
        self.request_stop()
        try:
            self._flush_or_quarantine("SIGTERM")
        finally:
            await self._close_transport()

    def backoff_delay(self, attempt: int) -> float:
        """Return bounded exponential backoff with injected symmetric jitter."""
        if attempt < 0:
            raise ValueError("attempt must be non-negative")
        base = min(self._config.backoff_max, self._config.backoff_base * (2**attempt))
        jitter = (self._random_value() * 2.0 - 1.0) * self._config.jitter_fraction
        return max(0.0, base * (1.0 + jitter))

    async def run(self) -> None:
        """Run until stopped, reconnecting only transport/protocol failures."""
        attempt = 0
        try:
            while not self._stopping:
                try:
                    self._connection_healthy = False
                    self._transport = await self._connector(self._config.endpoint)
                    self._protocol.connected()
                    await self._subscribe(self._transport)
                    await self._collect_connection(self._transport)
                    attempt = 0
                except (
                    ConnectionError,
                    EOFError,
                    OSError,
                    TimeoutError,
                    InvalidPublicStreamMessage,
                ) as error:
                    if self._stopping:
                        break
                    if self._connection_healthy:
                        attempt = 0
                    try:
                        self._flush_or_quarantine(_abandonment_reason(error))
                    finally:
                        await self._close_transport()
                    if self._protocol.pending_gap is None:
                        self._protocol.disconnected()
                    await self._sleeper(self.backoff_delay(attempt))
                    attempt += 1
        finally:
            try:
                self._flush_or_quarantine("SHUTDOWN")
            finally:
                await self._close_transport()
                if self._protocol.pending_gap is None:
                    self._protocol.disconnected()

    async def _subscribe(self, transport: PublicTransport) -> None:
        symbol = self._config.pair.replace("_", "")
        requests = (
            {"params": {"token": self._config.public_token}, "id": 1},
            {
                "method": 1,
                "params": {"channel": f"market:trade-activity-{symbol}"},
                "id": 2,
            },
            {
                "method": 1,
                "params": {"channel": f"market:order-book-{symbol}"},
                "id": 4,
            },
            {"method": 7, "id": 3},
        )
        for request in requests:
            await transport.send(canonical_json_bytes(request).decode("utf-8"))

    async def _collect_connection(self, transport: PublicTransport) -> None:
        last_heartbeat = self._monotonic()
        while not self._stopping:
            remaining = self._config.heartbeat_timeout - (
                self._monotonic() - last_heartbeat
            )
            if remaining <= 0:
                raise TimeoutError("public stream heartbeat deadline expired")
            raw = await transport.receive(timeout=remaining)
            raw_body = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            ingested_at = _utc_now(self._clock())
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as error:
                raise InvalidPublicStreamMessage("public message is not valid JSON") from error
            if (
                self._protocol.state is StreamState.RECOVERING
                and self._recovery.is_matching_response(payload)
            ):
                try:
                    recovered = self._recovery.apply(payload, ingested_at=ingested_at)
                except InvalidPublicStreamMessage as error:
                    self._quarantine_gap(ingested_at, f"RECOVERY_FAILED:{type(error).__name__}")
                    raise
                self._store(
                    payload,
                    kind="BOOK_RECOVERY",
                    offset=self._protocol.last_offset,
                    ingested_at=ingested_at,
                    eligible=recovered.feature_eligible,
                    events=[event.model_dump(mode="json") for event in recovered.books],
                )
                self._connection_healthy = True
                continue
            parsed = parse_public_message(
                payload,
                ingested_at=ingested_at,
                book_session_id=self._protocol.book_session_id,
                book_event_type=(
                    "SNAPSHOT"
                    if self._protocol.state is StreamState.SYNCING
                    else "UPDATE"
                ),
                expected_pair=self._config.pair,
            )
            self._connection_healthy = True
            if parsed.kind == "HEARTBEAT":
                last_heartbeat = self._monotonic()
                await transport.send('{"id":3,"method":7}')
                continue
            if parsed.kind in {"CONTROL", "SUBSCRIPTION"}:
                continue
            if parsed.kind == "BOOK":
                if self._protocol.state is StreamState.RECOVERING:
                    self._store(
                        payload,
                        kind="BOOK_UNRELIABLE",
                        offset=parsed.offset,
                        acknowledged_offset=self._protocol.last_offset,
                        ingested_at=ingested_at,
                        eligible=False,
                        events=[event.model_dump(mode="json") for event in parsed.books],
                    )
                    continue
                try:
                    outcome = self._protocol.handle(payload, ingested_at=ingested_at)
                except InvalidPublicStreamMessage:
                    if (
                        self._protocol.state is StreamState.GAP
                        and self._protocol.pending_gap is not None
                    ):
                        self._quarantine_gap(ingested_at, "PROTOCOL_ERROR")
                    raise
                if outcome.missing_offsets is not None:
                    await transport.send(
                        canonical_json_bytes(self._recovery.start()).decode("utf-8")
                    )
                    continue
                if outcome.duplicate:
                    continue
                eligible = outcome.feature_eligible
                events = [event.model_dump(mode="json") for event in outcome.books]
            else:
                eligible = False
                events = [event.model_dump(mode="json") for event in parsed.trades]
            self._store(
                payload,
                kind=parsed.kind,
                offset=parsed.offset,
                ingested_at=ingested_at,
                eligible=eligible,
                events=events,
                raw_body=raw_body,
            )

    def _store(
        self,
        payload: object,
        *,
        kind: str,
        offset: int | None,
        acknowledged_offset: int | None = None,
        ingested_at: datetime,
        eligible: bool,
        events: list[dict[str, object]],
        raw_body: bytes | None = None,
    ) -> None:
        if offset is None:
            return
        record: dict[str, object] = {
            "wire_schema_version": "1.0.0",
            "source": "indodax_public_websocket",
            "kind": kind,
            "offset": offset,
            "received_at": ingested_at.isoformat(),
            "book_session_id": self._protocol.book_session_id if kind.startswith("BOOK") else None,
            "lob_feature_eligible": eligible,
            "events": events,
        }
        if kind == "TRADE":
            if raw_body is None:
                raise ValueError("TRADE_WIRE_BODY_MISSING")
            channel = _payload_channel(payload)
            if channel is None:
                raise ValueError("TRADE_WIRE_CHANNEL_MISSING")
            wire = persist_trade_wire_artifact(
                self._writer.data_root,
                body=raw_body,
                received_at=ingested_at,
                expected_pair=self._config.pair,
                channel=channel,
                offset=offset,
            )
            record["trade_wire"] = wire.to_record(self._writer.data_root)
        else:
            record["payload"] = payload
        channel = _payload_channel(payload) or kind
        self._writer.append(
            record,
            acknowledged_offset=(
                offset if acknowledged_offset is None else acknowledged_offset
            ),
            checkpoint_key=channel,
        )

    def _quarantine_gap(self, detected_at: datetime, reason: str) -> None:
        quarantine = self._pending_quarantine
        if quarantine is None:
            self._writer.flush()
            quarantine = self._recovery.prepare_failure(
                detected_at=detected_at,
                abandonment_reason=reason,
            )
            self._pending_quarantine = quarantine
            record = {
                "wire_schema_version": "1.0.0",
                "source": "indodax_public_websocket",
                "kind": "BOOK_GAP_QUARANTINE",
                "book_session_id": quarantine.book_session_id,
                "pair": quarantine.pair,
                "channel": quarantine.channel,
                "missing_offset_start": quarantine.missing_offset_start,
                "missing_offset_end": quarantine.missing_offset_end,
                "observed_offset": quarantine.observed_offset,
                "last_reliable_offset": quarantine.last_reliable_offset,
                "detected_at": quarantine.detected_at.isoformat(),
                "quality_status": "QUARANTINED",
                "gap_reason": quarantine.gap_reason,
                "abandonment_reason": quarantine.abandonment_reason,
            }
            self._writer.append(
                record,
                acknowledged_offset=quarantine.last_reliable_offset,
                checkpoint_key=quarantine.channel,
            )
        self._writer.flush()
        self._recovery.commit_failure(quarantine)
        self._pending_quarantine = None

    def _flush_or_quarantine(self, reason: str) -> None:
        if self._protocol.state in {StreamState.GAP, StreamState.RECOVERING}:
            self._quarantine_gap(_utc_now(self._clock()), reason)
        else:
            self._writer.flush()

    async def _close_transport(self) -> None:
        transport, self._transport = self._transport, None
        if transport is not None:
            await transport.close()


def _utc_now(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("collector clock must return timezone-aware UTC")
    return value.astimezone(UTC)


def _payload_channel(payload: object) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    result = payload.get("result")
    if not isinstance(result, Mapping):
        return None
    channel = result.get("channel")
    return str(channel) if channel is not None else None


def _abandonment_reason(error: BaseException) -> str:
    if isinstance(error, StreamTransportClosed):
        return "TRANSPORT_CLOSED"
    if isinstance(error, TimeoutError):
        return "HEARTBEAT_TIMEOUT"
    if isinstance(error, InvalidPublicStreamMessage):
        return "PROTOCOL_ERROR"
    return "TRANSPORT_ERROR"
