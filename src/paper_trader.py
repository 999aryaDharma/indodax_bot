"""
paper_trader.py — Paper Trading (Ghost Mode) & Win-Rate Analytics

Memungkinkan simulasi trading tanpa modal nyata:
  - Mencatat sinyal seolah-olah dieksekusi
  - Monitor harga vs SL/TP secara paralel dengan real position tracker
  - Kirim Weekly Report setiap Minggu (akurasi, win rate, simulasi profit)

Database: SQLite terpisah dari real positions (logs/paper_trades.db)
"""

import logging
import math
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Tuple

import pytz

from config import APP_CONFIG, PAPER_CONFIG
from paper_accounting import BuyFill, account_buy, account_sell, realized_pnl
from signal_observer import (
    ConflictingCandleError,
    canonicalize_bars,
    resolve_barriers,
)

logger = logging.getLogger(__name__)
WIB = pytz.timezone(APP_CONFIG.timezone)

_ACCOUNTING_COLUMNS = {
    "gross_cash_debit": "TEXT",
    "base_qty": "TEXT",
    "buy_notional": "TEXT",
    "buy_fee": "TEXT",
    "sell_notional": "TEXT",
    "sell_fee": "TEXT",
    "net_cash_credit": "TEXT",
    "cost_model_id": "TEXT",
}
_COST_MODEL_ID = "cash_debit_v1"
_ACCOUNTING_EXACT = "EXACT"
_ACCOUNTING_LEGACY = "LEGACY_ESTIMATE"
_ACCOUNTING_MIXED = "MIXED"
_ACCOUNTING_EMPTY = "NO_CLOSED_TRADES"
_MIGRATION_BACKUP_SUFFIX = ".pre-cash-debit-v1.bak"
_REBUILD_TABLE_NAME = "paper_trades_accounting_rebuild"
_BAR_STATE_REBUILD_TABLE_NAME = "paper_trade_bar_state_rebuild"
_BAR_SECONDS = 15 * 60
_BAR_MIGRATION_BACKUP_SUFFIX = ".pre-closed-bar-v2.bak"


class Candle(Protocol):
    timestamp: int
    high: float
    low: float


# ==============================================================================
# DATA CLASS
# ==============================================================================

@dataclass
class PaperTrade:
    """Satu record paper trade (simulasi)."""
    id: Optional[int]
    pair: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_idr: float          # Jumlah IDR simulasi yang "dipakai"
    score_pct: int               # Skor sinyal saat masuk

    opened_at: float             # Unix timestamp

    # Diisi saat ditutup
    closed: bool                 = False
    close_price: Optional[float] = None
    close_reason: str            = ""    # "TP", "SL", "EXPIRED"
    closed_at: Optional[float]   = None
    pnl_idr: Optional[float]     = None
    pnl_pct: Optional[float]     = None


# ==============================================================================
# DATABASE
# ==============================================================================

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(PAPER_CONFIG.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migration_backup_path(db_path: Path) -> Path:
    return db_path.with_name(f"{db_path.name}{_MIGRATION_BACKUP_SUFFIX}")


def _create_migration_backup(
    source_conn: sqlite3.Connection,
    db_path: Path,
) -> Path:
    backup_path = _migration_backup_path(db_path)
    if backup_path.exists():
        return backup_path

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=db_path.parent,
        prefix=f"{backup_path.name}.",
        suffix=".tmp",
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    backup_conn = None
    try:
        backup_conn = sqlite3.connect(temporary_path)
        source_conn.backup(backup_conn)
        backup_conn.close()
        backup_conn = None
        os.replace(temporary_path, backup_path)
    except Exception:
        if backup_conn is not None:
            backup_conn.close()
        temporary_path.unlink(missing_ok=True)
        raise
    return backup_path


def _migrate_accounting_columns(conn: sqlite3.Connection) -> None:
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(paper_trades)")
    }
    for column, column_type in _ACCOUNTING_COLUMNS.items():
        if column not in existing_columns:
            conn.execute(
                f"ALTER TABLE paper_trades ADD COLUMN {column} {column_type}"
            )


