"""SQLite WAL durable leased queue implementation (JOB-01).

Contract: SQLite WAL local queue with terminal, retryable and blocked lifecycle states.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_artifacts (
                    job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
                    source_path TEXT,
                    artifact_path TEXT NOT NULL,
                    artifact_hash TEXT NOT NULL,
                    staged_at TEXT NOT NULL
                );
                """
            )
            artifact_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(job_artifacts);")
            }
            if "source_path" not in artifact_columns:
                conn.execute("ALTER TABLE job_artifacts ADD COLUMN source_path TEXT;")
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

    def claim_job(
        self,
        worker_id: str,
        as_of: datetime | None = None,
        *,
        only_job_id: str | None = None,
    ) -> JobRecord | None:
        """Atomically claim the next eligible job and increment lease generation.

        ``only_job_id`` restricts the claim to one job so a caller that owns a
        specific job (RW3-01) can never take another job's lease from a shared
        queue. ``None`` keeps the original oldest-eligible behavior.
        """
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
                SELECT job_id, generation, attempts, max_attempts, lease_duration_seconds,
                       status, owner_id, lease_expires_at
                FROM jobs
                WHERE attempts < max_attempts
                  AND (
                       status = ?
                    OR status = ?
                    OR status = ?
                    OR (status = ? AND lease_expires_at <= ?)
                  )
                  AND (? IS NULL OR job_id = ?)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (
                    JobStatus.PENDING.value,
                    JobStatus.STALE.value,
                    JobStatus.FAILED_RETRYABLE.value,
                    JobStatus.RUNNING.value,
                    as_of_iso,
                    only_job_id,
                    only_job_id,
                ),
            )
            row = cursor.fetchone()
            if not row:
                conn.execute("COMMIT;")
                return None

            job_id, curr_gen, curr_attempts, max_att, lease_sec = row[:5]
            prior_status, prior_owner, prior_expiry = row[5], row[6], row[7]
            next_gen = curr_gen + 1
            next_attempts = curr_attempts + 1
            expires_at = (as_of + timedelta(seconds=lease_sec)).isoformat()

            # A takeover of a crashed/expired lease (or a job already marked
            # STALE) must leave a durable audit trail, otherwise a worker that
            # died mid-flight is silently indistinguishable from one that never
            # started and duplicate work cannot be detected.
            if prior_status in (JobStatus.RUNNING.value, JobStatus.STALE.value):
                error_message = (
                    f"STALE_LEASE_TAKEOVER: previous owner {prior_owner or 'NONE'} generation "
                    f"{curr_gen} ended in status {prior_status} with lease expiry "
                    f"{prior_expiry or 'NONE'}; reclaimed by {worker_id} generation {next_gen} "
                    f"at {as_of_iso}"
                )
            else:
                error_message = None

            update_cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    owner_id = ?,
                    generation = ?,
                    attempts = ?,
                    lease_expires_at = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE job_id = ? AND generation = ? AND attempts < max_attempts
                """,
                (
                    JobStatus.RUNNING.value,
                    worker_id,
                    next_gen,
                    next_attempts,
                    expires_at,
                    error_message,
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
                    f"STALE_LEASE_FENCED: worker {worker_id} generation {generation} "
                    "does not match active lease"
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
        """Publish SUCCESS for job, verifying lease generation and artifact completeness.

        Ordering is deliberate: the lease fence is evaluated first and is
        authoritative, so a superseded worker is always refused as stale and
        never learns anything about the filesystem. Only a worker that still
        holds the live lease reaches artifact validation, where a missing,
        empty, or corrupt result raises :class:`PartialArtifactError` and leaves
        the job RUNNING (JOB-01-AC2, JOB-01-AC3).
        """
        if as_of is None:
            as_of = datetime.now(UTC)
        as_of = _ensure_utc(as_of, "as_of")
        as_of_iso = as_of.isoformat()

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            held = conn.execute(
                """
                SELECT 1 FROM jobs
                WHERE job_id = ? AND owner_id = ? AND generation = ?
                  AND status = ? AND lease_expires_at > ?
                """,
                (job_id, worker_id, generation, JobStatus.RUNNING.value, as_of_iso),
            ).fetchone()
            if not held:
                conn.execute("ROLLBACK;")
                raise LeaseFencingError(
                    f"STALE_LEASE_FENCED: cannot complete job {job_id} for stale worker "
                    f"{worker_id} gen {generation}"
                )

            # Invariant: a partial or absent artifact cannot transition to SUCCESS.
            if artifact_path is None:
                conn.execute("ROLLBACK;")
                raise PartialArtifactError(
                    f"ARTIFACT_PATH_REQUIRED: job {job_id} cannot be published as SUCCESS "
                    "without a "
                    "result artifact reference"
                )
            p = Path(artifact_path)
            try:
                if not p.exists() or not p.is_file():
                    raise PartialArtifactError(f"ARTIFACT_FILE_NOT_FOUND:{artifact_path}")
                content = p.read_bytes()
                if len(content) == 0:
                    raise PartialArtifactError(f"ARTIFACT_FILE_EMPTY:{artifact_path}")
                if (
                    expected_hash is None
                    or len(expected_hash) != 64
                    or any(char not in "0123456789abcdefABCDEF" for char in expected_hash)
                ):
                    raise PartialArtifactError(
                        "ARTIFACT_EXPECTED_HASH_REQUIRED: a complete SHA-256 digest is required"
                    )
                actual_hash = hashlib.sha256(content).hexdigest()
                if actual_hash != expected_hash.lower():
                    raise PartialArtifactError(
                        f"ARTIFACT_CHECKSUM_MISMATCH: expected {expected_hash}, got {actual_hash}"
                    )
            except (PartialArtifactError, OSError) as exc:
                conn.execute("ROLLBACK;")
                if isinstance(exc, PartialArtifactError):
                    raise
                raise PartialArtifactError(f"ARTIFACT_UNREADABLE:{artifact_path}:{exc}") from exc

            staged = conn.execute(
                "SELECT artifact_path, artifact_hash FROM job_artifacts WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if staged and staged[1] != actual_hash:
                conn.execute("ROLLBACK;")
                raise PartialArtifactError(
                    f"ARTIFACT_RETRY_OUTPUT_MISMATCH:{job_id}:"
                    f"expected {staged[1]}, got {actual_hash}"
                )
            published_path = Path(staged[0]) if staged else self._artifact_path(actual_hash)
            conn.execute(
                """
                INSERT OR IGNORE INTO job_artifacts (
                    job_id, source_path, artifact_path, artifact_hash, staged_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, str(p), str(published_path), actual_hash, as_of_iso),
            )
            conn.execute("COMMIT;")
            try:
                self._publish_artifact(actual_hash, content)
            except OSError as exc:
                raise PartialArtifactError(f"ARTIFACT_PUBLISH_FAILED:{exc}") from exc
            return self.recover_completed_artifact(
                job_id, worker_id, generation, as_of=as_of
            )
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def recover_completed_artifact(
        self,
        job_id: str,
        worker_id: str,
        generation: int,
        as_of: datetime | None = None,
    ) -> JobRecord:
        """Finalize a verified staged result after a worker/DB crash without rerunning work."""
        if as_of is None:
            as_of = datetime.now(UTC)
        as_of = _ensure_utc(as_of, "as_of")
        as_of_iso = as_of.isoformat()

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            held = conn.execute(
                """
                SELECT 1 FROM jobs
                WHERE job_id = ? AND owner_id = ? AND generation = ?
                  AND status = ? AND lease_expires_at > ?
                """,
                (job_id, worker_id, generation, JobStatus.RUNNING.value, as_of_iso),
            ).fetchone()
            if not held:
                conn.execute("ROLLBACK;")
                raise LeaseFencingError(
                    f"STALE_LEASE_FENCED: cannot recover job {job_id} for worker "
                    f"{worker_id} gen {generation}"
                )

            staged = conn.execute(
                """
                SELECT source_path, artifact_path, artifact_hash
                FROM job_artifacts WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if not staged:
                conn.execute("ROLLBACK;")
                raise PartialArtifactError(f"ARTIFACT_RECOVERY_NOT_AVAILABLE:{job_id}")

            source_path, artifact_path, artifact_hash = staged
            try:
                try:
                    content = Path(artifact_path).read_bytes()
                except OSError:
                    if source_path is None:
                        raise
                    content = Path(source_path).read_bytes()
            except OSError as exc:
                conn.execute("ROLLBACK;")
                raise PartialArtifactError(
                    f"ARTIFACT_STAGED_UNREADABLE:{job_id}"
                ) from exc
            if hashlib.sha256(content).hexdigest() != artifact_hash:
                conn.execute("ROLLBACK;")
                raise PartialArtifactError(f"ARTIFACT_STAGED_CHECKSUM_MISMATCH:{job_id}")
            try:
                self._publish_artifact(artifact_hash, content)
            except OSError as exc:
                conn.execute("ROLLBACK;")
                raise PartialArtifactError(f"ARTIFACT_PUBLISH_FAILED:{exc}") from exc

            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, result_artifact_path = ?, result_artifact_hash = ?,
                    error_message = NULL, updated_at = ?
                WHERE job_id = ? AND owner_id = ? AND generation = ? AND status = ?
                  AND lease_expires_at > ?
                """,
                (
                    JobStatus.SUCCESS.value,
                    artifact_path,
                    artifact_hash,
                    as_of_iso,
                    job_id,
                    worker_id,
                    generation,
                    JobStatus.RUNNING.value,
                    as_of_iso,
                ),
            )
            if cursor.rowcount != 1:
                conn.execute("ROLLBACK;")
                raise LeaseFencingError(f"STALE_LEASE_FENCED: cannot recover job {job_id}")
            conn.execute("COMMIT;")
            return self.get_job(job_id)
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    @property
    def _artifact_root(self) -> Path:
        return self.db_path.parent / f"{self.db_path.name}.artifacts"

    def _artifact_path(self, digest: str) -> Path:
        return self._artifact_root / digest[:2] / digest

    def _publish_artifact(self, digest: str, content: bytes) -> Path:
        """Atomically store/reuse a verified SHA-256-addressed immutable result."""
        destination = self._artifact_path(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            try:
                existing = destination.read_bytes()
            except OSError as exc:
                raise OSError(f"ARTIFACT_STORE_UNREADABLE:{exc}") from exc
            if hashlib.sha256(existing).hexdigest() != digest:
                raise OSError(
                    "ARTIFACT_STORE_CORRUPT: content-addressed object failed verification"
                )
            return destination

        # Each publisher owns its temp file; atomic replace safely converges
        # concurrent identical digests on the same object path.
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{digest}.", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as artifact:
                artifact.write(content)
                artifact.flush()
                os.fsync(artifact.fileno())
            os.replace(temporary, destination)
        except OSError:
            temporary.unlink(missing_ok=True)
            if destination.exists():
                existing = destination.read_bytes()
                if hashlib.sha256(existing).hexdigest() == digest:
                    return destination
            raise
        return destination

    def read_result_artifact(self, job_id: str) -> bytes:
        """Read a successful output only after verifying its persisted digest."""
        job = self.get_job(job_id)
        if (
            job.status != JobStatus.SUCCESS
            or not job.result_artifact_path
            or not job.result_artifact_hash
        ):
            raise PartialArtifactError(f"RESULT_ARTIFACT_UNAVAILABLE:{job_id}")
        try:
            content = Path(job.result_artifact_path).read_bytes()
        except OSError as exc:
            raise PartialArtifactError(f"ARTIFACT_PUBLISHED_UNREADABLE:{job_id}") from exc
        if hashlib.sha256(content).hexdigest() != job.result_artifact_hash:
            raise PartialArtifactError(f"ARTIFACT_PUBLISHED_CHECKSUM_MISMATCH:{job_id}")
        return content

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

    def cancel_job(
        self,
        job_id: str,
        *,
        reason: str,
        as_of: datetime | None = None,
    ) -> JobRecord:
        """Cancel a queued or running job so no worker can publish SUCCESS.

        PENDING jobs transition directly. RUNNING jobs transition and have
        their lease generation bumped, which fences the holding worker: its
        later complete_job fails the live-lease check (status must be
        RUNNING with matching owner and generation). Terminal jobs reject.
        """
        if not reason or not str(reason).strip():
            raise ValueError("CANCEL_REASON_REQUIRED")
        if as_of is None:
            as_of = datetime.now(UTC)
        as_of = _ensure_utc(as_of, "as_of")
        as_of_iso = as_of.isoformat()

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT status, generation FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK;")
                raise KeyError(f"JOB_NOT_FOUND:{job_id}")
            status = row[0]
            if status in (
                JobStatus.SUCCESS.value,
                JobStatus.FAILED_FINAL.value,
                JobStatus.CANCELLED.value,
            ):
                conn.execute("ROLLBACK;")
                raise ValueError(
                    f"TERMINAL_JOB_CANNOT_CANCEL:{job_id}:{status}"
                )
            if status == JobStatus.RUNNING.value:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, generation = generation + 1,
                        owner_id = NULL, lease_expires_at = NULL,
                        error_message = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (
                        JobStatus.CANCELLED.value,
                        reason,
                        as_of_iso,
                        job_id,
                    ),
                )
            elif status == JobStatus.PENDING.value:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = ?, error_message = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (JobStatus.CANCELLED.value, reason, as_of_iso, job_id),
                )
            else:
                conn.execute("ROLLBACK;")
                raise ValueError(
                    f"JOB_STATE_CANNOT_CANCEL:{job_id}:{status}"
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
                       error_message, created_at, updated_at, parameters_json
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise KeyError(f"JOB_NOT_FOUND:{job_id}")

            # parameters_json is NOT NULL, but a hand-edited or legacy row may hold
            # malformed JSON. Admission control must not crash on that, and an
            # unreadable parameter blob must not be read as an empty declaration.
            try:
                parameters = json.loads(row[14]) if row[14] else {}
            except ValueError as exc:
                raise ValueError(
                    f"JOB_PARAMETERS_CORRUPT: job {job_id} has unreadable parameters_json: {exc}"
                ) from exc
            if not isinstance(parameters, dict):
                raise ValueError(
                    f"JOB_PARAMETERS_CORRUPT: job {job_id} parameters_json is not a JSON object"
                )

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
                parameters=parameters,
            )
