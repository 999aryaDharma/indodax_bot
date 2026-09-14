import importlib
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

import config

NEW_ACCOUNTING_COLUMNS = {
    "gross_cash_debit",
    "base_qty",
    "buy_notional",
    "buy_fee",
    "sell_notional",
    "sell_fee",
    "net_cash_credit",
    "cost_model_id",
}
AUTHORITATIVE_DECIMAL_COLUMNS = NEW_ACCOUNTING_COLUMNS - {"cost_model_id"}


def _create_legacy_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
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
                pnl_pct REAL
            )
        """)
        conn.execute("""
            INSERT INTO paper_trades (
                pair, entry_price, stop_loss, take_profit,
                position_idr, score_pct, opened_at
            ) VALUES ('btc_idr', 10000, 9000, 11000, 99800, 80, 1)
        """)


def _create_v1_real_accounting_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
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
                gross_cash_debit REAL,
                base_qty REAL,
                buy_notional REAL,
                buy_fee REAL,
                sell_notional REAL,
                sell_fee REAL,
                net_cash_credit REAL,
                cost_model_id TEXT
            );
            INSERT INTO paper_trades (
                pair, entry_price, stop_loss, take_profit,
                position_idr, score_pct, opened_at
            ) VALUES ('btc_idr', 10000, 9000, 11000, 99800, 80, 1);
            INSERT INTO paper_trades (
                pair, entry_price, stop_loss, take_profit,
                position_idr, score_pct, opened_at, gross_cash_debit,
                base_qty, buy_notional, buy_fee, cost_model_id
            ) VALUES (
                'eth_idr', 10000, 9000, 11000, 100000, 85, 2,
                100000, 9.98, 99800, 200, 'cash_debit_v1'
            );
            INSERT INTO paper_trades (
                id, pair, entry_price, stop_loss, take_profit,
                position_idr, score_pct, opened_at
            ) VALUES (50, 'deleted_idr', 1, 1, 1, 1, 1, 3);
            DELETE FROM paper_trades WHERE id = 50;
            CREATE INDEX paper_trades_pair_idx ON paper_trades(pair);
            CREATE TABLE paper_trade_audit (trade_id INTEGER NOT NULL);
            CREATE TRIGGER paper_trades_insert_audit
            AFTER INSERT ON paper_trades
            BEGIN
                INSERT INTO paper_trade_audit(trade_id) VALUES (NEW.id);
            END;
        """)


def _point_module_at_db(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    db_path: Path,
) -> None:
    monkeypatch.setattr(
        module,
        "PAPER_CONFIG",
        replace(module.PAPER_CONFIG, db_path=str(db_path)),
    )


def _open_and_close_exact_trade(module: ModuleType, pair: str = "eth_idr") -> int:
    trade_id = module.paper_trader.open_trade(
        pair=pair,
        entry_price=10000,
        stop_loss=9000,
        take_profit=11000,
        position_idr=100000,
        score_pct=85,
    )
    assert module.paper_trader.close_trade(trade_id, 11000, "TP") is not None
    return trade_id


@pytest.fixture
def paper_trader_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    db_path = tmp_path / "paper_trades.db"
    _create_legacy_db(db_path)
    paper_config = replace(
        config.PAPER_CONFIG,
        db_path=str(db_path),
        buy_fee_pct=0.002,
        sell_fee_pct=0.004,
    )
    monkeypatch.setattr(config, "PAPER_CONFIG", paper_config)
    sys.modules.pop("paper_trader", None)
    module = importlib.import_module("paper_trader")
    yield module
    sys.modules.pop("paper_trader", None)


