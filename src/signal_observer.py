"""Persistent signal observations and deterministic intrabar outcomes."""

import hashlib
import json
import math
import os
import sqlite3
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_BAR_SECONDS = 15 * 60
_SCHEMA_BACKUP_SUFFIX = ".pre-signal-observer-v2.bak"
_POLICY_VERSION = "shadow_policy_v1"
_runtime_observer: "SignalObserver | None" = None


class Candle(Protocol):
    timestamp: int
    high: float
    low: float


class ConflictingCandleError(ValueError):
    """Raised when one bar identity has conflicting OHLCV values."""


class ConflictingDecisionError(ValueError):
    """Raised when one decision slot receives different final payloads."""


def canonicalize_bars(bars: Iterable[Candle]) -> list[Candle]:
    """Stable-sort bars, collapse identical duplicates, reject conflicts."""
    canonical: dict[int, tuple[tuple[object, ...], Candle]] = {}
    for bar in sorted(bars, key=lambda item: int(item.timestamp)):
        bar_id = int(bar.timestamp)
        signature = tuple(
            getattr(bar, field, None)
            for field in ("open", "high", "low", "close", "volume")
        )
        existing = canonical.get(bar_id)
        if existing is None:
            canonical[bar_id] = (signature, bar)
        elif existing[0] != signature:
            raise ConflictingCandleError(f"conflicting candle for bar {bar_id}")
    return [item[1] for item in canonical.values()]


@dataclass(frozen=True)
class BarrierResolution:
    """The first barrier chosen for an already-closed OHLC bar."""

    reason: str
    fill_price: float


def resolve_barriers(
    *,
    bar_high: float,
    bar_low: float,
    stop_loss: float,
    take_profit: float,
    same_bar_policy: str = "SL_FIRST",
) -> BarrierResolution | None:
    """Resolve long-position barriers using a conservative same-bar policy."""
    if same_bar_policy != "SL_FIRST":
        raise ValueError(f"Unsupported same-bar policy: {same_bar_policy}")

    stop_touched = bar_low <= stop_loss
    target_touched = bar_high >= take_profit
    if stop_touched:
        return BarrierResolution(reason="SL", fill_price=stop_loss)
    if target_touched:
        return BarrierResolution(reason="TP", fill_price=take_profit)
    return None


