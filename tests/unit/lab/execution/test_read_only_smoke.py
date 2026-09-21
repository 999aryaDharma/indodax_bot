"""Tests for the redacted private API smoke helper."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from indodax_lab.execution.indodax_readonly import (
    VenueAccountSnapshot,
    VenueBalance,
)
from indodax_lab.execution.read_only_smoke import run_read_only_smoke

NOW = datetime(2026, 9, 21, 11, 0, tzinfo=UTC)


class FakeSmokeClient:
    def __init__(self):
        self.calls = []

    def get_account_snapshot(self):
        self.calls.append(("account",))
        return VenueAccountSnapshot(
            server_time=NOW,
            balances={
                "idr": VenueBalance(
                    currency="idr",
                    available=Decimal("987654321"),
                    hold=Decimal("12345"),
                )
            },
        )

    def get_open_orders(self, pair):
        self.calls.append(("open", pair))
        return ()

    def get_order_history(self, pair, **kwargs):
        self.calls.append(("orders", pair, kwargs))
        return ()

    def get_trade_fills(self, pair, **kwargs):
        self.calls.append(("fills", pair, kwargs))
        return ()


def test_smoke_result_contains_only_structural_health_not_private_amounts():
    client = FakeSmokeClient()

    result = run_read_only_smoke(
        client,
        ("btc_idr",),
        now=NOW,
    )

    rendered = str(result)
    assert result["ok"] is True
    assert result["clock_skew_ms"] == 0
    assert result["pairs"]["btc_idr"]["trade_history_v2_ok"] is True
    assert "987654321" not in rendered
    assert "12345" not in rendered
    assert any(call[0] == "open" for call in client.calls)
    assert any(call[0] == "orders" for call in client.calls)
    assert any(call[0] == "fills" for call in client.calls)
