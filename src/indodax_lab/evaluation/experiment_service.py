"""Experiment lifecycle and backtest orchestration (RW3-01).

Thin lifecycle over existing primitives: EVAL-01 ExperimentRegistry (run
records stay queryable, including failures), JOB-01 leased queue (exactly
one publisher; cancel fences stale workers), RW2-03 pipeline digests,
RP-04 runtime kernel (common historical runtime), DATA-07-style resolvers.

No credentials, no live network, no Production authority. Trial decisions
come from an injected candidate factory; the default path calls the real
CandidateRuntime.load_plan (bootstrap without a completed candidate).

Publication ordering (RW3-01 Step 4): result bytes are written first, the
leased queue publishes them under the live lease fence, and only then does
the experiment catalog move to a terminal state. Every worker-side catalog
write is a compare-and-set on the status the worker observed, so a cancelled
or superseded worker can never overwrite a newer state.
"""

from __future__ import annotations

import decimal
import functools
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.contracts.workbench import VerifiedRuntimePlan
from indodax_lab.data.dataset_registry import DatasetRequest  # noqa: F401 (contract surface)
from indodax_lab.execution.state_store import ExecutionStateStore
from indodax_lab.orchestration.jobs import (
    JobDefinition,
    JobRecord,
    JobStatus,
    LeaseFencingError,
)
from indodax_lab.orchestration.queue import SqliteJobQueue
from indodax_lab.runtime.candidate import CandidateRuntime
from indodax_lab.runtime.kernel import RuntimeKernel

JOB_TYPE = "rw3_backtest"
WORKER_ID = "rw3-runner"
EXPERIMENT_ID_PREFIX = "exp_"


def _ensure_utc(value: datetime, name: str) -> datetime:
    from datetime import timedelta

    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{name}")
    return value


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _equal_share(capital: Decimal, count: int) -> Decimal:
    """Exact equal split or fail closed; remainders are never silently assigned."""
    with decimal.localcontext() as ctx:
        ctx.prec = 60
        share = capital / count
        if share * count != capital:
            raise ValueError(f"CAPITAL_NOT_SPLICEABLE:{capital}/{count}")
    return share


class ExperimentStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_TERMINAL = (ExperimentStatus.SUCCESS, ExperimentStatus.FAILED, ExperimentStatus.CANCELLED)

# States from which run_backtest may proceed. QUEUED/RUNNING are resumable
# only through the job lease (a live lease is never taken over).
_RUNNABLE = (
    ExperimentStatus.VALIDATED,
    ExperimentStatus.FAILED,
    ExperimentStatus.QUEUED,
    ExperimentStatus.RUNNING,
)

_ALLOWED: dict[ExperimentStatus, set[ExperimentStatus]] = {
    ExperimentStatus.DRAFT: {ExperimentStatus.VALIDATED, ExperimentStatus.CANCELLED},
    ExperimentStatus.VALIDATED: {ExperimentStatus.QUEUED, ExperimentStatus.CANCELLED},
    ExperimentStatus.QUEUED: {ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED},
    ExperimentStatus.RUNNING: {
        ExperimentStatus.SUCCESS,
        ExperimentStatus.FAILED,
        ExperimentStatus.CANCELLED,
    },
    ExperimentStatus.SUCCESS: set(),
    # FAILED is a retained attempt, not a dead end: a retry re-queues the same
    # experiment (history and failure artifacts stay). SUCCESS/CANCELLED are final.
    ExperimentStatus.FAILED: {ExperimentStatus.QUEUED},
    ExperimentStatus.CANCELLED: set(),
}


class ResolvedDataset(BaseModel):
    """Dataset resolution evidence supplied by the dataset owner boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str
    content_hash: str


class ExperimentManifest(BaseModel):
    """Immutable experiment inputs; edits are forbidden after DRAFT."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    dataset_ref: ArtifactRef
    pipeline_ref: ArtifactRef
    policy_version: str = Field(min_length=1)
    seed: int = Field(ge=0)
    pairs: tuple[str, ...] = Field(min_length=1)
    capital: Decimal = Field(gt=0)


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    reasons: tuple[str, ...] = ()
    runtime_plan_digest: str | None = None


class ChildResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    child_id: str
    pair: str
    status: str
    capital: Decimal
    order_ids: tuple[str, ...] = ()
    error_message: str | None = None


class ResultArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str
    status: str
    result_digest: str
    runtime_plan_digest: str
    artifact_path: str
    artifact_sha256: str
    children: tuple[ChildResult, ...] = ()


class ComparisonReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_ids: tuple[str, ...]
    digests: tuple[str, ...]
    equal: bool
    assumptions: tuple[dict[str, Any], ...] = ()
    reasons: tuple[str, ...] = ()


