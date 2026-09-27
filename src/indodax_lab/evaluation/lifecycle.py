"""Sealed candidate lifecycle, state machine, and exposure audit (EVAL-03).

Contract:
IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.
Config berubah setelah sealed menjadi challenger baru.
Gate dibuka sekali dan dicatat.
Invalid run tidak masuk ranking.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Iterator, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from indodax_lab.evaluation.registry import ExperimentRunRecord, ExperimentRunStatus


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class CandidateStage(StrEnum):
    """Lifecycle stages of a strategy candidate."""

    IDEA = "IDEA"
    IMPLEMENTED = "IMPLEMENTED"
    BACKTESTED = "BACKTESTED"
    VALIDATED = "VALIDATED"
    SEALED_PASS = "SEALED_PASS"
    SHADOW = "SHADOW"
    CHAMPION = "CHAMPION"
    ARCHIVED = "ARCHIVED"


class InvalidTransitionError(ValueError):
    """Raised when an illegal lifecycle state transition is attempted."""


class CandidateFrozenError(RuntimeError):
    """Raised when an attempt is made to mutate a frozen or sealed candidate configuration."""


class GateAlreadyOpenedError(RuntimeError):
    """Raised when an attempt is made to reopen an already evaluated sealed gate."""


class CandidateNotFoundError(KeyError):
    """Raised when candidate ID does not exist in registry."""


class CandidateRecord(BaseModel):
    """Immutable audit record representing a strategy candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    candidate_version: str
    strategy_name: str
    config_hash: str
    current_stage: CandidateStage = CandidateStage.IDEA
    parent_candidate_id: str | None = None
    sealed_gate_opened: bool = False
    created_at: datetime
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "timestamp")


class TransitionRecord(BaseModel):
    """Immutable log entry for a stage transition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transition_id: str
    candidate_id: str
    from_stage: CandidateStage
    to_stage: CandidateStage
    reason: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "timestamp")


class ExposureAuditRecord(BaseModel):
    """Immutable audit log for sealed gate exposure events."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exposure_id: str
    candidate_id: str
    candidate_version: str
    dataset_split_id: str
    authorized_by: str
    exposed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("exposed_at", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "exposed_at")


class LeaderboardEntry(BaseModel):
    """Ranked candidate entry on the experiment leaderboard."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rank: int
    candidate_id: str
    candidate_version: str
    metric_value: float
    sort_metric: str
    run_id: str


class LeaderboardMetricExclusion(BaseModel):
    """Append-only reason record for an eligible run omitted from ranking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exclusion_id: str
    run_id: str
    run_digest: str
    exposure_id: str
    candidate_id: str
    candidate_version: str
    dataset_split_id: str
    metric_name: str
    reason_code: str
    recorded_at: datetime

    @field_validator("recorded_at", mode="after")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "recorded_at")


_ALLOWED_TRANSITIONS: dict[CandidateStage, set[CandidateStage]] = {
    CandidateStage.IDEA: {CandidateStage.IMPLEMENTED, CandidateStage.ARCHIVED},
    CandidateStage.IMPLEMENTED: {CandidateStage.BACKTESTED, CandidateStage.ARCHIVED},
    CandidateStage.BACKTESTED: {CandidateStage.VALIDATED, CandidateStage.ARCHIVED},
    CandidateStage.VALIDATED: {CandidateStage.SEALED_PASS, CandidateStage.ARCHIVED},
    CandidateStage.SEALED_PASS: {CandidateStage.SHADOW, CandidateStage.ARCHIVED},
    CandidateStage.SHADOW: {CandidateStage.CHAMPION, CandidateStage.ARCHIVED},
    CandidateStage.CHAMPION: {CandidateStage.ARCHIVED},
    CandidateStage.ARCHIVED: set(),
}

# EVAL-03-F2: the sealed evaluation gate may only be opened from the stage that legally
# precedes SEALED_PASS. Any other stage is refused fail-closed.
_GATE_UNSEAL_PREDECESSOR: CandidateStage = CandidateStage.VALIDATED