def test_migration_adds_nullable_accounting_columns_without_rewriting_legacy_row(
    paper_trader_module: ModuleType,
) -> None:
    module = paper_trader_module

    assert module._init_db() is True

    with module._get_conn() as conn:
        column_rows = conn.execute("PRAGMA table_info(paper_trades)").fetchall()
        columns = [row["name"] for row in column_rows]
        column_types = {row["name"]: row["type"] for row in column_rows}
        legacy = conn.execute(
            "SELECT gross_cash_debit, base_qty, buy_notional, buy_fee, "
            "sell_notional, sell_fee, net_cash_credit, cost_model_id "
            "FROM paper_trades WHERE id = 1"
        ).fetchone()

    assert NEW_ACCOUNTING_COLUMNS.issubset(columns)
    assert all(columns.count(column) == 1 for column in NEW_ACCOUNTING_COLUMNS)
    assert all(column_types[column] == "TEXT" for column in NEW_ACCOUNTING_COLUMNS)
    assert tuple(legacy) == (None,) * len(NEW_ACCOUNTING_COLUMNS)


def test_migration_creates_one_deterministic_legacy_backup_before_schema_change(
    paper_trader_module: ModuleType,
) -> None:
    module = paper_trader_module
    backup_path = module._migration_backup_path(Path(module.PAPER_CONFIG.db_path))
    initial_mtime = backup_path.stat().st_mtime_ns

    assert module._init_db() is True

    assert backup_path.exists()
    assert backup_path.stat().st_mtime_ns == initial_mtime
    with sqlite3.connect(backup_path) as backup:
        columns = [row[1] for row in backup.execute("PRAGMA table_info(paper_trades)")]
        legacy_position = backup.execute(
            "SELECT position_idr FROM paper_trades WHERE id = 1"
        ).fetchone()[0]
    assert NEW_ACCOUNTING_COLUMNS.isdisjoint(columns)
    assert legacy_position == 99800