class TradeFill(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fill_id: str
    order_id: str
    pair: str
    side: str
    qty: Decimal
    price: Decimal


class ClosedTrade(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str
    qty: Decimal
    buy_price: Decimal
    sell_price: Decimal
    realized_pnl: Decimal


class TradeReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str
    fills: tuple[TradeFill, ...] = ()
    closed_trades: tuple[ClosedTrade, ...] = ()
    open_orders: tuple[dict[str, Any], ...] = ()
    fee_status: str = "FEES_UNKNOWN"
    fee_reason: str = "no fee schedule bound to trial"
    win_rate: Decimal | None = None
    win_rate_status: str = "UNAVAILABLE"
    win_rate_reason: str = "WIN_RATE_UNAVAILABLE:no_closed_trades"


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str
    parent_id: str | None = None
    manifest: ExperimentManifest
    plan_digest: str | None = None
    status: ExperimentStatus = ExperimentStatus.DRAFT
    validation: ValidationReport | None = None
    job_id: str | None = None
    result: ResultArtifact | None = None
    children: tuple[ChildResult, ...] = ()
    history: tuple[dict[str, Any], ...] = ()
    cancel_keys: tuple[str, ...] = ()
    error_message: str | None = None


class _PlanBoundCandidate:
    """Glue exposing plan digests for a verified plan-bound runtime.

    The wrapped runtime is the real CandidateRuntime.load_plan product, so
    plan linkage is genuinely verified; this adapter only surfaces the two
    digest attributes the kernel boundary requires.
    """

    def __init__(self, runtime: CandidateRuntime, plan_digest: str) -> None:
        self._runtime = runtime
        self.plan_digest = plan_digest
        self.candidate_digest: str | None = None

    def evaluate(self, event: Any, state: Any) -> tuple:
        return tuple(self._runtime.evaluate(event, state))


def _locked(method: Callable[..., Any]) -> Callable[..., Any]:
    """Serialize store access: one authoritative writer across worker/caller threads."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class ExperimentStore:
    """Single-writer SQLite lifecycle store (test namespaces are temp dirs)."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # A worker thread runs backtests while callers cancel/query, so the
        # connection is shared and every operation is serialized by _lock.
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if str(self._db_path) != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    manifest_json TEXT NOT NULL,
                    plan_digest TEXT,
                    status TEXT NOT NULL,
                    validation_json TEXT,
                    job_id TEXT,
                    result_json TEXT,
                    history_json TEXT NOT NULL,
                    cancel_keys_json TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @_locked
    def insert(self, record: ExperimentRecord, at: datetime) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO experiments (
                        experiment_id, parent_id, manifest_json, plan_digest,
                        status, validation_json, job_id, result_json,
                        history_json, cancel_keys_json, error_message,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.experiment_id,
                        record.parent_id,
                        record.manifest.model_dump_json(),
                        record.plan_digest,
                        record.status.value,
                        (
                            record.validation.model_dump_json()
                            if record.validation
                            else None
                        ),
                        record.job_id,
                        record.result.model_dump_json() if record.result else None,
                        json.dumps(list(record.history)),
                        json.dumps(list(record.cancel_keys)),
                        record.error_message,
                        at.isoformat(),
                        at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"EXPERIMENT_ID_CONFLICT:{record.experiment_id}"
            ) from exc

    @_locked
    def get(self, experiment_id: str) -> ExperimentRecord:
        cursor = self._conn.execute(
            "SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"EXPERIMENT_NOT_FOUND:{experiment_id}")
        return ExperimentRecord(
            experiment_id=row["experiment_id"],
            parent_id=row["parent_id"],
            manifest=ExperimentManifest.model_validate_json(row["manifest_json"]),
            plan_digest=row["plan_digest"],
            status=ExperimentStatus(row["status"]),
            validation=(
                ValidationReport.model_validate_json(row["validation_json"])
                if row["validation_json"]
                else None
            ),
            job_id=row["job_id"],
            result=(
                ResultArtifact.model_validate_json(row["result_json"])
                if row["result_json"]
                else None
            ),
            history=tuple(json.loads(row["history_json"])),
            cancel_keys=tuple(json.loads(row["cancel_keys_json"])),
            error_message=row["error_message"],
        )

    @_locked
    def put(
        self,
        record: ExperimentRecord,
        at: datetime,
        expected_status: ExperimentStatus | None = None,
    ) -> bool:
        """Write ``record``; with ``expected_status`` it is a compare-and-set.

        Returns True when a row was updated. A False return means the stored
        status no longer matches what the caller observed (e.g. cancelled while
        a worker ran) and the caller must not assume its write landed.
        """
        sql = """
            UPDATE experiments SET parent_id = ?, manifest_json = ?,
                plan_digest = ?, status = ?, validation_json = ?,
                job_id = ?, result_json = ?, history_json = ?,
                cancel_keys_json = ?, error_message = ?, updated_at = ?
            WHERE experiment_id = ?
            """
        params: list[Any] = [
            record.parent_id,
            record.manifest.model_dump_json(),
            record.plan_digest,
            record.status.value,
            record.validation.model_dump_json() if record.validation else None,
            record.job_id,
            record.result.model_dump_json() if record.result else None,
            json.dumps(list(record.history)),
            json.dumps(list(record.cancel_keys)),
            record.error_message,
            at.isoformat(),
            record.experiment_id,
        ]
        if expected_status is not None:
            sql += " AND status = ?"
            params.append(expected_status.value)
        with self._conn:
            cursor = self._conn.execute(sql, params)
        return cursor.rowcount == 1

    @_locked
    def list(self, status: ExperimentStatus | None = None) -> list[ExperimentRecord]:
        if status is None:
            rows = self._conn.execute(
                "SELECT experiment_id FROM experiments ORDER BY created_at ASC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT experiment_id FROM experiments WHERE status = ? ORDER BY created_at ASC",
                (status.value,),
            ).fetchall()
        return [self.get(row["experiment_id"]) for row in rows]

    @_locked
    def claim_cancel_key(self, request_id: str, experiment_id: str) -> str | None:
        """Return the experiment already holding this key, else record the claim.

        Same key + same experiment -> idempotent replay. Same key +
        different experiment -> conflict (fail closed).
        """
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cancel_keys (
                    request_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL
                )
                """
            )
            row = self._conn.execute(
                "SELECT experiment_id FROM cancel_keys WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is not None:
                return str(row["experiment_id"])
            self._conn.execute(
                "INSERT INTO cancel_keys (request_id, experiment_id) VALUES (?, ?)",
                (request_id, experiment_id),
            )
            return None


def _transition(
    record: ExperimentRecord, target: ExperimentStatus, reason: str, at: datetime
) -> ExperimentRecord:
    if target not in _ALLOWED[record.status]:
        raise ValueError(
            f"EXPERIMENT_TRANSITION_REJECTED:{record.status.value}->{target.value}"
        )
    history = tuple(record.history) + (
        {"status": target.value, "reason": reason, "at": at.isoformat()},
    )
    return record.model_copy(update={"status": target, "history": history})


class ExperimentService:
    """Lifecycle orchestrator over registry, queue, kernel and resolvers."""

    def __init__(
        self,
        *,
        run_root: Path | str,
        queue_path: Path | str,
        clock: Callable[[], datetime],
        dataset_resolver: Callable[[ArtifactRef], ResolvedDataset],
        pipeline_resolver: Callable[[ArtifactRef], VerifiedRuntimePlan],
        candidate_factory: Callable[[VerifiedRuntimePlan, str], Any] | None = None,
        policy_versions: set[str] | None = None,
        experiment_registry: Any | None = None,
    ) -> None:
        self._root = Path(run_root)
        self._root.mkdir(parents=True, exist_ok=True)
        self.queue = SqliteJobQueue(queue_path)
        self._experiments = ExperimentStore(self._root / "experiments.sqlite")
        self._clock = clock
        self._dataset_resolver = dataset_resolver
        self._pipeline_resolver = pipeline_resolver
        self._candidate_factory = candidate_factory
        self._policies = set(policy_versions or set())
        self._legacy = experiment_registry
        self.event_source: Callable[[str], list] | None = None

    # -- CRUD ----------------------------------------------------------

    def create(self, manifest: ExperimentManifest) -> ExperimentRecord:
        if len(set(manifest.pairs)) != len(manifest.pairs):
            raise ValueError("EXPERIMENT_DUPLICATE_PAIRS")
        now = self._clock()
        record = ExperimentRecord(
            experiment_id=f"{EXPERIMENT_ID_PREFIX}{uuid.uuid4().hex[:12]}",
            manifest=manifest,
            history=({"status": "DRAFT", "reason": "CREATED", "at": now.isoformat()},),
        )
        self._experiments.insert(record, now)
        return record

    def get(self, experiment_id: str) -> ExperimentRecord:
        return self._experiments.get(experiment_id)

    def list_experiments(
        self, status: ExperimentStatus | str | None = None
    ) -> list[ExperimentRecord]:
        if isinstance(status, str):
            status = ExperimentStatus(status)
        return self._experiments.list(status)

    def edit(self, experiment_id: str, **changes: Any) -> ExperimentRecord:
        record = self._experiments.get(experiment_id)
        if record.status != ExperimentStatus.DRAFT:
            raise ValueError(
                f"EXPERIMENT_EDIT_REJECTED:{record.status.value}: "
                "completed-or-active experiments are immutable; clone instead"
            )
        unknown = set(changes) - set(ExperimentManifest.model_fields)
        if unknown:
            raise ValueError(f"EXPERIMENT_EDIT_UNKNOWN_FIELDS:{sorted(unknown)}")
        manifest = record.manifest.model_copy(update=changes)
        updated = record.model_copy(update={"manifest": manifest})
        if not self._experiments.put(
            updated, self._clock(), expected_status=ExperimentStatus.DRAFT
        ):
            current = self._experiments.get(experiment_id)
            raise ValueError(
                f"EXPERIMENT_EDIT_REJECTED:{current.status.value}: "
                "completed-or-active experiments are immutable; clone instead"
            )
        return updated

    def clone(self, experiment_id: str, changes: dict[str, Any]) -> ExperimentRecord:
        record = self._experiments.get(experiment_id)
        unknown = set(changes) - set(ExperimentManifest.model_fields)
        if unknown:
            raise ValueError(f"EXPERIMENT_CLONE_UNKNOWN_FIELDS:{sorted(unknown)}")
        now = self._clock()
        cloned = ExperimentRecord(
            experiment_id=f"{EXPERIMENT_ID_PREFIX}{uuid.uuid4().hex[:12]}",
            parent_id=record.experiment_id,
            manifest=record.manifest.model_copy(update=changes),
            history=(
                {
                    "status": "DRAFT",
                    "reason": f"CLONED_FROM:{record.experiment_id}",
                    "at": now.isoformat(),
                },
            ),
        )
        self._experiments.insert(cloned, now)
        return cloned

    # -- validate ------------------------------------------------------

    def validate(self, experiment_id: str) -> ValidationReport:
        record = self._experiments.get(experiment_id)
        reasons: list[str] = []
        plan_digest: str | None = None
        manifest = record.manifest
        try:
            self._dataset_resolver(manifest.dataset_ref)
        except Exception as exc:
            reasons.append(f"DATASET_UNRESOLVED:{type(exc).__name__}")
        try:
            plan = self._pipeline_resolver(manifest.pipeline_ref)
            if manifest_digest(plan.plan) != plan.plan_digest:
                reasons.append("PLAN_DIGEST_MISMATCH")
            else:
                plan_digest = plan.plan_digest
        except Exception as exc:
            reasons.append(f"PIPELINE_UNRESOLVED:{type(exc).__name__}")
        if manifest.policy_version not in self._policies:
            reasons.append(f"POLICY_UNKNOWN:{manifest.policy_version}")
        for pair in manifest.pairs:
            try:
                from indodax_lab.contracts.common import CanonicalPair

                CanonicalPair(pair=pair)
            except ValueError:
                reasons.append(f"PAIR_INVALID:{pair}")
        try:
            _equal_share(manifest.capital, len(manifest.pairs))
        except ValueError as exc:
            reasons.append(str(exc))
        report = ValidationReport(
            valid=not reasons, reasons=tuple(reasons), runtime_plan_digest=plan_digest
        )
        if report.valid:
            updated = _transition(record, ExperimentStatus.VALIDATED, "VALIDATED", self._clock())
            updated = updated.model_copy(
                update={"plan_digest": plan_digest, "validation": report}
            )
        else:
            updated = record.model_copy(update={"validation": report})
        self._experiments.put(updated, self._clock())
        return report

    # -- run -----------------------------------------------------------

    def _payload_hash(self, record: ExperimentRecord) -> str:
        return _sha(
            {
                "experiment_id": record.experiment_id,
                "manifest": json.loads(record.manifest.model_dump_json()),
                "plan_digest": record.plan_digest,
            }
        )

    def run_backtest(self, experiment_id: str) -> JobRecord | None:
        record = self._experiments.get(experiment_id)
        job_id = f"rw3_{record.experiment_id}"
        if record.status == ExperimentStatus.SUCCESS:
            return self.queue.get_job(job_id)
        if record.status == ExperimentStatus.CANCELLED:
            raise ValueError(f"RUN_CANCELLED:{experiment_id}: clone to rerun")
        if record.status not in _RUNNABLE:
            raise ValueError(f"RUN_NOT_VALIDATED:{record.status.value}")
        if record.plan_digest is None:
            raise ValueError("RUN_PLAN_DIGEST_MISSING")

        share = _equal_share(record.manifest.capital, len(record.manifest.pairs))

        digest = self._payload_hash(record)
        job_def = JobDefinition(
            job_id=job_id,
            job_type=JOB_TYPE,
            recipe_hash=digest,
            input_ids=[],
            parameters={
                "resource_class": "LOW",
                "experiment_id": record.experiment_id,
                "payload_hash": digest,
            },
            created_at=self._clock(),
        )
        try:
            self.queue.submit_job(job_def)
        except sqlite3.IntegrityError:
            existing = self.queue.get_job(job_id)
            if existing.status == JobStatus.SUCCESS:
                # The queue already published this result (crash between job
                # publication and catalog finalization): finish the catalog
                # from the published bytes instead of re-running anything.
                return self._recover_published(record, existing)
            if existing.status in (JobStatus.FAILED_FINAL, JobStatus.CANCELLED):
                return existing

        # Claim only this experiment's job so a shared queue's other leases
        # are never taken. A live lease held elsewhere yields None.
        claimed = self.queue.claim_job(
            WORKER_ID, as_of=self._clock(), only_job_id=job_id
        )
        if claimed is None:
            return self.queue.get_job(job_id)
        running = self._enter_running(record, job_id)
        if running is None:
            return None
        record = running

        try:
            children, evidence = self._execute_children(record, share, claimed.attempts)
        except Exception as exc:
            return self._fail(record, claimed, f"{type(exc).__name__}:{exc}")

        failed = [c for c in children if c.status != "SUCCESS"]
        try:
            # Fence before touching any result bytes: a cancelled or superseded
            # worker must not publish anything.
            self.queue.heartbeat(
                job_id, WORKER_ID, claimed.generation, as_of=self._clock()
            )
            if failed:
                error = ";".join(f"{c.pair}:{c.error_message}" for c in failed)
                artifact = self._write_artifact(
                    record, children, evidence, "FAILED", error=error
                )
                self.queue.fail_job(
                    job_id, WORKER_ID, claimed.generation,
                    error_message=error, retryable=True, as_of=self._clock(),
                )
                self._store_result(record, children, artifact, "FAILED", error=error)
                return self.queue.get_job(job_id)
            artifact = self._write_artifact(record, children, evidence, "SUCCESS")
            # Queue publication (fenced) precedes the terminal catalog write.
            self.queue.complete_job(
                job_id, WORKER_ID, claimed.generation,
                artifact_path=artifact["path"],
                expected_hash=artifact["sha256"],
                as_of=self._clock(),
            )
            self._store_result(record, children, artifact, "SUCCESS")
            return self.queue.get_job(job_id)
        except LeaseFencingError:
            # Cancelled or superseded: the fence already decided; leave the
            # catalog to whoever holds the newer state.
            return None
        except Exception as exc:
            return self._fail(record, claimed, f"{type(exc).__name__}:{exc}")

    def _enter_running(self, record: ExperimentRecord, job_id: str) -> ExperimentRecord | None:
        """Move to RUNNING via compare-and-set; None if the state changed underneath."""
        current = record
        if current.status in (ExperimentStatus.VALIDATED, ExperimentStatus.FAILED):
            queued = _transition(
                current, ExperimentStatus.QUEUED, "JOB_SUBMITTED", self._clock()
            ).model_copy(update={"job_id": job_id, "error_message": None})
            if not self._experiments.put(queued, self._clock(), expected_status=current.status):
                return None
            current = queued
        if current.status == ExperimentStatus.QUEUED:
            started = _transition(
                current, ExperimentStatus.RUNNING, "WORKER_CLAIMED", self._clock()
            )
            if not self._experiments.put(
                started, self._clock(), expected_status=ExperimentStatus.QUEUED
            ):
                return None
            current = started
        # Already RUNNING: resumed after the previous lease expired.
        return current

    def _recover_published(self, record: ExperimentRecord, job: JobRecord) -> JobRecord:
        """Finish the catalog from a result the queue already published."""
        if record.status == ExperimentStatus.SUCCESS:
            return job
        content = self.queue.read_result_artifact(job.job_id)  # verifies checksum
        doc = json.loads(content)
        if (
            doc.get("experiment_id") != record.experiment_id
            or doc.get("runtime_plan_digest") != record.plan_digest
            or doc.get("status") != "SUCCESS"
        ):
            raise ValueError("RESULT_IDENTITY_MISMATCH")
        children = tuple(
            ChildResult(
                child_id=c["child_id"],
                pair=c["pair"],
                status=c["status"],
                capital=Decimal(c["capital"]),
                order_ids=tuple(sorted(c["evidence"]["orders"])),
                error_message=c["error"],
            )
            for c in doc["children"]
        )
        result = ResultArtifact(
            experiment_id=record.experiment_id,
            status="SUCCESS",
            result_digest=str(doc["result_digest"]),
            runtime_plan_digest=str(doc["runtime_plan_digest"]),
            artifact_path=str(job.result_artifact_path or ""),
            artifact_sha256=str(job.result_artifact_hash or ""),
            children=children,
        )
        now = self._clock()
        history = tuple(record.history) + (
            {
                "status": "SUCCESS",
                "reason": "RECOVERED_FROM_PUBLISHED_JOB_ARTIFACT",
                "at": now.isoformat(),
            },
        )
        updated = record.model_copy(
            update={
                "status": ExperimentStatus.SUCCESS,
                "result": result,
                "children": children,
                "history": history,
                "job_id": job.job_id,
                "error_message": None,
            }
        )
        self._experiments.put(updated, now, expected_status=record.status)
        return job

    def _fail(self, record: ExperimentRecord, claimed: JobRecord, reason: str) -> None:
        try:
            self.queue.heartbeat(
                claimed.job_id, WORKER_ID, claimed.generation, as_of=self._clock()
            )
            artifact = self._write_artifact(record, [], {}, "FAILED", error=reason)
            self.queue.fail_job(
                claimed.job_id, WORKER_ID, claimed.generation,
                error_message=reason, retryable=True, as_of=self._clock(),
            )
            self._store_result(record, [], artifact, "FAILED", error=reason)
        except LeaseFencingError:
            return None  # stale worker: never finalize
        except Exception:
            current = self._experiments.get(record.experiment_id)
            if current.status == ExperimentStatus.RUNNING:
                failed = _transition(current, ExperimentStatus.FAILED, reason, self._clock())
                failed = failed.model_copy(update={"error_message": reason})
                self._experiments.put(
                    failed, self._clock(), expected_status=ExperimentStatus.RUNNING
                )
        return None

    # -- trial execution -----------------------------------------------

    def _candidate_for(self, plan: VerifiedRuntimePlan, pair: str) -> Any:
        if self._candidate_factory is not None:
            return self._candidate_factory(plan, pair)
        return _PlanBoundCandidate(CandidateRuntime.load_plan(plan), plan.plan_digest)

    def _execute_children(
        self, record: ExperimentRecord, share: Decimal, attempt: int
    ) -> tuple[list[ChildResult], dict[str, dict[str, Any]]]:
        from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter

        manifest = record.manifest
        plan = self._pipeline_resolver(manifest.pipeline_ref)
        children: list[ChildResult] = []
        evidence_by_child: dict[str, dict[str, Any]] = {}
        # Each attempt replays from a fresh child store, so a resumed run can
        # never double-apply fills from an interrupted attempt; earlier
        # attempts stay on disk as retained evidence.
        attempt_dir = self._root / record.experiment_id / f"attempt_{attempt}"
        for pair in manifest.pairs:
            child_id = f"{record.experiment_id}:{pair}"
            try:
                events = self.event_source(pair) if self.event_source else None
                if not events:
                    raise ValueError("TRIAL_NO_EVENTS")
                attempt_dir.mkdir(parents=True, exist_ok=True)
                store = ExecutionStateStore(
                    attempt_dir / f"child_{pair}.db",
                    namespace=child_id,
                    initial_cash=share,
                )
                candidate = self._candidate_for(plan, pair)
                kernel = RuntimeKernel(
                    candidate_runtime=candidate,
                    store=store,
                    venue=SimulatorVenueAdapter(clock=self._clock),
                    venue_name="simulator",
                    risk_stage=lambda intents, _state: tuple(intents),
                )
                for event in events:
                    kernel.process(event)
                snapshot = store.restore()
                order_ids = tuple(sorted(snapshot.orders))
                child = ChildResult(
                    child_id=child_id, pair=pair, status="SUCCESS",
                    capital=share, order_ids=order_ids,
                )
                evidence_by_child[child_id] = self._persist_child_evidence(
                    attempt_dir, child, snapshot, kernel._venue
                )
            except Exception as exc:
                child = ChildResult(
                    child_id=child_id, pair=pair, status="FAILED",
                    capital=share,
                    error_message=f"{type(exc).__name__}:{exc}",
                )
            children.append(child)
        return children, evidence_by_child

    def _persist_child_evidence(
        self, attempt_dir: Path, child: ChildResult, snapshot: Any, venue: Any
    ) -> dict[str, Any]:
        receipts: list[dict[str, Any]] = []
        held = getattr(venue, "_receipts", None)
        if isinstance(held, dict):
            import dataclasses

            for receipt in held.values():
                if dataclasses.is_dataclass(receipt):
                    receipts.append(dataclasses.asdict(receipt))
                elif hasattr(receipt, "model_dump"):
                    receipts.append(receipt.model_dump(mode="python"))
                else:
                    receipts.append(dict(receipt))
        orders = json.loads(json.dumps(dict(snapshot.orders), sort_keys=True, default=str))
        evidence = {
            "orders": orders,
            "receipts": receipts,
            "cash": str(snapshot.cash),
            "positions": json.loads(json.dumps(dict(snapshot.positions), sort_keys=True, default=str)),
        }
        path = attempt_dir / f"{child.child_id.replace(':', '_')}.evidence.json"
        path.write_bytes(_canon(evidence))
        # Round-trip through canonical JSON so the digest input is exactly
        # what a later reader of the artifact sees.
        return json.loads(_canon(evidence))

    # -- artifacts / results --------------------------------------------

    def _write_artifact(
        self, record: ExperimentRecord, children: list[ChildResult],
        evidence_by_child: dict[str, dict[str, Any]],
        status: str, error: str | None = None,
    ) -> dict[str, Any]:
        digest_input: dict[str, Any] = {
            "plan_digest": record.plan_digest,
            "seed": record.manifest.seed,
            "pairs": list(record.manifest.pairs),
            "capital": str(record.manifest.capital),
            "children": [],
        }
        doc_children: list[dict[str, Any]] = []
        for child in children:
            evidence = evidence_by_child.get(child.child_id) if child.status == "SUCCESS" else None
            if evidence is None:
                evidence = {"orders": {}, "receipts": [], "cash": None, "positions": {}}
            digest_input["children"].append(
                {
                    "pair": child.pair,
                    "status": child.status,
                    "capital": str(child.capital),
                    "evidence": evidence,
                    "error": child.error_message,
                }
            )
            doc_children.append(
                {
                    "child_id": child.child_id,
                    "pair": child.pair,
                    "status": child.status,
                    "capital": str(child.capital),
                    "evidence": evidence,
                    "error": child.error_message,
                }
            )
        result_digest = _sha(digest_input)
        doc = {
            "experiment_id": record.experiment_id,
            "status": status,
            "result_digest": result_digest,
            "runtime_plan_digest": record.plan_digest,
            "children": doc_children,
            "error": error,
        }
        content = _canon(doc)
        sha = hashlib.sha256(content).hexdigest()
        # Content-addressed and no-clobber: identical bytes converge on one
        # object, and a failed attempt's artifact is never overwritten by a
        # later attempt with different bytes.
        path = self._root / record.experiment_id / "results" / f"{sha}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ValueError(f"ARTIFACT_STORE_CORRUPT:{path}")
        else:
            tmp = path.with_name(f".{sha}.{uuid.uuid4().hex}.tmp")
            try:
                tmp.write_bytes(content)
                os.replace(tmp, path)
            finally:
                tmp.unlink(missing_ok=True)
        return {"path": str(path), "sha256": sha, "doc": doc}

    def _store_result(
        self, record: ExperimentRecord, children: list[ChildResult],
        artifact: dict[str, Any], status: str, error: str | None = None,
    ) -> ExperimentRecord | None:
        """Finalize the catalog record; compare-and-set on RUNNING.

        Returns None (and writes nothing) when the experiment is no longer
        RUNNING, e.g. it was cancelled while this worker was finishing.
        """
        doc = artifact["doc"]
        result = ResultArtifact(
            experiment_id=record.experiment_id,
            status=status,
            result_digest=str(doc["result_digest"]),
            runtime_plan_digest=str(doc["runtime_plan_digest"] or ""),
            artifact_path=artifact["path"],
            artifact_sha256=artifact["sha256"],
            children=tuple(children),
        )
        updated = _transition(record, ExperimentStatus[status], f"ARTIFACT_{status}", self._clock())
        updated = updated.model_copy(
            update={
                "result": result,
                "children": tuple(children),
                "error_message": error,
            }
        )
        if not self._experiments.put(
            updated, self._clock(), expected_status=ExperimentStatus.RUNNING
        ):
            return None
        return updated

    def result(self, experiment_id: str) -> ResultArtifact:
        record = self._experiments.get(experiment_id)
        if record.status not in (ExperimentStatus.SUCCESS, ExperimentStatus.FAILED):
            raise ValueError(f"NOT_TERMINAL:{record.status.value}")
        if record.result is None:
            raise ValueError("RESULT_UNAVAILABLE:no_artifact_recorded")
        content = Path(record.result.artifact_path).read_bytes()
        if hashlib.sha256(content).hexdigest() != record.result.artifact_sha256:
            raise ValueError("RESULT_ARTIFACT_CHECKSUM_MISMATCH")
        return record.result

    # -- cancel ----------------------------------------------------------

    def cancel(self, experiment_id: str, request_id: str) -> ExperimentRecord:
        if not request_id or not str(request_id).strip():
            raise ValueError("CANCEL_REQUEST_ID_REQUIRED")
        holder = self._experiments.claim_cancel_key(str(request_id), experiment_id)
        if holder is not None and holder != experiment_id:
            raise ValueError(f"REQUEST_ID_CONFLICT:{request_id}")
        record = self._experiments.get(experiment_id)
        if holder is not None:
            return record
        if record.status in _TERMINAL:
            raise ValueError(f"TERMINAL_CANCEL_REJECTED:{record.status.value}")
        if record.job_id is not None:
            try:
                job = self.queue.get_job(record.job_id)
                if job.status == JobStatus.SUCCESS:
                    # Result already published: cancel cannot undo it.
                    raise ValueError("TERMINAL_CANCEL_REJECTED:JOB_SUCCESS_PUBLISHED")
                if job.status not in (JobStatus.FAILED_FINAL, JobStatus.CANCELLED):
                    self.queue.cancel_job(
                        record.job_id,
                        reason=f"EXPERIMENT_CANCELLED:{request_id}",
                        as_of=self._clock(),
                    )
            except KeyError:
                pass
            except ValueError as exc:
                if "TERMINAL_CANCEL_REJECTED" in str(exc) or "TERMINAL_JOB_CANNOT_CANCEL" in str(exc):
                    raise ValueError(
                        f"TERMINAL_CANCEL_REJECTED:{exc}"
                    ) from exc
                # Non-cancellable retry state (e.g. FAILED_RETRYABLE): the
                # experiment record below is the authoritative cancel.
        updated = _transition(
            record, ExperimentStatus.CANCELLED, f"CANCELLED:{request_id}", self._clock()
        )
        if not self._experiments.put(
            updated, self._clock(), expected_status=record.status
        ):
            current = self._experiments.get(experiment_id)
            if current.status == ExperimentStatus.CANCELLED:
                return current
            raise ValueError(f"TERMINAL_CANCEL_REJECTED:{current.status.value}")
        return updated

    # -- compare / trade report / legacy ----------------------------------

    def compare(self, experiment_ids: list[str]) -> ComparisonReport:
        results = [self.result(experiment_id) for experiment_id in experiment_ids]
        digests = tuple(r.result_digest for r in results)
        records = [self._experiments.get(experiment_id) for experiment_id in experiment_ids]
        assumptions: list[dict[str, Any]] = []
        for label, values in (
            ("same_pairs", [list(r.manifest.pairs) for r in records]),
            ("same_capital", [str(r.manifest.capital) for r in records]),
            ("same_plan", [r.plan_digest for r in records]),
            ("same_seed", [r.manifest.seed for r in records]),
        ):
            first = values[0] if values else None
            assumptions.append({"assumption": label, "matched": all(v == first for v in values)})
        reasons: list[str] = []
        if len(set(digests)) != 1:
            reasons.append("RESULT_DIGEST_MISMATCH")
            for assumption in assumptions:
                if not assumption["matched"]:
                    reasons.append(f"ASSUMPTION_DIVERGED:{assumption['assumption']}")
        return ComparisonReport(
            experiment_ids=tuple(experiment_ids),
            digests=digests,
            equal=len(set(digests)) == 1,
            assumptions=tuple(assumptions),
            reasons=tuple(reasons),
        )

    def trade_report(self, experiment_id: str) -> "TradeReport":
        from indodax_lab.evaluation.experiment_service_reports import build_trade_report

        result = self.result(experiment_id)
        doc = json.loads(Path(result.artifact_path).read_bytes())
        return build_trade_report(result.experiment_id, doc)

    # -- legacy EVAL-01 passthrough (Step 1: historical terminal evidence) --

    def legacy_get_run(self, run_id: str) -> Any:
        if self._legacy is None:
            raise ValueError("LEGACY_REGISTRY_UNCONFIGURED")
        return self._legacy.get_run(run_id)

    def legacy_list_runs(self, **filters: Any) -> list:
        if self._legacy is None:
            raise ValueError("LEGACY_REGISTRY_UNCONFIGURED")
        return self._legacy.list_runs(**filters)

    def legacy_trial_count(self, **filters: Any) -> int:
        if self._legacy is None:
            raise ValueError("LEGACY_REGISTRY_UNCONFIGURED")
        return self._legacy.get_trial_count(**filters)
