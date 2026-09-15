"""SQLite WAL durable leased queue implementation (JOB-01).

Contract:
SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Sequence

from indodax_lab.orchestration.jobs import (
    JobDefinition,
    JobRecord,
    JobStatus,
    LeaseFencingError,
    PartialArtifactError,
)


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def _parse_utc_iso(val: str | None) -> datetime | None:
    if val is None:
        return None
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class SqliteJobQueue:
    """Durable local SQLite queue with lease generation fencing and atomic claims."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    recipe_hash TEXT NOT NULL,
                    input_ids TEXT NOT NULL,
                    cadence_window TEXT,
                    parameters_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner_id TEXT,
                    generation INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    lease_duration_seconds INTEGER NOT NULL DEFAULT 60,
                    lease_expires_at TEXT,
                    result_artifact_path TEXT,
                    result_artifact_hash TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")

    def submit_job(self, job_def: JobDefinition) -> JobRecord:
        """Submit a new job to the queue in PENDING status."""
        created_at_iso = _ensure_utc(job_def.created_at, "created_at").isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, job_type, recipe_hash, input_ids, cadence_window,
                    parameters_json, status, owner_id, generation, attempts,
                    max_attempts, lease_duration_seconds, lease_expires_at,
                    result_artifact_path, result_artifact_hash, error_message,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_def.job_id,
                    job_def.job_type,
                    job_def.recipe_hash,
                    json.dumps(job_def.input_ids),
                    job_def.cadence_window,
                    json.dumps(job_def.parameters),
                    JobStatus.PENDING.value,
                    None,
                    0,
                    0,
                    job_def.max_attempts,
                    job_def.lease_duration_seconds,
                    None,
                    None,
                    None,
                    None,
                    created_at_iso,
                    created_at_iso,
                ),
            )
        return self.get_job(job_def.job_id)

    def claim_job(self, worker_id: str, as_of: datetime | None = None) -> JobRecord | None:
        """Atomically claim the next eligible job and increment lease generation."""
        if as_of is None:
            as_of = datetime.now(UTC)
        as_of = _ensure_utc(as_of, "as_of")
        as_of_iso = as_of.isoformat()

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            # Exhausted work is terminal regardless of which claimable state a
            # previous process left behind. State/worker edits cannot reset budget.
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, owner_id = NULL, lease_expires_at = NULL,
                    error_message = ?, updated_at = ?
                WHERE attempts >= max_attempts
                  AND (
                      status IN (?, ?, ?)
                      OR (status = ? AND lease_expires_at <= ?)
                  )
                """,
                (
                    JobStatus.FAILED_FINAL.value,
                    "ATTEMPT_BUDGET_EXHAUSTED",
                    as_of_iso,
                    JobStatus.PENDING.value,
                    JobStatus.STALE.value,
                    JobStatus.FAILED_RETRYABLE.value,
                    JobStatus.RUNNING.value,
                    as_of_iso,
                ),
            )
            # Eligible candidate: PENDING, STALE, retryable FAILED, or expired RUNNING
            cursor = conn.execute(
                """
                SELECT job_id, generation, attempts, max_attempts, lease_duration_seconds
                FROM jobs
                WHERE attempts < max_attempts
                  AND (
                       status = ?
                    OR status = ?
                    OR status = ?
                    OR (status = ? AND lease_expires_at <= ?)
                  )
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (
                    JobStatus.PENDING.value,
                    JobStatus.STALE.value,
                    JobStatus.FAILED_RETRYABLE.value,
                    JobStatus.RUNNING.value,
                    as_of_iso,
                ),
            )
            row = cursor.fetchone()
            if not row:
                conn.execute("COMMIT;")
                return None

            job_id, curr_gen, curr_attempts, max_att, lease_sec = row
            next_gen = curr_gen + 1
            next_attempts = curr_attempts + 1
            expires_at = (as_of + timedelta(seconds=lease_sec)).isoformat()

            update_cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    owner_id = ?,
                    generation = ?,
                    attempts = ?,
                    lease_expires_at = ?,
                    updated_at = ?
                WHERE job_id = ? AND generation = ? AND attempts < max_attempts
                """,
                (
                    JobStatus.RUNNING.value,
                    worker_id,
                    next_gen,
                    next_attempts,
                    expires_at,
                    as_of_iso,
                    job_id,
                    curr_gen,
                ),
            )
            if update_cur.rowcount == 0:
                # Concurrent update race lost
                conn.execute("COMMIT;")
                return None

            conn.execute("COMMIT;")
            return self.get_job(job_id)
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        generation: int,
        as_of: datetime | None = None,
    ) -> None:
        """Extend lease expiration for active worker holding current generation."""
        if as_of is None:
            as_of = datetime.now(UTC)
        as_of = _ensure_utc(as_of, "as_of")
        as_of_iso = as_of.isoformat()

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """SELECT status, owner_id, generation, lease_duration_seconds, lease_expires_at
                   FROM jobs WHERE job_id = ?""",
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                conn.execute("ROLLBACK;")
                raise KeyError(f"JOB_NOT_FOUND:{job_id}")

            status, owner, gen, lease_sec, lease_expires_at = row
            if (
                status != JobStatus.RUNNING.value
                or owner != worker_id
                or gen != generation
                or lease_expires_at is None
                or lease_expires_at <= as_of_iso
            ):
                conn.execute("ROLLBACK;")
                raise LeaseFencingError(
                    f"STALE_LEASE_FENCED: worker {worker_id} generation {generation} does not match active lease"
                )

            new_expires = (as_of + timedelta(seconds=lease_sec)).isoformat()
            conn.execute(
                """UPDATE jobs SET lease_expires_at = ?, updated_at = ?
                   WHERE job_id = ? AND owner_id = ? AND generation = ?
                     AND status = ? AND lease_expires_at > ?""",
                (
                    new_expires,
                    as_of_iso,
                    job_id,
                    worker_id,
                    generation,
                    JobStatus.RUNNING.value,
                    as_of_iso,
                ),
            )
            conn.execute("COMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def complete_job(
        self,
        job_id: str,
        worker_id: str,
        generation: int,
        artifact_path: Path | str | None = None,
        expected_hash: str | None = None,
        as_of: datetime | None = None,
    ) -> JobRecord:
        """Publish SUCCESS for job, verifying artifact completeness and lease generation."""
        if as_of is None:
            as_of = datetime.now(UTC)
        as_of = _ensure_utc(as_of, "as_of")
        as_of_iso = as_of.isoformat()

        path_str = None
        hash_str = expected_hash

        # Invariant: Partial or corrupted artifact cannot transition to SUCCESS
        if artifact_path is not None:
            p = Path(artifact_path)
            if not p.exists() or not p.is_file():
                raise PartialArtifactError(f"ARTIFACT_FILE_NOT_FOUND:{artifact_path}")
            content = p.read_bytes()
            if len(content) == 0:
                raise PartialArtifactError(f"ARTIFACT_FILE_EMPTY:{artifact_path}")
            actual_hash = hashlib.sha256(content).hexdigest()
            if expected_hash is not None and actual_hash != expected_hash:
                raise PartialArtifactError(
                    f"ARTIFACT_CHECKSUM_MISMATCH: expected {expected_hash}, got {actual_hash}"
                )
            path_str = str(p)
            hash_str = actual_hash

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    result_artifact_path = ?,
                    result_artifact_hash = ?,
                    updated_at = ?
                WHERE job_id = ? AND owner_id = ? AND generation = ? AND status = ?
                  AND lease_expires_at > ?
                """,
                (
                    JobStatus.SUCCESS.value,
                    path_str,
                    hash_str,
                    as_of_iso,
                    job_id,
                    worker_id,
                    generation,
                    JobStatus.RUNNING.value,
                    as_of_iso,
                ),
            )
            if cursor.rowcount == 0:
                conn.execute("ROLLBACK;")
                raise LeaseFencingError(
                    f"STALE_LEASE_FENCED: cannot complete job {job_id} for stale worker {worker_id} gen {generation}"
                )
            conn.execute("COMMIT;")
            return self.get_job(job_id)
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def fail_job(
        self,
        job_id: str,
        worker_id: str,
        generation: int,
        error_message: str,
        retryable: bool = True,
        as_of: datetime | None = None,
    ) -> JobRecord:
        """Mark job as FAILED_RETRYABLE or FAILED_FINAL with generation fencing."""
        if as_of is None:
            as_of = datetime.now(UTC)
        as_of = _ensure_utc(as_of, "as_of")
        as_of_iso = as_of.isoformat()

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cur = conn.execute(
                """SELECT attempts, max_attempts FROM jobs
                   WHERE job_id = ? AND owner_id = ? AND generation = ?
                     AND status = ? AND lease_expires_at > ?""",
                (job_id, worker_id, generation, JobStatus.RUNNING.value, as_of_iso),
            )
            row = cur.fetchone()
            if not row:
                conn.execute("ROLLBACK;")
                raise LeaseFencingError(f"STALE_LEASE_FENCED: job {job_id} fail rejected")

            attempts, max_att = row
            new_status = (
                JobStatus.FAILED_RETRYABLE.value
                if (retryable and attempts < max_att)
                else JobStatus.FAILED_FINAL.value
            )

            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE job_id = ? AND generation = ?
                """,
                (new_status, error_message, as_of_iso, job_id, generation),
            )
            conn.execute("COMMIT;")
            return self.get_job(job_id)
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def get_job(self, job_id: str) -> JobRecord:
        """Fetch JobRecord by job_id."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT job_id, job_type, status, owner_id, generation,
                       attempts, max_attempts, lease_duration_seconds,
                       lease_expires_at, result_artifact_path, result_artifact_hash,
                       error_message, created_at, updated_at
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise KeyError(f"JOB_NOT_FOUND:{job_id}")

            return JobRecord(
                job_id=row[0],
                job_type=row[1],
                status=JobStatus(row[2]),
                owner_id=row[3],
                generation=row[4],
                attempts=row[5],
                max_attempts=row[6],
                lease_duration_seconds=row[7],
                lease_expires_at=_parse_utc_iso(row[8]),
                result_artifact_path=row[9],
                result_artifact_hash=row[10],
                error_message=row[11],
                created_at=_parse_utc_iso(row[12]),
                updated_at=_parse_utc_iso(row[13]),
            )
