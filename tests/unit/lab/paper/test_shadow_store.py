"""Durability and corruption tests for the shadow SQLite state boundary."""

import sqlite3
from pathlib import Path

import pytest

from indodax_lab.paper.shadow_store import ShadowStateCorruptionError, ShadowStateStore


def test_shadow_store_roundtrip_and_wal(tmp_path: Path) -> None:
    path = tmp_path / "shadow.sqlite3"
    store = ShadowStateStore(path)
    payload = {"available_cash": "500000.00", "open_positions": {}}
    store.save_checkpoint(
        payload,
        event_id="evt-1",
        event_type="TEST",
        event_payload={"reason": "roundtrip"},
    )
    assert store.load_checkpoint() == payload

    with sqlite3.connect(path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM shadow_events").fetchone()[0]
    assert mode.lower() == "wal"
    assert event_count == 1


def test_shadow_store_corruption_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "shadow.sqlite3"
    store = ShadowStateStore(path)
    store.save_checkpoint({"available_cash": "500000.00"})
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE shadow_checkpoint SET payload = ? WHERE singleton = 1",
            ('{"available_cash":"999999999"}',),
        )
        conn.commit()

    with pytest.raises(ShadowStateCorruptionError, match="HASH_MISMATCH"):
        store.load_checkpoint()
