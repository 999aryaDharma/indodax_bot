"""Reliability, recovery, durability, and lifecycle tests for public book capture."""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from indodax_lab.cli import collect_market_stream
from indodax_lab.cli.collect_market_stream import (
    _connect,
    _run,
    _WebsocketsTransport,
    main,
)
from indodax_lab.data import indodax_stream
from indodax_lab.data.book_recovery import BookRecoveryCoordinator
from indodax_lab.data.indodax_stream import (
    AppendOnlyStreamWriter,
    CollectorConfig,
    PublicMarketCollector,
    StreamTransportClosed,
)
from indodax_lab.data.stream_protocol import (
    BookSessionProtocol,
    InvalidPublicStreamMessage,
    SequenceRegressionError,
    StreamState,
)

FIXTURES = Path(__file__).parents[3] / "fixtures" / "indodax" / "stream"
NOW = datetime(2024, 8, 6, 0, 0, 1, tzinfo=UTC)


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_gap_recovers_from_official_offset_without_crossing_an_unreliable_window():
    """Declaring recovery before every missing offset replays would bridge an unknown book."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    recovery = BookRecoveryCoordinator(protocol, request_id_factory=lambda: 91)
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=NOW)
    protocol.handle(_fixture("book_update.json"), ingested_at=NOW)

    gap = protocol.handle(_fixture("gap_sequence.json"), ingested_at=NOW)
    request = recovery.start()

    assert gap.missing_offsets == (67411, 67411)
    assert protocol.state is StreamState.RECOVERING
    assert protocol.feature_eligible is False
    assert request == {
        "method": 1,
        "params": {
            "channel": "market:order-book-btcidr",
            "recover": True,
            "offset": 67410,
        },
        "id": 91,
    }

    response = _fixture("reconnect.json")
    response["id"] = 91
    replay = recovery.apply(response, ingested_at=NOW)

    assert [event.sequence for event in replay.books] == [67411, 67411, 67412, 67412]
    assert protocol.state is StreamState.RELIABLE
    assert protocol.feature_eligible is True
    assert protocol.book_session_id == "book-session-1"
    assert protocol.last_offset == 67412


@pytest.mark.parametrize(
    "mutation", ["request_id", "response_channel", "payload_pair", "session"]
)
def test_recovery_response_must_match_outstanding_request_session_and_pair(mutation):
    """A stale or unrelated replay must never restore a gapped book session."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    recovery = BookRecoveryCoordinator(protocol, request_id_factory=lambda: 91)
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=NOW)
    protocol.handle(_fixture("book_update.json"), ingested_at=NOW)
    protocol.handle(_fixture("gap_sequence.json"), ingested_at=NOW)
    recovery.start()
    response = _fixture("reconnect.json")
    response["id"] = 91
    if mutation == "request_id":
        response["id"] = 90
    elif mutation == "response_channel":
        response["result"]["channel"] = "market:order-book-ethidr"
    elif mutation == "payload_pair":
        response["result"]["publications"][0]["data"]["pair"] = "ethidr"
    else:
        protocol.book_session_id = "book-session-stale"

    with pytest.raises(InvalidPublicStreamMessage, match="recovery"):
        recovery.apply(response, ingested_at=NOW)

    assert protocol.state is StreamState.RECOVERING
    assert protocol.feature_eligible is False
    assert protocol.pending_gap == (67411, 67411)