def _quote_identifier(identifier: str) -> str:
    escaped_identifier = identifier.replace('"', '""')
    return f'"{escaped_identifier}"'


def _rebuild_column_declaration(row: sqlite3.Row) -> str:
    name = row["name"]
    column_type = _ACCOUNTING_COLUMNS.get(name, row["type"] or "")
    parts = [_quote_identifier(name), column_type]
    if row["pk"]:
        parts.append("PRIMARY KEY")
        if name == "id" and column_type.upper() == "INTEGER":
            parts.append("AUTOINCREMENT")
    if row["notnull"]:
        parts.append("NOT NULL")
    if row["dflt_value"] is not None:
        parts.extend(("DEFAULT", row["dflt_value"]))
    return " ".join(part for part in parts if part)


def _sqlite_sequence_state(
    conn: sqlite3.Connection,
    table_name: str,
) -> Tuple[bool, Optional[int]]:
    sequence_table_exists = conn.execute("""
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'sqlite_sequence'
    """).fetchone()
    if not sequence_table_exists:
        return False, None
    row = conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = ?", (table_name,)
    ).fetchone()
    return True, int(row["seq"]) if row is not None else None


def _restore_paper_trades_sequence(
    conn: sqlite3.Connection,
    original_sequence: Optional[int],
) -> None:
    _, current_sequence = _sqlite_sequence_state(conn, "paper_trades")
    max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM paper_trades").fetchone()[0]
    target_sequence = max(
        value for value in (original_sequence, current_sequence, max_id) if value is not None
    )
    if current_sequence is None:
        conn.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES ('paper_trades', ?)",
            (target_sequence,),
        )
    elif current_sequence < target_sequence:
        conn.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = 'paper_trades'",
            (target_sequence,),
        )


def _rebuild_accounting_table(conn: sqlite3.Connection) -> None:
    bar_state_schema = conn.execute("""
        SELECT sql FROM sqlite_master
        WHERE type = 'table' AND name = 'paper_trade_bar_state'
    """).fetchone()
    bar_state_columns: list[str] = []
    bar_state_objects: list[str] = []
    if bar_state_schema is not None:
        bar_state_columns = [
            row["name"]
            for row in conn.execute("PRAGMA table_info(paper_trade_bar_state)")
        ]
        bar_state_objects = [
            row["sql"]
            for row in conn.execute("""
                SELECT sql FROM sqlite_master
                WHERE tbl_name = 'paper_trade_bar_state'
                  AND type IN ('index', 'trigger')
                  AND sql IS NOT NULL
                ORDER BY type, name
            """)
        ]
        quoted_bar_columns = ", ".join(
            _quote_identifier(name) for name in bar_state_columns
        )
        bar_state_rebuild = _quote_identifier(_BAR_STATE_REBUILD_TABLE_NAME)
        conn.execute(
            f"CREATE TEMP TABLE {bar_state_rebuild} AS "
            f"SELECT {quoted_bar_columns} FROM paper_trade_bar_state"
        )
        conn.execute("DROP TABLE paper_trade_bar_state")

    _, original_sequence = _sqlite_sequence_state(conn, "paper_trades")
    column_rows = conn.execute("PRAGMA table_info(paper_trades)").fetchall()
    schema_objects = [
        row["sql"]
        for row in conn.execute("""
            SELECT type, name, sql FROM sqlite_master
            WHERE tbl_name = 'paper_trades'
              AND type IN ('index', 'trigger')
              AND sql IS NOT NULL
            ORDER BY type, name
        """)
    ]
    declarations = ",\n            ".join(
        _rebuild_column_declaration(row) for row in column_rows
    )
    rebuild_table = _quote_identifier(_REBUILD_TABLE_NAME)
    conn.execute(f"CREATE TABLE {rebuild_table} ({declarations})")

    column_names = [row["name"] for row in column_rows]
    quoted_columns = ", ".join(_quote_identifier(name) for name in column_names)
    select_values = ", ".join(
        f"CAST({_quote_identifier(name)} AS TEXT)"
        if name in _ACCOUNTING_COLUMNS
        else _quote_identifier(name)
        for name in column_names
    )
    conn.execute(f"""
        INSERT INTO {rebuild_table} ({quoted_columns})
        SELECT {select_values} FROM paper_trades
    """)
    conn.execute("DROP TABLE paper_trades")
    conn.execute(f"ALTER TABLE {rebuild_table} RENAME TO paper_trades")
    _restore_paper_trades_sequence(conn, original_sequence)
    for schema_sql in schema_objects:
        conn.execute(schema_sql)
    if bar_state_schema is not None:
        conn.execute(bar_state_schema["sql"])
        quoted_bar_columns = ", ".join(
            _quote_identifier(name) for name in bar_state_columns
        )
        bar_state_rebuild = _quote_identifier(_BAR_STATE_REBUILD_TABLE_NAME)
        conn.execute(
            f"INSERT INTO paper_trade_bar_state ({quoted_bar_columns}) "
            f"SELECT {quoted_bar_columns} FROM {bar_state_rebuild}"
        )
        for schema_sql in bar_state_objects:
            conn.execute(schema_sql)
        conn.execute(f"DROP TABLE {bar_state_rebuild}")
    _migrate_accounting_columns(conn)