def test_backup_failure_aborts_migration_without_mutating_original(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = paper_trader_module
    db_path = tmp_path / "backup-failure.db"
    _create_legacy_db(db_path)
    _point_module_at_db(module, monkeypatch, db_path)

    def fail_backup(*_args, **_kwargs) -> None:
        raise OSError("simulated backup failure")

    monkeypatch.setattr(module, "_create_migration_backup", fail_backup, raising=False)

    assert module._init_db() is False

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(paper_trades)")]
        legacy_position = conn.execute(
            "SELECT position_idr FROM paper_trades WHERE id = 1"
        ).fetchone()[0]
    assert NEW_ACCOUNTING_COLUMNS.isdisjoint(columns)
    assert legacy_position == 99800


def test_migration_failure_rolls_back_original_and_keeps_recovery_backup(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = paper_trader_module
    db_path = tmp_path / "migration-failure.db"
    _create_legacy_db(db_path)
    _point_module_at_db(module, monkeypatch, db_path)

    def fail_after_first_column(conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE paper_trades ADD COLUMN gross_cash_debit TEXT")
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(module, "_migrate_accounting_columns", fail_after_first_column)

    assert module._init_db() is False

    backup_path = module._migration_backup_path(db_path)
    with sqlite3.connect(db_path) as original:
        original_columns = [
            row[1] for row in original.execute("PRAGMA table_info(paper_trades)")
        ]
    with sqlite3.connect(backup_path) as backup:
        backup_columns = [
            row[1] for row in backup.execute("PRAGMA table_info(paper_trades)")
        ]
        legacy_position = backup.execute(
            "SELECT position_idr FROM paper_trades WHERE id = 1"
        ).fetchone()[0]
    assert NEW_ACCOUNTING_COLUMNS.isdisjoint(original_columns)
    assert NEW_ACCOUNTING_COLUMNS.isdisjoint(backup_columns)
    assert legacy_position == 99800


def test_v1_real_accounting_schema_rebuilds_to_text_and_preserves_owned_objects(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = paper_trader_module
    db_path = tmp_path / "v1-real-accounting.db"
    _create_v1_real_accounting_db(db_path)
    _point_module_at_db(module, monkeypatch, db_path)
    backup_path = module._migration_backup_path(db_path)

    assert module._init_db() is True

    assert backup_path.exists()
    initial_backup_mtime = backup_path.stat().st_mtime_ns
    with module._get_conn() as conn:
        column_types = {
            row["name"]: row["type"]
            for row in conn.execute("PRAGMA table_info(paper_trades)")
        }
        rows = conn.execute(
            "SELECT id, pair, position_idr, score_pct, opened_at, "
            "gross_cash_debit, base_qty, buy_notional, buy_fee, cost_model_id "
            "FROM paper_trades ORDER BY id"
        ).fetchall()
        owned_objects = {
            (row["type"], row["name"])
            for row in conn.execute("""
                SELECT type, name FROM sqlite_master
                WHERE tbl_name = 'paper_trades' AND type IN ('index', 'trigger')
            """)
        }
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM paper_trade_audit"
        ).fetchone()[0]
        migrated_sequence = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'paper_trades'"
        ).fetchone()[0]

    assert all(
        column_types[column] == "TEXT" for column in AUTHORITATIVE_DECIMAL_COLUMNS
    )
    assert len(rows) == 2
    assert tuple(rows[0]) == (1, "btc_idr", 99800, 80, 1, None, None, None, None, None)
    assert rows[1][0:5] == (2, "eth_idr", 100000, 85, 2)
    assert Decimal(str(rows[1][5])) == Decimal("100000")
    assert Decimal(str(rows[1][6])) == Decimal("9.98")
    assert Decimal(str(rows[1][7])) == Decimal("99800")
    assert Decimal(str(rows[1][8])) == Decimal("200")
    assert rows[1][9] == "cash_debit_v1"
    assert owned_objects == {
        ("index", "paper_trades_pair_idx"),
        ("trigger", "paper_trades_insert_audit"),
    }
    assert audit_count == 0
    assert migrated_sequence == 50

    assert module._init_db() is True
    assert backup_path.stat().st_mtime_ns == initial_backup_mtime
    with module._get_conn() as conn:
        idempotent_sequence = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'paper_trades'"
        ).fetchone()[0]
    assert idempotent_sequence == 50

    with sqlite3.connect(backup_path) as backup:
        backup_types = {
            row[1]: row[2] for row in backup.execute("PRAGMA table_info(paper_trades)")
        }
        backup_count = backup.execute(
            "SELECT COUNT(*) FROM paper_trades"
        ).fetchone()[0]
        backup_sequence = backup.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'paper_trades'"
        ).fetchone()[0]
    assert all(
        backup_types[column] == "REAL" for column in AUTHORITATIVE_DECIMAL_COLUMNS
    )
    assert backup_count == 2
    assert backup_sequence == 50

    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(
        module,
        "PAPER_CONFIG",
        replace(module.PAPER_CONFIG, buy_fee_pct=0, sell_fee_pct=0),
    )
    cash_budget = Decimal("123456789.123456789123456789")
    trade_id = module.paper_trader.open_trade(
        pair="xrp_idr",
        entry_price=Decimal("10"),
        stop_loss=Decimal("9"),
        take_profit=Decimal("11"),
        position_idr=cash_budget,
        score_pct=90,
    )
    assert module.paper_trader.close_trade(trade_id, Decimal("10"), "TP") is not None

    with module._get_conn() as conn:
        exact = conn.execute("""
            SELECT gross_cash_debit, typeof(gross_cash_debit),
                   base_qty, typeof(base_qty),
                   buy_notional, typeof(buy_notional),
                   sell_notional, typeof(sell_notional),
                   net_cash_credit, typeof(net_cash_credit)
            FROM paper_trades WHERE id = ?
        """, (trade_id,)).fetchone()
        audited_trade_ids = [
            row[0] for row in conn.execute("SELECT trade_id FROM paper_trade_audit")
        ]

    assert trade_id == 51
    assert tuple(exact) == (
        "123456789.123456789123456789", "text",
        "12345678.9123456789123456789", "text",
        "123456789.123456789123456789", "text",
        "123456789.1234567891234567890", "text",
        "123456789.1234567891234567890", "text",
    )
    assert audited_trade_ids == [51]