def test_recovering_demultiplexes_heartbeat_trade_book_and_stale_control(tmp_path):
    """Treating every frame as recovery can restore from stale data or discard public trades."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=20)
    collector: PublicMarketCollector
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=NOW)
    protocol.handle(_fixture("book_update.json"), ingested_at=NOW)
    protocol.handle(_fixture("gap_sequence.json"), ingested_at=NOW)
    recovery_response = _fixture("reconnect.json")
    recovery_response["id"] = 91
    stale_response = copy.deepcopy(recovery_response)
    stale_response["id"] = 90

    def stop_after_recovery() -> str:
        collector.request_stop()
        return json.dumps(_fixture("heartbeat.json"))

    transport = _FakeTransport(
        [
            json.dumps(_fixture("heartbeat.json")),
            json.dumps(_fixture("public_trade.json")),
            json.dumps(_fixture("gap_sequence.json")),
            json.dumps(stale_response),
            json.dumps(recovery_response),
            stop_after_recovery,
        ]
    )

    async def connect(_url: str) -> _FakeTransport:
        return transport

    async def sleep(_delay: float) -> None:
        raise AssertionError("focused connection replay must not sleep")

    collector = PublicMarketCollector(
        config=CollectorConfig(
            endpoint="wss://public.example/ws/",
            pair="btc_idr",
            public_token="public-token",
        ),
        writer=writer,
        protocol=protocol,
        connector=connect,
        clock=lambda: NOW,
        sleeper=sleep,
        random_value=lambda: 0.5,
        monotonic=lambda: 0.0,
        request_id_factory=lambda: 91,
    )
    collector._recovery.start()

    asyncio.run(collector._collect_connection(transport))
    writer.flush()

    records = [
        json.loads(line)
        for path in tmp_path.rglob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert protocol.state is StreamState.RELIABLE
    assert sum(record["kind"] == "TRADE" for record in records) == 1
    unreliable = [record for record in records if record["kind"] == "BOOK_UNRELIABLE"]
    assert len(unreliable) == 1
    assert unreliable[0]["lob_feature_eligible"] is False
    assert any(record["kind"] == "BOOK_RECOVERY" for record in records)


def test_batch_is_durable_before_checkpoint_and_failed_flush_remains_retryable(
    tmp_path, monkeypatch
):
    """Advancing a checkpoint after a failed batch publish would permanently skip events."""
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=2)
    publish = indodax_stream._publish_immutable
    calls = 0

    def fail_once(path, content):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated durable batch failure")
        return publish(path, content)

    monkeypatch.setattr(indodax_stream, "_publish_immutable", fail_once)
    writer.append({"kind": "book", "offset": 67409}, acknowledged_offset=67409)

    with pytest.raises(OSError, match="durable batch"):
        writer.append({"kind": "book", "offset": 67410}, acknowledged_offset=67410)

    assert writer.pending_count == 2
    assert not writer.checkpoint_path.exists()
    assert not list(tmp_path.rglob("*.jsonl"))

    writer.append({"kind": "book", "offset": 67411}, acknowledged_offset=67411)

    assert writer.pending_count == 1
    durable_checkpoint = json.loads(writer.checkpoint_path.read_text(encoding="utf-8"))
    assert durable_checkpoint["last_acknowledged_offset"] == 67410

    artifact = writer.flush()

    assert writer.pending_count == 0
    assert artifact is not None and artifact.is_file()
    checkpoint = json.loads(writer.checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["last_acknowledged_offset"] == 67411
    assert checkpoint["batch_sha256"] in artifact.name
    assert not list(tmp_path.rglob("*.partial"))


def test_heartbeat_timeout_reconnects_with_injected_backoff_then_shutdown_flushes(
    tmp_path,
):
    """A silent socket must not hang forever or lose the last stable in-memory batch."""
    sessions = iter(["session-1", "session-2"])
    protocol = BookSessionProtocol(pair="btc_idr", session_id_factory=lambda: next(sessions))
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=10)
    sleeps: list[float] = []
    transports: list[_FakeTransport] = []
    collector: PublicMarketCollector

    def stop_and_heartbeat() -> str:
        collector.request_stop()
        return json.dumps(_fixture("heartbeat.json"))

    responses = iter(
        [
            [json.dumps(_fixture("book_snapshot.json")), TimeoutError("silent")],
            [stop_and_heartbeat],
        ]
    )

    async def connect(_url: str) -> _FakeTransport:
        transport = _FakeTransport(next(responses))
        transports.append(transport)
        return transport

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    collector = PublicMarketCollector(
        config=CollectorConfig(
            endpoint="wss://public.example/ws/",
            pair="btc_idr",
            public_token="documented-static-token",
            heartbeat_timeout=7.0,
            backoff_base=2.0,
            backoff_max=20.0,
            jitter_fraction=0.25,
        ),
        writer=writer,
        protocol=protocol,
        connector=connect,
        clock=lambda: NOW,
        sleeper=sleep,
        random_value=lambda: 0.75,
        monotonic=lambda: 0.0,
    )

    asyncio.run(collector.run())

    assert sleeps == [2.25]
    assert [transport.receive_timeouts for transport in transports] == [[7.0, 7.0], [7.0]]
    assert all(transport.closed for transport in transports)
    assert writer.pending_count == 0
    checkpoint = json.loads(writer.checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["last_acknowledged_offset"] == 67409
    persisted = b"".join(path.read_bytes() for path in tmp_path.rglob("*.*"))
    assert b"documented-static-token" not in persisted


def test_failed_recovery_quarantines_exact_gap_and_rotates_session():
    """Reusing a session after unsupported recovery would silently bridge missing offsets."""
    sessions = iter(["book-session-1", "book-session-2"])
    protocol = BookSessionProtocol(pair="btc_idr", session_id_factory=lambda: next(sessions))
    recovery = BookRecoveryCoordinator(protocol, request_id_factory=lambda: 91)
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=NOW)
    protocol.handle(_fixture("book_update.json"), ingested_at=NOW)
    protocol.handle(_fixture("gap_sequence.json"), ingested_at=NOW)
    recovery.start()

    quarantine = recovery.prepare_failure(
        detected_at=NOW, abandonment_reason="RECOVERY_UNSUPPORTED"
    )

    assert protocol.book_session_id == "book-session-1"
    assert protocol.state is StreamState.RECOVERING
    assert protocol.pending_gap == (67411, 67411)

    recovery.commit_failure(quarantine)

    assert quarantine.book_session_id == "book-session-1"
    assert (quarantine.missing_offset_start, quarantine.missing_offset_end) == (67411, 67411)
    assert protocol.book_session_id == "book-session-2"
    assert protocol.state is StreamState.SYNCING
    assert protocol.feature_eligible is False
    assert protocol.last_offset is None


def test_quarantine_publish_failure_preserves_gap_for_retry_without_duplicate(
    tmp_path, monkeypatch
):
    """Clearing gap state before durable quarantine makes a failed write unrecoverable."""
    sessions = iter(["book-session-1", "book-session-2"])
    protocol = BookSessionProtocol(pair="btc_idr", session_id_factory=lambda: next(sessions))
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=1)
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=NOW)
    protocol.handle(_fixture("book_update.json"), ingested_at=NOW)
    protocol.handle(_fixture("gap_sequence.json"), ingested_at=NOW)
    publish = indodax_stream._publish_immutable
    calls = 0

    def fail_once(path, content):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated quarantine failure")
        return publish(path, content)

    monkeypatch.setattr(indodax_stream, "_publish_immutable", fail_once)
    collector = _collector_for(protocol=protocol, writer=writer)
    collector._recovery.start()

    with pytest.raises(OSError, match="quarantine"):
        collector._quarantine_gap(NOW, "TRANSPORT_CLOSED")

    assert protocol.state is StreamState.RECOVERING
    assert protocol.book_session_id == "book-session-1"
    assert protocol.pending_gap == (67411, 67411)
    assert writer.pending_count == 1

    collector._quarantine_gap(NOW, "TRANSPORT_CLOSED")

    assert protocol.state is StreamState.SYNCING
    assert protocol.book_session_id == "book-session-2"
    assert protocol.pending_gap is None
    records = [
        json.loads(line)
        for path in tmp_path.rglob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["pair"] == "btc_idr"
    assert records[0]["channel"] == "market:order-book-btcidr"
    assert records[0]["gap_reason"] == "OFFSET_GAP"
    assert records[0]["observed_offset"] == 67412
    assert records[0]["abandonment_reason"] == "TRANSPORT_CLOSED"


@pytest.mark.parametrize("failure_point", ["recovery_send", "recovery_receive"])
def test_transport_abandonment_durably_quarantines_pending_gap(tmp_path, failure_point):
    """Closing a gapped connection without a durable quarantine loses its unreliable window."""
    sessions = iter(["book-session-1", "book-session-2"])
    protocol = BookSessionProtocol(pair="btc_idr", session_id_factory=lambda: next(sessions))
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=20)
    collector: PublicMarketCollector

    class FailingRecoveryTransport(_FakeTransport):
        async def send(self, message: str) -> None:
            await super().send(message)
            request = json.loads(message)
            if failure_point == "recovery_send" and request.get("params", {}).get("recover"):
                raise StreamTransportClosed("send closed")

    responses: list[str | Exception | Callable[[], str]] = [
        json.dumps(_fixture("book_snapshot.json")),
        json.dumps(_fixture("book_update.json")),
        json.dumps(_fixture("gap_sequence.json")),
    ]
    if failure_point == "recovery_receive":
        responses.append(StreamTransportClosed("receive closed"))
    transport = FailingRecoveryTransport(responses)

    async def connect(_url: str) -> _FakeTransport:
        return transport

    async def stop_after_delay(_delay: float) -> None:
        collector.request_stop()

    collector = PublicMarketCollector(
        config=CollectorConfig(
            endpoint="wss://public.example/ws/",
            pair="btc_idr",
            public_token="public-token",
        ),
        writer=writer,
        protocol=protocol,
        connector=connect,
        clock=lambda: NOW,
        sleeper=stop_after_delay,
        random_value=lambda: 0.5,
        monotonic=lambda: 0.0,
        request_id_factory=lambda: 91,
    )

    asyncio.run(collector.run())

    records = [
        json.loads(line)
        for path in tmp_path.rglob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    quarantine = [record for record in records if record["kind"] == "BOOK_GAP_QUARANTINE"]
    assert len(quarantine) == 1
    assert quarantine[0]["missing_offset_start"] == 67411
    assert quarantine[0]["missing_offset_end"] == 67411
    assert quarantine[0]["abandonment_reason"] == "TRANSPORT_CLOSED"
    assert transport.closed is True


def test_offset_regression_is_quarantined_before_new_session_sync(tmp_path):
    """A wrap/regression must rotate through durable quarantine, never inverted recovery."""
    sessions = iter(["book-session-1", "book-session-2"])
    protocol = BookSessionProtocol(pair="btc_idr", session_id_factory=lambda: next(sessions))
    protocol.connected()
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=20)
    regressed = copy.deepcopy(_fixture("book_update.json"))
    regressed["result"]["data"]["offset"] = 0
    transport = _FakeTransport(
        [
            json.dumps(_fixture("book_snapshot.json")),
            json.dumps(_fixture("book_update.json")),
            json.dumps(regressed),
        ]
    )
    collector = _collector_for(protocol=protocol, writer=writer)

    with pytest.raises(SequenceRegressionError):
        asyncio.run(collector._collect_connection(transport))

    assert protocol.state is StreamState.SYNCING
    assert protocol.book_session_id == "book-session-2"
    records = [
        json.loads(line)
        for path in tmp_path.rglob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    quarantine = [record for record in records if record["kind"] == "BOOK_GAP_QUARANTINE"]
    assert len(quarantine) == 1
    assert quarantine[0]["gap_reason"] == "OFFSET_REGRESSION"
    assert quarantine[0]["observed_offset"] == 0
    assert quarantine[0]["last_reliable_offset"] == 67410
    assert quarantine[0]["abandonment_reason"] == "PROTOCOL_ERROR"
    checkpoint = json.loads(writer.checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["acknowledged_offsets"]["market:order-book-btcidr"] == 67410


def test_backoff_resets_after_a_subscribed_connection_receives_a_valid_frame(tmp_path):
    """Keeping lifetime retry count after recovery makes later transient failures over-sleep."""
    sessions = iter(["session-1", "session-2", "session-3"])
    protocol = BookSessionProtocol(pair="btc_idr", session_id_factory=lambda: next(sessions))
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=10)
    sleeps: list[float] = []
    collector: PublicMarketCollector

    def stop_on_third_connection() -> str:
        collector.request_stop()
        return json.dumps(_fixture("heartbeat.json"))

    responses = iter(
        [
            [StreamTransportClosed("first failure")],
            [json.dumps(_fixture("heartbeat.json")), StreamTransportClosed("after healthy")],
            [stop_on_third_connection],
        ]
    )

    async def connect(_url: str) -> _FakeTransport:
        return _FakeTransport(next(responses))

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    collector = PublicMarketCollector(
        config=CollectorConfig(
            endpoint="wss://public.example/ws/",
            pair="btc_idr",
            public_token="public-token",
            backoff_base=2.0,
            backoff_max=20.0,
            jitter_fraction=0.0,
        ),
        writer=writer,
        protocol=protocol,
        connector=connect,
        clock=lambda: NOW,
        sleeper=sleep,
        random_value=lambda: 0.5,
        monotonic=lambda: 0.0,
    )

    asyncio.run(collector.run())

    assert sleeps == [2.0, 2.0]


def test_trade_and_control_traffic_do_not_refresh_heartbeat_deadline(tmp_path):
    """Treating any active traffic as a heartbeat can hide a dead protocol heartbeat forever."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=10)
    monotonic_values = iter([0.0, 0.0, 3.0, 5.0])
    transport = _FakeTransport(
        [
            json.dumps(_fixture("public_trade.json")),
            json.dumps(
                {
                    "id": 1,
                    "result": {
                        "client": "public-client-id",
                        "version": "2.8.6",
                        "expires": True,
                        "ttl": 100,
                    },
                }
            ),
        ]
    )

    collector = PublicMarketCollector(
        config=CollectorConfig(
            endpoint="wss://public.example/ws/",
            pair="btc_idr",
            public_token="public-token",
            heartbeat_timeout=5.0,
        ),
        writer=writer,
        protocol=protocol,
        connector=lambda _url: None,
        clock=lambda: NOW,
        monotonic=lambda: next(monotonic_values),
        sleeper=lambda _delay: None,
        random_value=lambda: 0.5,
    )

    with pytest.raises(TimeoutError, match="heartbeat deadline"):
        asyncio.run(collector._collect_connection(transport))

    assert transport.receive_timeouts == [5.0, 2.0]


