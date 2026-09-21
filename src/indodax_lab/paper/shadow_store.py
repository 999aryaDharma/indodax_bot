"""Durable SQLite checkpoint/event store for forward shadow trading.

This module is deliberately small: SQLite is the local durability boundary, JSON is only
the serialization format inside a transaction. Corrupt checkpoints fail closed.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ShadowStateCorruptionError(RuntimeError):
    """Raised when a persisted checkpoint cannot be trusted."""


class ShadowStateStore:
    """Transactional local store for paper portfolio checkpoints and audit events."""

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
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS shadow_checkpoint (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    payload TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shadow_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def save_checkpoint(
        self,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        event_type: str | None = None,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        canonical = self._canonical(payload)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO shadow_checkpoint(singleton, payload, sha256, updated_at_utc)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    payload=excluded.payload,
                    sha256=excluded.sha256,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (canonical, digest, now),
            )
            if event_id is not None and event_type is not None:
                event_json = self._canonical(event_payload or {})
                conn.execute(
                    """
                    INSERT OR IGNORE INTO shadow_events(event_id, event_type, payload, created_at_utc)
                    VALUES (?, ?, ?, ?)
                    """,
                    (event_id, event_type, event_json, now),
                )
            conn.commit()

    def load_checkpoint(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload, sha256 FROM shadow_checkpoint WHERE singleton = 1"
            ).fetchone()
        if row is None:
            return None
        payload, stored_digest = row
        actual = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if actual != stored_digest:
            raise ShadowStateCorruptionError("SHADOW_CHECKPOINT_HASH_MISMATCH")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ShadowStateCorruptionError("SHADOW_CHECKPOINT_INVALID_JSON") from exc
        if not isinstance(decoded, dict):
            raise ShadowStateCorruptionError("SHADOW_CHECKPOINT_NOT_MAPPING")
        return decoded
