"""Tests for PortfolioConstructor and TargetExposure calculation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import Position
from indodax_lab.portfolio.constructor import PortfolioConstructor

NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)


def test_construct_exposures_incremental_buy() -> None:
    constructor = PortfolioConstructor()
    positions = {"btc_idr": Position(pair="btc_idr", base_qty=Decimal("0.02"))}
    marks = {"btc_idr": Decimal("1000000000")}

    intent = SignalIntent(
        intent_id="sig_1",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.05"),
        limit_price=Decimal("1000000000"),
    )

    exposures = constructor.construct_exposures([intent], positions, marks)
    assert len(exposures) == 1
    exp = exposures[0]
    assert exp.pair == "btc_idr"
    assert exp.current_qty == Decimal("0.02")
    assert exp.target_qty == Decimal("0.07")
    assert exp.delta_qty == Decimal("0.05")
    assert exp.side == OrderSide.BUY
    assert exp.target_notional == Decimal("70000000")
    assert exp.delta_notional == Decimal("50000000")


def test_construct_exposures_sell_reduction() -> None:
    constructor = PortfolioConstructor()
    positions = {"btc_idr": Position(pair="btc_idr", base_qty=Decimal("0.10"))}
    marks = {"btc_idr": Decimal("1000000000")}

    intent = SignalIntent(
        intent_id="sig_2",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.SELL,
        desired_qty=Decimal("0.04"),
        limit_price=Decimal("1000000000"),
    )

    exposures = constructor.construct_exposures([intent], positions, marks)
    assert len(exposures) == 1
    exp = exposures[0]
    assert exp.current_qty == Decimal("0.10")
    assert exp.target_qty == Decimal("0.06")
    assert exp.delta_qty == Decimal("-0.04")
    assert exp.side == OrderSide.SELL
    assert exp.target_notional == Decimal("60000000")
    assert exp.delta_notional == Decimal("40000000")


def test_generate_rebalance_intents_filters_dust() -> None:
    constructor = PortfolioConstructor(min_order_notional=Decimal("10000"))
    positions = {
        "btc_idr": Position(pair="btc_idr", base_qty=Decimal("0.000001")),
        "eth_idr": Position(pair="eth_idr", base_qty=Decimal("0.0")),
    }
    marks = {
        "btc_idr": Decimal("1000000000"),  # 1e-6 * 1e9 = 1,000 IDR (< min 10,000)
        "eth_idr": Decimal("50000000"),  # 0.01 * 5e7 = 500,000 IDR (>= min 10,000)
    }

    intent_btc = SignalIntent(
        intent_id="sig_dust",
        decision_ts=NOW,
        pair="btc_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.000001"),  # 1,000 IDR
    )
    intent_eth = SignalIntent(
        intent_id="sig_valid",
        decision_ts=NOW,
        pair="eth_idr",
        side=OrderSide.BUY,
        desired_qty=Decimal("0.01"),  # 500,000 IDR
    )

    exposures = constructor.construct_exposures([intent_btc, intent_eth], positions, marks)
    rebalance_intents = constructor.generate_rebalance_intents(exposures, decision_ts=NOW)

    # Only eth_idr should generate an executable intent
    assert len(rebalance_intents) == 1
    assert rebalance_intents[0].pair == "eth_idr"
    assert rebalance_intents[0].desired_qty == Decimal("0.01")


def test_missing_mark_price_fails_closed() -> None:
    constructor = PortfolioConstructor()
    positions = {"btc_idr": Position(pair="btc_idr", base_qty=Decimal("0.02"))}
    marks = {}  # Empty mark prices

    with pytest.raises(ValueError, match="MISSING_OR_INVALID_MARK_PRICE"):
        constructor.construct_exposures([], positions, marks)