def test_recognized_heartbeat_refreshes_deadline_and_requests_next_ping(tmp_path):
    """A one-shot pong without the next official ping cannot sustain heartbeat freshness."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=10)
    collector: PublicMarketCollector
    monotonic_values = iter([0.0, 0.0, 1.0, 2.0, 3.0])

    def stop_on_second_pong() -> str:
        collector.request_stop()
        return json.dumps(_fixture("heartbeat.json"))

    transport = _FakeTransport(
        [json.dumps(_fixture("heartbeat.json")), stop_on_second_pong]
    )
    collector = PublicMarketCollector(
        config=CollectorConfig(
            endpoint="wss://public.example/ws/",
            pair="btc_idr",
            public_token="public-token",
            heartbeat_timeout=5.0,
        ),
        writer=writer,
        protocol=protocol,
        connector=lambda _url: None,
        clock=lambda: NOW,
        monotonic=lambda: next(monotonic_values),
        sleeper=lambda _delay: None,
        random_value=lambda: 0.5,
    )

    asyncio.run(collector._collect_connection(transport))

    assert transport.receive_timeouts == [5.0, 4.0]
    assert [json.loads(message) for message in transport.sent] == [
        {"method": 7, "id": 3},
        {"method": 7, "id": 3},
    ]


def test_cli_retains_and_awaits_signal_shutdown_task(tmp_path, monkeypatch):
    """A fire-and-forget SIGTERM task can hide a durable flush failure as unobserved."""
    callbacks: list[Callable[[], None]] = []

    class SignalLoop:
        def add_signal_handler(self, _signum, callback):
            callbacks.append(callback)

    class FailingShutdownCollector:
        def __init__(self, **_kwargs):
            pass

        async def run(self):
            callbacks[0]()
            await asyncio.sleep(0)

        async def shutdown(self):
            await asyncio.sleep(0)
            raise OSError("simulated SIGTERM flush failure")

    monkeypatch.setattr(collect_market_stream.asyncio, "get_running_loop", SignalLoop)
    monkeypatch.setattr(
        collect_market_stream, "PublicMarketCollector", FailingShutdownCollector
    )
    config = CollectorConfig(
        endpoint="wss://public.example/ws/",
        pair="btc_idr",
        public_token="public-token",
    )

    with pytest.raises(OSError, match="SIGTERM flush"):
        asyncio.run(_run(config, tmp_path, 10))


def test_shutdown_flush_failure_still_closes_transport(tmp_path, monkeypatch):
    """Durability failure must surface without leaving a blocked transport open."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=10)
    writer.append({"kind": "trade"}, acknowledged_offset=1)
    collector = _collector_for(protocol=protocol, writer=writer)
    transport = _FakeTransport([])
    collector._transport = transport

    def fail_flush():
        raise OSError("simulated shutdown flush failure")

    monkeypatch.setattr(writer, "flush", fail_flush)

    with pytest.raises(OSError, match="shutdown flush"):
        asyncio.run(collector.shutdown())

    assert transport.closed is True