def test_bar_state_migration_preserves_later_checkpoint(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = paper_trader_module
    db_path = tmp_path / "bar-state-checkpoint.db"
    _create_legacy_db(db_path)
    with sqlite3.connect(db_path) as conn:
        for column in sorted(AUTHORITATIVE_DECIMAL_COLUMNS):
            conn.execute(f"ALTER TABLE paper_trades ADD COLUMN {column} TEXT")
        conn.execute("ALTER TABLE paper_trades ADD COLUMN cost_model_id TEXT")
        conn.executescript("""
            CREATE TABLE paper_trade_bar_state (
                trade_id INTEGER PRIMARY KEY,
                last_processed_bar_id INTEGER NOT NULL,
                FOREIGN KEY(trade_id) REFERENCES paper_trades(id)
            );
            INSERT INTO paper_trade_bar_state (trade_id, last_processed_bar_id)
            VALUES (1, 3600);
        """)
    _point_module_at_db(module, monkeypatch, db_path)

    assert module._init_db() is True

    with module._get_conn() as conn:
        state = conn.execute(
            "SELECT first_eligible_bar_id, last_processed_bar_id "
            "FROM paper_trade_bar_state WHERE trade_id = 1"
        ).fetchone()
    assert tuple(state) == (900, 3600)


def test_real_accounting_rebuild_preserves_existing_bar_state_foreign_key(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = paper_trader_module
    db_path = tmp_path / "v1-real-with-bar-state.db"
    _create_v1_real_accounting_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript("""
            CREATE TABLE paper_trade_bar_state (
                trade_id INTEGER PRIMARY KEY,
                first_eligible_bar_id INTEGER NOT NULL,
                last_processed_bar_id INTEGER NOT NULL,
                FOREIGN KEY(trade_id) REFERENCES paper_trades(id)
            );
            INSERT INTO paper_trade_bar_state (
                trade_id, first_eligible_bar_id, last_processed_bar_id
            ) VALUES (2, 900, 3600);
        """)
    _point_module_at_db(module, monkeypatch, db_path)
    backup_path = module._migration_backup_path(db_path)

    assert module._init_db() is True

    assert backup_path.exists()
    with module._get_conn() as conn:
        types = {
            row["name"]: row["type"]
            for row in conn.execute("PRAGMA table_info(paper_trades)")
        }
        state = conn.execute(
            "SELECT trade_id, first_eligible_bar_id, last_processed_bar_id "
            "FROM paper_trade_bar_state"
        ).fetchone()
        sequence = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'paper_trades'"
        ).fetchone()[0]
        owned_objects = {
            (row["type"], row["name"])
            for row in conn.execute("""
                SELECT type, name FROM sqlite_master
                WHERE tbl_name = 'paper_trades' AND type IN ('index', 'trigger')
            """)
        }
        foreign_key_violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    with sqlite3.connect(backup_path) as backup:
        backup_types = {
            row[1]: row[2]
            for row in backup.execute("PRAGMA table_info(paper_trades)")
        }
        backup_state = backup.execute(
            "SELECT trade_id, first_eligible_bar_id, last_processed_bar_id "
            "FROM paper_trade_bar_state"
        ).fetchone()

    assert all(types[column] == "TEXT" for column in AUTHORITATIVE_DECIMAL_COLUMNS)
    assert all(
        backup_types[column] == "REAL"
        for column in AUTHORITATIVE_DECIMAL_COLUMNS
    )
    assert tuple(state) == (2, 900, 3600)
    assert backup_state == (2, 900, 3600)
    assert foreign_key_violations == []
    assert sequence == 50
    assert owned_objects == {
        ("index", "paper_trades_pair_idx"),
        ("trigger", "paper_trades_insert_audit"),
    }


def test_v1_real_schema_rebuild_failure_rolls_back_and_keeps_backup(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = paper_trader_module
    db_path = tmp_path / "v1-real-rebuild-failure.db"
    _create_v1_real_accounting_db(db_path)
    _point_module_at_db(module, monkeypatch, db_path)

    def fail_during_rebuild(conn: sqlite3.Connection) -> None:
        conn.execute(
            "ALTER TABLE paper_trades RENAME TO paper_trades_rebuild_failed"
        )
        raise RuntimeError("simulated rebuild failure")

    monkeypatch.setattr(
        module,
        "_rebuild_accounting_table",
        fail_during_rebuild,
        raising=False,
    )

    assert module._init_db() is False

    backup_path = module._migration_backup_path(db_path)
    assert backup_path.exists()
    with sqlite3.connect(db_path) as original:
        original_types = {
            row[1]: row[2]
            for row in original.execute("PRAGMA table_info(paper_trades)")
        }
        original_count = original.execute(
            "SELECT COUNT(*) FROM paper_trades"
        ).fetchone()[0]
        original_objects = {
            (row[0], row[1])
            for row in original.execute("""
                SELECT type, name FROM sqlite_master
                WHERE tbl_name = 'paper_trades' AND type IN ('index', 'trigger')
            """)
        }
        original_sequence = original.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'paper_trades'"
        ).fetchone()[0]
    with sqlite3.connect(backup_path) as backup:
        backup_count = backup.execute(
            "SELECT COUNT(*) FROM paper_trades"
        ).fetchone()[0]
        backup_sequence = backup.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'paper_trades'"
        ).fetchone()[0]

    assert all(
        original_types[column] == "REAL" for column in AUTHORITATIVE_DECIMAL_COLUMNS
    )
    assert original_count == 2
    assert backup_count == 2
    assert original_sequence == 50
    assert backup_sequence == 50
    assert original_objects == {
        ("index", "paper_trades_pair_idx"),
        ("trigger", "paper_trades_insert_audit"),
    }


