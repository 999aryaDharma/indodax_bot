"""Unit tests for operator CLI tools: approval, kill_switch, and reconcile."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.cli.approval import main as approval_main
from indodax_lab.cli.kill_switch import main as kill_switch_main
from indodax_lab.cli.reconcile import main as reconcile_main
from indodax_lab.control.approval import ManualApprovalStore
from indodax_lab.execution.oms import OmsOrder


def test_kill_switch_cli_lifecycle(tmp_path: Path) -> None:
    sentinel = tmp_path / "emergency_kill_switch"

    # 1. Initial status: inactive
    out = io.StringIO()
    code = kill_switch_main(["--sentinel-path", str(sentinel), "status"], stdout=out)
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["kill_switch_active"] is False

    # 2. Trip kill switch
    out = io.StringIO()
    code = kill_switch_main(
        ["--sentinel-path", str(sentinel), "trip", "--reason", "TEST_HALT"],
        stdout=out,
    )
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["action"] == "TRIPPED"
    assert sentinel.exists()

    # 3. Status: active
    out = io.StringIO()
    code = kill_switch_main(["--sentinel-path", str(sentinel), "status"], stdout=out)
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["kill_switch_active"] is True
    assert "TEST_HALT" in res["details"]

    # 4. Clear kill switch
    out = io.StringIO()
    code = kill_switch_main(["--sentinel-path", str(sentinel), "clear"], stdout=out)
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["action"] == "CLEARED"
    assert not sentinel.exists()


def test_approval_cli_lifecycle(tmp_path: Path) -> None:
    store_file = tmp_path / "approvals.json"
    store = ManualApprovalStore(persistence_path=store_file)

    now = datetime.now(UTC)
    order = OmsOrder(
        internal_order_id="ord_test_01",
        client_order_id="clord_btc_01",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
        created_at=now,
        updated_at=now,
    )
    prop = store.propose(order, at=now, ttl_seconds=300)

    # 1. List pending
    out = io.StringIO()
    code = approval_main(["--store-path", str(store_file), "list"], stdout=out)
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["count"] == 1
    assert res["proposals"][0]["proposal_id"] == prop.proposal_id

    # 2. Approve proposal
    out = io.StringIO()
    code = approval_main(
        [
            "--store-path",
            str(store_file),
            "approve",
            prop.proposal_id,
            "--operator-id",
            "op_alice",
            "--reason",
            "Approved for testing",
        ],
        stdout=out,
    )
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["ok"] is True
    assert res["action"] == "APPROVED"
    assert res["proposal"]["decided_by"] == "op_alice"

    # 3. List pending should now be empty
    out = io.StringIO()
    code = approval_main(["--store-path", str(store_file), "list"], stdout=out)
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["count"] == 0

    # 4. List ALL shows approved proposal
    out = io.StringIO()
    code = approval_main(
        ["--store-path", str(store_file), "list", "--status", "ALL"],
        stdout=out,
    )
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["count"] == 1
    assert res["proposals"][0]["status"] == "APPROVED"


def test_approval_cli_reject_and_clean(tmp_path: Path) -> None:
    store_file = tmp_path / "approvals.json"
    store = ManualApprovalStore(persistence_path=store_file)

    now = datetime.now(UTC)
    order = OmsOrder(
        internal_order_id="ord_test_02",
        client_order_id="clord_btc_02",
        pair="btc_idr",
        side=OrderSide.SELL,
        desired_qty=Decimal("0.02"),
        limit_price=Decimal("1000000000"),
        created_at=now,
        updated_at=now,
    )
    prop = store.propose(order, at=now - timedelta(seconds=400), ttl_seconds=300)

    # Attempting to approve expired proposal returns exit code 2
    out = io.StringIO()
    code = approval_main(
        [
            "--store-path",
            str(store_file),
            "approve",
            prop.proposal_id,
            "--operator-id",
            "op_bob",
        ],
        stdout=out,
    )
    assert code == 2
    res = json.loads(out.getvalue())
    assert res["ok"] is False
    assert "PROPOSAL_EXPIRED" in res["error"]

    # Add another expired proposal to test clean command
    order2 = OmsOrder(
        internal_order_id="ord_test_03",
        client_order_id="clord_btc_03",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=Decimal("1000000000"),
        created_at=now,
        updated_at=now,
    )
    store.propose(order2, at=now - timedelta(seconds=500), ttl_seconds=300)

    # Clean expired
    out = io.StringIO()
    code = approval_main(["--store-path", str(store_file), "clean"], stdout=out)
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["expired_count"] == 2


def test_reconcile_cli_missing_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INDODAX_VIEW_API_KEY", raising=False)
    monkeypatch.delenv("INDODAX_VIEW_SECRET_KEY", raising=False)

    cursor_db = tmp_path / "cursor.db"
    out = io.StringIO()
    # Initialize cursor first
    code = reconcile_main(
        [
            "--cursor-db",
            str(cursor_db),
            "--scope-id",
            "test_scope",
            "--init-cursor-ms",
            "1700000000000",
        ],
        stdout=out,
    )
    # Exits with code 2 and reports BLOCKED_EXTERNAL
    assert code == 2
    res = json.loads(out.getvalue())
    assert res["status"] == "BLOCKED_EXTERNAL"
    assert res["error"] == "INDODAX_VIEW_CREDENTIALS_MISSING"


def test_reconcile_cli_fake_drill(tmp_path: Path) -> None:
    cursor_db = tmp_path / "cursor.db"
    out = io.StringIO()

    # Running with --fake automatically exercises drill mode
    code = reconcile_main(
        [
            "--cursor-db",
            str(cursor_db),
            "--scope-id",
            "test_fake_scope",
            "--fake",
            "--pairs",
            "btc_idr",
        ],
        stdout=out,
    )
    assert code == 0
    res = json.loads(out.getvalue())
    assert res["ok"] is True
    assert res["status"] == "HEALTHY"
    assert res["cursor_advanced"] is True
    assert res["cursor_after_revision"] == 2