def test_sigterm_quarantine_failure_closes_transport_and_keeps_gap_retryable(
    tmp_path, monkeypatch
):
    """SIGTERM must wake the socket but cannot erase a quarantine that failed durability."""
    protocol = BookSessionProtocol(
        pair="btc_idr", session_id_factory=lambda: "book-session-1"
    )
    protocol.connected()
    protocol.handle(_fixture("book_snapshot.json"), ingested_at=NOW)
    protocol.handle(_fixture("book_update.json"), ingested_at=NOW)
    protocol.handle(_fixture("gap_sequence.json"), ingested_at=NOW)
    writer = AppendOnlyStreamWriter(tmp_path, max_batch_size=1)
    collector = _collector_for(protocol=protocol, writer=writer)
    collector._recovery.start()
    transport = _FakeTransport([])
    collector._transport = transport

    def fail_publish(_path, _content):
        raise OSError("simulated SIGTERM quarantine failure")

    monkeypatch.setattr(indodax_stream, "_publish_immutable", fail_publish)

    with pytest.raises(OSError, match="SIGTERM quarantine"):
        asyncio.run(collector.shutdown())

    assert transport.closed is True
    assert protocol.state is StreamState.RECOVERING
    assert protocol.pending_gap == (67411, 67411)
    assert protocol.book_session_id == "book-session-1"