def test_new_trade_persists_exact_cost_basis_fees_and_net_proceeds(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = paper_trader_module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)

    trade_id = module.paper_trader.open_trade(
        pair="eth_idr",
        entry_price=10000,
        stop_loss=9000,
        take_profit=11000,
        position_idr=100000,
        score_pct=85,
    )
    closed = module.paper_trader.close_trade(trade_id, 11000, "TP")

    with module._get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM paper_trades WHERE id = ?", (trade_id,)
        ).fetchone()

    assert trade_id > 0
    assert closed is not None
    assert Decimal(str(row["position_idr"])) == Decimal("100000")
    assert Decimal(str(row["gross_cash_debit"])) == Decimal("100000")
    assert Decimal(str(row["base_qty"])) == Decimal("9.98")
    assert Decimal(str(row["buy_notional"])) == Decimal("99800")
    assert Decimal(str(row["buy_fee"])) == Decimal("200")
    assert Decimal(str(row["sell_notional"])) == Decimal("109780")
    assert Decimal(str(row["sell_fee"])) == Decimal("439.12")
    assert Decimal(str(row["net_cash_credit"])) == Decimal("109340.88")
    assert Decimal(str(row["pnl_idr"])) == Decimal("9340.88")
    assert Decimal(str(row["pnl_pct"])) == Decimal("9.34088")
    assert row["cost_model_id"] == "cash_debit_v1"


