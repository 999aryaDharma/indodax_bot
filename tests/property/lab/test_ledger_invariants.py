"""Property and invariant tests for double-entry research ledger (LED-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest

from indodax_lab.backtest.costs import (
    CostScheduleTable,
    OrderRole,
    OrderSide,
    load_cost_schedule_table,
    lookup_cost,
)
from indodax_lab.backtest.orders import Fill
from indodax_lab.backtest.ledger import (
    AccountType,
    DuplicateFillError,
    InsufficientQuantityError,
    ResearchLedger,
)


BASE_TS = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)


def test_transaction_balance_invariant() -> None:
    """Every generated transaction must have balanced postings summing exactly to zero."""
    ledger = ResearchLedger(initial_cash=Decimal("5000000"), valuation_currency="IDR")

    # Series of buys and partial sells across two pairs
    trades = [
        ("btc_idr", OrderSide.BUY, Decimal("0.002"), Decimal("1000000000"), Decimal("4222")),
        ("eth_idr", OrderSide.BUY, Decimal("0.05"), Decimal("50000000"), Decimal("5277")),
        ("btc_idr", OrderSide.SELL, Decimal("0.0005"), Decimal("1050000000"), Decimal("1108")),
        ("eth_idr", OrderSide.SELL, Decimal("0.02"), Decimal("52000000"), Decimal("2195")),
        ("btc_idr", OrderSide.SELL, Decimal("0.0015"), Decimal("1020000000"), Decimal("3228")),
        ("eth_idr", OrderSide.SELL, Decimal("0.03"), Decimal("49000000"), Decimal("3099")),
    ]

    for i, (pair, side, qty, price, fee) in enumerate(trades):
        fill = Fill(
            fill_id=f"f-{i}",
            order_id=f"o-{i}",
            event_id=f"e-{i}",
            pair=pair,
            side=side,
            role=OrderRole.TAKER,
            qty=qty,
            price=price,
            fees=fee,
            timestamp=BASE_TS + timedelta(minutes=i * 15),
        )
        tx = ledger.process_fill(fill)
        assert tx.is_balanced
        assert sum(p.amount for p in tx.postings) == Decimal("0")

    # Invariant: all transactions recorded in ledger remain balanced
    for tx in ledger.transactions:
        assert tx.is_balanced
        assert sum(p.amount for p in tx.postings) == Decimal("0")

    # Both positions closed, base_qty is exactly 0
    assert ledger.get_position("btc_idr").base_qty == Decimal("0")
    assert ledger.get_position("eth_idr").base_qty == Decimal("0")
    assert ledger.cash == ledger.equity(mark_prices={})


def test_unit_separation_and_equity_invariant() -> None:
    """Asset quantities and quote currency valuations must never mix in postings or balance."""
    ledger = ResearchLedger(initial_cash=Decimal("1000000"), valuation_currency="IDR")

    fill = Fill(
        fill_id="f-unit-1",
        order_id="o-1",
        event_id="e-1",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.0005"),
        price=Decimal("800000000"),
        fees=Decimal("844"),
        timestamp=BASE_TS,
    )
    tx = ledger.process_fill(fill)

    # All posting amounts are strictly in valuation currency (IDR)
    for p in tx.postings:
        assert p.currency == "IDR"
        # No base units (e.g. 0.0005 BTC) appear in valued postings
        assert abs(p.amount) != Decimal("0.0005")

    # Base qty delta is tracked separately
    assert tx.base_qty_delta == Decimal("0.0005")

    # Equity formula strictly marks open units: cash + base_qty * mark_price
    mark_price = Decimal("850000000")
    expected_equity = ledger.cash + (Decimal("0.0005") * mark_price)
    assert ledger.equity(mark_prices={"btc_idr": mark_price}) == expected_equity


def test_cost_schedule_integration(tmp_path) -> None:
    """Verify integration of COST-01 time-valid lookup_cost with LED-01 ResearchLedger."""
    yaml_content = (
        "schedule_set_id: indodax_idr\n"
        "version: 1.0.0\n"
        "intervals:\n"
        "  - schedule_id: indodax_idr_2024_current\n"
        "    market: spot_idr\n"
        "    side: buy\n"
        "    role: taker\n"
        "    valid_from: '2024-01-01T00:00:00Z'\n"
        "    valid_to: null\n"
        "    service_fee_rate: '0.002111'\n"
        "    tax_rate: '0.001100'\n"
        "    exchange_fee_rate: '0.000200'\n"
        "    min_notional: '10000'\n"
        "    precision: 0\n"
        "    sources: ['PMK 68']\n"
        "  - schedule_id: indodax_idr_2024_current_sell\n"
        "    market: spot_idr\n"
        "    side: sell\n"
        "    role: taker\n"
        "    valid_from: '2024-01-01T00:00:00Z'\n"
        "    valid_to: null\n"
        "    service_fee_rate: '0.002111'\n"
        "    tax_rate: '0.001000'\n"
        "    exchange_fee_rate: '0.000200'\n"
        "    min_notional: '10000'\n"
        "    precision: 0\n"
        "    sources: ['PMK 68']\n"
    )
    cfg_file = tmp_path / "costs.yaml"
    cfg_file.write_text(yaml_content, encoding="utf-8")
    table = load_cost_schedule_table(cfg_file)

    ledger = ResearchLedger(initial_cash=Decimal("2000000"), valuation_currency="IDR")

    # Buy fill with fee resolved from cost schedule
    buy_res = lookup_cost(
        table,
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        event_ts=BASE_TS,
    )
    buy_qty = Decimal("0.001")
    buy_price = Decimal("600000000")
    buy_gross = buy_qty * buy_price  # 600_000
    buy_fee = (buy_gross * buy_res.total_rate).quantize(Decimal("1"))

    buy_fill = Fill(
        fill_id="f-sched-buy",
        order_id="o-1",
        event_id="e-1",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=buy_qty,
        price=buy_price,
        fees=buy_fee,
        timestamp=BASE_TS,
        fee_components={
            "service": buy_gross * buy_res.service_fee_rate,
            "tax": buy_gross * buy_res.tax_rate,
            "exchange": buy_gross * buy_res.exchange_fee_rate,
        },
    )
    tx_buy = ledger.process_fill(buy_fill)
    assert tx_buy.is_balanced

    # Sell fill with fee resolved from cost schedule
    sell_res = lookup_cost(
        table,
        market="spot_idr",
        side=OrderSide.SELL,
        role=OrderRole.TAKER,
        event_ts=BASE_TS + timedelta(days=1),
    )
    sell_qty = Decimal("0.001")
    sell_price = Decimal("650000000")
    sell_gross = sell_qty * sell_price  # 650_000
    sell_fee = (sell_gross * sell_res.total_rate).quantize(Decimal("1"))

    sell_fill = Fill(
        fill_id="f-sched-sell",
        order_id="o-2",
        event_id="e-2",
        pair="btc_idr",
        side=OrderSide.SELL,
        role=OrderRole.TAKER,
        qty=sell_qty,
        price=sell_price,
        fees=sell_fee,
        timestamp=BASE_TS + timedelta(days=1),
        fee_components={
            "service": sell_gross * sell_res.service_fee_rate,
            "tax": sell_gross * sell_res.tax_rate,
            "exchange": sell_gross * sell_res.exchange_fee_rate,
        },
    )
    tx_sell = ledger.process_fill(sell_fill)
    assert tx_sell.is_balanced

    # Verify final accounting consistency
    expected_cash_delta = (sell_gross - sell_fee) - (buy_gross + buy_fee)
    assert ledger.cash - Decimal("2000000") == expected_cash_delta
    assert ledger.total_net_pnl == expected_cash_delta
