"""Transactional SQLite persistence for OMS order snapshots and lifecycle events."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from indodax_lab.execution.oms import OmsOrder


class OmsStateCorruptionError(RuntimeError):
    """Persisted OMS state cannot be trusted."""


class OmsConcurrencyError(RuntimeError):
    """A stale writer attempted to overwrite a newer OMS version."""


class OmsStore:
    """Single-node durable OMS store with optimistic version fencing."""

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
                CREATE TABLE IF NOT EXISTS oms_orders (
                    internal_order_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS oms_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    internal_order_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    FOREIGN KEY(internal_order_id)
                        REFERENCES oms_orders(internal_order_id)
                );

                CREATE INDEX IF NOT EXISTS idx_oms_events_order
                    ON oms_events(internal_order_id, seq);
                """
            )

    @staticmethod
    def _canonical_order(order: OmsOrder) -> str:
        return json.dumps(
            order.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def _canonical_payload(payload: dict[str, Any]) -> str:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def _digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _decode_order(cls, payload: str, stored_digest: str) -> OmsOrder:
        if cls._digest(payload) != stored_digest:
            raise OmsStateCorruptionError("OMS_ORDER_HASH_MISMATCH")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise OmsStateCorruptionError("OMS_ORDER_INVALID_JSON") from exc
        if not isinstance(decoded, dict):
            raise OmsStateCorruptionError("OMS_ORDER_NOT_MAPPING")
        try:
            return OmsOrder.model_validate(decoded)
        except ValueError as exc:
            raise OmsStateCorruptionError("OMS_ORDER_SCHEMA_INVALID") from exc

    def create_order(
        self,
        order: OmsOrder,
        *,
        event_id: str,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        """Insert a NEW order and creation event atomically."""

        if order.version != 1:
            raise ValueError("OMS_INITIAL_VERSION_MUST_BE_ONE")
        canonical = self._canonical_order(order)
        digest = self._digest(canonical)
        event_json = self._canonical_payload(event_payload or {})
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO oms_orders(
                        internal_order_id, payload, sha256, version, updated_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        order.internal_order_id,
                        canonical,
                        digest,
                        order.version,
                        order.updated_at.isoformat(),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO oms_events(
                        event_id, internal_order_id, from_state, to_state,
                        payload, created_at_utc
                    )
                    VALUES (?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        event_id,
                        order.internal_order_id,
                        order.state.value,
                        event_json,
                        order.updated_at.isoformat(),
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise OmsConcurrencyError("OMS_DUPLICATE_ORDER_OR_EVENT") from exc

    def apply_transition(
        self,
        previous: OmsOrder,
        current: OmsOrder,
        *,
        event_id: str,
        event_payload: dict[str, Any] | None = None,
    ) -> None:
        """Persist one already-validated transition with stale-writer fencing."""

        if previous.internal_order_id != current.internal_order_id:
            raise ValueError("OMS_ORDER_ID_CHANGED")
        if current.version != previous.version + 1:
            raise ValueError("OMS_VERSION_NOT_SEQUENTIAL")

        current_json = self._canonical_order(current)
        current_digest = self._digest(current_json)
        event_json = self._canonical_payload(event_payload or {})

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT payload, sha256, version
                FROM oms_orders
                WHERE internal_order_id = ?
                """,
                (previous.internal_order_id,),
            ).fetchone()
            if row is None:
                raise OmsConcurrencyError("OMS_ORDER_NOT_FOUND")

            stored_payload, stored_digest, stored_version = row
            stored_order = self._decode_order(stored_payload, stored_digest)
            if stored_version != previous.version or stored_order != previous:
                raise OmsConcurrencyError("OMS_STALE_WRITER")

            cursor = conn.execute(
                """
                UPDATE oms_orders
                SET payload = ?, sha256 = ?, version = ?, updated_at_utc = ?
                WHERE internal_order_id = ? AND version = ?
                """,
                (
                    current_json,
                    current_digest,
                    current.version,
                    current.updated_at.isoformat(),
                    current.internal_order_id,
                    previous.version,
                ),
            )
            if cursor.rowcount != 1:
                raise OmsConcurrencyError("OMS_STALE_WRITER")

            try:
                conn.execute(
                    """
                    INSERT INTO oms_events(
                        event_id, internal_order_id, from_state, to_state,
                        payload, created_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        current.internal_order_id,
                        previous.state.value,
                        current.state.value,
                        event_json,
                        current.updated_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise OmsConcurrencyError("OMS_DUPLICATE_EVENT_ID") from exc
            conn.commit()

    def load_order(self, internal_order_id: str) -> OmsOrder | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload, sha256
                FROM oms_orders
                WHERE internal_order_id = ?
                """,
                (internal_order_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decode_order(row[0], row[1])

    def load_nonterminal_orders(self) -> tuple[OmsOrder, ...]:
        """Restore every order whose lifecycle still requires supervision."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload, sha256
                FROM oms_orders
                ORDER BY internal_order_id
                """
            ).fetchall()

        active: list[OmsOrder] = []
        for payload, digest in rows:
            order = self._decode_order(payload, digest)
            if order.state.value not in {"FILLED", "CANCELLED", "REJECTED"}:
                active.append(order)
        return tuple(active)
