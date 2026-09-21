"""Tests for the canonical read-only Indodax private adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import hmac
from urllib.parse import urlencode

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.execution.indodax_readonly import IndodaxReadOnlyClient


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, headers, data, timeout):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def test_get_info_signing_and_balance_normalization():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "success": 1,
                    "return": {
                        "server_time": 1_726_000_000,
                        "balance": {"idr": "90000", "btc": "0.001"},
                        "balance_hold": {"idr": "10000", "btc": "0.0002"},
                    },
                }
            )
        ]
    )
    client = IndodaxReadOnlyClient(
        "view-key",
        "super-secret",
        session=session,
        clock_ms=lambda: 1_578_304_294_000,
        max_attempts=1,
    )

    snapshot = client.get_account_snapshot()

    call = session.calls[0]
    expected_body = urlencode(
        [
            ("method", "getInfo"),
            ("timestamp", "1578304294000"),
            ("recvWindow", "5000"),
        ]
    )
    expected_sign = hmac.new(
        b"super-secret",
        expected_body.encode(),
        hashlib.sha512,
    ).hexdigest()

    assert call["method"] == "POST"
    assert call["data"] == expected_body
    assert call["headers"]["Key"] == "view-key"
    assert call["headers"]["Sign"] == expected_sign
    assert snapshot.server_time == datetime.fromtimestamp(1_726_000_000, tz=UTC)
    assert snapshot.balances["idr"].available == Decimal("90000")
    assert snapshot.balances["idr"].hold == Decimal("10000")
    assert snapshot.balances["idr"].total == Decimal("100000")
    assert snapshot.balances["btc"].total == Decimal("0.0012")
    assert "super-secret" not in repr(client)
    assert "view-key" not in repr(client)


def test_v2_trade_history_uses_current_endpoint_and_normalizes_fill():
    session = FakeSession(
        [
            FakeResponse(
                {
                    "data": [
                        {
                            "tradeId": "72057594037936570",
                            "orderId": "btcidr-limit-42",
                            "clientOrderId": "bot-42",
                            "symbol": "btcidr",
                            "price": "1000000000",
                            "qty": "0.0001",
                            "quoteQty": "100000",
                            "commission": "321",
                            "commissionAsset": "idr",
                            "isBuyer": True,
                            "isMaker": False,
                            "time": 1_726_000_000_000,
                        }
                    ]
                }
            )
        ]
    )
    client = IndodaxReadOnlyClient(
        "view-key",
        "secret",
        session=session,
        clock_ms=lambda: 1_726_000_001_000,
        max_attempts=1,
    )

    fills = client.get_trade_fills("btc_idr", limit=10)

    assert len(fills) == 1
    fill = fills[0]
    assert fill.fill_id == "72057594037936570"
    assert fill.side == OrderSide.BUY
    assert fill.role == OrderRole.TAKER
    assert fill.qty == Decimal("0.0001")
    assert fill.commission == Decimal("321")

    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"].startswith(
        "https://tapi.indodax.com/api/v2/myTrades?symbol=btcidr"
    )
    assert call["headers"]["X-APIKEY"] == "view-key"
    assert call["data"] is None


def test_client_exposes_no_order_write_or_withdraw_methods():
    client = IndodaxReadOnlyClient(
        "view-key",
        "secret",
        session=FakeSession([]),
        max_attempts=1,
    )

    forbidden_names = {
        "trade",
        "create_order",
        "cancel_order",
        "withdraw",
        "withdraw_coin",
    }
    assert all(not hasattr(client, name) for name in forbidden_names)
