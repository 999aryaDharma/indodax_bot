"""Canonical global public-trade sentry regression tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.contracts import (
    AggressorSide,
    CanonicalPair,
    QualityStatus,
    TradeEvent,
)
from indodax_lab.data.checksums import sha256_bytes
from indodax_lab.data.manifest import canonical_json_bytes
from indodax_lab.data.stream_protocol import parse_public_message
from indodax_lab.data.trade_sentry import (
    POLICY_VERSION,
    SCHEMA_VERSION,
    require_existing_approved_trade_decision,
    validate_trade_batches,
)
from indodax_lab.data.trade_wire import persist_trade_wire_artifact

BASE = datetime(2024, 1, 1, tzinfo=UTC)
_DEFAULT_SEQUENCE = object()


def test_global_validator_rejects_garbage_wire_with_supplied_valid_event(
    tmp_path: Path,
) -> None:
    """Deleting wire parsing must not let caller-supplied canonical-looking events pass."""
    link = _wire_link(
        tmp_path,
        body=b'{"garbage":true}',
        received_at=BASE + timedelta(seconds=1),
        expected_pair="btc_idr",
        channel="market:trade-activity-btcidr",
        offset=10,
    )
    batch = _raw_batch(
        tmp_path,
        offset=10,
        events=(_trade("supplied-valid", 0, sequence=20),),
        trade_wire=link,
    )

    with pytest.raises(ValueError, match="TRADE_WIRE_PAYLOAD_INVALID"):
        validate_trade_batches(tmp_path, (batch,))


def test_global_validator_rejects_batch_event_different_from_parsed_wire(
    tmp_path: Path,
) -> None:
    """Changing any supplied event field must fail against the canonical Task 11 parse."""
    received_at = BASE + timedelta(seconds=1)
    payload = _official_payload(offset=10, sequence=20)
    parsed = parse_public_message(
        payload,
        ingested_at=received_at,
        expected_pair="btc_idr",
    )
    forged = parsed.trades[0].model_copy(update={"price": Decimal("999")})
    link = _wire_link(
        tmp_path,
        body=canonical_json_bytes(payload),
        received_at=received_at,
        expected_pair="btc_idr",
        channel="market:trade-activity-btcidr",
        offset=10,
    )
    batch = _raw_batch(
        tmp_path,
        offset=10,
        events=(forged,),
        trade_wire=link,
    )

    with pytest.raises(ValueError, match="TRADE_WIRE_EVENT_MISMATCH"):
        validate_trade_batches(tmp_path, (batch,))


def test_loader_rejects_content_addressed_forged_pass_for_mixed_pairs(tmp_path: Path) -> None:
    """Removing semantic revalidation would admit a self-consistent forged PASS."""
    batches = (
        _batch(tmp_path, offset=40, events=(_trade("btc-1", 0, pair="btc_idr"),)),
        _batch(tmp_path, offset=41, events=(_trade("eth-1", 1, pair="eth_idr"),)),
    )
    record = _forge_pass(tmp_path, batches)

    with pytest.raises(ValueError, match="TRADE_PAIR_MISMATCH"):
        require_existing_approved_trade_decision(tmp_path, batches, record)


@pytest.mark.parametrize(
    ("batches", "code"),
    [
        (
            lambda root: (
                _batch(
                    root,
                    offset=10,
                    events=(_trade("one", 0, sequence=20), _trade("two", 1, sequence=None)),
                ),
            ),
            "TRADE_SEQUENCE_PRESENCE_MIXED",
        ),
        (
            lambda root: (
                _batch(
                    root,
                    offset=10,
                    events=(_trade("one", 0, sequence=20), _trade("two", 1, sequence=22)),
                ),
            ),
            "TRADE_SEQUENCE_NOT_CONTIGUOUS",
        ),
        (
            lambda root: (
                _batch(root, offset=10, events=(_trade("one", 0),)),
                _batch(root, offset=12, events=(_trade("two", 1),)),
            ),
            "TRADE_OFFSET_NOT_CONTIGUOUS",
        ),
        (
            lambda root: (
                _batch(root, offset=10, events=(_trade("one", 0),)),
                _batch(root, offset=10, events=(_trade("two", 1),)),
            ),
            "TRADE_OFFSET_NOT_CONTIGUOUS",
        ),
    ],
)
def test_global_validator_rejects_mixed_presence_duplicates_and_gaps(
    tmp_path: Path, batches, code: str
) -> None:
    """Weak monotonic sorting cannot prove global stream continuity."""
    with pytest.raises(ValueError, match=code):
        validate_trade_batches(tmp_path, batches(tmp_path))


def test_global_validator_detects_omitted_middle_batch_and_ignores_cli_order(
    tmp_path: Path,
) -> None:
    """Canonical batch order must not depend on CLI order, while omissions remain visible."""
    first = _batch(tmp_path, offset=70, events=(_trade("one", 0),))
    middle = _batch(tmp_path, offset=71, events=(_trade("two", 1),))
    last = _batch(tmp_path, offset=72, events=(_trade("three", 2),))

    forward = validate_trade_batches(tmp_path, (first, middle, last))
    reverse = validate_trade_batches(tmp_path, (last, middle, first))
    assert reverse.record_sha256 == forward.record_sha256
    assert reverse.batch_paths == forward.batch_paths

    with pytest.raises(ValueError, match="TRADE_SEQUENCE_NOT_CONTIGUOUS"):
        validate_trade_batches(tmp_path, (first, last))


def _trade(
    event_id: str,
    seconds: int,
    *,
    pair: str = "btc_idr",
    sequence: int | None | object = _DEFAULT_SEQUENCE,
    status: QualityStatus = QualityStatus.PASS,
) -> TradeEvent:
    event_ts = BASE + timedelta(seconds=seconds)
    sequence_value = 20 + seconds if sequence is _DEFAULT_SEQUENCE else sequence
    source_event_id = (
        f"indodax:public-trade:{pair.replace('_', '')}:{sequence_value}"
        if sequence_value is not None
        else event_id
    )
    return TradeEvent(
        schema_version="1.0.0",
        pair=CanonicalPair(pair=pair),
        venue_symbol=pair.replace("_", "").upper(),
        event_ts=event_ts,
        ingested_at=event_ts + timedelta(milliseconds=1),
        available_at=event_ts + timedelta(milliseconds=1),
        price=Decimal("100"),
        base_qty=Decimal("1"),
        quote_qty=Decimal("100"),
        source_event_id=source_event_id,
        source="indodax_public_websocket",
        sequence=sequence_value,
        aggressor_side=AggressorSide.BUY,
        quality_status=status,
        quality_flags=[],
    )


def _batch(root: Path, *, offset: int, events: tuple[TradeEvent, ...]) -> Path:
    pair = events[0].pair.pair
    received_at = max(event.ingested_at for event in events)
    wire = {
        "result": {
            "channel": f"market:trade-activity-{pair.replace('_', '')}",
            "data": {
                "data": [
                    [
                        event.pair.pair.replace("_", ""),
                        int(event.event_ts.timestamp()),
                        event.sequence if event.sequence is not None else 90_000 + index,
                        (event.aggressor_side or AggressorSide.UNKNOWN).value.lower(),
                        str(event.price),
                        str(event.quote_qty),
                        str(event.base_qty),
                    ]
                    for index, event in enumerate(events)
                ],
                "offset": offset,
            },
        }
    }
    link = persist_trade_wire_artifact(
        root,
        body=canonical_json_bytes(wire),
        received_at=received_at,
        expected_pair=pair,
        channel=f"market:trade-activity-{pair.replace('_', '')}",
        offset=offset,
    )
    record = {
        "kind": "TRADE",
        "offset": offset,
        "events": [event.model_dump(mode="json") for event in events],
        "trade_wire": link.to_record(root),
    }
    content = canonical_json_bytes(record) + b"\n"
    digest = sha256_bytes(content)
    path = (
        root
        / "wire"
        / "source=indodax"
        / "dataset=public-market-stream"
        / f"batch={digest}.jsonl"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _official_payload(*, offset: int, sequence: int) -> dict[str, object]:
    return {
        "result": {
            "channel": "market:trade-activity-btcidr",
            "data": {
                "data": [["btcidr", int(BASE.timestamp()), sequence, "buy", "100", "100", "1"]],
                "offset": offset,
            },
        }
    }


def _wire_link(
    root: Path,
    *,
    body: bytes,
    received_at: datetime,
    expected_pair: str,
    channel: str,
    offset: int,
) -> dict[str, object]:
    body_sha256 = sha256_bytes(body)
    metadata_without_id = {
        "wire_schema_version": "1.0.0",
        "parser_policy_version": "indodax-public-trade-v1",
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
        root
        / "wire"
        / "source=indodax"
        / "dataset=public-trade-message"
        / f"wire={wire_id.removeprefix('sha256:')}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    body_path = directory / "body.json"
    metadata_path = directory / "metadata.json"
    body_path.write_bytes(body)
    metadata_path.write_bytes(metadata_bytes)
    return {
        "wire_id": wire_id,
        "body_path": body_path.relative_to(root).as_posix(),
        "body_sha256": body_sha256,
        "metadata_path": metadata_path.relative_to(root).as_posix(),
        "metadata_sha256": metadata_sha256,
    }


def _raw_batch(
    root: Path,
    *,
    offset: int,
    events: tuple[TradeEvent, ...],
    trade_wire: dict[str, object],
) -> Path:
    record = {
        "kind": "TRADE",
        "offset": offset,
        "events": [event.model_dump(mode="json") for event in events],
        "trade_wire": trade_wire,
    }
    content = canonical_json_bytes(record) + b"\n"
    digest = sha256_bytes(content)
    path = (
        root
        / "wire"
        / "source=indodax"
        / "dataset=public-market-stream"
        / f"batch={digest}.jsonl"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _forge_pass(root: Path, batches: tuple[Path, ...]) -> Path:
    loaded: list[tuple[Path, str, list[dict[str, object]]]] = []
    all_events: list[dict[str, object]] = []
    for path in batches:
        digest = sha256_bytes(path.read_bytes())
        records = [json.loads(line) for line in path.read_bytes().splitlines()]
        events = [event for record in records for event in record["events"]]
        loaded.append((path, digest, events))
        all_events.extend(events)
    loaded.sort(key=lambda row: (row[2][0]["event_ts"], row[1]))
    decision = {
        "decision_schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "PASS",
        "pair": "btc_idr",
        "expected_rows": len(all_events),
        "actual_rows": len(all_events),
        "batch_count": len(loaded),
        "batches": [
            {
                "batch_id": f"sha256:{digest}",
                "path": path.relative_to(root).as_posix(),
                "sha256": digest,
                "size_bytes": path.stat().st_size,
                "row_count": len(events),
            }
            for path, digest, events in loaded
        ],
        "source_event_ids": sorted(str(event["source_event_id"]) for event in all_events),
        "findings": [],
    }
    payload = canonical_json_bytes(decision)
    record = root / "quality" / "trades" / "decisions" / f"{sha256_bytes(payload)}.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_bytes(payload)
    return record
