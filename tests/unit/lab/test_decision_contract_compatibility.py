"""Characterization tests for the SignalIntent public contract."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.events import SignalIntent


def test_existing_signal_serialization() -> None:
    value = SignalIntent(
        intent_id="intent-1",
        decision_ts=datetime(2026, 9, 21, tzinfo=UTC),
        pair="btc_idr",
        side="buy",
        desired_qty=Decimal("0.0100"),
    )

    assert value.model_dump(mode="json") == {
        "intent_id": "intent-1",
        "decision_ts": "2026-09-21T00:00:00Z",
        "pair": "btc_idr",
        "side": "buy",
        "desired_qty": "0.0100",
        "limit_price": None,
        "stop_loss": None,
        "take_profit": None,
        "role_preference": "taker",
        "strategy_id": "default_strat",
        "time_in_force": "IOC",
    }


def test_sell_signal_serialization_preserves_explicit_execution_fields() -> None:
    value = SignalIntent(
        intent_id="sell-1",
        decision_ts=datetime(2026, 9, 21, tzinfo=UTC),
        pair="eth_idr",
        side=OrderSide.SELL,
        desired_qty=Decimal("2.50"),
        limit_price=Decimal("123.45"),
        stop_loss=Decimal("120"),
        take_profit=Decimal("130"),
        role_preference=OrderRole.MAKER,
        strategy_id="c02",
        time_in_force="GTC",
    )

    assert value.model_dump(mode="json") == {
        "intent_id": "sell-1",
        "decision_ts": "2026-09-21T00:00:00Z",
        "pair": "eth_idr",
        "side": "sell",
        "desired_qty": "2.50",
        "limit_price": "123.45",
        "stop_loss": "120",
        "take_profit": "130",
        "role_preference": "maker",
        "strategy_id": "c02",
        "time_in_force": "GTC",
    }


@pytest.mark.parametrize("qty", ["0", "-1", "NaN", "Infinity"])
def test_invalid_quantity_rejected(qty: str) -> None:
    with pytest.raises(ValueError, match="POSITIVE_DESIRED_QTY_REQUIRED"):
        SignalIntent(
            intent_id="bad",
            decision_ts=datetime(2026, 9, 21, tzinfo=UTC),
            pair="btc_idr",
            side="buy",
            desired_qty=qty,
        )


def test_naive_decision_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="UTC_TIMEZONE_AWARE_REQUIRED:decision_ts"):
        SignalIntent(
            intent_id="bad-time",
            decision_ts=datetime(2026, 9, 21),
            pair="btc_idr",
            side="buy",
            desired_qty="1",
        )


@pytest.mark.parametrize("field", ["limit_price", "stop_loss", "take_profit"])
@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_invalid_optional_prices_rejected(field: str, value: str) -> None:
    payload = {
        "intent_id": "bad-price",
        "decision_ts": datetime(2026, 9, 21, tzinfo=UTC),
        "pair": "btc_idr",
        "side": "buy",
        "desired_qty": "1",
        field: value,
    }

    with pytest.raises(ValueError, match="POSITIVE_PRICE_REQUIRED"):
        SignalIntent(**payload)