def test_authoritative_decimal_fields_round_trip_as_canonical_text_without_float_loss(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = paper_trader_module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(
        module,
        "PAPER_CONFIG",
        replace(module.PAPER_CONFIG, buy_fee_pct=0, sell_fee_pct=0),
    )
    cash_budget = Decimal("123456789.123456789123456789")

    trade_id = module.paper_trader.open_trade(
        pair="xrp_idr",
        entry_price=Decimal("10"),
        stop_loss=Decimal("9"),
        take_profit=Decimal("11"),
        position_idr=cash_budget,
        score_pct=90,
    )
    closed = module.paper_trader.close_trade(trade_id, Decimal("10"), "TP")

    with module._get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM paper_trades WHERE id = ?", (trade_id,)
        ).fetchone()

    assert closed is not None
    assert row["gross_cash_debit"] == "123456789.123456789123456789"
    assert row["buy_notional"] == "123456789.123456789123456789"
    assert row["base_qty"] == "12345678.9123456789123456789"
    assert row["buy_fee"] == "0.000000000000000000"
    assert row["sell_notional"] == "123456789.1234567891234567890"
    assert row["sell_fee"] == "0.0000000000000000000"
    assert row["net_cash_credit"] == "123456789.1234567891234567890"
    assert Decimal(str(row["pnl_idr"])) == Decimal("0")


@pytest.mark.parametrize(
    ("entry_price", "stop_loss", "take_profit", "position_idr"),
    [
        (0, 9000, 11000, 100000),
        (-1, 9000, 11000, 100000),
        (float("nan"), 9000, 11000, 100000),
        (10000, 0, 11000, 100000),
        (10000, 9000, float("inf"), 100000),
        (10000, 9000, 11000, 0),
        (10000, 9000, 11000, -1),
    ],
)
def test_open_trade_rejects_invalid_inputs_without_inserting(
    paper_trader_module: ModuleType,
    entry_price,
    stop_loss,
    take_profit,
    position_idr,
) -> None:
    module = paper_trader_module

    result = module.paper_trader.open_trade(
        pair="eth_idr",
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_idr=position_idr,
        score_pct=85,
    )

    with module._get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0]
    assert result == -1
    assert count == 1


@pytest.mark.parametrize("close_price", [0, -1, float("nan"), float("inf")])
def test_close_trade_rejects_invalid_price_and_leaves_trade_open(
    paper_trader_module: ModuleType,
    close_price,
) -> None:
    module = paper_trader_module

    result = module.paper_trader.close_trade(1, close_price, "TP")

    with module._get_conn() as conn:
        closed = conn.execute(
            "SELECT closed FROM paper_trades WHERE id = 1"
        ).fetchone()[0]
    assert result is None
    assert closed == 0


def test_weekly_report_marks_legacy_accounting_as_estimated(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = paper_trader_module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)

    closed = module.paper_trader.close_trade(1, 11000, "TP")
    stats = module.paper_trader.get_weekly_stats()
    report = module.paper_trader.format_weekly_report()

    with module._get_conn() as conn:
        legacy = conn.execute(
            "SELECT gross_cash_debit, base_qty, buy_notional, buy_fee, "
            "sell_notional, sell_fee, net_cash_credit, cost_model_id "
            "FROM paper_trades WHERE id = 1"
        ).fetchone()

    assert closed is not None
    assert tuple(legacy) == (None,) * len(NEW_ACCOUNTING_COLUMNS)
    assert stats["accounting_status"] == "LEGACY_ESTIMATE"
    assert stats["exact_accounting_count"] == 0
    assert stats["legacy_accounting_count"] == 1
    assert stats["best_trade"]["accounting_status"] == "LEGACY_ESTIMATE"
    assert "accounting_status=LEGACY_ESTIMATE" in report


