"""Tests for durable reconciliation cursor persistence."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from indodax_lab.execution.reconciliation_store import (
    ReconciliationCursorConcurrencyError,
    ReconciliationCursorCorruptionError,
    ReconciliationCursorStore,
)

NOW = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)


def test_cursor_initializes_and_advances_with_overlap(tmp_path):
    store = ReconciliationCursorStore(tmp_path / "reconciliation.sqlite3")
    cursor = store.initialize(
        scope_id="prod-idr",
        start_ms=1_000_000,
        at=NOW,
    )

    advanced = store.advance_after_healthy(
        cursor,
        observed_end_ms=1_020_000,
        overlap_ms=5_000,
        at=NOW,
    )

    assert advanced.next_start_ms == 1_015_000
    assert advanced.revision == 2
    assert ReconciliationCursorStore(store.path).load("prod-idr") == advanced


def test_stale_cursor_writer_is_rejected(tmp_path):
    store = ReconciliationCursorStore(tmp_path / "reconciliation.sqlite3")
    cursor = store.initialize(
        scope_id="prod-idr",
        start_ms=1_000_000,
        at=NOW,
    )
    store.advance_after_healthy(
        cursor,
        observed_end_ms=1_020_000,
        at=NOW,
    )

    with pytest.raises(
        ReconciliationCursorConcurrencyError,
        match="RECONCILIATION_CURSOR_STALE_WRITER",
    ):
        store.advance_after_healthy(
            cursor,
            observed_end_ms=1_030_000,
            at=NOW,
        )


def test_cursor_tampering_fails_closed(tmp_path):
    path = tmp_path / "reconciliation.sqlite3"
    store = ReconciliationCursorStore(path)
    store.initialize(
        scope_id="prod-idr",
        start_ms=1_000_000,
        at=NOW,
    )

    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE reconciliation_cursors SET payload = ? WHERE scope_id = ?",
            ("{}", "prod-idr"),
        )
        conn.commit()

    with pytest.raises(
        ReconciliationCursorCorruptionError,
        match="RECONCILIATION_CURSOR_HASH_MISMATCH",
    ):
        store.load("prod-idr")