class CandidateLifecycleManager:
    """Persistent lifecycle state machine with SQLite audit trails."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    @contextmanager
    def _atomic(self) -> Iterator[sqlite3.Connection]:
        """Run a multi-statement state change as one all-or-nothing SQLite transaction.

        EVAL-03-F1: ``isolation_level=None`` puts the connection in autocommit mode, so a
        failure between the state write and its audit record used to leave the lifecycle
        inconsistent with no rollback. ``BEGIN IMMEDIATE`` + an explicit rollback on any
        exception makes the state change and its audit record commit together.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
        except BaseException:
            conn.rollback()
            conn.close()
            raise
        else:
            conn.commit()
            conn.close()

    def _fetch_candidate(self, conn: sqlite3.Connection, candidate_id: str) -> CandidateRecord:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT candidate_id, candidate_version, strategy_name, config_hash,
                   current_stage, parent_candidate_id, sealed_gate_opened,
                   created_at, updated_at
            FROM candidates WHERE candidate_id = ?
            """,
            (candidate_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise CandidateNotFoundError(f"CANDIDATE_NOT_FOUND:{candidate_id}")

        return CandidateRecord(
            candidate_id=row[0],
            candidate_version=row[1],
            strategy_name=row[2],
            config_hash=row[3],
            current_stage=CandidateStage(row[4]),
            parent_candidate_id=row[5],
            sealed_gate_opened=bool(row[6]),
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
        )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    candidate_version TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    parent_candidate_id TEXT,
                    sealed_gate_opened INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transitions (
                    transition_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    from_stage TEXT NOT NULL,
                    to_stage TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exposure_audits (
                    exposure_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    candidate_version TEXT NOT NULL,
                    dataset_split_id TEXT NOT NULL,
                    authorized_by TEXT NOT NULL,
                    exposed_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leaderboard_metric_exclusions (
                    exclusion_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    run_digest TEXT NOT NULL,
                    exposure_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    candidate_version TEXT NOT NULL,
                    dataset_split_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                """
            )

    def register_candidate(self, candidate: CandidateRecord) -> CandidateRecord:
        """Register a new candidate in the lifecycle registry."""
        if candidate.current_stage != CandidateStage.IDEA or candidate.sealed_gate_opened:
            raise ValueError("CANDIDATE_MUST_START_IDEA_GATE_CLOSED")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO candidates (
                    candidate_id, candidate_version, strategy_name, config_hash,
                    current_stage, parent_candidate_id, sealed_gate_opened,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    candidate.candidate_version,
                    candidate.strategy_name,
                    candidate.config_hash,
                    candidate.current_stage.value,
                    candidate.parent_candidate_id,
                    1 if candidate.sealed_gate_opened else 0,
                    candidate.created_at.isoformat(),
                    candidate.updated_at.isoformat(),
                ),
            )
        return candidate

    def get_candidate(self, candidate_id: str) -> CandidateRecord:
        """Fetch candidate by ID."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT candidate_id, candidate_version, strategy_name, config_hash,
                       current_stage, parent_candidate_id, sealed_gate_opened,
                       created_at, updated_at
                FROM candidates WHERE candidate_id = ?
                """,
                (candidate_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise CandidateNotFoundError(f"CANDIDATE_NOT_FOUND:{candidate_id}")

            return CandidateRecord(
                candidate_id=row[0],
                candidate_version=row[1],
                strategy_name=row[2],
                config_hash=row[3],
                current_stage=CandidateStage(row[4]),
                parent_candidate_id=row[5],
                sealed_gate_opened=bool(row[6]),
                created_at=datetime.fromisoformat(row[7]),
                updated_at=datetime.fromisoformat(row[8]),
            )

    def transition_stage(
        self,
        candidate_id: str,
        to_stage: CandidateStage,
        reason: str | None = None,
        as_of: datetime | None = None,
    ) -> CandidateRecord:
        """Advance candidate along the immutable lifecycle pipeline.

        EVAL-03-F1/F3: the current stage is read, validated and written inside a single
        ``BEGIN IMMEDIATE`` transaction together with its audit record, so a concurrent
        transition cannot both observe the same predecessor stage and a failed audit
        insert cannot leave an advanced stage behind.
        """
        ts = _ensure_utc(as_of or datetime.now(UTC), "as_of")
        transition_id = f"tr_{uuid.uuid4().hex[:12]}"

        with self._atomic() as conn:
            candidate = self._fetch_candidate(conn, candidate_id)
            from_stage = candidate.current_stage

            allowed = _ALLOWED_TRANSITIONS.get(from_stage, set())
            if to_stage not in allowed:
                raise InvalidTransitionError(f"INVALID_STAGE_TRANSITION:{from_stage} -> {to_stage}")

            if to_stage == CandidateStage.SEALED_PASS and not candidate.sealed_gate_opened:
                raise InvalidTransitionError("CANNOT_TRANSITION_TO_SEALED_PASS_WITHOUT_UNSEAL_GATE")

            cur = conn.execute(
                """
                UPDATE candidates
                SET current_stage = ?, updated_at = ?
                WHERE candidate_id = ? AND current_stage = ?
                """,
                (to_stage.value, ts.isoformat(), candidate_id, from_stage.value),
            )
            if cur.rowcount != 1:
                raise InvalidTransitionError(
                    f"CONCURRENT_STAGE_CHANGE:{candidate_id} is no longer at {from_stage}"
                )
            conn.execute(
                """
                INSERT INTO transitions (
                    transition_id, candidate_id, from_stage, to_stage, reason, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    transition_id,
                    candidate_id,
                    from_stage.value,
                    to_stage.value,
                    reason,
                    ts.isoformat(),
                ),
            )

        return self.get_candidate(candidate_id)

    def unseal_gate(
        self,
        candidate_id: str,
        dataset_split_id: str,
        authorized_by: str,
        as_of: datetime | None = None,
    ) -> ExposureAuditRecord:
        """Authorize single-use unsealing of the sealed evaluation gate (EVAL-03-AC2).

        EVAL-03-F2: reachable only from ``VALIDATED``, the legal predecessor of
        ``SEALED_PASS``; every other stage is refused fail-closed.
        EVAL-03-F1: the flag flip and the exposure audit record commit together, so a
        failed audit insert leaves the gate closed and still usable.
        """
        if not str(dataset_split_id).strip():
            raise ValueError(
                "DATASET_SPLIT_ID_REQUIRED: unseal requires a declared dataset split id"
            )
        if not str(authorized_by).strip():
            raise ValueError(
                "UNSEAL_AUTHORIZED_BY_REQUIRED: unseal requires a named authorizer"
            )

        ts = _ensure_utc(as_of or datetime.now(UTC), "as_of")
        exposure_id = f"exp_{uuid.uuid4().hex[:12]}"

        with self._atomic() as conn:
            candidate = self._fetch_candidate(conn, candidate_id)
            if candidate.current_stage != _GATE_UNSEAL_PREDECESSOR:
                raise InvalidTransitionError(
                    f"UNSEAL_REQUIRES_VALIDATED_STAGE: candidate {candidate_id} is at "
                    f"{candidate.current_stage}; the sealed gate may only be opened from "
                    f"{_GATE_UNSEAL_PREDECESSOR}"
                )
            if candidate.sealed_gate_opened:
                raise GateAlreadyOpenedError(
                    f"GATE_ALREADY_OPENED: candidate {candidate_id} (v{candidate.candidate_version}) has already opened the sealed gate"
                )

            # Conditional update: a second opener sees no changed row and is rejected.
            cur = conn.execute(
                """
                UPDATE candidates SET sealed_gate_opened = 1, updated_at = ?
                WHERE candidate_id = ? AND sealed_gate_opened = 0
                """,
                (ts.isoformat(), candidate_id),
            )
            if cur.rowcount != 1:
                raise GateAlreadyOpenedError(
                    f"GATE_ALREADY_OPENED: candidate {candidate_id} (v{candidate.candidate_version}) has already opened the sealed gate"
                )
            conn.execute(
                """
                INSERT INTO exposure_audits (
                    exposure_id, candidate_id, candidate_version, dataset_split_id,
                    authorized_by, exposed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    exposure_id,
                    candidate_id,
                    candidate.candidate_version,
                    dataset_split_id,
                    authorized_by,
                    ts.isoformat(),
                ),
            )
            audit_record = ExposureAuditRecord(
                exposure_id=exposure_id,
                candidate_id=candidate_id,
                candidate_version=candidate.candidate_version,
                dataset_split_id=dataset_split_id,
                authorized_by=authorized_by,
                exposed_at=ts,
            )

        return audit_record

    def update_config(self, candidate_id: str, new_config_hash: str) -> None:
        """Attempt in-place configuration modification (EVAL-03-AC1).

        Sealed or validated candidates cannot be mutated in place.
        """
        frozen_stages = {
            CandidateStage.VALIDATED,
            CandidateStage.SEALED_PASS,
            CandidateStage.SHADOW,
            CandidateStage.CHAMPION,
        }
        with self._atomic() as conn:
            candidate = self._fetch_candidate(conn, candidate_id)
            if candidate.current_stage in frozen_stages or candidate.sealed_gate_opened:
                raise CandidateFrozenError(
                    f"CONFIG_MUTATION_FORBIDDEN: candidate {candidate_id} is at stage {candidate.current_stage}; spawn new challenger"
                )

            cur = conn.execute(
                """UPDATE candidates SET config_hash = ?, updated_at = ?
                   WHERE candidate_id = ? AND current_stage = ? AND sealed_gate_opened = 0""",
                (
                    new_config_hash,
                    datetime.now(UTC).isoformat(),
                    candidate_id,
                    candidate.current_stage.value,
                ),
            )
            if cur.rowcount != 1:
                raise CandidateFrozenError(
                    f"CONFIG_MUTATION_FORBIDDEN: candidate {candidate_id} changed lifecycle state; spawn new challenger"
                )

    def fork_challenger(
        self,
        parent_candidate_id: str,
        new_candidate_id: str,
        new_candidate_version: str,
        new_config_hash: str,
        created_at: datetime | None = None,
    ) -> CandidateRecord:
        """Spawn a new challenger candidate when configuration changes (EVAL-03-AC1)."""
        parent = self.get_candidate(parent_candidate_id)
        ts = created_at or datetime.now(UTC)

        challenger = CandidateRecord(
            candidate_id=new_candidate_id,
            candidate_version=new_candidate_version,
            strategy_name=parent.strategy_name,
            config_hash=new_config_hash,
            current_stage=CandidateStage.IDEA,
            parent_candidate_id=parent.candidate_id,
            sealed_gate_opened=False,
            created_at=ts,
            updated_at=ts,
        )
        return self.register_candidate(challenger)

    def get_transition_history(self, candidate_id: str) -> list[TransitionRecord]:
        """Fetch chronological transition records for candidate."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT transition_id, candidate_id, from_stage, to_stage, reason, timestamp
                FROM transitions WHERE candidate_id = ? ORDER BY timestamp ASC
                """,
                (candidate_id,),
            )
            rows = cur.fetchall()
            return [
                TransitionRecord(
                    transition_id=r[0],
                    candidate_id=r[1],
                    from_stage=CandidateStage(r[2]),
                    to_stage=CandidateStage(r[3]),
                    reason=r[4],
                    timestamp=datetime.fromisoformat(r[5]),
                )
                for r in rows
            ]

    def compute_leaderboard(
        self,
        runs: Sequence[ExperimentRunRecord],
        sort_metric: str = "sharpe_ratio",
        ascending: bool = False,
    ) -> list[LeaderboardEntry]:
        """Rank valid candidates on experiment leaderboard (EVAL-03-AC3).

        Invariant:
        Runs with status INVALID_RUN or failed runs are strictly excluded from ranking.
        EVAL-03-F4: a run whose ranking metric is absent or non-finite (NaN/inf) carries no
        usable evidence, so it is excluded too rather than sorted as if it were neutral.
        """
        valid_runs: list[tuple[float, ExperimentRunRecord]] = []
        for run in runs:
            if run.status != ExperimentRunStatus.SUCCESS or sort_metric not in run.metrics:
                continue
            try:
                candidate = self.get_candidate(run.candidate_id)
            except CandidateNotFoundError:
                continue
            if (
                candidate.candidate_version != run.candidate_version
                or candidate.config_hash != run.config_hash
                or not candidate.sealed_gate_opened
            ):
                continue
            with self._connect() as conn:
                exposure = conn.execute(
                    """SELECT exposure_id, dataset_split_id, exposed_at FROM exposure_audits
                       WHERE candidate_id = ? AND candidate_version = ?
                       ORDER BY exposed_at DESC LIMIT 1""",
                    (candidate.candidate_id, candidate.candidate_version),
                ).fetchone()
            if (
                exposure is None
                or run.dataset_split_id is None
                or run.dataset_split_id != exposure[1]
                or run.created_at < datetime.fromisoformat(exposure[2])
            ):
                continue
            try:
                metric_value = float(run.metrics[sort_metric])
            except (TypeError, ValueError):
                continue
            if not math.isfinite(metric_value):
                self._record_metric_exclusion(
                    run=run,
                    exposure_id=exposure[0],
                    metric_name=sort_metric,
                )
                continue
            valid_runs.append((metric_value, run))

        sorted_runs = sorted(
            (run for _, run in valid_runs),
            key=lambda r: float(r.metrics[sort_metric]),
            reverse=not ascending,
        )

        entries = []
        for idx, run in enumerate(sorted_runs, start=1):
            entries.append(
                LeaderboardEntry(
                    rank=idx,
                    candidate_id=run.candidate_id,
                    candidate_version=run.candidate_version,
                    metric_value=float(run.metrics[sort_metric]),
                    sort_metric=sort_metric,
                    run_id=run.run_id,
                )
            )
        return entries

    def _record_metric_exclusion(
        self,
        *,
        run: ExperimentRunRecord,
        exposure_id: str,
        metric_name: str,
    ) -> None:
        reason_code = "RANK_METRIC_NON_FINITE"
        identity = {
            "run_digest": run.content_digest(),
            "exposure_id": exposure_id,
            "candidate_id": run.candidate_id,
            "candidate_version": run.candidate_version,
            "dataset_split_id": run.dataset_split_id,
            "metric_name": metric_name,
            "reason_code": reason_code,
        }
        exclusion_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        recorded_at = datetime.now(UTC)
        with self._atomic() as conn:
            conn.execute(
                """INSERT INTO leaderboard_metric_exclusions (
                       exclusion_id, run_id, run_digest, exposure_id, candidate_id,
                       candidate_version, dataset_split_id, metric_name, reason_code,
                       recorded_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(exclusion_id) DO NOTHING""",
                (
                    exclusion_id,
                    run.run_id,
                    identity["run_digest"],
                    exposure_id,
                    run.candidate_id,
                    run.candidate_version,
                    run.dataset_split_id,
                    metric_name,
                    reason_code,
                    recorded_at.isoformat(),
                ),
            )

    def get_leaderboard_exclusions(self) -> list[LeaderboardMetricExclusion]:
        """Read persisted metric exclusions in recording order."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT exclusion_id, run_id, run_digest, exposure_id, candidate_id,
                          candidate_version, dataset_split_id, metric_name, reason_code,
                          recorded_at
                   FROM leaderboard_metric_exclusions
                   ORDER BY recorded_at, exclusion_id"""
            ).fetchall()
        return [
            LeaderboardMetricExclusion(
                exclusion_id=row[0],
                run_id=row[1],
                run_digest=row[2],
                exposure_id=row[3],
                candidate_id=row[4],
                candidate_version=row[5],
                dataset_split_id=row[6],
                metric_name=row[7],
                reason_code=row[8],
                recorded_at=datetime.fromisoformat(row[9]),
            )
            for row in rows
        ]
