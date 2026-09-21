"""Unit tests for OmsOrder limit_price invariants and venue enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.execution.indodax_trading import IndodaxTradingClient
from indodax_lab.execution.oms import OmsOrder, OmsOrderState, OmsStateMachine

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_oms_order_limit_price_validation() -> None:
    # Valid limit order
    order = OmsStateMachine.create(
        internal_order_id="ord_valid",
        client_order_id="cl_valid",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
        time_in_force="GTC",
        created_at=NOW,
    )
    assert order.limit_price == Decimal("1000000000")
    assert order.order_type == "limit"
    assert order.time_in_force == "GTC"
    assert order.state == OmsOrderState.NEW

    # Non-positive limit price rejected
    with pytest.raises(ValueError, match="OMS_LIMIT_PRICE_INVALID"):
        OmsStateMachine.create(
            internal_order_id="ord_bad_price",
            client_order_id="cl_bad_price",
            pair="btc_idr",
            side=OrderSide.BUY,
            desired_qty=Decimal("0.05"),
            limit_price=Decimal("0"),
            created_at=NOW,
        )

    # Missing limit price rejected for limit orders
    with pytest.raises(ValueError, match="LIMIT_PRICE_REQUIRED"):
        OmsOrder(
            internal_order_id="ord_no_price",
            client_order_id="cl_no_price",
            pair="btc_idr",
            side=OrderSide.BUY,
            desired_qty=Decimal("0.05"),
            limit_price=None,
            order_type="limit",
            created_at=NOW,
            updated_at=NOW,
        )


def test_indodax_trading_client_rejects_missing_or_invalid_limit_price() -> None:
    client = IndodaxTradingClient(api_key="test_key", secret_key="test_secret")

    # Order without positive limit price directly rejected before network
    invalid_order = OmsOrder(
        internal_order_id="ord_direct",
        client_order_id="cl_direct",
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),
        limit_price=None,
        order_type="market",  # Bypass limit price requirement on OmsOrder
        created_at=NOW,
        updated_at=NOW,
    )

    with pytest.raises(ValueError, match="ORDER_LIMIT_PRICE_REQUIRED"):
        client.submit_order(invalid_order)
