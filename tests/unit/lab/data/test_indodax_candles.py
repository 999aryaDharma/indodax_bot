"""Offline behavioral tests for the auditable Indodax candle boundary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.data import wire_store
from indodax_lab.data.indodax_candles import (
    HttpResponse,
    IndodaxCandleAdapter,
    IndodaxCandleClient,
    InvalidCandlePayload,
    parse_columnar,
    parse_pascal_rows,
)
from indodax_lab.data.manifest import ImmutableContentConflictError
from indodax_lab.data.parquet_store import IndeterminatePublicationError
from indodax_lab.data.wire_store import WireRequest, WireStore

FIXTURES = Path(__file__).parents[3] / "fixtures" / "indodax"
INGESTED_AT = datetime(2024, 1, 2, tzinfo=UTC)


def _wire_request() -> WireRequest:
    return WireRequest(
        endpoint="https://indodax.com/tradingview/history_v2",
        pair="btc_idr",
        venue_symbol="BTCIDR",
        interval="1h",
        start_epoch=1704067200,
        end_epoch=1704074400,
    )


def test_named_shape_parsers_are_offline_boundary_functions():
    """Hiding shape parsing inside HTTP code would prevent deterministic wire replay."""
    pascal = json.loads((FIXTURES / "history_v2_pascal.json").read_text(encoding="utf-8"))
    columns = json.loads((FIXTURES / "history_v2_columns.json").read_text(encoding="utf-8"))

    pascal_batch = parse_pascal_rows(
        pascal, pair="btc_idr", interval="1h", ingested_at=INGESTED_AT
    )
    column_batch = parse_columnar(
        columns, pair="btc_idr", interval="1h", ingested_at=INGESTED_AT
    )

    assert [item.source_event_id for item in pascal_batch.items] == [
        item.source_event_id for item in column_batch.items
    ]


@pytest.mark.parametrize(
    "fixture_name", ["history_v2_pascal.json", "history_v2_columns.json"]
)
def test_parser_canonicalizes_supported_shapes_without_zero_filling(fixture_name):
    """Casting a malformed price to zero would turn an explicit reject into market data."""
    payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))

    batch = IndodaxCandleAdapter().parse(
        payload, pair="btc_idr", interval="1h", ingested_at=INGESTED_AT
    )

    assert [item.candle.open_time.isoformat() for item in batch.items] == [
        "2024-01-01T00:00:00+00:00",
        "2024-01-01T01:00:00+00:00",
    ]
    first = batch.items[0]
    assert first.candle.pair.pair == "btc_idr"
    assert first.candle.venue_symbol == "BTCIDR"
    assert first.candle.open == Decimal("100.00")
    assert first.candle.base_volume == Decimal("1.500")
    assert first.candle.close_time.isoformat() == "2024-01-01T01:00:00+00:00"
    assert first.wire_metadata == {"original_epoch": 1704067200, "epoch_unit": "seconds"}
    assert len(batch.rejects) == 1
    assert batch.rejects[0].row_index == 3
    assert batch.rejects[0].reason == "INVALID_ROW"


def test_source_event_ids_ignore_ingestion_time_and_input_order():
    """Using arrival time or row index in the ID would break deterministic replay deduplication."""
    rows = [
        {
            "Time": 1704067200,
            "Open": "100",
            "High": "102",
            "Low": "99",
            "Close": "101",
            "Volume": "1.5",
        },
        {
            "Time": 1704070800,
            "Open": "101",
            "High": "103",
            "Low": "100",
            "Close": "102",
            "Volume": "2.5",
        },
    ]
    adapter = IndodaxCandleAdapter()

    first = adapter.parse(rows, pair="btc_idr", interval="1h", ingested_at=INGESTED_AT)
    replay = adapter.parse(
        list(reversed(rows)),
        pair="btc_idr",
        interval="1h",
        ingested_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    assert [item.source_event_id for item in first.items] == [
        "sha256:abe0ee0353e6a72fc99ceb3a8c419e2b2360a1c362ed74776a8ccdd62b81d55a",
        "sha256:b4ecf11a9435fe3029fe51b3a78eb605b1c2af7118aa1799ef76849600bd5046",
    ]
    assert [item.source_event_id for item in replay.items] == [
        "sha256:abe0ee0353e6a72fc99ceb3a8c419e2b2360a1c362ed74776a8ccdd62b81d55a",
        "sha256:b4ecf11a9435fe3029fe51b3a78eb605b1c2af7118aa1799ef76849600bd5046",
    ]


def test_conflicting_duplicate_identity_is_rejected_without_order_dependent_winner():
    """Keeping either conflicting duplicate would make replay depend on wire row order."""
    shared = {
        "Time": 1704067200,
        "Open": "100",
        "High": "102",
        "Low": "99",
        "Volume": "1.5",
    }
    rows = [{**shared, "Close": "101"}, {**shared, "Close": "101.5"}]

    batch = IndodaxCandleAdapter().parse(
        rows, pair="btc_idr", interval="1h", ingested_at=INGESTED_AT
    )

    assert batch.items == ()
    assert [(reject.row_index, reject.reason) for reject in batch.rejects] == [
        (0, "CONFLICTING_DUPLICATE_SOURCE_EVENT_ID"),
        (1, "CONFLICTING_DUPLICATE_SOURCE_EVENT_ID"),
    ]
    assert batch.rejects[0].source_event_id == batch.rejects[1].source_event_id


def test_epoch_overflow_is_an_explicit_row_reject_and_does_not_abort_batch():
    """Platform timestamp overflow must not bypass the malformed-row policy."""
    rows = [
        {
            "Time": 1704067200,
            "Open": "100",
            "High": "102",
            "Low": "99",
            "Close": "101",
            "Volume": "1",
        },
        {
            "Time": 10**100,
            "Open": "100",
            "High": "102",
            "Low": "99",
            "Close": "101",
            "Volume": "1",
        },
    ]

    batch = IndodaxCandleAdapter().parse(
        rows, pair="btc_idr", interval="1h", ingested_at=INGESTED_AT
    )

    assert len(batch.items) == 1
    assert [(reject.row_index, reject.reason) for reject in batch.rejects] == [(1, "INVALID_ROW")]
    assert batch.rejects[0].wire_metadata == {
        "original_epoch": 10**100,
        "epoch_unit": "seconds",
    }


@pytest.mark.parametrize(
    "payload",
    [
        42,
        "candles",
        {"t": [], "o": []},
        {"t": "1704067200", "o": [], "h": [], "l": [], "c": [], "v": []},
    ],
)
def test_unsupported_top_level_shapes_fail_closed(payload):
    """Treating an unknown envelope as empty data would falsely mark a request complete."""
    with pytest.raises(InvalidCandlePayload):
        IndodaxCandleAdapter().parse(
            payload, pair="btc_idr", interval="1h", ingested_at=INGESTED_AT
        )


def test_wire_store_persists_raw_response_and_safe_audit_metadata_immutably(tmp_path):
    """Persisting request credentials or replacing prior bytes would destroy the audit boundary."""
    store = WireStore(tmp_path)
    request = _wire_request()
    body = b'[{"Time":1704067200,"Close":"101"}]'

    artifact = store.write_response(
        request=request,
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "ETag": '"fixture"',
            "Authorization": "Bearer must-not-persist",
            "Set-Cookie": "secret-cookie",
        },
        body=body,
        received_at=INGESTED_AT,
    )
    replay = store.write_response(
        request=request,
        status_code=200,
        headers={"Content-Type": "application/json", "ETag": '"fixture"'},
        body=body,
        received_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    assert artifact.body_path.read_bytes() == body
    metadata = json.loads(artifact.metadata_path.read_text(encoding="utf-8"))
    assert metadata["body_sha256"] == (
        "d4820c0c02053d9bae3c03d22e1de27c54cfaa34ba46b3a0e736fb1e92050023"
    )
    assert metadata["status_code"] == 200
    assert metadata["response_headers"] == {
        "content-type": "application/json",
        "etag": '"fixture"',
    }
    assert artifact.request_id == replay.request_id
    assert artifact.received_at == replay.received_at == INGESTED_AT
    persisted = b"".join(path.read_bytes() for path in tmp_path.rglob("*.*"))
    assert b"must-not-persist" not in persisted
    assert b"secret-cookie" not in persisted

    with pytest.raises(ImmutableContentConflictError):
        store.write_response(
            request=request,
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b"different body",
            received_at=INGESTED_AT,
        )
    assert artifact.body_path.read_bytes() == body


def test_wire_metadata_publish_failure_rolls_back_new_body(tmp_path, monkeypatch):
    """Reporting metadata failure while leaving a raw-body final creates a partial wire record."""
    publish = wire_store._publish_immutable

    def fail_metadata(path, content):
        if path.name == "metadata.json":
            raise OSError("simulated metadata publication failure")
        return publish(path, content)

    monkeypatch.setattr(wire_store, "_publish_immutable", fail_metadata)

    with pytest.raises(OSError, match="metadata publication"):
        WireStore(tmp_path).write_response(
            request=_wire_request(),
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b"[]",
            received_at=INGESTED_AT,
        )

    assert not list(tmp_path.rglob("body.json"))
    assert not list(tmp_path.rglob("metadata.json"))


def test_wire_publish_durably_records_parent_creation_and_idempotent_reuse(
    tmp_path, monkeypatch
):
    """A success must fsync created parents and the reused no-clobber namespace."""
    fsync_directory = wire_store._fsync_directory
    calls: list[Path] = []

    def record_fsync(path):
        calls.append(Path(path))
        fsync_directory(path)

    monkeypatch.setattr(wire_store, "_fsync_directory", record_fsync)
    store = WireStore(tmp_path)
    kwargs = {
        "request": _wire_request(),
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "body": b"[]",
        "received_at": INGESTED_AT,
    }
    first = store.write_response(**kwargs)
    first_calls = set(calls)
    calls.clear()
    store.write_response(**kwargs)

    assert tmp_path in first_calls
    assert first.body_path.parent in calls


def test_wire_partial_cleanup_failure_rolls_back_visible_body(tmp_path, monkeypatch):
    """A failed durable partial cleanup must not leave a newly visible final."""
    unlink = Path.unlink

    def fail_partial(path, *args, **kwargs):
        if path.suffix == ".partial":
            raise OSError("simulated partial cleanup failure")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_partial)

    with pytest.raises(OSError, match="partial cleanup"):
        WireStore(tmp_path).write_response(
            request=_wire_request(),
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b"[]",
            received_at=INGESTED_AT,
        )

    assert not list(tmp_path.rglob("body.json"))


def test_wire_failed_rollback_reports_indeterminate_publication(tmp_path, monkeypatch):
    """If neither partial cleanup nor final rollback is durable, retry safety is unknown."""

    def fail_unlink(_path, *args, **kwargs):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(IndeterminatePublicationError):
        WireStore(tmp_path).write_response(
            request=_wire_request(),
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b"[]",
            received_at=INGESTED_AT,
        )


def test_client_writes_wire_before_unsupported_json_shape_is_parsed(tmp_path):
    """Parsing before persistence would lose the exact body that explains a parser failure."""

    class FakeTransport:
        def get(self, url, *, params, timeout):
            return HttpResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=b'{"unexpected":"shape"}',
            )

    client = IndodaxCandleClient(
        transport=FakeTransport(), wire_store=WireStore(tmp_path), timeout_seconds=3
    )

    with pytest.raises(InvalidCandlePayload):
        client.fetch_window(
            pair="btc_idr",
            interval="1h",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 2, tzinfo=UTC),
            received_at=INGESTED_AT,
        )

    assert len(list(tmp_path.rglob("body.json"))) == 1
    assert len(list(tmp_path.rglob("metadata.json"))) == 1
