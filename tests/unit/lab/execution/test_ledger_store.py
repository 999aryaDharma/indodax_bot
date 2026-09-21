"""Tests for ProductionLedgerStore durability and cryptographic hash chaining."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.execution.fill_ingestion import VenueFillIngester
from indodax_lab.execution.indodax_readonly import VenueFill
from indodax_lab.execution.ledger_store import (
    LedgerIntegrityError,
    ProductionLedgerStore,
)

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_ledger_store_initialization(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    store = ProductionLedgerStore(db_path)

    ledger = store.initialize_if_empty(
        initial_cash=Decimal("50000000"),
        valuation_currency="IDR",
        init_timestamp=NOW,
    )
    assert ledger.cash == Decimal("50000000")
    assert store.verify_chain_integrity() is True

    # Re-initialization on populated DB should load existing without error
    ledger2 = store.initialize_if_empty(
        initial_cash=Decimal("99999999"),
        valuation_currency="IDR",
        init_timestamp=NOW,
    )
    assert ledger2.cash == Decimal("50000000")


def test_ledger_store_durability_across_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    store1 = ProductionLedgerStore(db_path)
    ledger1 = store1.initialize_if_empty(
        initial_cash=Decimal("100000000"),
        valuation_currency="IDR",
        init_timestamp=NOW,
    )
    ingester1 = VenueFillIngester(ledger=ledger1, ledger_store=store1)

    fill1 = VenueFill(
        fill_id="f1",
        order_id="ord1",
        client_order_id="cl1",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("1000000000"),
        qty=Decimal("0.05"),
        quote_qty=Decimal("50000000"),
        commission=Decimal("50000"),
        commission_asset="idr",
        timestamp=NOW + timedelta(seconds=1),
    )
    res = ingester1.ingest_fill(fill1)
    assert res.status == "INGESTED"

    expected_cash = Decimal("49950000")
    assert ledger1.cash == expected_cash
    assert store1.verify_chain_integrity() is True
    assert store1.is_fill_recorded("f1") is True

    # SIMULATE CRASH & RESTART
    del ingester1
    del ledger1
    del store1

    store2 = ProductionLedgerStore(db_path)
    assert store2.verify_chain_integrity() is True
    ledger2 = store2.load_ledger()
    assert ledger2.cash == expected_cash
    assert ledger2.get_position("btc_idr").base_qty == Decimal("0.05")
    assert store2.is_fill_recorded("f1") is True
    assert store2.get_processed_fill_ids() == {"f1"}


def test_ledger_store_tamper_detection(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    store = ProductionLedgerStore(db_path)
    ledger = store.initialize_if_empty(
        initial_cash=Decimal("10000000"),
        valuation_currency="IDR",
        init_timestamp=NOW,
    )
    ingester = VenueFillIngester(ledger=ledger, ledger_store=store)

    fill = VenueFill(
        fill_id="f_tamper",
        order_id="ord_t",
        client_order_id="cl_t",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        price=Decimal("500000000"),
        qty=Decimal("0.01"),
        quote_qty=Decimal("5000000"),
        commission=Decimal("5000"),
        commission_asset="idr",
        timestamp=NOW + timedelta(seconds=1),
    )
    ingester.ingest_fill(fill)
    assert store.verify_chain_integrity() is True

    # Malicious direct modification of transaction table
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE ledger_transactions SET base_qty_delta = '999.0' WHERE fill_id = 'f_tamper'"
        )
        conn.commit()

    with pytest.raises(LedgerIntegrityError, match="ENTRY_HASH_MISMATCH"):
        store.verify_chain_integrity()


def test_ledger_store_snapshot_tamper_detection(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite3"
    store = ProductionLedgerStore(db_path)
    store.initialize_if_empty(
        initial_cash=Decimal("10000000"),
        valuation_currency="IDR",
        init_timestamp=NOW,
    )

    # Malicious direct modification of snapshot JSON
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE ledger_snapshots SET state_json = '{\"hacked\": true}' WHERE snapshot_id = 1"
        )
        conn.commit()

    with pytest.raises(LedgerIntegrityError, match="LEDGER_SNAPSHOT_CORRUPTED"):
        store.load_ledger()