class SignalObserver:
    """SQLite-backed ledger of every evaluated signal candidate."""

    def __init__(
        self,
        *,
        db_path: str | Path,
        clock: Callable[[], float] = time.time,
        candle_fetcher: Callable[[str, str], Iterable[Candle]] | None = None,
        shadow_enabled: bool = False,
        shadow_policy_version: str = _POLICY_VERSION,
    ) -> None:
        self._db_path = str(db_path)
        self._clock = clock
        self._candle_fetcher = candle_fetcher
        self._shadow_enabled = shadow_enabled
        self._shadow_policy_version = shadow_policy_version
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='signal_observations'"
            ).fetchone()
            if not exists:
                conn.execute("""
                    CREATE TABLE signal_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_ts REAL NOT NULL,
                    decision_bar_id INTEGER NOT NULL,
                    first_eligible_bar_id INTEGER NOT NULL,
                    decision_key TEXT NOT NULL UNIQUE,
                    pair TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    score REAL NOT NULL,
                    passed INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    planned_entry REAL,
                    planned_stop_loss REAL,
                    planned_take_profit REAL,
                    planned_position_idr REAL,
                    dataset_version TEXT NOT NULL,
                    runtime_version TEXT NOT NULL,
                    shadow_policy_version TEXT NOT NULL,
                    shadow_status TEXT NOT NULL DEFAULT 'NOT_OPENED',
                    last_processed_bar_id INTEGER,
                    outcome TEXT,
                    outcome_price REAL,
                    outcome_ts REAL
                    )
                """)
            else:
                columns = {
                    row["name"]
                    for row in conn.execute(
                        "PRAGMA table_info(signal_observations)"
                    )
                }
                additions = {
                    "decision_bar_id": "INTEGER",
                    "first_eligible_bar_id": "INTEGER",
                    "decision_key": "TEXT",
                    "planned_position_idr": "REAL",
                    "shadow_policy_version": "TEXT",
                }
                missing = additions.keys() - columns
                if missing:
                    self._create_schema_backup(conn)
                    conn.execute("BEGIN IMMEDIATE")
                    for name in sorted(missing):
                        conn.execute(
                            f"ALTER TABLE signal_observations "
                            f"ADD COLUMN {name} {additions[name]}"
                        )
                    rows = conn.execute(
                        "SELECT id, decision_ts FROM signal_observations"
                    ).fetchall()
                    for row in rows:
                        decision_ts = float(row["decision_ts"])
                        decision_bar_id = int(decision_ts // _BAR_SECONDS) * _BAR_SECONDS
                        first_eligible = math.ceil(decision_ts / _BAR_SECONDS) * _BAR_SECONDS
                        conn.execute("""
                            UPDATE signal_observations
                            SET decision_bar_id=?, first_eligible_bar_id=?,
                                decision_key=?, shadow_policy_version=?
                            WHERE id=?
                        """, (
                            decision_bar_id,
                            first_eligible,
                            f"legacy:{row['id']}",
                            _POLICY_VERSION,
                            row["id"],
                        ))
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    signal_observations_decision_key_uq
                ON signal_observations(decision_key)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_action_intents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observation_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    action_ts REAL NOT NULL,
                    source TEXT NOT NULL,
                    FOREIGN KEY(observation_id) REFERENCES signal_observations(id)
                )
            """)

    def _create_schema_backup(self, source_conn: sqlite3.Connection) -> Path:
        db_path = Path(self._db_path)
        backup_path = db_path.with_name(f"{db_path.name}{_SCHEMA_BACKUP_SUFFIX}")
        if backup_path.exists():
            return backup_path
        descriptor, temporary_name = tempfile.mkstemp(
            dir=db_path.parent,
            prefix=f"{backup_path.name}.",
            suffix=".tmp",
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        backup_conn = sqlite3.connect(temporary_path)
        try:
            source_conn.backup(backup_conn)
            backup_conn.close()
            os.replace(temporary_path, backup_path)
        except Exception:
            backup_conn.close()
            temporary_path.unlink(missing_ok=True)
            raise
        return backup_path

    def record_candidate(
        self,
        *,
        pair: str,
        strategy: str,
        strategy_version: str,
        score: float,
        passed: bool,
        reason: str,
        dataset_version: str,
        runtime_version: str,
        planned_entry: float | None = None,
        planned_stop_loss: float | None = None,
        planned_take_profit: float | None = None,
        planned_position_idr: float | None = None,
    ) -> int:
        """Persist one final decision and optional plan in a single transaction."""
        decision_ts = self._clock()
        decision_bar_id = int(decision_ts // _BAR_SECONDS) * _BAR_SECONDS
        first_eligible_bar_id = math.ceil(decision_ts / _BAR_SECONDS) * _BAR_SECONDS
        decision_key = hashlib.sha256(json.dumps(
            [
                pair,
                strategy,
                strategy_version,
                decision_bar_id,
                dataset_version,
                runtime_version,
            ],
            separators=(",", ":"),
        ).encode()).hexdigest()
        has_plan = all(value is not None for value in (
            planned_entry,
            planned_stop_loss,
            planned_take_profit,
        ))
        shadow_status = (
            "OPEN" if passed and has_plan and self._shadow_enabled else "NOT_OPENED"
        )
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO signal_observations (
                    decision_ts, decision_bar_id, first_eligible_bar_id,
                    decision_key, pair, strategy, strategy_version, score,
                    passed, reason, planned_entry, planned_stop_loss,
                    planned_take_profit, planned_position_idr, dataset_version,
                    runtime_version, shadow_policy_version, shadow_status,
                    last_processed_bar_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_key) DO NOTHING
            """, (
                decision_ts, decision_bar_id, first_eligible_bar_id,
                decision_key, pair, strategy, strategy_version, score,
                int(passed), reason, planned_entry, planned_stop_loss,
                planned_take_profit, planned_position_idr, dataset_version,
                runtime_version, self._shadow_policy_version, shadow_status,
                first_eligible_bar_id - _BAR_SECONDS,
            ))
            if cursor.rowcount == 1:
                return int(cursor.lastrowid)
            row = conn.execute(
                """
                SELECT id, pair, strategy, strategy_version, score, passed,
                       reason, planned_entry, planned_stop_loss,
                       planned_take_profit, planned_position_idr,
                       dataset_version, runtime_version,
                       shadow_policy_version, shadow_status
                FROM signal_observations WHERE decision_key = ?
                """,
                (decision_key,),
            ).fetchone()
            stored_payload = tuple(row[field] for field in (
                "pair", "strategy", "strategy_version", "score", "passed",
                "reason", "planned_entry", "planned_stop_loss",
                "planned_take_profit", "planned_position_idr",
                "dataset_version", "runtime_version",
                "shadow_policy_version", "shadow_status",
            ))
            candidate_payload = (
                pair, strategy, strategy_version, score, int(passed), reason,
                planned_entry, planned_stop_loss, planned_take_profit,
                planned_position_idr, dataset_version, runtime_version,
                self._shadow_policy_version, shadow_status,
            )
            if stored_payload != candidate_payload:
                raise ConflictingDecisionError(
                    f"conflicting decision payload for slot {decision_key}"
                )
            return int(row["id"])

    def record_action_intent(
        self,
        *,
        observation_id: int,
        action: str,
        source: str,
    ) -> int:
        """Persist user intent separately from the canonical observation."""
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO signal_action_intents (
                    observation_id, action, action_ts, source
                ) VALUES (?, ?, ?, ?)
            """, (observation_id, action, self._clock(), source))
            return int(cursor.lastrowid)

    def open_shadow(
        self,
        *,
        observation_id: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        last_closed_bar_id: int | None = None,
    ) -> bool:
        """Compatibility API: persist a plan and apply shadow policy."""

        with self._connect() as conn:
            observation = conn.execute(
                "SELECT decision_ts FROM signal_observations "
                "WHERE id = ? AND passed = 1",
                (observation_id,),
            ).fetchone()
            if observation is None:
                return False
            if last_closed_bar_id is None:
                decision_ts = float(observation["decision_ts"])
                first_eligible = math.ceil(decision_ts / _BAR_SECONDS) * _BAR_SECONDS
                last_closed_bar_id = first_eligible - _BAR_SECONDS
            status = "OPEN" if self._shadow_enabled else "NOT_OPENED"
            cursor = conn.execute("""
                UPDATE signal_observations
                SET planned_entry = ?, planned_stop_loss = ?,
                    planned_take_profit = ?, shadow_status = ?,
                    last_processed_bar_id = ?
                WHERE id = ? AND passed = 1
            """, (
                entry_price,
                stop_loss,
                take_profit,
                status,
                last_closed_bar_id,
                observation_id,
            ))
            return cursor.rowcount == 1 and self._shadow_enabled

    def get_observation(self, observation_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM signal_observations WHERE id = ?",
                (observation_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def monitor_all(self) -> list[dict]:
        """Resolve open observations from finalized 15-minute candle ranges."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM signal_observations
                WHERE shadow_status = 'OPEN'
                ORDER BY id
            """).fetchall()
        if not rows:
            return []

        fetcher = self._candle_fetcher
        if fetcher is None:
            from indodax_api import fetch_ohlcv

            fetcher = fetch_ohlcv

        events: list[dict] = []
        bars_by_pair: dict[str, list[Candle] | None] = {}
        now = self._clock()
        for row in rows:
            pair = str(row["pair"])
            if pair not in bars_by_pair:
                try:
                    bars_by_pair[pair] = canonicalize_bars(fetcher(pair, "15m"))
                except ConflictingCandleError:
                    bars_by_pair[pair] = None
            if bars_by_pair[pair] is None:
                continue
            eligible_bars = sorted(
                (
                    bar for bar in bars_by_pair[pair]
                    if int(bar.timestamp) > int(row["last_processed_bar_id"])
                    and int(bar.timestamp) + _BAR_SECONDS <= now
                ),
                key=lambda bar: int(bar.timestamp),
            )
            for bar in eligible_bars:
                event = self._process_bar(row, bar)
                if event is not None:
                    events.append(event)
                    break
                row = dict(row)
                row["last_processed_bar_id"] = int(bar.timestamp)
        return events

    def _process_bar(
        self,
        observation: sqlite3.Row | dict,
        bar: Candle,
    ) -> dict | None:
        resolution = resolve_barriers(
            bar_high=float(bar.high),
            bar_low=float(bar.low),
            stop_loss=float(observation["planned_stop_loss"]),
            take_profit=float(observation["planned_take_profit"]),
        )
        bar_id = int(bar.timestamp)
        with self._connect() as conn:
            if resolution is None:
                conn.execute("""
                    UPDATE signal_observations
                    SET last_processed_bar_id = ?
                    WHERE id = ? AND shadow_status = 'OPEN'
                      AND last_processed_bar_id < ?
                """, (bar_id, observation["id"], bar_id))
                return None

            cursor = conn.execute("""
                UPDATE signal_observations
                SET shadow_status = 'CLOSED', last_processed_bar_id = ?,
                    outcome = ?, outcome_price = ?, outcome_ts = ?
                WHERE id = ? AND shadow_status = 'OPEN'
                  AND last_processed_bar_id < ?
            """, (
                bar_id,
                resolution.reason,
                resolution.fill_price,
                float(bar_id + _BAR_SECONDS),
                observation["id"],
                bar_id,
            ))
            if cursor.rowcount != 1:
                return None
        return {
            "observation_id": observation["id"],
            "pair": observation["pair"],
            "reason": resolution.reason,
            "price": resolution.fill_price,
            "bar_id": bar_id,
        }


def set_runtime_observer(observer: SignalObserver | None) -> None:
    global _runtime_observer
    _runtime_observer = observer


def get_runtime_observer() -> SignalObserver:
    global _runtime_observer
    if _runtime_observer is None:
        from config import PAPER_CONFIG

        _runtime_observer = SignalObserver(
            db_path=PAPER_CONFIG.db_path,
            shadow_enabled=PAPER_CONFIG.shadow_observations_enabled,
            shadow_policy_version=PAPER_CONFIG.shadow_policy_version,
        )
    return _runtime_observer