def test_cli_dry_run_exposes_only_public_channels_and_never_the_static_token(capsys, tmp_path):
    """A configuration check must not expose credentials or enable private/trading endpoints."""
    exit_code = main(
        [
            "--data-root",
            str(tmp_path),
            "--pair",
            "btc_idr",
            "--public-token",
            "must-not-print",
            "--dry-run",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "market:trade-activity-btcidr" in output
    assert "market:order-book-btcidr" in output
    assert "must-not-print" not in output
    assert "myTrades" not in output
    assert "createOrder" not in output


def test_websocket_library_close_is_normalized_at_lazy_transport_boundary():
    """Leaking a library close exception bypasses the collector's reconnect policy."""

    class FakeWebSocketClosed(Exception):
        pass

    class ClosedConnection:
        async def recv(self):
            raise FakeWebSocketClosed("normal close")

    transport = _WebsocketsTransport(
        ClosedConnection(), closed_error_types=(FakeWebSocketClosed,)
    )

    with pytest.raises(StreamTransportClosed, match="public WebSocket closed"):
        asyncio.run(transport.receive(timeout=1.0))


def test_lazy_connector_uses_supported_websockets_exception_module(monkeypatch):
    """Accessing a removed package attribute breaks connection before normalization exists."""
    import websockets

    class Connection:
        pass

    async def connect(_endpoint, **_kwargs):
        return Connection()

    monkeypatch.setattr(websockets, "connect", connect)
    monkeypatch.delattr(websockets, "exceptions", raising=False)

    transport = asyncio.run(_connect("wss://public.example/ws/"))

    assert isinstance(transport, _WebsocketsTransport)


def test_websocket_handshake_failure_is_normalized_for_reconnect(monkeypatch):
    """A library handshake exception must enter the same reconnect path as socket closure."""
    import websockets
    from websockets.exceptions import WebSocketException

    async def fail_connect(_endpoint, **_kwargs):
        raise WebSocketException("handshake failed")

    monkeypatch.setattr(websockets, "connect", fail_connect)

    with pytest.raises(StreamTransportClosed, match="connection failed"):
        asyncio.run(_connect("wss://public.example/ws/"))


def _collector_for(
    *, protocol: BookSessionProtocol, writer: AppendOnlyStreamWriter
) -> PublicMarketCollector:
    async def unused_connect(_url: str) -> _FakeTransport:
        raise AssertionError("transport is not used by this focused test")

    async def unused_sleep(_delay: float) -> None:
        raise AssertionError("sleep is not used by this focused test")

    return PublicMarketCollector(
        config=CollectorConfig(
            endpoint="wss://public.example/ws/",
            pair="btc_idr",
            public_token="public-token",
        ),
        writer=writer,
        protocol=protocol,
        connector=unused_connect,
        clock=lambda: NOW,
        sleeper=unused_sleep,
        random_value=lambda: 0.5,
        monotonic=lambda: 0.0,
        request_id_factory=lambda: 91,
    )


class _FakeTransport:
    def __init__(self, responses: list[str | Exception | Callable[[], str]]) -> None:
        self._responses = iter(responses)
        self.sent: list[str] = []
        self.receive_timeouts: list[float] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def receive(self, *, timeout: float) -> str:
        self.receive_timeouts.append(timeout)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response()
        return response

    async def close(self) -> None:
        self.closed = True
