"""Durable reconciliation cursor with optimistic fencing.

The cursor advances only after a healthy reconciliation cycle. A small overlap is kept
between windows so timestamp-boundary fills are re-read rather than accidentally skipped.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ReconciliationCursorError(RuntimeError):
    """Base error for reconciliation cursor persistence."""


class ReconciliationCursorCorruptionError(ReconciliationCursorError):
    """Persisted cursor cannot be trusted."""


class ReconciliationCursorConcurrencyError(ReconciliationCursorError):
    """A stale process attempted to move a cursor."""


@dataclass(frozen=True)
class ReconciliationCursor:
    """One durable fill-history cursor for a reconciliation scope."""

    scope_id: str
    next_start_ms: int
    revision: int
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.scope_id.strip():
            raise ValueError("RECONCILIATION_SCOPE_REQUIRED")
        if self.next_start_ms <= 0:
            raise ValueError("RECONCILIATION_CURSOR_TIME_INVALID")
        if self.revision < 1:
            raise ValueError("RECONCILIATION_CURSOR_REVISION_INVALID")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("RECONCILIATION_CURSOR_UTC_REQUIRED")
        if self.updated_at.utcoffset().total_seconds() != 0:
            raise ValueError("RECONCILIATION_CURSOR_UTC_REQUIRED")


class ReconciliationCursorStore:
    """SQLite-backed single-node cursor store."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reconciliation_cursors (
                        scope_id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        updated_at_utc TEXT NOT NULL
                    )
                    """
                )
        finally:
            conn.close()

    @staticmethod
    def _canonical(cursor: ReconciliationCursor) -> str:
        return json.dumps(
            {
                "scope_id": cursor.scope_id,
                "next_start_ms": cursor.next_start_ms,
                "revision": cursor.revision,
                "updated_at": cursor.updated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _decode(cls, payload: str, stored_digest: str) -> ReconciliationCursor:
        if cls._digest(payload) != stored_digest:
            raise ReconciliationCursorCorruptionError(
                "RECONCILIATION_CURSOR_HASH_MISMATCH"
            )
        try:
            data: Any = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ReconciliationCursorCorruptionError(
                "RECONCILIATION_CURSOR_INVALID_JSON"
            ) from exc
        if not isinstance(data, dict):
            raise ReconciliationCursorCorruptionError(
                "RECONCILIATION_CURSOR_NOT_MAPPING"
            )
        try:
            updated_at = datetime.fromisoformat(str(data["updated_at"]))
            return ReconciliationCursor(
                scope_id=str(data["scope_id"]),
                next_start_ms=int(data["next_start_ms"]),
                revision=int(data["revision"]),
                updated_at=updated_at,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ReconciliationCursorCorruptionError(
                "RECONCILIATION_CURSOR_SCHEMA_INVALID"
            ) from exc

    def initialize(
        self,
        *,
        scope_id: str,
        start_ms: int,
        at: datetime | None = None,
    ) -> ReconciliationCursor:
        """Create the reviewed activation boundary exactly once."""

        cursor = ReconciliationCursor(
            scope_id=scope_id,
            next_start_ms=start_ms,
            revision=1,
            updated_at=at or datetime.now(UTC),
        )
        payload = self._canonical(cursor)
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO reconciliation_cursors(
                        scope_id, payload, sha256, revision, updated_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        cursor.scope_id,
                        payload,
                        self._digest(payload),
                        cursor.revision,
                        cursor.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ReconciliationCursorConcurrencyError(
                "RECONCILIATION_CURSOR_ALREADY_EXISTS"
            ) from exc
        finally:
            conn.close()
        return cursor

    def load(self, scope_id: str) -> ReconciliationCursor | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT payload, sha256
                FROM reconciliation_cursors
                WHERE scope_id = ?
                """,
                (scope_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        cursor = self._decode(row[0], row[1])
        if cursor.scope_id != scope_id:
            raise ReconciliationCursorCorruptionError(
                "RECONCILIATION_CURSOR_SCOPE_MISMATCH"
            )
        return cursor

    def advance_after_healthy(
        self,
        cursor: ReconciliationCursor,
        *,
        observed_end_ms: int,
        overlap_ms: int = 5000,
        at: datetime | None = None,
    ) -> ReconciliationCursor:
        """Advance with overlap after, and only after, caller proved HEALTHY."""

        if observed_end_ms < cursor.next_start_ms:
            raise ValueError("RECONCILIATION_CURSOR_END_REGRESSION")
        if overlap_ms < 0:
            raise ValueError("RECONCILIATION_CURSOR_OVERLAP_INVALID")

        next_start_ms = max(
            cursor.next_start_ms,
            observed_end_ms - overlap_ms,
        )
        updated = ReconciliationCursor(
            scope_id=cursor.scope_id,
            next_start_ms=next_start_ms,
            revision=cursor.revision + 1,
            updated_at=at or datetime.now(UTC),
        )
        payload = self._canonical(updated)

        conn = self._connect()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT payload, sha256, revision
                    FROM reconciliation_cursors
                    WHERE scope_id = ?
                    """,
                    (cursor.scope_id,),
                ).fetchone()
                if row is None:
                    raise ReconciliationCursorConcurrencyError(
                        "RECONCILIATION_CURSOR_NOT_FOUND"
                    )
                persisted = self._decode(row[0], row[1])
                if row[2] != cursor.revision or persisted != cursor:
                    raise ReconciliationCursorConcurrencyError(
                        "RECONCILIATION_CURSOR_STALE_WRITER"
                    )

                result = conn.execute(
                    """
                    UPDATE reconciliation_cursors
                    SET payload = ?, sha256 = ?, revision = ?, updated_at_utc = ?
                    WHERE scope_id = ? AND revision = ?
                    """,
                    (
                        payload,
                        self._digest(payload),
                        updated.revision,
                        updated.updated_at.isoformat(),
                        updated.scope_id,
                        cursor.revision,
                    ),
                )
                if result.rowcount != 1:
                    raise ReconciliationCursorConcurrencyError(
                        "RECONCILIATION_CURSOR_STALE_WRITER"
                    )
        finally:
            conn.close()

        return updated
