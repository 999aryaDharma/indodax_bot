"""Immutable, pre-publication sentry decisions for public-trade batches."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from indodax_lab.contracts import QualityStatus, TradeEvent

from .checksums import sha256_bytes
from .manifest import canonical_json_bytes
from .publication import publish_immutable_bytes
from .trade_wire import VerifiedTradeWireArtifact, load_trade_wire_artifact

POLICY_VERSION = "public-trade-batch-sentry-v3"
SCHEMA_VERSION = "2.0.0"


@dataclass(frozen=True)
class TradeBatchDecision:
    """One global decision over a canonical, exact set of writer batches."""

    batch_paths: tuple[Path, ...]
    batch_sha256s: tuple[str, ...]
    row_count: int
    record_path: Path
    record_sha256: str
    status: str
    events: tuple[TradeEvent, ...]
    wire_artifacts: tuple[VerifiedTradeWireArtifact, ...]
    wire_batch_sha256s: tuple[str, ...]


@dataclass(frozen=True)
class _Batch:
    path: Path
    sha256: str
    events: tuple[TradeEvent, ...]
    offsets: tuple[int, ...]
    size_bytes: int
    wire_artifacts: tuple[VerifiedTradeWireArtifact, ...]
    wire_events: tuple[TradeEvent, ...]

    @property
    def sort_key(self) -> tuple[int, datetime, int, str]:
        first = self.wire_events[0]
        return (
            self.offsets[0],
            first.event_ts,
            first.sequence if first.sequence is not None else -1,
            self.sha256,
        )


@dataclass(frozen=True)
class _CanonicalDecision:
    batches: tuple[_Batch, ...]
    payload: bytes
    digest: str
    row_count: int


def validate_trade_batches(data_root: Path, batch_paths: tuple[Path, ...]) -> TradeBatchDecision:
    """Validate and publish one global immutable decision before bar publication."""
    root = Path(data_root).resolve()
    canonical = _canonical_trade_decision(root, _load_current_batches(root, batch_paths))
    batches = canonical.batches
    record = root / "quality" / "trades" / "decisions" / f"{canonical.digest}.json"
    publish_immutable_bytes(record, canonical.payload)
    return TradeBatchDecision(
        batch_paths=tuple(batch.path for batch in batches),
        batch_sha256s=tuple(batch.sha256 for batch in batches),
        row_count=canonical.row_count,
        record_path=record,
        record_sha256=canonical.digest,
        status="PASS",
        events=tuple(event for batch in batches for event in batch.wire_events),
        wire_artifacts=tuple(wire for batch in batches for wire in batch.wire_artifacts),
        wire_batch_sha256s=tuple(
            batch.sha256 for batch in batches for _wire in batch.wire_artifacts
        ),
    )


def _canonical_trade_decision(
    root: Path, batches: tuple[_Batch, ...]
) -> _CanonicalDecision:
    """Purely validate loaded exact bytes and emit the sole canonical decision."""
    if len({batch.sha256 for batch in batches}) != len(batches):
        raise ValueError("TRADE_BATCH_DUPLICATE: trade sentry batch set has duplicates")
    events = tuple(event for batch in batches for event in batch.events)
    offsets = tuple(offset for batch in batches for offset in batch.offsets)
    if len({event.source_event_id for event in events}) != len(events):
        raise ValueError("TRADE_EVENT_ID_DUPLICATE: trade sentry has duplicate event IDs")
    if len({event.pair.pair for event in events}) != 1:
        raise ValueError("TRADE_PAIR_MISMATCH: trade sentry batches have inconsistent pairs")
    if any(event.quality_status is not QualityStatus.PASS for event in events):
        raise ValueError("TRADE_QUALITY_NOT_PASS: trade sentry contains non-PASS events")
    sequence_values = tuple(event.sequence for event in events)
    present_sequences = tuple(value for value in sequence_values if value is not None)
    if present_sequences and len(present_sequences) != len(sequence_values):
        raise ValueError(
            "TRADE_SEQUENCE_PRESENCE_MIXED: sequence continuity must be all-present or all-absent"
        )
    if present_sequences and not _strictly_contiguous(present_sequences):
        raise ValueError(
            "TRADE_SEQUENCE_NOT_CONTIGUOUS: sequences must increase globally by exactly one"
        )
    if not offsets or not _strictly_contiguous(offsets):
        raise ValueError(
            "TRADE_OFFSET_NOT_CONTIGUOUS: offsets must increase globally by exactly one"
        )
    for batch in batches:
        if batch.events != batch.wire_events:
            raise ValueError(
                "TRADE_WIRE_EVENT_MISMATCH: batch events must equal canonical wire parse"
            )
    rows = [
        {
            "batch_id": f"sha256:{batch.sha256}",
            "path": batch.path.relative_to(root).as_posix(),
            "sha256": batch.sha256,
            "size_bytes": batch.size_bytes,
            "row_count": len(batch.events),
            "trade_wire_ids": [wire.link.wire_id for wire in batch.wire_artifacts],
        }
        for batch in batches
    ]
    decision = {
        "decision_schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "status": "PASS",
        "pair": events[0].pair.pair,
        "expected_rows": len(events),
        "actual_rows": len(events),
        "batch_count": len(rows),
        "batches": rows,
        "source_event_ids": sorted(event.source_event_id for event in events),
        "findings": [],
    }
    payload = canonical_json_bytes(decision)
    digest = sha256_bytes(payload)
    return _CanonicalDecision(batches, payload, digest, len(events))


def require_existing_approved_trade_decision(
    data_root: Path, batch_paths: tuple[Path, ...], decision_path: Path
) -> TradeBatchDecision:
    """Load only a previously published global PASS decision; never mint one."""
    root = Path(data_root).resolve()
    path = Path(decision_path).resolve()
    try:
        path.relative_to(root / "quality" / "trades" / "decisions")
        payload = path.read_bytes()
        if path.stem != sha256_bytes(payload):
            raise ValueError
        raw = json.loads(payload)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("trade quality decision is missing or invalid") from error
    if not isinstance(raw, dict):
        raise ValueError("trade quality decision schema is incomplete")
    canonical = _canonical_trade_decision(
        root, _load_current_batches(root, batch_paths)
    )
    if payload != canonical.payload or path.stem != canonical.digest:
        raise ValueError("trade quality decision is not the canonical decision for exact batches")
    checked = canonical.batches
    return TradeBatchDecision(
        tuple(batch.path for batch in checked),
        tuple(batch.sha256 for batch in checked),
        canonical.row_count,
        path,
        canonical.digest,
        "PASS",
        tuple(event for batch in checked for event in batch.wire_events),
        tuple(wire for batch in checked for wire in batch.wire_artifacts),
        tuple(batch.sha256 for batch in checked for _wire in batch.wire_artifacts),
    )


def _load_batch(root: Path, path: Path) -> _Batch:
    path = Path(path).resolve()
    try:
        path.relative_to(root)
        content = path.read_bytes()
    except (OSError, ValueError) as error:
        raise ValueError("trade batch is unavailable") from error
    digest = sha256_bytes(content)
    if path.name != f"batch={digest}.jsonl":
        raise ValueError("trade batch checksum filename mismatch")
    events: list[TradeEvent] = []
    offsets: list[int] = []
    wire_artifacts: list[VerifiedTradeWireArtifact] = []
    wire_events: list[TradeEvent] = []
    for line in content.splitlines():
        record = json.loads(line)
        if not isinstance(record, dict) or record.get("kind") != "TRADE":
            continue
        if not isinstance(record.get("offset"), int) or record["offset"] < 0:
            raise ValueError("trade batch offset is invalid")
        offsets.append(record["offset"])
        if "trade_wire" not in record:
            raise ValueError(
                "TRADE_WIRE_REFERENCE_MISSING: every trade record requires raw wire lineage"
            )
        wire = load_trade_wire_artifact(root, record["trade_wire"])
        if wire.offset != record["offset"]:
            raise ValueError("TRADE_WIRE_OFFSET_MISMATCH")
        wire_artifacts.append(wire)
        wire_events.extend(wire.events)
        encoded = record.get("events")
        if not isinstance(encoded, list):
            raise ValueError("trade batch events are invalid")
        for event in encoded:
            converted = dict(event)
            for field in ("price", "base_qty", "quote_qty"):
                converted[field] = Decimal(str(converted[field]))
            events.append(TradeEvent.model_validate(converted))
    if not events:
        raise ValueError("trade batch contains no public trades")
    if not wire_events:
        raise ValueError("TRADE_WIRE_EVENT_SET_EMPTY")
    return _Batch(
        path,
        digest,
        tuple(events),
        tuple(offsets),
        len(content),
        tuple(wire_artifacts),
        tuple(wire_events),
    )


def _load_current_batches(root: Path, batch_paths: tuple[Path, ...]) -> tuple[_Batch, ...]:
    if not batch_paths:
        raise ValueError("TRADE_BATCH_SET_EMPTY: trade sentry requires at least one batch")
    return tuple(
        sorted(
            (_load_batch(root, path) for path in batch_paths),
            key=lambda row: row.sort_key,
        )
    )


def _strictly_contiguous(values: tuple[int, ...]) -> bool:
    return all(
        current == previous + 1
        for previous, current in zip(values, values[1:], strict=False)
    )