def test_weekly_stats_marks_all_exact_accounting(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = paper_trader_module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    _open_and_close_exact_trade(module)

    stats = module.paper_trader.get_weekly_stats()
    report = module.paper_trader.format_weekly_report()

    assert stats["accounting_status"] == "EXACT"
    assert stats["exact_accounting_count"] == 1
    assert stats["legacy_accounting_count"] == 0
    assert "accounting_status=EXACT (exact=1, legacy=0)" in report


def test_weekly_stats_distinguishes_mixed_accounting_from_all_legacy(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = paper_trader_module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    assert module.paper_trader.close_trade(1, 11000, "TP") is not None
    _open_and_close_exact_trade(module)

    stats = module.paper_trader.get_weekly_stats()
    report = module.paper_trader.format_weekly_report()

    assert stats["accounting_status"] == "MIXED"
    assert stats["exact_accounting_count"] == 1
    assert stats["legacy_accounting_count"] == 1
    assert "accounting_status=MIXED (exact=1, legacy=1)" in report


def test_empty_weekly_stats_include_accounting_status_and_zero_counts(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = paper_trader_module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)

    stats = module.paper_trader.get_weekly_stats()

    assert stats["closed"] == 0
    assert stats["accounting_status"] == "NO_CLOSED_TRADES"
    assert stats["exact_accounting_count"] == 0
    assert stats["legacy_accounting_count"] == 0


class _CoordinatedCursor:
    def __init__(
        self,
        cursor: sqlite3.Cursor,
        connection: "_CoordinatedConnection",
        synchronize_stale_read: bool,
    ) -> None:
        self._cursor = cursor
        self._connection = connection
        self._synchronize_stale_read = synchronize_stale_read

    def fetchone(self):
        row = self._cursor.fetchone()
        if self._synchronize_stale_read and not self._connection.transactional_close:
            self._connection.stale_read_barrier.wait(timeout=2)
        return row

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _CoordinatedConnection:
    def __init__(
        self,
        connection: sqlite3.Connection,
        index: int,
        stale_read_barrier: threading.Barrier,
        first_commit: threading.Event,
    ) -> None:
        self._connection = connection
        self.index = index
        self.stale_read_barrier = stale_read_barrier
        self.first_commit = first_commit
        self.transactional_close = False

    def execute(self, sql: str, parameters=()):
        normalized = " ".join(sql.split()).upper()
        if normalized == "BEGIN IMMEDIATE":
            self.transactional_close = True
        if (
            normalized.startswith("UPDATE PAPER_TRADES")
            and self.index == 1
            and not self.transactional_close
        ):
            assert self.first_commit.wait(timeout=2)
        cursor = self._connection.execute(sql, parameters)
        synchronize = normalized.startswith(
            "SELECT * FROM PAPER_TRADES WHERE ID = ?"
        )
        return _CoordinatedCursor(cursor, self, synchronize)

    def commit(self) -> None:
        self._connection.commit()
        if self.index == 0:
            self.first_commit.set()

    def __getattr__(self, name):
        return getattr(self._connection, name)


def test_two_connections_cannot_both_successfully_close_the_same_trade(
    paper_trader_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = paper_trader_module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    trade_id = module.paper_trader.open_trade(
        pair="eth_idr",
        entry_price=10000,
        stop_loss=9000,
        take_profit=11000,
        position_idr=100000,
        score_pct=85,
    )
    db_path = module.PAPER_CONFIG.db_path
    stale_read_barrier = threading.Barrier(2)
    first_commit = threading.Event()
    connection_count = 0
    connection_count_lock = threading.Lock()

    def coordinated_connection() -> _CoordinatedConnection:
        nonlocal connection_count
        with connection_count_lock:
            index = connection_count
            connection_count += 1
        conn = sqlite3.connect(db_path, timeout=2)
        conn.row_factory = sqlite3.Row
        return _CoordinatedConnection(conn, index, stale_read_barrier, first_commit)

    monkeypatch.setattr(module, "_get_conn", coordinated_connection)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(module.paper_trader.close_trade, trade_id, 11000, reason)
            for reason in ("TP-A", "TP-B")
        ]
        results = [future.result(timeout=5) for future in futures]

    assert sum(result is not None for result in results) == 1
    assert sum(result is None for result in results) == 1
