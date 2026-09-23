"""Authoritative transactional SQLite store for execution state and recovery (PM-02, ADR-007).

Consolidates:
- Event inbox / outbox (PREPARED -> DECIDED -> ACKNOWLEDGED)
- Order Management System (OMS) state & cumulative fills
- Double-entry ResearchLedger journal & hash chain
- Processed fill identities & quarantine
- Optimistic revision concurrency fencing
- Fail-closed restart and recovery
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.ledger import (
    AccountType,
    LedgerTransaction,
    Posting,
)
from indodax_lab.backtest.orders import Fill
from indodax_lab.execution.oms import OmsOrder, OmsOrderState

logger = logging.getLogger("execution_state_store")

_GENESIS_HASH = "0" * 64


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExecutionStateError(RuntimeError):
    """Base error for execution state and transaction boundary violations."""


class RevisionMismatchError(ExecutionStateError):
    """Raised when an operation provides a stale or mismatched expected revision."""


class EventConflictError(ExecutionStateError):
    """Raised when an event with the same ID arrives with differing content/hash."""


class ConflictingFillError(ExecutionStateError):
    """Raised when a fill ID is re-submitted with differing financial attributes."""


class UnmatchedFillError(ExecutionStateError):
    """Raised when an observed fill cannot be matched to any known internal order."""


class OverfillInvariantError(ExecutionStateError):
    """Raised when observed fill quantity exceeds target order desired quantity."""


class CorruptStateError(ExecutionStateError):
    """Raised when snapshot checksum or journal hash chain integrity fails."""


class HaltedStateError(ExecutionStateError):
    """Raised when an operation is attempted on an execution store latched in HALTED state."""


# ---------------------------------------------------------------------------
# Data Transfer Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EventEnvelope:
    envelope_id: str
    event_id: str
    event_hash: str
    sequence_num: int
    status: str  # PREPARED, DECIDED, ACKNOWLEDGED, HALTED
    revision: int
    created_at_utc: datetime
    event_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubmissionAttempt:
    attempt_id: str
    outbox_id: str
    internal_order_id: str
    status: str  # ATTEMPTING, SUBMITTED, REJECTED, UNKNOWN
    revision: int


@dataclass(frozen=True)
class FillCommitResult:
    revision: int
    transaction_id: str | None
    internal_order_id: str | None
    order_state: str | None
    is_duplicate: bool
    quarantined: bool = False
    error: str | None = None


@dataclass(frozen=True)
class ExecutionSnapshot:
    namespace: str
    revision: int
    feed_cursor: str | None
    cash: Decimal
    positions: dict[str, dict[str, Any]]
    orders: dict[str, dict[str, Any]]
    reservations: dict[str, Decimal]
    last_transaction_id: str | None
    halted: bool = False


@dataclass(frozen=True)
class RuntimeStepResult:
    event_id: str
    envelope_id: str
    namespace: str
    status: str
    cursor: str | None
    revision: int


@dataclass(frozen=True)
class RecoveryReport:
    namespace: str
    reloaded_revision: int
    resumed_envelopes: list[str]
    reconciled_attempts: list[str]
    halted: bool
    status: str


@dataclass(frozen=True)
class MigrationReport:
    target_namespace: str
    migrated_orders: int
    migrated_transactions: int
    status: str


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _canonical_bytes(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _sha256_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# ExecutionStateStore Implementation
# ---------------------------------------------------------------------------


class ExecutionStateStore:
    """One local SQLite transactional execution store per namespace (ADR-007)."""

    def __init__(
        self,
        db_path: Path | str,
        *,
        namespace: str = "default",
        initial_cash: Decimal = Decimal("0"),
        valuation_currency: str = "IDR",
    ) -> None:
        self.db_path = Path(db_path)
        self.namespace = namespace
        self.initial_cash = initial_cash
        self.valuation_currency = valuation_currency
        self._lock = threading.RLock()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS state_metadata (
                    namespace TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    feed_cursor TEXT,
                    initial_cash TEXT NOT NULL,
                    current_cash TEXT NOT NULL,
                    valuation_currency TEXT NOT NULL,
                    halted INTEGER NOT NULL DEFAULT 0,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events_inbox (
                    envelope_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    event_hash TEXT NOT NULL,
                    sequence_num INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    event_data_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events_outbox (
                    outbox_id TEXT PRIMARY KEY,
                    envelope_id TEXT NOT NULL,
                    internal_order_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS oms_orders (
                    internal_order_id TEXT PRIMARY KEY,
                    client_order_id TEXT NOT NULL,
                    venue_order_id TEXT,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    desired_qty TEXT NOT NULL,
                    filled_qty TEXT NOT NULL,
                    limit_price TEXT,
                    state TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS oms_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    internal_order_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

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

                CREATE TABLE IF NOT EXISTS ledger_applied_fills (
                    fill_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    fill_hash TEXT NOT NULL,
                    applied_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ledger_positions (
                    pair TEXT PRIMARY KEY,
                    base_qty TEXT NOT NULL,
                    cost_basis TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state_reservations (
                    res_key TEXT PRIMARY KEY,
                    amount TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quarantined_fills (
                    fill_id TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    fill_data_json TEXT NOT NULL,
                    quarantined_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    revision INTEGER NOT NULL,
                    feed_cursor TEXT,
                    state_json TEXT NOT NULL,
                    state_sha256 TEXT NOT NULL,
                    last_transaction_id TEXT,
                    created_at_utc TEXT NOT NULL
                );
                """
            )
            # Initialize metadata if not present
            cur = conn.execute(
                "SELECT namespace FROM state_metadata WHERE namespace=?", (self.namespace,)
            )
            if cur.fetchone() is None:
                now_str = _now_utc().isoformat()
                conn.execute(
                    """
                    INSERT INTO state_metadata (
                        namespace, revision, feed_cursor, initial_cash,
                        current_cash, valuation_currency, halted, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.namespace,
                        0,
                        None,
                        str(self.initial_cash),
                        str(self.initial_cash),
                        self.valuation_currency,
                        0,
                        now_str,
                    ),
                )
            conn.commit()

    def _get_meta(self, conn: sqlite3.Connection) -> dict[str, Any]:
        cur = conn.execute("SELECT * FROM state_metadata WHERE namespace=?", (self.namespace,))
        row = cur.fetchone()
        if row is None:
            raise CorruptStateError(f"MISSING_METADATA: namespace '{self.namespace}'")
        return dict(row)

    def _check_revision(self, conn: sqlite3.Connection, expected_revision: int) -> dict[str, Any]:
        meta = self._get_meta(conn)
        if meta["halted"]:
            raise HaltedStateError(
                f"STORE_HALTED: namespace '{self.namespace}' is latched in HALTED state"
            )
        if meta["revision"] != expected_revision:
            raise RevisionMismatchError(
                f"REVISION_MISMATCH: expected {expected_revision}, got {meta['revision']}"
            )
        return meta

    # -----------------------------------------------------------------------
    # Event Inbox & Outbox Lifecycle
    # -----------------------------------------------------------------------

    def prepare_event(self, event: Any, expected_revision: int) -> EventEnvelope:
        """Transactionally insert event in inbox with PREPARED status."""
        event_dict = (
            event
            if isinstance(event, dict)
            else (
                event.model_dump(mode="json")
                if hasattr(event, "model_dump")
                else {"data": str(event)}
            )
        )
        event_id = event_dict.get("event_id") or f"evt_{uuid.uuid4().hex[:12]}"
        event_hash = _sha256_digest(event_dict)

        with self._lock, self._connect() as conn:
            self._check_revision(conn, expected_revision)

            cur = conn.execute("SELECT * FROM events_inbox WHERE event_id=?", (event_id,))
            existing = cur.fetchone()
            if existing is not None:
                if existing["event_hash"] != event_hash:
                    raise EventConflictError(
                        f"EVENT_CONFLICT: event '{event_id}' arrived with different content hash"
                    )
                # Idempotent return existing
                return EventEnvelope(
                    envelope_id=existing["envelope_id"],
                    event_id=existing["event_id"],
                    event_hash=existing["event_hash"],
                    sequence_num=existing["sequence_num"],
                    status=existing["status"],
                    revision=existing["revision"],
                    created_at_utc=datetime.fromisoformat(existing["created_at_utc"]),
                    event_data=json.loads(existing["event_data_json"]),
                )

            # Check next sequence num
            cur = conn.execute(
                "SELECT COALESCE(MAX(sequence_num), 0) + 1 AS next_seq FROM events_inbox"
            )
            next_seq = cur.fetchone()["next_seq"]

            envelope_id = f"env_{event_id}_{next_seq}"
            now_str = _now_utc().isoformat()

            conn.execute(
                """
                INSERT INTO events_inbox (
                    envelope_id, event_id, event_hash, sequence_num,
                    status, revision, event_data_json, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope_id,
                    event_id,
                    event_hash,
                    next_seq,
                    "PREPARED",
                    expected_revision,
                    json.dumps(event_dict, sort_keys=True, ensure_ascii=False),
                    now_str,
                    now_str,
                ),
            )
            conn.commit()

            return EventEnvelope(
                envelope_id=envelope_id,
                event_id=event_id,
                event_hash=event_hash,
                sequence_num=next_seq,
                status="PREPARED",
                revision=expected_revision,
                created_at_utc=datetime.fromisoformat(now_str),
                event_data=event_dict,
            )

    def commit_decision(
        self,
        envelope_id: str,
        expected_revision: int,
        next_state: Any,
        intents: Sequence[Any],
        reservations: Mapping[str, Decimal],
    ) -> EventEnvelope:
        """Atomically write DECIDED status, OMS orders, outbox entries, and next revision."""
        with self._lock, self._connect() as conn:
            self._check_revision(conn, expected_revision)

            cur = conn.execute("SELECT * FROM events_inbox WHERE envelope_id=?", (envelope_id,))
            env_row = cur.fetchone()
            if env_row is None:
                raise ExecutionStateError(f"ENVELOPE_NOT_FOUND:{envelope_id}")

            now_str = _now_utc().isoformat()
            next_rev = expected_revision + 1

            # 1. Update inbox envelope to DECIDED
            conn.execute(
                """
                UPDATE events_inbox
                SET status='DECIDED', revision=?, updated_at_utc=?
                WHERE envelope_id=?
                """,
                (next_rev, now_str, envelope_id),
            )

            # 2. Persist OMS orders and outbox entries
            for intent in intents:
                order: OmsOrder = (
                    intent if isinstance(intent, OmsOrder) else OmsOrder.model_validate(intent)
                )
                order_json = json.dumps(
                    order.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
                )
                order_sha = _sha256_digest(order)

                conn.execute(
                    """
                    INSERT OR REPLACE INTO oms_orders (
                        internal_order_id, client_order_id, venue_order_id,
                        pair, side, desired_qty, filled_qty, limit_price,
                        state, version, payload_json, sha256, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order.internal_order_id,
                        order.client_order_id,
                        order.venue_order_id,
                        order.pair,
                        str(order.side),
                        str(order.desired_qty),
                        str(order.filled_qty),
                        str(order.limit_price) if order.limit_price is not None else None,
                        str(order.state),
                        order.version,
                        order_json,
                        order_sha,
                        now_str,
                    ),
                )

                outbox_id = f"outbox_{order.internal_order_id}"
                conn.execute(
                    """
                    INSERT OR REPLACE INTO events_outbox (
                        outbox_id, envelope_id, internal_order_id,
                        status, attempt_id, payload_json, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        outbox_id,
                        envelope_id,
                        order.internal_order_id,
                        "PENDING",
                        None,
                        order_json,
                        now_str,
                        now_str,
                    ),
                )

            # 3. Update reservations
            for key, val in reservations.items():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO state_reservations (res_key, amount, updated_at_utc)
                    VALUES (?, ?, ?)
                    """,
                    (key, str(val), now_str),
                )

            # 4. Advance revision in metadata
            conn.execute(
                "UPDATE state_metadata SET revision=?, updated_at_utc=? WHERE namespace=?",
                (next_rev, now_str, self.namespace),
            )
            conn.commit()

            return EventEnvelope(
                envelope_id=envelope_id,
                event_id=env_row["event_id"],
                event_hash=env_row["event_hash"],
                sequence_num=env_row["sequence_num"],
                status="DECIDED",
                revision=next_rev,
                created_at_utc=datetime.fromisoformat(env_row["created_at_utc"]),
                event_data=json.loads(env_row["event_data_json"]),
            )

    def claim_submission(self, outbox_id: str, expected_revision: int) -> SubmissionAttempt:
        """Commit ATTEMPTING state before sending an order to a venue."""
        with self._lock, self._connect() as conn:
            self._check_revision(conn, expected_revision)

            cur = conn.execute("SELECT * FROM events_outbox WHERE outbox_id=?", (outbox_id,))
            outbox = cur.fetchone()
            if outbox is None:
                raise ExecutionStateError(f"OUTBOX_NOT_FOUND:{outbox_id}")

            attempt_id = f"att_{uuid.uuid4().hex[:12]}"
            now_str = _now_utc().isoformat()
            next_rev = expected_revision + 1

            conn.execute(
                """
                UPDATE events_outbox
                SET status='ATTEMPTING', attempt_id=?, updated_at_utc=?
                WHERE outbox_id=?
                """,
                (attempt_id, now_str, outbox_id),
            )

            # Transition OMS order to SUBMITTING
            conn.execute(
                """
                UPDATE oms_orders
                SET state='SUBMITTING', updated_at_utc=?
                WHERE internal_order_id=?
                """,
                (now_str, outbox["internal_order_id"]),
            )

            conn.execute(
                "UPDATE state_metadata SET revision=?, updated_at_utc=? WHERE namespace=?",
                (next_rev, now_str, self.namespace),
            )
            conn.commit()

            return SubmissionAttempt(
                attempt_id=attempt_id,
                outbox_id=outbox_id,
                internal_order_id=outbox["internal_order_id"],
                status="ATTEMPTING",
                revision=next_rev,
            )

    def record_submission(self, attempt_id: str, outcome: Any) -> EventEnvelope:
        """Record venue submission outcome."""
        outcome_dict = (
            outcome
            if isinstance(outcome, dict)
            else (outcome.__dict__ if hasattr(outcome, "__dict__") else {"status": str(outcome)})
        )
        status = outcome_dict.get("status", "SUBMITTED").upper()

        with self._lock, self._connect() as conn:
            cur = conn.execute("SELECT * FROM events_outbox WHERE attempt_id=?", (attempt_id,))
            outbox = cur.fetchone()
            if outbox is None:
                raise ExecutionStateError(f"ATTEMPT_NOT_FOUND:{attempt_id}")

            meta = self._get_meta(conn)
            now_str = _now_utc().isoformat()
            next_rev = meta["revision"] + 1

            outbox_status = (
                "SUBMITTED"
                if status == "SUBMITTED"
                else ("REJECTED" if status == "REJECTED" else "UNKNOWN")
            )
            order_state = (
                "ACKNOWLEDGED"
                if outbox_status == "SUBMITTED"
                else ("REJECTED" if outbox_status == "REJECTED" else "UNKNOWN")
            )

            conn.execute(
                """
                UPDATE events_outbox
                SET status=?, updated_at_utc=?
                WHERE attempt_id=?
                """,
                (outbox_status, now_str, attempt_id),
            )

            conn.execute(
                """
                UPDATE oms_orders
                SET state=?, updated_at_utc=?
                WHERE internal_order_id=?
                """,
                (order_state, now_str, outbox["internal_order_id"]),
            )

            # If outcome is UNKNOWN, latch halted
            halted_val = 1 if outbox_status == "UNKNOWN" else meta["halted"]
            conn.execute(
                """
                UPDATE state_metadata
                SET revision=?, halted=?, updated_at_utc=?
                WHERE namespace=?
                """,
                (next_rev, halted_val, now_str, self.namespace),
            )

            cur = conn.execute(
                "SELECT * FROM events_inbox WHERE envelope_id=?", (outbox["envelope_id"],)
            )
            env_row = cur.fetchone()
            conn.commit()

            return EventEnvelope(
                envelope_id=env_row["envelope_id"],
                event_id=env_row["event_id"],
                event_hash=env_row["event_hash"],
                sequence_num=env_row["sequence_num"],
                status=env_row["status"],
                revision=next_rev,
                created_at_utc=datetime.fromisoformat(env_row["created_at_utc"]),
                event_data=json.loads(env_row["event_data_json"]),
            )

    def acknowledge_event(self, envelope_id: str, expected_revision: int) -> RuntimeStepResult:
        """Atomically record ACKNOWLEDGED and advance cursor."""
        with self._lock, self._connect() as conn:
            self._check_revision(conn, expected_revision)

            cur = conn.execute("SELECT * FROM events_inbox WHERE envelope_id=?", (envelope_id,))
            env_row = cur.fetchone()
            if env_row is None:
                raise ExecutionStateError(f"ENVELOPE_NOT_FOUND:{envelope_id}")

            now_str = _now_utc().isoformat()
            next_rev = expected_revision + 1
            cursor = env_row["event_id"]

            conn.execute(
                """
                UPDATE events_inbox
                SET status='ACKNOWLEDGED', revision=?, updated_at_utc=?
                WHERE envelope_id=?
                """,
                (next_rev, now_str, envelope_id),
            )

            conn.execute(
                """
                UPDATE state_metadata
                SET revision=?, feed_cursor=?, updated_at_utc=?
                WHERE namespace=?
                """,
                (next_rev, cursor, now_str, self.namespace),
            )
            conn.commit()

            return RuntimeStepResult(
                event_id=env_row["event_id"],
                envelope_id=envelope_id,
                namespace=self.namespace,
                status="ACKNOWLEDGED",
                cursor=cursor,
                revision=next_rev,
            )

    # -----------------------------------------------------------------------
    # Financial Fills & ResearchLedger Transactions
    # -----------------------------------------------------------------------

    def apply_fill(self, fill: Fill, expected_revision: int) -> FillCommitResult:
        """Apply a normalized fill atomically across OMS, Ledger, and applied ID."""
        fill = Fill.model_validate(fill.model_dump())
        fill_hash = _sha256_digest(fill)

        with self._lock, self._connect() as conn:
            meta = self._check_revision(conn, expected_revision)

            # 1. Idempotency & duplicate check
            cur = conn.execute(
                "SELECT * FROM ledger_applied_fills WHERE fill_id=?", (fill.fill_id,)
            )
            existing_fill = cur.fetchone()
            if existing_fill is not None:
                if existing_fill["fill_hash"] != fill_hash:
                    # Conflicting duplicate: fail closed immediately
                    raise ConflictingFillError(
                        f"CONFLICTING_DUPLICATE_FILL: fill '{fill.fill_id}' "
                        "resubmitted with changed attributes"
                    )
                # Same fill replay -> no-op
                cur = conn.execute(
                    "SELECT * FROM oms_orders WHERE internal_order_id=?", (fill.order_id,)
                )
                order_row = cur.fetchone()
                order_state = order_row["state"] if order_row else None
                return FillCommitResult(
                    revision=meta["revision"],
                    transaction_id=existing_fill["transaction_id"],
                    internal_order_id=fill.order_id,
                    order_state=order_state,
                    is_duplicate=True,
                )

            # 2. OMS Matching and Overfill check
            cur = conn.execute(
                "SELECT * FROM oms_orders WHERE internal_order_id=?", (fill.order_id,)
            )
            order_row = cur.fetchone()
            if order_row is None:
                # Unmatched fill -> quarantine and halt
                now_str = _now_utc().isoformat()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO quarantined_fills
                    (fill_id, reason, fill_data_json, quarantined_at_utc)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        fill.fill_id,
                        "UNMATCHED_ORDER",
                        json.dumps(fill.model_dump(mode="json")),
                        now_str,
                    ),
                )
                conn.commit()
                raise UnmatchedFillError(
                    f"UNMATCHED_FILL: order '{fill.order_id}' not found in OMS"
                )

            desired_qty = Decimal(order_row["desired_qty"])
            current_filled = Decimal(order_row["filled_qty"])
            new_filled = current_filled + fill.qty

            # Check Overfill
            if new_filled > desired_qty:
                now_str = _now_utc().isoformat()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO quarantined_fills
                    (fill_id, reason, fill_data_json, quarantined_at_utc)
                    VALUES (?, ?, ?, ?)
                    """,
                    (fill.fill_id, "OVERFILL", json.dumps(fill.model_dump(mode="json")), now_str),
                )
                conn.commit()
                raise OverfillInvariantError(
                    f"OVERFILL_DETECTED: fill qty {fill.qty} + current "
                    f"{current_filled} exceeds desired {desired_qty}"
                )

            # Check Late Fill on terminal state
            is_cancelled = order_row["state"] == OmsOrderState.CANCELLED
            if is_cancelled:
                # Retain CANCELLED lifecycle fact while updating cumulative filled_qty
                new_state = OmsOrderState.CANCELLED
            elif new_filled == desired_qty:
                new_state = OmsOrderState.FILLED
            else:
                new_state = OmsOrderState.PARTIALLY_FILLED

            now_str = _now_utc().isoformat()

            # 3. Post to ResearchLedger
            cur = conn.execute("SELECT * FROM ledger_positions WHERE pair=?", (fill.pair,))
            pos_row = cur.fetchone()
            base_pos = Decimal(pos_row["base_qty"]) if pos_row else Decimal("0")
            cost_basis = Decimal(pos_row["cost_basis"]) if pos_row else Decimal("0")
            current_cash = Decimal(meta["current_cash"])

            gross = fill.gross
            fee = fill.fees

            if fill.side == OrderSide.BUY:
                cash_debit = gross + fee
                next_cash = current_cash - cash_debit
                next_base_pos = base_pos + fill.qty
                next_cost_basis = cost_basis + gross
                qty_delta = fill.qty

                p_cash = Posting(
                    account=AccountType.CASH, amount=-cash_debit, currency=self.valuation_currency
                )
                p_asset = Posting(
                    account=AccountType.ASSET, amount=gross, currency=self.valuation_currency
                )
                p_fee = Posting(
                    account=AccountType.FEE, amount=fee, currency=self.valuation_currency
                )
                postings = (p_cash, p_asset, p_fee)

            elif fill.side == OrderSide.SELL:
                if fill.qty > base_pos:
                    raise ExecutionStateError(
                        f"INSUFFICIENT_BASE_QUANTITY: sell {fill.qty} > held {base_pos}"
                    )
                net_credit = gross - fee
                next_cash = current_cash + net_credit
                if fill.qty == base_pos:
                    allocated_basis = cost_basis
                    next_base_pos = Decimal("0")
                    next_cost_basis = Decimal("0")
                else:
                    allocated_basis = (fill.qty * cost_basis) / base_pos
                    next_base_pos = base_pos - fill.qty
                    next_cost_basis = cost_basis - allocated_basis

                gross_pnl = gross - allocated_basis
                qty_delta = -fill.qty

                p_cash = Posting(
                    account=AccountType.CASH, amount=net_credit, currency=self.valuation_currency
                )
                p_asset = Posting(
                    account=AccountType.ASSET,
                    amount=-allocated_basis,
                    currency=self.valuation_currency,
                )
                p_fee = Posting(
                    account=AccountType.FEE, amount=fee, currency=self.valuation_currency
                )
                p_pnl = Posting(
                    account=AccountType.PNL, amount=-gross_pnl, currency=self.valuation_currency
                )
                postings = (p_cash, p_asset, p_fee, p_pnl)
            else:
                raise ExecutionStateError(f"UNSUPPORTED_SIDE:{fill.side}")

            tx_id = f"tx_{fill.fill_id}"
            tx = LedgerTransaction(
                transaction_id=tx_id,
                fill_id=fill.fill_id,
                timestamp=fill.timestamp,
                postings=postings,
                base_qty_delta=qty_delta,
                pair=fill.pair,
            )
            if not tx.is_balanced:
                raise RuntimeError(f"UNBALANCED_TRANSACTION:{tx_id}")

            # 4. Hash Chaining
            cur = conn.execute(
                "SELECT entry_hash FROM ledger_transactions ORDER BY sequence_num DESC LIMIT 1"
            )
            last_entry = cur.fetchone()
            prev_hash = last_entry["entry_hash"] if last_entry else _GENESIS_HASH

            postings_data = [p.model_dump(mode="json") for p in postings]
            postings_json = json.dumps(postings_data, sort_keys=True, ensure_ascii=False)
            tx_payload = (
                f"{tx_id}:{fill.fill_id}:{fill.timestamp.isoformat()}:{postings_json}:{prev_hash}"
            )
            entry_hash = hashlib.sha256(tx_payload.encode("utf-8")).hexdigest()

            conn.execute(
                """
                INSERT INTO ledger_transactions (
                    transaction_id, fill_id, timestamp_utc, pair,
                    base_qty_delta, postings_json, prev_hash, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx_id,
                    fill.fill_id,
                    fill.timestamp.isoformat(),
                    fill.pair,
                    str(qty_delta),
                    postings_json,
                    prev_hash,
                    entry_hash,
                ),
            )

            conn.execute(
                """
                INSERT INTO ledger_applied_fills
                (fill_id, transaction_id, fill_hash, applied_at_utc)
                VALUES (?, ?, ?, ?)
                """,
                (fill.fill_id, tx_id, fill_hash, now_str),
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO ledger_positions (pair, base_qty, cost_basis, updated_at_utc)
                VALUES (?, ?, ?, ?)
                """,
                (fill.pair, str(next_base_pos), str(next_cost_basis), now_str),
            )

            # 5. Update OMS order
            conn.execute(
                """
                UPDATE oms_orders
                SET filled_qty=?, state=?, updated_at_utc=?
                WHERE internal_order_id=?
                """,
                (str(new_filled), str(new_state), now_str, fill.order_id),
            )

            # 6. Update Metadata & Advance Revision
            next_rev = expected_revision + 1
            conn.execute(
                """
                UPDATE state_metadata
                SET revision=?, current_cash=?, updated_at_utc=?
                WHERE namespace=?
                """,
                (next_rev, str(next_cash), now_str, self.namespace),
            )

            conn.commit()

            return FillCommitResult(
                revision=next_rev,
                transaction_id=tx_id,
                internal_order_id=fill.order_id,
                order_state=str(new_state),
                is_duplicate=False,
            )

    # -----------------------------------------------------------------------
    # Restore & Integrity Verification
    # -----------------------------------------------------------------------

    def restore(self) -> ExecutionSnapshot:
        """Verify journal hash chain integrity and reconstitute ExecutionSnapshot fail-closed."""
        with self._lock, self._connect() as conn:
            meta = self._get_meta(conn)

            # 1. Verify hash chain of all transactions
            cur = conn.execute("SELECT * FROM ledger_transactions ORDER BY sequence_num ASC")
            rows = cur.fetchall()
            expected_prev = _GENESIS_HASH
            last_tx_id: str | None = None

            for row in rows:
                if row["prev_hash"] != expected_prev:
                    raise CorruptStateError(
                        f"HASH_CHAIN_DIVERGENCE: seq {row['sequence_num']} prev_hash "
                        f"{row['prev_hash']} != expected {expected_prev}"
                    )
                # Recompute hash
                tx_payload = (
                    f"{row['transaction_id']}:{row['fill_id']}:{row['timestamp_utc']}:"
                    f"{row['postings_json']}:{row['prev_hash']}"
                )
                recomputed_hash = hashlib.sha256(tx_payload.encode("utf-8")).hexdigest()
                if row["entry_hash"] != recomputed_hash:
                    raise CorruptStateError(
                        f"CORRUPT_ENTRY_HASH: seq {row['sequence_num']} hash mismatch"
                    )
                expected_prev = row["entry_hash"]
                last_tx_id = row["transaction_id"]

            # 2. Reconstitute positions
            cur = conn.execute("SELECT * FROM ledger_positions")
            positions = {
                r["pair"]: {
                    "base_qty": Decimal(r["base_qty"]),
                    "cost_basis": Decimal(r["cost_basis"]),
                }
                for r in cur.fetchall()
            }

            # 3. Reconstitute orders
            cur = conn.execute("SELECT * FROM oms_orders")
            orders = {
                r["internal_order_id"]: {
                    "client_order_id": r["client_order_id"],
                    "venue_order_id": r["venue_order_id"],
                    "pair": r["pair"],
                    "side": r["side"],
                    "desired_qty": Decimal(r["desired_qty"]),
                    "filled_qty": Decimal(r["filled_qty"]),
                    "state": r["state"],
                }
                for r in cur.fetchall()
            }

            # 4. Reconstitute reservations
            cur = conn.execute("SELECT * FROM state_reservations")
            reservations = {r["res_key"]: Decimal(r["amount"]) for r in cur.fetchall()}

            return ExecutionSnapshot(
                namespace=self.namespace,
                revision=meta["revision"],
                feed_cursor=meta["feed_cursor"],
                cash=Decimal(meta["current_cash"]),
                positions=positions,
                orders=orders,
                reservations=reservations,
                last_transaction_id=last_tx_id,
                halted=bool(meta["halted"]),
            )

    # -----------------------------------------------------------------------
    # Recovery Protocol (AC5)
    # -----------------------------------------------------------------------

    def recover(self) -> RecoveryReport:
        """Enter RECOVERY, verify integrity, resolve unfinished attempts to UNKNOWN, and halt."""
        with self._lock, self._connect() as conn:
            # 1. Restore & verify integrity
            snapshot = self.restore()

            resumed_envelopes: list[str] = []
            reconciled_attempts: list[str] = []

            # 2. Check PREPARED envelopes
            cur = conn.execute("SELECT * FROM events_inbox WHERE status='PREPARED'")
            for r in cur.fetchall():
                resumed_envelopes.append(r["event_id"])

            # 3. Check ATTEMPTING outbox entries
            cur = conn.execute("SELECT * FROM events_outbox WHERE status='ATTEMPTING'")
            attempting = cur.fetchall()
            halted = snapshot.halted

            now_str = _now_utc().isoformat()
            if attempting:
                # Crashed submission becomes UNKNOWN pending reconciliation; latches HALTED
                halted = True
                for row in attempting:
                    reconciled_attempts.append(row["outbox_id"])
                    conn.execute(
                        "UPDATE events_outbox SET status='UNKNOWN', updated_at_utc=? "
                        "WHERE outbox_id=?",
                        (now_str, row["outbox_id"]),
                    )
                    conn.execute(
                        "UPDATE oms_orders SET state='UNKNOWN', updated_at_utc=? "
                        "WHERE internal_order_id=?",
                        (now_str, row["internal_order_id"]),
                    )

                conn.execute(
                    "UPDATE state_metadata SET halted=1, updated_at_utc=? WHERE namespace=?",
                    (now_str, self.namespace),
                )
                conn.commit()

            return RecoveryReport(
                namespace=self.namespace,
                reloaded_revision=snapshot.revision,
                resumed_envelopes=resumed_envelopes,
                reconciled_attempts=reconciled_attempts,
                halted=halted,
                status="RECOVERED",
            )

    # -----------------------------------------------------------------------
    # Read-Only Migration (Step 5)
    # -----------------------------------------------------------------------

    def migrate_readonly(
        self, source_paths: Sequence[Path], target_namespace: str
    ) -> MigrationReport:
        """Migrate historical orders and ledger entries into target namespace fail-closed."""
        migrated_orders = 0
        migrated_transactions = 0

        for path in source_paths:
            if not path.exists():
                continue
            # Open source read-only
            src_conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
            src_conn.row_factory = sqlite3.Row
            try:
                # Check for oms_orders
                cur = src_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='oms_orders'"
                )
                if cur.fetchone():
                    orders_cur = src_conn.execute("SELECT * FROM oms_orders")
                    with self._lock, self._connect() as conn:
                        for row in orders_cur.fetchall():
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO oms_orders (
                                    internal_order_id, client_order_id, venue_order_id,
                                    pair, side, desired_qty, filled_qty, limit_price,
                                    state, version, payload_json, sha256, updated_at_utc
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    row["internal_order_id"],
                                    row.get("client_order_id", row["internal_order_id"]),
                                    row.get("venue_order_id"),
                                    row.get("pair", "btc_idr"),
                                    row.get("side", "BUY"),
                                    str(row.get("desired_qty", "0")),
                                    str(row.get("filled_qty", "0")),
                                    str(row.get("limit_price")) if row.get("limit_price") else None,
                                    row.get("state", "NEW"),
                                    row.get("version", 1),
                                    row.get("payload", "{}"),
                                    row.get("sha256", _sha256_digest(row["internal_order_id"])),
                                    row.get("updated_at_utc", _now_utc().isoformat()),
                                ),
                            )
                            migrated_orders += 1
                        conn.commit()

                # Check for ledger_transactions
                cur = src_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='ledger_transactions'"
                )
                if cur.fetchone():
                    tx_cur = src_conn.execute("SELECT * FROM ledger_transactions")
                    with self._lock, self._connect() as conn:
                        for row in tx_cur.fetchall():
                            conn.execute(
                                """
                                INSERT OR IGNORE INTO ledger_transactions (
                                    transaction_id, fill_id, timestamp_utc, pair,
                                    base_qty_delta, postings_json, prev_hash, entry_hash
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    row["transaction_id"],
                                    row.get("fill_id"),
                                    row["timestamp_utc"],
                                    row.get("pair"),
                                    row["base_qty_delta"],
                                    row["postings_json"],
                                    row["prev_hash"],
                                    row["entry_hash"],
                                ),
                            )
                            migrated_transactions += 1
                        conn.commit()
            finally:
                src_conn.close()

        return MigrationReport(
            target_namespace=target_namespace,
            migrated_orders=migrated_orders,
            migrated_transactions=migrated_transactions,
            status="MIGRATED",
        )
