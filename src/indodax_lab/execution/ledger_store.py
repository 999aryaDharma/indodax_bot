"""Production durable SQLite store for double-entry ResearchLedger.

Guarantees:
- SQLite WAL mode + synchronous=FULL for ACID durability.
- Append-only chained cryptographic transaction journal (SHA-256).
- Explicit tracking of processed venue fill IDs.
- Deterministic reconstituting of ResearchLedger on process startup/recovery.
- Fail-closed verification of double-entry balance and hash-chain integrity.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from indodax_lab.backtest.ledger import (
    LedgerTransaction,
    ResearchLedger,
)

logger = logging.getLogger("production_ledger_store")

_GENESIS_HASH = "0" * 64


class LedgerIntegrityError(RuntimeError):
    """Raised when ledger store records detect tampering, hash divergence, or imbalance."""


class ProductionLedgerStore:
    """Durable SQLite storage for ResearchLedger with chained hash integrity."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_transactions (
                    sequence_num INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL UNIQUE,
                    fill_id TEXT,
                    timestamp_utc TEXT NOT NULL,
                    pair TEXT,
                    base_qty_delta TEXT NOT NULL,
                    postings_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_applied_fills (
                    fill_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    applied_at_utc TEXT NOT NULL,
                    FOREIGN KEY(transaction_id) REFERENCES ledger_transactions(transaction_id)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    state_sha256 TEXT NOT NULL,
                    last_transaction_id TEXT
                );
                """
            )
            conn.commit()

    @staticmethod
    def _compute_entry_hash(
        prev_hash: str,
        transaction_id: str,
        fill_id: str | None,
        timestamp_utc: str,
        pair: str | None,
        base_qty_delta: str,
        postings_json: str,
    ) -> str:
        payload = (
            f"{prev_hash}|{transaction_id}|{fill_id or ''}|"
            f"{timestamp_utc}|{pair or ''}|{base_qty_delta}|{postings_json}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def initialize_if_empty(
        self,
        *,
        initial_cash: Decimal,
        valuation_currency: str = "IDR",
        init_timestamp: datetime | None = None,
    ) -> ResearchLedger:
        """Initialize ledger store with initial capital if not already populated."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM ledger_transactions").fetchone()
            if row and row["cnt"] > 0:
                # Already populated, load existing
                return self.load_ledger()

            ts = init_timestamp or datetime.now(UTC)
            ledger = ResearchLedger(
                initial_cash=initial_cash,
                valuation_currency=valuation_currency,
                init_timestamp=ts,
            )

            # Persist initial transaction if present
            if ledger.transactions:
                init_tx = ledger.transactions[0]
                self._persist_transaction_locked(conn, init_tx, prev_hash=_GENESIS_HASH)

            # Persist initial snapshot
            last_id = ledger.transactions[0].transaction_id if ledger.transactions else None
            self._save_snapshot_locked(conn, ledger, last_tx_id=last_id)
            conn.commit()
            return ledger

    def _persist_transaction_locked(
        self,
        conn: sqlite3.Connection,
        tx: LedgerTransaction,
        prev_hash: str | None = None,
    ) -> str:
        if prev_hash is None:
            last_row = conn.execute(
                "SELECT entry_hash FROM ledger_transactions ORDER BY sequence_num DESC LIMIT 1"
            ).fetchone()
            prev_hash = last_row["entry_hash"] if last_row else _GENESIS_HASH

        postings_data = [p.model_dump(mode="json") for p in tx.postings]
        postings_json = json.dumps(postings_data, sort_keys=True)
        ts_utc = tx.timestamp.astimezone(UTC).isoformat()
        delta_str = str(tx.base_qty_delta)

        entry_hash = self._compute_entry_hash(
            prev_hash=prev_hash,
            transaction_id=tx.transaction_id,
            fill_id=tx.fill_id,
            timestamp_utc=ts_utc,
            pair=tx.pair,
            base_qty_delta=delta_str,
            postings_json=postings_json,
        )

        conn.execute(
            """
            INSERT INTO ledger_transactions (
                transaction_id, fill_id, timestamp_utc, pair,
                base_qty_delta, postings_json, prev_hash, entry_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx.transaction_id,
                tx.fill_id,
                ts_utc,
                tx.pair,
                delta_str,
                postings_json,
                prev_hash,
                entry_hash,
            ),
        )

        if tx.fill_id:
            conn.execute(
                """
                INSERT OR IGNORE INTO ledger_applied_fills (fill_id, transaction_id, applied_at_utc)
                VALUES (?, ?, ?)
                """,
                (tx.fill_id, tx.transaction_id, ts_utc),
            )

        return entry_hash

    def _save_snapshot_locked(
        self,
        conn: sqlite3.Connection,
        ledger: ResearchLedger,
        last_tx_id: str | None = None,
    ) -> None:
        state = ledger.to_dict()
        state_json = json.dumps(state, sort_keys=True)
        state_sha256 = hashlib.sha256(state_json.encode("utf-8")).hexdigest()
        now_utc = datetime.now(UTC).isoformat()

        conn.execute(
            """
            INSERT INTO ledger_snapshots (
                created_at_utc, state_json, state_sha256, last_transaction_id
            ) VALUES (?, ?, ?, ?)
            """,
            (now_utc, state_json, state_sha256, last_tx_id),
        )

    def persist_transaction(self, tx: LedgerTransaction, ledger: ResearchLedger) -> None:
        """Persist a single double-entry transaction and snapshot atomically."""
        if not tx.is_balanced:
            raise LedgerIntegrityError(f"Cannot persist unbalanced transaction {tx.transaction_id}")

        with self._get_connection() as conn:
            # Check if transaction already recorded
            existing = conn.execute(
                "SELECT sequence_num FROM ledger_transactions WHERE transaction_id = ?",
                (tx.transaction_id,),
            ).fetchone()
            if existing:
                return

            self._persist_transaction_locked(conn, tx)
            self._save_snapshot_locked(conn, ledger, last_tx_id=tx.transaction_id)
            conn.commit()

    def load_ledger(self) -> ResearchLedger:
        """Load and reconstitute the latest valid ResearchLedger with integrity check."""
        with self._get_connection() as conn:
            snap = conn.execute(
                """
                SELECT state_json, state_sha256
                FROM ledger_snapshots
                ORDER BY snapshot_id DESC LIMIT 1
                """
            ).fetchone()
            if snap is None:
                raise LedgerIntegrityError("No ledger snapshot found in database")

            computed_sha = hashlib.sha256(snap["state_json"].encode("utf-8")).hexdigest()
            if computed_sha != snap["state_sha256"]:
                raise LedgerIntegrityError(
                    f"LEDGER_SNAPSHOT_CORRUPTED: expected {snap['state_sha256']} got {computed_sha}"
                )

            data: dict[str, Any] = json.loads(snap["state_json"])
            ledger = ResearchLedger.from_dict(data)
            return ledger

    def verify_chain_integrity(self) -> bool:
        """Verify sequential cryptographic hash chain of all transactions fail-closed."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT sequence_num, transaction_id, fill_id, timestamp_utc, pair,
                       base_qty_delta, postings_json, prev_hash, entry_hash
                FROM ledger_transactions
                ORDER BY sequence_num ASC
                """
            )
            rows = cursor.fetchall()
            if not rows:
                return True

            expected_prev = _GENESIS_HASH
            for row in rows:
                if row["prev_hash"] != expected_prev:
                    raise LedgerIntegrityError(
                        f"HASH_CHAIN_BROKEN at seq {row['sequence_num']}: "
                        f"expected prev_hash {expected_prev} but found {row['prev_hash']}"
                    )
                calculated_hash = self._compute_entry_hash(
                    prev_hash=row["prev_hash"],
                    transaction_id=row["transaction_id"],
                    fill_id=row["fill_id"],
                    timestamp_utc=row["timestamp_utc"],
                    pair=row["pair"],
                    base_qty_delta=row["base_qty_delta"],
                    postings_json=row["postings_json"],
                )
                if calculated_hash != row["entry_hash"]:
                    raise LedgerIntegrityError(
                        f"ENTRY_HASH_MISMATCH at seq {row['sequence_num']}: "
                        f"stored {row['entry_hash']} != calculated {calculated_hash}"
                    )
                expected_prev = row["entry_hash"]

            return True

    def is_fill_recorded(self, fill_id: str) -> bool:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT fill_id FROM ledger_applied_fills WHERE fill_id = ?",
                (fill_id,),
            ).fetchone()
            return row is not None

    def get_processed_fill_ids(self) -> set[str]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT fill_id FROM ledger_applied_fills").fetchall()
            return {r["fill_id"] for r in rows}
