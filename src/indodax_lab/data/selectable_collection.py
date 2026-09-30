"""Selectable public collection and coverage workflow (DATA-07).

Thin service over the existing collector (IndodaxCandleClient), durable job
queue (SqliteJobQueue), range-aware registry (DatasetRegistry) and admission
guard (evaluate_admission). No credentials, no live network in tests, no
Production authority. Reuses CanonicalPair/DatasetRequest validation as-is.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from indodax_lab.contracts.common import CanonicalPair
from indodax_lab.contracts.identity import ArtifactRef
from indodax_lab.data.dataset_registry import (
    DatasetCoverageError,
    DatasetRegistry,
    DatasetRequest,
)
from indodax_lab.data.indodax_candles import (
    INTERVAL_TO_SECONDS,
    PAIR_TO_VENUE_SYMBOL,
    IndodaxCandleClient,
)
from indodax_lab.data.quality import QualityFinding, QualityReport
from indodax_lab.data.wire_store import WireArtifact, WireStore
from indodax_lab.orchestration.jobs import JobDefinition, JobRecord, JobStatus
from indodax_lab.orchestration.queue import SqliteJobQueue
from indodax_lab.orchestration.resources import (
    AdmissionPolicy,
    evaluate_admission,
)

JOB_TYPE = "data07_collect"
WORKER_ID = "data07-collector"
QUALITY_POLICY_VERSION = "data07-collect-v1"
QUALITY_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class CollectionCapabilities:
    """Public catalog: which pairs/timeframes may be collected, and how.

    Immutable; extension returns a new instance. Existing validation and
    historical hashes are never touched by an extension (DATA-07-AC4).
    """

    pairs: tuple[str, ...]
    timeframes: tuple[str, ...]
    venue_symbols: dict[str, str] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> CollectionCapabilities:
        return cls(
            pairs=tuple(PAIR_TO_VENUE_SYMBOL),
            timeframes=tuple(INTERVAL_TO_SECONDS),
            venue_symbols=dict(PAIR_TO_VENUE_SYMBOL),
        )

    def extend_pairs(self, new_pairs: dict[str, str]) -> CollectionCapabilities:
        merged = dict(self.venue_symbols)
        for pair, venue_symbol in new_pairs.items():
            CanonicalPair(pair=pair.lower())
            if not venue_symbol or not str(venue_symbol).strip():
                raise ValueError(f"VENUE_SYMBOL_REQUIRED:{pair}")
            merged[pair.lower()] = str(venue_symbol).strip()
        pairs = tuple(self.pairs) + tuple(
            p for p in (k.lower() for k in new_pairs) if p not in self.pairs
        )
        return CollectionCapabilities(
            pairs=pairs, timeframes=self.timeframes, venue_symbols=merged
        )


@dataclass(frozen=True)
class CollectionResult:
    """Explicit outcome of one collect() call; never an implicit success."""

    status: str  # COLLECTED | RESUMED | DEFERRED | REJECTED | FAILED
    reason: str
    job_id: str
    dataset_ref: ArtifactRef | None = None
    quality: QualityReport | None = None
    complete_coverage: bool = False
    resumed: bool = False
    wire_request_ids: tuple[str, ...] = ()
    fetch_calls: int = 0


def _canonical_payload(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _payload_hash(request: DatasetRequest) -> str:
    return hashlib.sha256(
        _canonical_payload(
            {
                "venue": request.venue,
                "pair": request.pair,
                "timeframe": request.timeframe,
                "start": request.start.isoformat(),
                "end": request.end.isoformat(),
                "source_id": request.source_id,
                "source_version": request.source_version,
                "version": request.version,
            }
        )
    ).hexdigest()


def _expected_epochs(start: datetime, end: datetime, step: int) -> list[int]:
    return list(range(int(start.timestamp()), int(end.timestamp()), step))


def _merge_gaps(missing: list[int], step: int) -> list[tuple[datetime, datetime]]:
    gaps: list[tuple[datetime, datetime]] = []
    if not missing:
        return gaps
    run_start = prev = missing[0]
    for epoch in missing[1:]:
        if epoch == prev + step:
            prev = epoch
            continue
        gaps.append(
            (
                datetime.fromtimestamp(run_start, tz=UTC),
                datetime.fromtimestamp(prev + step, tz=UTC),
            )
        )
        run_start = prev = epoch
    gaps.append(
        (
            datetime.fromtimestamp(run_start, tz=UTC),
            datetime.fromtimestamp(prev + step, tz=UTC),
        )
    )
    return gaps


class SelectableCollector:
    """collect(DatasetRequest, request_id) over existing contracts (DATA-07)."""

    def __init__(
        self,
        *,
        data_root: Path | str,
        registry_root: Path | str,
        queue_path: Path | str,
        transport: Any,
        clock: Callable[[], datetime],
        capabilities: CollectionCapabilities | None = None,
        admission: dict[str, Any] | None = None,
        wire_sink: Callable[[WireArtifact], None] | None = None,
    ) -> None:
        self._root = Path(data_root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._results_dir = self._root / "collect_results"
        self._results_dir.mkdir(parents=True, exist_ok=True)
        self._client = IndodaxCandleClient(
            transport=transport, wire_store=WireStore(self._root)
        )
        self.registry = DatasetRegistry(
            Path(registry_root), fetch_provider=self._fetch_partitions
        )
        self._queue = SqliteJobQueue(queue_path)
        self._clock = clock
        self._capabilities = capabilities or CollectionCapabilities.defaults()
        self._admission = admission
        self._wire_sink = wire_sink
        self._evidence: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Registry fetch provider: wire-first public fetch -> partition records
    # ------------------------------------------------------------------

    def _fetch_partitions(self, request: DatasetRequest) -> list[dict[str, Any]]:
        received_at = self._clock()
        fetch = self._client.fetch_window(
            pair=request.pair,
            interval=request.timeframe,
            start=request.start,
            end=request.end,
            received_at=received_at,
            venue_symbol=self._capabilities.venue_symbols[request.pair],
        )
        if self._wire_sink is not None:
            self._wire_sink(fetch.wire)
        records = fetch.batch.records
        if not records:
            raise DatasetCoverageError(
                f"COLLECTION_EMPTY:{request.pair}/{request.timeframe}: "
                "no accepted rows, nothing published"
            )
        step = INTERVAL_TO_SECONDS[request.timeframe]
        actual = {int(c.open_time.timestamp()): c for c in records}
        missing = [
            e for e in _expected_epochs(request.start, request.end, step) if e not in actual
        ]
        gaps = _merge_gaps(sorted(missing), step)
        conflicts = sum(
            1 for r in fetch.batch.rejects
            if r.reason == "CONFLICTING_DUPLICATE_SOURCE_EVENT_ID"
        )
        identities = sorted(
            (
                {
                    "event": c.source_event_id if hasattr(c, "source_event_id") else "",
                    "open": c.open_time.isoformat(),
                    "close": c.close_time.isoformat(),
                    "o": str(c.open),
                    "h": str(c.high),
                    "l": str(c.low),
                    "c": str(c.close),
                    "v": str(c.base_volume),
                }
                for c in records
            ),
            key=lambda d: (d["open"], d["event"]),
        )
        body = _canonical_payload(identities)
        opens = sorted(actual)
        closes = sorted(int(c.close_time.timestamp()) for c in records)
        partition = {
            "bytes": body,
            "sha256": hashlib.sha256(body).hexdigest(),
            "row_count": len(records),
            "duplicate_count": conflicts,
            "start_ts": datetime.fromtimestamp(opens[0], tz=UTC).isoformat(),
            "end_ts": datetime.fromtimestamp(closes[-1], tz=UTC).isoformat(),
            "gaps": [[s.isoformat(), e.isoformat()] for s, e in gaps],
        }
        self._evidence.append(
            {"wire": fetch.wire, "batch": fetch.batch, "gaps": gaps}
        )
        return [partition]

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    def _quality_for(
        self,
        request: DatasetRequest,
        *,
        bar_count: int,
        duplicate_count: int,
        gaps: list[tuple[datetime, datetime]],
        actual_start: datetime | None,
        actual_end: datetime | None,
        source_checksums: tuple[str, ...],
        dataset_id: str,
    ) -> QualityReport:
        step = INTERVAL_TO_SECONDS[request.timeframe]
        expected = _expected_epochs(request.start, request.end, step)
        as_of = self._clock()
        complete = bool(expected) and not gaps and bar_count == len(expected)
        findings = tuple(
            QualityFinding(
                code="COVERAGE_GAP",
                severity="WARN",
                pair=request.pair,
                start_ts=s,
                end_ts=e,
                row_count=0,
                details={"dataset_id": dataset_id},
            )
            for s, e in gaps
        )
        return QualityReport(
            quality_schema_version=QUALITY_SCHEMA_VERSION,
            policy_version=QUALITY_POLICY_VERSION,
            expected_start=request.start,
            expected_end=request.end,
            interval=request.timeframe,
            as_of=as_of,
            max_final_bar_age_microseconds=(
                int((as_of - actual_end).total_seconds() * 1_000_000)
                if actual_end is not None
                else None
            ),
            expected_rows=len(expected),
            actual_rows=bar_count,
            gap_ranges=tuple(gaps),
            duplicate_count=duplicate_count,
            invariant_counts={},
            min_ts=actual_start,
            max_ts=actual_end,
            coverage=(actual_start, actual_end),
            source_checksums=source_checksums,
            status="PASS" if complete else "WARN",
            silver_eligible=complete,
            findings=findings,
        )

    # ------------------------------------------------------------------
    # collect()
    # ------------------------------------------------------------------

    def collect(self, request: DatasetRequest, request_id: str) -> CollectionResult:
        if not request_id or not str(request_id).strip():
            raise ValueError("REQUEST_ID_REQUIRED")
        request_id = str(request_id)
        now = self._clock()

        # AC0: capability gate before any fetch or durable write.
        try:
            CanonicalPair(pair=request.pair)
        except ValueError:
            return CollectionResult(
                status="REJECTED",
                reason=f"UNSUPPORTED_PAIR:{request.pair}",
                job_id=request_id,
            )
        if request.pair not in self._capabilities.pairs:
            return CollectionResult(
                status="REJECTED",
                reason=f"UNSUPPORTED_PAIR:{request.pair}",
                job_id=request_id,
            )
        if request.timeframe not in self._capabilities.timeframes:
            return CollectionResult(
                status="REJECTED",
                reason=f"UNSUPPORTED_TIMEFRAME:{request.timeframe}",
                job_id=request_id,
            )

        digest = _payload_hash(request)
        job_def = JobDefinition(
            job_id=request_id,
            job_type=JOB_TYPE,
            recipe_hash=digest,
            input_ids=[],
            parameters={
                "resource_class": "LOW",
                "venue": request.venue,
                "pair": request.pair,
                "timeframe": request.timeframe,
                "start": request.start.isoformat(),
                "end": request.end.isoformat(),
                "source_id": request.source_id,
                "source_version": request.source_version,
                "payload_hash": digest,
            },
            created_at=now,
        )
        try:
            self._queue.submit_job(job_def)
            record = self._queue.get_job(request_id)
        except sqlite3.IntegrityError:
            record = self._queue.get_job(request_id)
            if record.status == JobStatus.SUCCESS:
                return self._resume_success(record, digest, request_id)
            if record.status == JobStatus.FAILED_FINAL:
                return CollectionResult(
                    status="FAILED",
                    reason=record.error_message or "COLLECTION_FAILED_FINAL",
                    job_id=request_id,
                )

        # AC5: guarded admission before any fetch; deferral stays durable.
        if self._admission is not None:
            reading = self._admission["reading_provider"]()
            decision = evaluate_admission(
                job_def,
                reading,
                self._admission["host_profile"],
                policy=self._admission.get("policy") or AdmissionPolicy(),
                capacity=self._admission.get("capacity"),
            )
            if not decision.admitted:
                return CollectionResult(
                    status="DEFERRED",
                    reason=decision.reason or "ADMISSION_DEFERRED",
                    job_id=request_id,
                )

        claimed = self._queue.claim_job(WORKER_ID, as_of=now)
        if claimed is None:
            return CollectionResult(
                status="DEFERRED",
                reason="COLLECTION_IN_PROGRESS:lease_held_elsewhere",
                job_id=request_id,
            )
        if claimed.job_id != request_id:
            return CollectionResult(
                status="FAILED",
                reason=f"CLAIM_FOREIGN_JOB:{claimed.job_id}",
                job_id=request_id,
            )

        try:
            self._evidence.clear()
            try:
                refs = self.registry.find(
                    request.venue, request.pair, request.timeframe,
                    request.start, request.end,
                )
                manifest = self.registry.get(refs[0])
                resumed = True
                fetches = 0
                wires: tuple[str, ...] = ()
            except DatasetCoverageError:
                manifest = self.registry.create(request)
                resumed = False
                fetches = len(self._evidence)
                wires = tuple(e["wire"].request_id for e in self._evidence)
            gaps = list(manifest.missing_intervals)
            quality = self._quality_for(
                request,
                bar_count=manifest.bar_count,
                duplicate_count=manifest.duplicate_count,
                gaps=gaps,
                actual_start=manifest.actual_start,
                actual_end=manifest.actual_end,
                source_checksums=tuple(manifest.partition_byte_hashes),
                dataset_id=manifest.dataset_id,
            )
            result = CollectionResult(
                status="COLLECTED",
                reason="COVERAGE_COMPLETE" if quality.status == "PASS" else "COVERAGE_WITH_GAPS",
                job_id=request_id,
                dataset_ref=manifest.to_artifact_ref(),
                quality=quality,
                complete_coverage=quality.status == "PASS",
                resumed=resumed,
                wire_request_ids=wires,
                fetch_calls=fetches,
            )
            self._complete(claimed, result)
            return result
        except Exception as exc:  # fail closed: explicit FAILED, durable marker
            reason = f"{type(exc).__name__}:{exc}"
            try:
                self._queue.fail_job(
                    request_id, WORKER_ID, claimed.generation,
                    error_message=reason, retryable=True, as_of=self._clock(),
                )
            except Exception:
                pass
            return CollectionResult(status="FAILED", reason=reason, job_id=request_id)

    # ------------------------------------------------------------------
    # Durable job completion / resume
    # ------------------------------------------------------------------

    def _result_document(self, result: CollectionResult, payload_hash: str) -> bytes:
        quality = result.quality
        doc = {
            "request_id": result.job_id,
            "payload_hash": payload_hash,
            "status": result.status,
            "reason": result.reason,
            "job_id": result.job_id,
            "dataset_ref": (
                {
                    "kind": result.dataset_ref.kind,
                    "id": result.dataset_ref.id,
                    "version": result.dataset_ref.version,
                    "sha256": result.dataset_ref.sha256,
                }
                if result.dataset_ref is not None
                else None
            ),
            "quality": quality.to_dict() if quality is not None else None,
            "quality_iso": (
                {
                    "expected_start": quality.expected_start.isoformat()
                    if quality.expected_start
                    else None,
                    "expected_end": quality.expected_end.isoformat()
                    if quality.expected_end
                    else None,
                    "as_of": quality.as_of.isoformat() if quality.as_of else None,
                    "gap_ranges": [
                        [s.isoformat(), e.isoformat()] for s, e in quality.gap_ranges
                    ],
                    "min_ts": quality.min_ts.isoformat() if quality.min_ts else None,
                    "max_ts": quality.max_ts.isoformat() if quality.max_ts else None,
                    "coverage": [
                        quality.coverage[0].isoformat() if quality.coverage[0] else None,
                        quality.coverage[1].isoformat() if quality.coverage[1] else None,
                    ],
                    "findings": [
                        {
                            "code": f.code,
                            "severity": f.severity,
                            "pair": f.pair,
                            "start_ts": f.start_ts.isoformat(),
                            "end_ts": f.end_ts.isoformat(),
                            "row_count": f.row_count,
                            "details": dict(f.details),
                        }
                        for f in quality.findings
                    ],
                }
                if quality is not None
                else None
            ),
            "complete_coverage": result.complete_coverage,
            "resumed": result.resumed,
            "wire_request_ids": list(result.wire_request_ids),
            "fetch_calls": result.fetch_calls,
        }
        return _canonical_payload(doc)

    def _complete(self, claimed: JobRecord, result: CollectionResult) -> None:
        content = self._result_document(result, _payload_hash_from_claim(claimed))
        path = self._results_dir / f"{claimed.job_id}.json"
        path.write_bytes(content)
        self._queue.complete_job(
            claimed.job_id,
            WORKER_ID,
            claimed.generation,
            artifact_path=path,
            expected_hash=hashlib.sha256(content).hexdigest(),
            as_of=self._clock(),
        )

    def _resume_success(
        self, record: JobRecord, digest: str, request_id: str
    ) -> CollectionResult:
        try:
            doc = json.loads(self._queue.read_result_artifact(request_id))
        except Exception as exc:
            return CollectionResult(
                status="FAILED",
                reason=f"RESULT_ARTIFACT_UNREADABLE:{type(exc).__name__}",
                job_id=request_id,
            )
        if doc.get("payload_hash") != digest:
            return CollectionResult(
                status="REJECTED",
                reason=f"REQUEST_ID_CONFLICT:{request_id}",
                job_id=request_id,
            )
        ref = doc.get("dataset_ref")
        dataset_ref = ArtifactRef(**ref) if ref else None
        quality = _quality_from_json(doc.get("quality"), doc.get("quality_iso"))
        return CollectionResult(
            status="COLLECTED",
            reason=str(doc.get("reason", "")),
            job_id=request_id,
            dataset_ref=dataset_ref,
            quality=quality,
            complete_coverage=bool(doc.get("complete_coverage", False)),
            resumed=True,
            wire_request_ids=tuple(doc.get("wire_request_ids", [])),
            fetch_calls=0,
        )


def _payload_hash_from_claim(claimed: JobRecord) -> str:
    params = claimed.parameters or {}
    digest = params.get("payload_hash", "")
    if not digest or len(digest) != 64:
        raise ValueError("JOB_PAYLOAD_HASH_MISSING")
    return str(digest)


def _parse_opt(value: Any) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _quality_from_json(
    quality: dict[str, Any] | None, iso: dict[str, Any] | None
) -> QualityReport | None:
    if not quality or not iso:
        return None
    findings = tuple(
        QualityFinding(
            code=str(f["code"]),
            severity=str(f["severity"]),  # type: ignore[arg-type]
            pair=str(f["pair"]),
            start_ts=_parse_opt(f["start_ts"]) or datetime.fromtimestamp(0, tz=UTC),
            end_ts=_parse_opt(f["end_ts"]) or datetime.fromtimestamp(0, tz=UTC),
            row_count=int(f["row_count"]),
            details=dict(f["details"]),
        )
        for f in iso.get("findings", [])
    )
    coverage = iso.get("coverage", [None, None])
    return QualityReport(
        quality_schema_version=str(quality.get("quality_schema_version", "1")),
        policy_version=str(quality.get("policy_version", "")),
        expected_start=_parse_opt(iso.get("expected_start")),
        expected_end=_parse_opt(iso.get("expected_end")),
        interval=quality.get("interval"),
        as_of=_parse_opt(iso.get("as_of")),
        max_final_bar_age_microseconds=quality.get("max_final_bar_age_microseconds"),
        expected_rows=int(quality.get("expected_rows", 0)),
        actual_rows=int(quality.get("actual_rows", 0)),
        gap_ranges=tuple(
            (_parse_opt(s), _parse_opt(e)) for s, e in iso.get("gap_ranges", [])
        ),
        duplicate_count=int(quality.get("duplicate_count", 0)),
        invariant_counts=dict(quality.get("invariant_counts", {})),
        min_ts=_parse_opt(iso.get("min_ts")),
        max_ts=_parse_opt(iso.get("max_ts")),
        coverage=(_parse_opt(coverage[0]), _parse_opt(coverage[1])),
        source_checksums=tuple(quality.get("source_checksums", [])),
        status=quality.get("status", "FAIL"),  # type: ignore[arg-type]
        silver_eligible=bool(quality.get("silver_eligible", False)),
        findings=findings,
    )
