"""Immutable experiment registry and trial lifecycle manager (EVAL-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _ensure_utc(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class ExperimentRunStatus(StrEnum):
    """Lifecycle and execution statuses of an experiment run."""

    SUCCESS = "success"
    FAILED = "failed"
    INVALID_RUN = "invalid_run"


class ExperimentRunRecord(BaseModel):
    """Immutable audit record representing a single experiment run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    parent_run_id: str | None = None
    candidate_id: str
    candidate_version: str
    family: str
    git_sha: str
    is_dirty: bool = False
    environment_hash: str
    dataset_snapshot_id: str
    dataset_hash: str
    config_hash: str
    cost_schedule_hash: str
    execution_hash: str
    status: ExperimentRunStatus
    metrics: dict[str, Any]
    error_message: str | None = None
    created_at: datetime
    promotable: bool = False

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")

    @model_validator(mode="after")
    def validate_promotable_and_clean(self) -> ExperimentRunRecord:
        if self.is_dirty and self.promotable:
            raise ValueError("DIRTY_WORKTREE_CANNOT_BE_PROMOTABLE: Dirty worktree cannot produce a promotable run.")
        return self

    def content_digest(self) -> str:
        """Deterministic content-addressed hash of all semantic fields."""
        payload = {
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "candidate_id": self.candidate_id,
            "candidate_version": self.candidate_version,
            "family": self.family,
            "git_sha": self.git_sha,
            "is_dirty": self.is_dirty,
            "environment_hash": self.environment_hash,
            "dataset_snapshot_id": self.dataset_snapshot_id,
            "dataset_hash": self.dataset_hash,
            "config_hash": self.config_hash,
            "cost_schedule_hash": self.cost_schedule_hash,
            "execution_hash": self.execution_hash,
            "status": self.status.value,
            "metrics": self.metrics,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "promotable": self.promotable,
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ExperimentRegistry:
    """SQLite-backed immutable experiment registry tracking all runs and trial accounting."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_runs (
                    run_id TEXT PRIMARY KEY,
                    parent_run_id TEXT,
                    candidate_id TEXT NOT NULL,
                    candidate_version TEXT NOT NULL,
                    family TEXT NOT NULL,
                    git_sha TEXT NOT NULL,
                    is_dirty INTEGER NOT NULL,
                    environment_hash TEXT NOT NULL,
                    dataset_snapshot_id TEXT NOT NULL,
                    dataset_hash TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    cost_schedule_hash TEXT NOT NULL,
                    execution_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    promotable INTEGER NOT NULL,
                    content_hash TEXT NOT NULL
                )
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_candidate ON experiment_runs(candidate_id)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_family ON experiment_runs(family)")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_parent ON experiment_runs(parent_run_id)")

    def record_run(self, run: ExperimentRunRecord) -> None:
        """Atomically record an immutable experiment run.

        Rejects duplicate run_id if content differs. Idempotent on identical content.
        """
        digest = run.content_digest()
        cursor = self._conn.cursor()
        cursor.execute("SELECT content_hash FROM experiment_runs WHERE run_id = ?", (run.run_id,))
        row = cursor.fetchone()

        if row is not None:
            existing_hash = row["content_hash"]
            if existing_hash != digest:
                raise ValueError(
                    f"DUPLICATE_RUN_KEY_CANNOT_OVERWRITE_DIFFERENT_RESULT: Run '{run.run_id}' already exists with different contents."
                )
            return

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO experiment_runs (
                    run_id, parent_run_id, candidate_id, candidate_version, family,
                    git_sha, is_dirty, environment_hash, dataset_snapshot_id,
                    dataset_hash, config_hash, cost_schedule_hash, execution_hash,
                    status, metrics_json, error_message, created_at, promotable, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.parent_run_id,
                    run.candidate_id,
                    run.candidate_version,
                    run.family,
                    run.git_sha,
                    1 if run.is_dirty else 0,
                    run.environment_hash,
                    run.dataset_snapshot_id,
                    run.dataset_hash,
                    run.config_hash,
                    run.cost_schedule_hash,
                    run.execution_hash,
                    run.status.value,
                    json.dumps(run.metrics, sort_keys=True, default=str),
                    run.error_message,
                    run.created_at.isoformat(),
                    1 if run.promotable else 0,
                    digest,
                ),
            )

    def get_run(self, run_id: str) -> ExperimentRunRecord | None:
        """Fetch an experiment run by run_id."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM experiment_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_ancestry(self, run_id: str) -> list[ExperimentRunRecord]:
        """Return full lineage from the specified run backwards to the root ancestor."""
        chain: list[ExperimentRunRecord] = []
        curr_id: str | None = run_id

        while curr_id is not None:
            record = self.get_run(curr_id)
            if record is None:
                break
            chain.append(record)
            curr_id = record.parent_run_id

        return chain

    def get_trial_count(self, family: str | None = None, candidate_id: str | None = None) -> int:
        """Count total trials (including SUCCESS, FAILED, and INVALID_RUN) for honest accounting."""
        query = "SELECT COUNT(*) as cnt FROM experiment_runs WHERE 1=1"
        params: list[Any] = []
        if family is not None:
            query += " AND family = ?"
            params.append(family)
        if candidate_id is not None:
            query += " AND candidate_id = ?"
            params.append(candidate_id)

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return int(row["cnt"]) if row else 0

    def list_runs(
        self,
        family: str | None = None,
        candidate_id: str | None = None,
        promotable_only: bool = False,
    ) -> list[ExperimentRunRecord]:
        """List experiment runs matching filters."""
        query = "SELECT * FROM experiment_runs WHERE 1=1"
        params: list[Any] = []
        if family is not None:
            query += " AND family = ?"
            params.append(family)
        if candidate_id is not None:
            query += " AND candidate_id = ?"
            params.append(candidate_id)
        if promotable_only:
            query += " AND promotable = 1"

        query += " ORDER BY created_at ASC"
        cursor = self._conn.cursor()
        cursor.execute(query, params)
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def _row_to_record(self, row: sqlite3.Row) -> ExperimentRunRecord:
        return ExperimentRunRecord(
            run_id=row["run_id"],
            parent_run_id=row["parent_run_id"],
            candidate_id=row["candidate_id"],
            candidate_version=row["candidate_version"],
            family=row["family"],
            git_sha=row["git_sha"],
            is_dirty=bool(row["is_dirty"]),
            environment_hash=row["environment_hash"],
            dataset_snapshot_id=row["dataset_snapshot_id"],
            dataset_hash=row["dataset_hash"],
            config_hash=row["config_hash"],
            cost_schedule_hash=row["cost_schedule_hash"],
            execution_hash=row["execution_hash"],
            status=ExperimentRunStatus(row["status"]),
            metrics=json.loads(row["metrics_json"]),
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            promotable=bool(row["promotable"]),
        )