def _create_paper_trades_table(conn: sqlite3.Connection) -> None:
    accounting_columns = ",\n                ".join(
        f"{column} {column_type}" for column, column_type in _ACCOUNTING_COLUMNS.items()
    )
    conn.execute(f"""
        CREATE TABLE paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit REAL NOT NULL,
            position_idr REAL NOT NULL,
            score_pct INTEGER NOT NULL,
            opened_at REAL NOT NULL,
            closed INTEGER DEFAULT 0,
            close_price REAL,
            close_reason TEXT DEFAULT '',
            closed_at REAL,
            pnl_idr REAL,
            pnl_pct REAL,
            {accounting_columns}
        )
    """)


def _create_bar_state_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paper_trade_bar_state (
            trade_id INTEGER PRIMARY KEY,
            first_eligible_bar_id INTEGER NOT NULL,
            last_processed_bar_id INTEGER NOT NULL,
            FOREIGN KEY(trade_id) REFERENCES paper_trades(id)
        )
    """)
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(paper_trade_bar_state)")
    }
    if "first_eligible_bar_id" not in columns:
        backup_path = Path(PAPER_CONFIG.db_path).with_name(
            f"{Path(PAPER_CONFIG.db_path).name}{_BAR_MIGRATION_BACKUP_SUFFIX}"
        )
        if not backup_path.exists():
            descriptor, temporary_name = tempfile.mkstemp(
                dir=backup_path.parent,
                prefix=f"{backup_path.name}.",
                suffix=".tmp",
            )
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            backup_conn = sqlite3.connect(temporary_path)
            try:
                conn.backup(backup_conn)
                backup_conn.close()
                os.replace(temporary_path, backup_path)
            except Exception:
                backup_conn.close()
                temporary_path.unlink(missing_ok=True)
                raise
        conn.execute(
            "ALTER TABLE paper_trade_bar_state "
            "ADD COLUMN first_eligible_bar_id INTEGER"
        )
        rows = conn.execute("""
            SELECT s.trade_id, p.opened_at
            FROM paper_trade_bar_state AS s
            JOIN paper_trades AS p ON p.id = s.trade_id
        """).fetchall()
        for row in rows:
            first_eligible = math.ceil(
                float(row["opened_at"]) / _BAR_SECONDS
            ) * _BAR_SECONDS
            conn.execute("""
                UPDATE paper_trade_bar_state
                SET first_eligible_bar_id=?,
                    last_processed_bar_id=MAX(last_processed_bar_id, ?)
                WHERE trade_id=?
            """, (first_eligible, first_eligible - _BAR_SECONDS, row["trade_id"]))


def _init_db() -> bool:
    """Inisialisasi tabel paper_trades jika belum ada."""
    conn = None
    try:
        conn = _get_conn()
        table_exists = conn.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'paper_trades'
        """).fetchone()
        if table_exists:
            column_rows = conn.execute("PRAGMA table_info(paper_trades)").fetchall()
            column_types = {
                row["name"]: (row["type"] or "").upper() for row in column_rows
            }
            missing_columns = _ACCOUNTING_COLUMNS.keys() - column_types.keys()
            wrong_types = {
                column
                for column, expected_type in _ACCOUNTING_COLUMNS.items()
                if column in column_types
                and column_types[column] != expected_type.upper()
            }
            if missing_columns or wrong_types:
                _create_migration_backup(conn, Path(PAPER_CONFIG.db_path))
                conn.execute("BEGIN IMMEDIATE")
                if wrong_types:
                    _rebuild_accounting_table(conn)
                else:
                    _migrate_accounting_columns(conn)
        else:
            _create_paper_trades_table(conn)
        _create_bar_state_table(conn)
        conn.commit()
        logger.debug("Paper trading DB siap")
        return True
    except Exception as e:
        if conn is not None:
            conn.rollback()
        logger.error(f"Gagal init paper trading DB: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()


def _positive_decimal(value: object, name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except Exception as error:
        raise ValueError(f"{name} must be a decimal number") from error
    if not decimal_value.is_finite() or decimal_value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return decimal_value


def _decimal_storage(value: Decimal) -> str:
    return format(value, "f")


# ==============================================================================
# PAPER TRADER ENGINE
# ==============================================================================

class PaperTrader:
    """Engine untuk paper trading dan analytics."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        candle_fetcher: Optional[
            Callable[[str, str], Iterable[Candle]]
        ] = None,
    ) -> None:
        self._clock = clock
        self._candle_fetcher = candle_fetcher
        _init_db()

    # ------------------------------------------------------------------
    # OPEN & CLOSE
    # ------------------------------------------------------------------

    def open_trade(
        self,
        pair: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_idr: float,
        score_pct: int,
    ) -> int:
        """
        Buka paper trade baru. Mengembalikan ID trade.
        Fee sudah diperhitungkan dari position_idr.
        """
        conn = None
        try:
            entry = _positive_decimal(entry_price, "entry_price")
            stop = _positive_decimal(stop_loss, "stop_loss")
            target = _positive_decimal(take_profit, "take_profit")
            buy = account_buy(
                cash_budget=Decimal(str(position_idr)),
                price=entry,
                fee_rate=Decimal(str(PAPER_CONFIG.buy_fee_pct)),
            )
            opened_at = self._clock()
            conn = _get_conn()
            cursor = conn.execute("""
                INSERT INTO paper_trades
                (pair, entry_price, stop_loss, take_profit, position_idr,
                 score_pct, opened_at, gross_cash_debit, base_qty,
                 buy_notional, buy_fee, cost_model_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pair, float(entry), float(stop), float(target), float(buy.cash_debit),
                score_pct, opened_at, _decimal_storage(buy.cash_debit),
                _decimal_storage(buy.base_qty), _decimal_storage(buy.notional),
                _decimal_storage(buy.fee), _COST_MODEL_ID,
            ))
            trade_id = cursor.lastrowid
            first_eligible_bar_id = math.ceil(opened_at / _BAR_SECONDS) * _BAR_SECONDS
            last_closed_bar_id = first_eligible_bar_id - _BAR_SECONDS
            conn.execute("""
                INSERT INTO paper_trade_bar_state (
                    trade_id, first_eligible_bar_id, last_processed_bar_id
                ) VALUES (?, ?, ?)
            """, (trade_id, first_eligible_bar_id, last_closed_bar_id))
            conn.commit()

            logger.info(
                f"[PAPER] [{pair}] Trade #{trade_id} dibuka | "
                f"Entry: {float(entry):,.0f} | SL: {float(stop):,.0f} | "
                f"TP: {float(target):,.0f} | Simulasi: Rp {float(buy.cash_debit):,.0f}"
            )
            return trade_id
        except Exception as e:
            if conn is not None:
                conn.rollback()
            logger.error(f"[PAPER] Gagal buka trade: {e}")
            return -1
        finally:
            if conn is not None:
                conn.close()

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        reason: str,
        processed_bar_id: Optional[int] = None,
    ) -> Optional[PaperTrade]:
        """Tutup paper trade dan hitung PnL simulasi."""
        conn = None
        try:
            close_price_decimal = _positive_decimal(close_price, "close_price")
            conn = _get_conn()
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM paper_trades WHERE id = ?", (trade_id,)
            ).fetchone()

            if not row or row["closed"]:
                conn.rollback()
                return None

            entry = row["entry_price"]
            position = row["position_idr"]

            if row["cost_model_id"] == _COST_MODEL_ID:
                gross_cash_debit = _positive_decimal(
                    row["gross_cash_debit"], "gross_cash_debit"
                )
                buy = BuyFill(
                    cash_debit=gross_cash_debit,
                    fee=Decimal(str(row["buy_fee"])),
                    notional=Decimal(str(row["buy_notional"])),
                    base_qty=Decimal(str(row["base_qty"])),
                )
                sell = account_sell(
                    base_qty=buy.base_qty,
                    price=close_price_decimal,
                    fee_rate=Decimal(str(PAPER_CONFIG.sell_fee_pct)),
                )
                pnl = realized_pnl(buy, sell)
                pnl_pct_decimal = pnl / gross_cash_debit * Decimal("100")
                pnl_idr = float(pnl)
                pnl_pct = float(pnl_pct_decimal)
                cursor = conn.execute("""
                    UPDATE paper_trades
                    SET closed=1, close_price=?, close_reason=?, closed_at=?,
                        pnl_idr=?, pnl_pct=?, sell_notional=?, sell_fee=?,
                        net_cash_credit=?
                    WHERE id=? AND closed=0
                """, (
                    float(close_price_decimal), reason, self._clock(), pnl_idr, pnl_pct,
                    _decimal_storage(sell.notional), _decimal_storage(sell.fee),
                    _decimal_storage(sell.net_credit),
                    trade_id,
                ))
            else:
                # Legacy rows stored buy notional in position_idr, not gross cash debit.
                entry_decimal = _positive_decimal(entry, "entry_price")
                position_decimal = _positive_decimal(position, "position_idr")
                sell = account_sell(
                    base_qty=position_decimal / entry_decimal,
                    price=close_price_decimal,
                    fee_rate=Decimal(str(PAPER_CONFIG.sell_fee_pct)),
                )
                pnl_decimal = sell.net_credit - position_decimal
                pnl_idr = float(pnl_decimal)
                pnl_pct = float(pnl_decimal / position_decimal * Decimal("100"))
                cursor = conn.execute("""
                    UPDATE paper_trades
                    SET closed=1, close_price=?, close_reason=?,
                        closed_at=?, pnl_idr=?, pnl_pct=?
                    WHERE id=? AND closed=0
                """, (
                    float(close_price_decimal), reason, self._clock(), pnl_idr,
                    pnl_pct, trade_id,
                ))
            if cursor.rowcount != 1:
                conn.rollback()
                return None
            if processed_bar_id is not None:
                checkpoint = conn.execute("""
                    UPDATE paper_trade_bar_state
                    SET last_processed_bar_id=?
                    WHERE trade_id=? AND last_processed_bar_id < ?
                """, (processed_bar_id, trade_id, processed_bar_id))
                if checkpoint.rowcount != 1:
                    conn.rollback()
                    return None
            conn.commit()

            emoji = "🟢" if pnl_idr >= 0 else "🔴"
            logger.info(
                f"[PAPER] Trade #{trade_id} ditutup ({reason}) | "
                f"{emoji} PnL: {pnl_idr:+,.0f} IDR ({pnl_pct:+.2f}%)"
            )

            return PaperTrade(
                id=trade_id,
                pair=row["pair"],
                entry_price=entry,
                stop_loss=row["stop_loss"],
                take_profit=row["take_profit"],
                position_idr=position,
                score_pct=row["score_pct"],
                opened_at=row["opened_at"],
                closed=True,
                close_price=float(close_price_decimal),
                close_reason=reason,
                pnl_idr=pnl_idr,
                pnl_pct=pnl_pct,
            )
        except Exception as e:
            if conn is not None:
                conn.rollback()
            logger.error(f"[PAPER] Gagal tutup trade #{trade_id}: {e}")
            return None
        finally:
            if conn is not None:
                conn.close()

    # ------------------------------------------------------------------
    # MONITOR
    # ------------------------------------------------------------------

    def monitor_all(self) -> List[dict]:
        """
        Cek semua paper trade aktif terhadap candle 15m yang sudah tutup.
        Dipanggil setiap scan oleh main.py (sama seperti position_tracker).
        """
        events = []
        try:
            conn = _get_conn()
            rows = conn.execute("""
                SELECT p.*, s.first_eligible_bar_id, s.last_processed_bar_id
                FROM paper_trades AS p
                LEFT JOIN paper_trade_bar_state AS s ON s.trade_id = p.id
                WHERE p.closed = 0
                ORDER BY p.id
            """).fetchall()
            conn.close()

            fetcher = self._candle_fetcher
            if fetcher is None:
                from indodax_api import fetch_ohlcv

                fetcher = fetch_ohlcv
            now = self._clock()
            bars_by_pair: dict[str, list[Candle] | None] = {}
            for row in rows:
                row_dict = dict(row)
                pair = row_dict["pair"]
                if pair not in bars_by_pair:
                    try:
                        bars_by_pair[pair] = canonicalize_bars(fetcher(pair, "15m"))
                    except ConflictingCandleError:
                        bars_by_pair[pair] = None
                if bars_by_pair[pair] is None:
                    continue
                event = self._check_trade(row_dict, bars_by_pair[pair], now)
                if event:
                    events.append(event)
        except Exception as e:
            logger.error(f"[PAPER] Monitor error: {e}")
        return events

    def _check_trade(
        self,
        row: dict,
        bars: Iterable[Candle],
        now: float,
    ) -> Optional[dict]:
        """Resolve one trade using finalized candle ranges after its state."""
        last_bar_id = row["last_processed_bar_id"]
        if last_bar_id is None:
            first_eligible = math.ceil(
                float(row["opened_at"]) / _BAR_SECONDS
            ) * _BAR_SECONDS
            last_bar_id = first_eligible - _BAR_SECONDS
            self._initialize_bar_state(row["id"], first_eligible, last_bar_id)

        for bar in sorted(bars, key=lambda candle: int(candle.timestamp)):
            bar_id = int(bar.timestamp)
            if bar_id <= last_bar_id or bar_id + _BAR_SECONDS > now:
                continue
            resolution = resolve_barriers(
                bar_high=float(bar.high),
                bar_low=float(bar.low),
                stop_loss=float(row["stop_loss"]),
                take_profit=float(row["take_profit"]),
            )
            if resolution is None:
                self._store_last_bar(row["id"], bar_id)
                last_bar_id = bar_id
                continue
            closed = self.close_trade(
                row["id"], resolution.fill_price, resolution.reason, bar_id
            )
            if closed:
                return {
                    "type": f"PAPER_{resolution.reason}",
                    "trade": closed,
                    "price": resolution.fill_price,
                    "bar_id": bar_id,
                }
        return None

    def _initialize_bar_state(
        self,
        trade_id: int,
        first_eligible_bar_id: int,
        last_processed_bar_id: int,
    ) -> None:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO paper_trade_bar_state (
                    trade_id, first_eligible_bar_id, last_processed_bar_id
                ) VALUES (?, ?, ?)
                ON CONFLICT(trade_id) DO NOTHING
            """, (trade_id, first_eligible_bar_id, last_processed_bar_id))

    def _store_last_bar(self, trade_id: int, bar_id: int) -> None:
        with _get_conn() as conn:
            cursor = conn.execute("""
                UPDATE paper_trade_bar_state
                SET last_processed_bar_id=?
                WHERE trade_id=? AND last_processed_bar_id < ?
            """, (bar_id, trade_id, bar_id))
            if cursor.rowcount != 1:
                raise RuntimeError(f"paper bar checkpoint failed for trade {trade_id}")

    # ------------------------------------------------------------------
    # ANALYTICS ENGINE
    # ------------------------------------------------------------------

    def get_weekly_stats(self) -> dict:
        """
        Hitung statistik performa paper trading untuk 7 hari terakhir.

        Returns dict dengan semua metrik untuk weekly report.
        """
        cutoff = time.time() - (7 * 24 * 3600)

        try:
            conn = _get_conn()
            rows = conn.execute("""
                SELECT * FROM paper_trades
                WHERE opened_at >= ? AND closed = 1
                ORDER BY opened_at ASC
            """, (cutoff,)).fetchall()

            # Total sinyal dikirim (termasuk yang belum ditutup)
            total_signals = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE opened_at >= ?", (cutoff,)
            ).fetchone()[0]

            open_count = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE opened_at >= ? AND closed = 0", (cutoff,)
            ).fetchone()[0]

            conn.close()
        except Exception as e:
            logger.error(f"[PAPER] Gagal hitung weekly stats: {e}")
            return {}

        closed = [dict(r) for r in rows]
        for trade in closed:
            trade["accounting_status"] = (
                _ACCOUNTING_EXACT
                if trade["cost_model_id"] == _COST_MODEL_ID
                else _ACCOUNTING_LEGACY
            )
        exact_accounting_count = sum(
            trade["accounting_status"] == _ACCOUNTING_EXACT for trade in closed
        )
        legacy_accounting_count = len(closed) - exact_accounting_count
        if not closed:
            return {
                "total_signals": total_signals,
                "closed": 0,
                "open": open_count,
                "wins": 0, "losses": 0,
                "win_rate": 0.0,
                "total_pnl_idr": 0.0,
                "avg_pnl_pct": 0.0,
                "accounting_status": _ACCOUNTING_EMPTY,
                "exact_accounting_count": 0,
                "legacy_accounting_count": 0,
                "best_trade": None,
                "worst_trade": None,
                "by_pair": {},
            }

        wins   = [t for t in closed if t["pnl_idr"] >= 0]
        losses = [t for t in closed if t["pnl_idr"] < 0]
        win_rate = (len(wins) / len(closed)) * 100 if closed else 0
        total_pnl = sum(t["pnl_idr"] for t in closed)
        avg_pnl_pct = sum(t["pnl_pct"] for t in closed) / len(closed)
        if exact_accounting_count and legacy_accounting_count:
            accounting_status = _ACCOUNTING_MIXED
        elif exact_accounting_count:
            accounting_status = _ACCOUNTING_EXACT
        else:
            accounting_status = _ACCOUNTING_LEGACY

        best  = max(closed, key=lambda t: t["pnl_idr"])
        worst = min(closed, key=lambda t: t["pnl_idr"])

        # Breakdown per pair
        by_pair: Dict[str, dict] = {}
        for t in closed:
            p = t["pair"]
            if p not in by_pair:
                by_pair[p] = {"count": 0, "wins": 0, "pnl": 0.0}
            by_pair[p]["count"] += 1
            by_pair[p]["pnl"] += t["pnl_idr"]
            if t["pnl_idr"] >= 0:
                by_pair[p]["wins"] += 1

        return {
            "total_signals": total_signals,
            "closed": len(closed),
            "open": open_count,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl_idr": total_pnl,
            "avg_pnl_pct": avg_pnl_pct,
            "accounting_status": accounting_status,
            "exact_accounting_count": exact_accounting_count,
            "legacy_accounting_count": legacy_accounting_count,
            "best_trade": best,
            "worst_trade": worst,
            "by_pair": by_pair,
        }

    def format_weekly_report(self) -> str:
        """Format weekly report sebagai string Markdown untuk Telegram."""
        stats = self.get_weekly_stats()
        if not stats:
            return "❌ Gagal mengambil data weekly report\\."

        if stats["closed"] == 0:
            return (
                "📊 *Weekly Paper Trading Report*\n\n"
                f"`Periode  : 7 hari terakhir`\n"
                f"`Sinyal   : {stats['total_signals']} dikirim`\n"
                f"`Masih open: {stats['open']} trade`\n"
                f"`accounting_status={stats['accounting_status']} "
                f"(exact={stats['exact_accounting_count']}, "
                f"legacy={stats['legacy_accounting_count']})`\n\n"
                "_Belum ada trade yang selesai minggu ini\\._"
            )

        week_str = datetime.now(WIB).strftime("%d %b %Y")
        win_emoji = "🟢" if stats["win_rate"] >= 60 else ("🟡" if stats["win_rate"] >= 40 else "🔴")
        pnl_emoji = "🟢" if stats["total_pnl_idr"] >= 0 else "🔴"
        pnl_sign = "+" if stats["total_pnl_idr"] >= 0 else ""

        # Breakdown per pair
        pair_lines = ""
        for pair, data in sorted(stats["by_pair"].items(), key=lambda x: x[1]["pnl"], reverse=True):
            coin = pair.replace("_idr", "").upper()
            pair_pnl_sign = "+" if data["pnl"] >= 0 else ""
            pair_lines += (
                f"  {coin}: {data['wins']}/{data['count']} menang "
                f"| {pair_pnl_sign}Rp {data['pnl']:,.0f}\n"
            )

        best = stats["best_trade"]
        worst = stats["worst_trade"]
        best_str = (
            f"`  🏆 Best  : {best['pair'].upper()} {best['pnl_pct']:+.1f}% "
            f"(+Rp {best['pnl_idr']:,.0f})`"
            if best else ""
        )
        worst_str = (
            f"`  💀 Worst : {worst['pair'].upper()} {worst['pnl_pct']:+.1f}% "
            f"(Rp {worst['pnl_idr']:,.0f})`"
            if worst else ""
        )

        report = (
            f"📊 *Weekly Paper Trading Report*\n"
            f"`{week_str}`\n\n"
            f"```\n"
            f"  Sinyal dikirim  : {stats['total_signals']}\n"
            f"  Trade selesai   : {stats['closed']}\n"
            f"  Masih open      : {stats['open']}\n"
            f"  ─────────────────────────────\n"
            f"  Menang (TP)     : {stats['wins']} trade\n"
            f"  Kalah  (SL)     : {stats['losses']} trade\n"
            f"  Win Rate        : {win_emoji} {stats['win_rate']:.1f}%\n"
            f"  ─────────────────────────────\n"
            f"  Simulasi PnL    : {pnl_emoji} {pnl_sign}Rp {stats['total_pnl_idr']:,.0f}\n"
            f"  Rata-rata/trade : {stats['avg_pnl_pct']:+.2f}%\n"
            f"  accounting_status={stats['accounting_status']} "
            f"(exact={stats['exact_accounting_count']}, "
            f"legacy={stats['legacy_accounting_count']})\n"
            f"```\n\n"
            f"*Breakdown per Pair:*\n"
            f"`{pair_lines.strip()}`\n\n"
            f"{best_str}\n"
            f"{worst_str}\n\n"
            f"_Ini adalah simulasi\\. Modal nyata tidak terpengaruh\\._"
        )

        return report


# ==============================================================================
# SINGLETON
# ==============================================================================

paper_trader = PaperTrader()
