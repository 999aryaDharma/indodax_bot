"""Balanced research postings and double-entry ledger contract tests (LED-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest

from indodax_lab.backtest.costs import OrderRole, OrderSide
from indodax_lab.backtest.orders import Fill
from indodax_lab.backtest.ledger import (
    AccountType,
    DuplicateFillError,
    InsufficientQuantityError,
    Posting,
    ResearchLedger,
)


BASE_TS = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def test_led_01_valid_contract() -> None:
    """LED-01-AC0: Simulasi kas dan posisi memakai posting balance dengan cost basis exact."""
    ledger = ResearchLedger(initial_cash=Decimal("1000000"), valuation_currency="IDR")

    # Initial balance check
    assert ledger.cash == Decimal("1000000")
    assert ledger.equity(mark_prices={}) == Decimal("1000000")

    # 1. Buy 0.001 BTC @ 500_000_000 IDR. Gross = 500_000. Fee = 1_000 IDR.
    buy_fill = Fill(
        fill_id="fill-001",
        order_id="ord-001",
        event_id="evt-001",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.001"),
        price=Decimal("500000000"),
        fees=Decimal("1000"),
        timestamp=BASE_TS,
    )
    tx_buy = ledger.process_fill(buy_fill)

    # Postings must sum to 0
    assert tx_buy.is_balanced
    assert sum(p.amount for p in tx_buy.postings) == Decimal("0")

    # Cash debited by gross + fee = 501_000
    assert ledger.cash == Decimal("499000")
    pos = ledger.get_position("btc_idr")
    assert pos.base_qty == Decimal("0.001")
    assert pos.cost_basis == Decimal("500000")

    # Equity marked at purchase price
    assert ledger.equity(mark_prices={"btc_idr": Decimal("500000000")}) == Decimal("999000")

    # 2. Partial Sell 0.0004 BTC @ 600_000_000 IDR. Gross = 240_000. Fee = 500 IDR.
    sell_fill_1 = Fill(
        fill_id="fill-002",
        order_id="ord-002",
        event_id="evt-002",
        pair="btc_idr",
        side=OrderSide.SELL,
        role=OrderRole.TAKER,
        qty=Decimal("0.0004"),
        price=Decimal("600000000"),
        fees=Decimal("500"),
        timestamp=BASE_TS + timedelta(hours=1),
    )
    tx_sell_1 = ledger.process_fill(sell_fill_1)

    assert tx_sell_1.is_balanced
    assert sum(p.amount for p in tx_sell_1.postings) == Decimal("0")

    # Allocated gross basis = (0.0004 / 0.001) * 500_000 = 200_000 IDR
    # Net sell credit = 240_000 - 500 = 239_500 IDR
    # Cash = 499_000 + 239_500 = 738_500 IDR
    assert ledger.cash == Decimal("738500")
    pos = ledger.get_position("btc_idr")
    assert pos.base_qty == Decimal("0.0006")
    assert pos.cost_basis == Decimal("300000")

    # 3. Final Sell 0.0006 BTC @ 550_000_000 IDR. Gross = 330_000. Fee = 700 IDR.
    sell_fill_2 = Fill(
        fill_id="fill-003",
        order_id="ord-003",
        event_id="evt-003",
        pair="btc_idr",
        side=OrderSide.SELL,
        role=OrderRole.TAKER,
        qty=Decimal("0.0006"),
        price=Decimal("550000000"),
        fees=Decimal("700"),
        timestamp=BASE_TS + timedelta(hours=2),
    )
    tx_sell_2 = ledger.process_fill(sell_fill_2)

    assert tx_sell_2.is_balanced
    assert sum(p.amount for p in tx_sell_2.postings) == Decimal("0")

    # Allocated basis = 300_000 IDR
    # Net sell credit = 330_000 - 700 = 329_300 IDR
    # Cash = 738_500 + 329_300 = 1_067_800 IDR
    assert ledger.cash == Decimal("1067800")
    pos = ledger.get_position("btc_idr")
    assert pos.base_qty == Decimal("0")
    assert pos.cost_basis == Decimal("0")

    # Equity equals cash when zero open inventory
    assert ledger.equity(mark_prices={"btc_idr": Decimal("550000000")}) == Decimal("1067800")
    assert ledger.total_net_pnl == Decimal("67800")
    assert ledger.total_fees_paid == Decimal("2200")


def test_led_01_contract_1() -> None:
    """LED-01-AC1: Buy partial sell final sell menjaga quantity nonnegative."""
    ledger = ResearchLedger(initial_cash=Decimal("1000000"), valuation_currency="IDR")

    # Buy 0.001 BTC
    ledger.process_fill(
        Fill(
            fill_id="fill-b1",
            order_id="ord-b1",
            event_id="evt-b1",
            pair="btc_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            qty=Decimal("0.001"),
            price=Decimal("500000000"),
            fees=Decimal("1000"),
            timestamp=BASE_TS,
        )
    )
    assert ledger.get_position("btc_idr").base_qty == Decimal("0.001")

    # Partial sell 0.0004 BTC -> Remaining 0.0006 BTC (nonnegative)
    ledger.process_fill(
        Fill(
            fill_id="fill-s1",
            order_id="ord-s1",
            event_id="evt-s1",
            pair="btc_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            qty=Decimal("0.0004"),
            price=Decimal("510000000"),
            fees=Decimal("500"),
            timestamp=BASE_TS + timedelta(minutes=10),
        )
    )
    assert ledger.get_position("btc_idr").base_qty == Decimal("0.0006")

    # Attempt to sell 0.0007 BTC (> 0.0006) -> MUST FAIL and keep quantity nonnegative
    with pytest.raises(InsufficientQuantityError) as exc_info:
        ledger.process_fill(
            Fill(
                fill_id="fill-s-oversell",
                order_id="ord-s-oversell",
                event_id="evt-s-oversell",
                pair="btc_idr",
                side=OrderSide.SELL,
                role=OrderRole.TAKER,
                qty=Decimal("0.0007"),
                price=Decimal("510000000"),
                fees=Decimal("500"),
                timestamp=BASE_TS + timedelta(minutes=20),
            )
        )
    assert "INSUFFICIENT_BASE_QUANTITY" in str(exc_info.value)
    # Position strictly intact
    assert ledger.get_position("btc_idr").base_qty == Decimal("0.0006")

    # Final sell remaining 0.0006 BTC -> Exactly 0 BTC (nonnegative)
    ledger.process_fill(
        Fill(
            fill_id="fill-s2",
            order_id="ord-s2",
            event_id="evt-s2",
            pair="btc_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            qty=Decimal("0.0006"),
            price=Decimal("520000000"),
            fees=Decimal("600"),
            timestamp=BASE_TS + timedelta(minutes=30),
        )
    )
    assert ledger.get_position("btc_idr").base_qty == Decimal("0")
    assert ledger.get_position("btc_idr").base_qty >= Decimal("0")


def test_led_01_contract_2() -> None:
    """LED-01-AC2: Fee lebih tinggi tidak meningkatkan fixed-path PnL."""
    # Run 1: Normal fees
    ledger_low_fee = ResearchLedger(initial_cash=Decimal("1000000"), valuation_currency="IDR")
    ledger_low_fee.process_fill(
        Fill(
            fill_id="b1",
            order_id="o1",
            event_id="e1",
            pair="btc_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            qty=Decimal("0.001"),
            price=Decimal("500000000"),
            fees=Decimal("1000"),
            timestamp=BASE_TS,
        )
    )
    ledger_low_fee.process_fill(
        Fill(
            fill_id="s1",
            order_id="o2",
            event_id="e2",
            pair="btc_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            qty=Decimal("0.0005"),
            price=Decimal("520000000"),
            fees=Decimal("500"),
            timestamp=BASE_TS + timedelta(hours=1),
        )
    )
    ledger_low_fee.process_fill(
        Fill(
            fill_id="s2",
            order_id="o3",
            event_id="e3",
            pair="btc_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            qty=Decimal("0.0005"),
            price=Decimal("530000000"),
            fees=Decimal("500"),
            timestamp=BASE_TS + timedelta(hours=2),
        )
    )

    # Run 2: Stressed / higher fees on the identical execution path
    ledger_high_fee = ResearchLedger(initial_cash=Decimal("1000000"), valuation_currency="IDR")
    ledger_high_fee.process_fill(
        Fill(
            fill_id="b1",
            order_id="o1",
            event_id="e1",
            pair="btc_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            qty=Decimal("0.001"),
            price=Decimal("500000000"),
            fees=Decimal("2500"),  # Higher fee
            timestamp=BASE_TS,
        )
    )
    ledger_high_fee.process_fill(
        Fill(
            fill_id="s1",
            order_id="o2",
            event_id="e2",
            pair="btc_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            qty=Decimal("0.0005"),
            price=Decimal("520000000"),
            fees=Decimal("1200"),  # Higher fee
            timestamp=BASE_TS + timedelta(hours=1),
        )
    )
    ledger_high_fee.process_fill(
        Fill(
            fill_id="s2",
            order_id="o3",
            event_id="e3",
            pair="btc_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            qty=Decimal("0.0005"),
            price=Decimal("530000000"),
            fees=Decimal("1300"),  # Higher fee
            timestamp=BASE_TS + timedelta(hours=2),
        )
    )

    # Invariant: Higher fees must strictly reduce (never increase) fixed-path PnL and final equity
    assert ledger_high_fee.total_net_pnl < ledger_low_fee.total_net_pnl
    assert ledger_high_fee.cash < ledger_low_fee.cash
    assert ledger_high_fee.equity(mark_prices={}) < ledger_low_fee.equity(mark_prices={})
    pnl_diff = ledger_low_fee.total_net_pnl - ledger_high_fee.total_net_pnl
    fee_diff = ledger_high_fee.total_fees_paid - ledger_low_fee.total_fees_paid
    # Exact accounting equality: difference in PnL equals exactly the difference in fees paid
    assert pnl_diff == fee_diff


def test_led_01_contract_3() -> None:
    """LED-01-AC3: Duplicate fill ID tidak menggandakan posting."""
    ledger = ResearchLedger(initial_cash=Decimal("1000000"), valuation_currency="IDR")

    fill = Fill(
        fill_id="fill-unique-01",
        order_id="ord-01",
        event_id="evt-01",
        pair="btc_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        qty=Decimal("0.001"),
        price=Decimal("500000000"),
        fees=Decimal("1000"),
        timestamp=BASE_TS,
    )
    ledger.process_fill(fill)

    initial_tx_count = len(ledger.transactions)
    initial_cash = ledger.cash
    initial_qty = ledger.get_position("btc_idr").base_qty

    # Presenting duplicate fill ID
    with pytest.raises(DuplicateFillError) as exc_info:
        ledger.process_fill(fill)
    assert "DUPLICATE_FILL_ID:fill-unique-01" in str(exc_info.value)

    # Postings, transactions, cash, and quantity must not be duplicated
    assert len(ledger.transactions) == initial_tx_count
    assert ledger.cash == initial_cash
    assert ledger.get_position("btc_idr").base_qty == initial_qty



def test_ledger_state_roundtrip_preserves_balanced_history() -> None:
    ledger = ResearchLedger(
        initial_cash=Decimal("500000"),
        valuation_currency="IDR",
        init_timestamp=BASE_TS,
    )
    ledger.process_fill(
        Fill(
            fill_id="persist-buy",
            order_id="persist-order",
            event_id="persist-event",
            pair="eth_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            qty=Decimal("0.002"),
            price=Decimal("100000000"),
            fees=Decimal("200"),
            timestamp=BASE_TS + timedelta(minutes=1),
        )
    )

    restored = ResearchLedger.from_dict(ledger.to_dict())

    assert restored.cash == ledger.cash
    assert restored.total_fees_paid == ledger.total_fees_paid
    assert restored.positions["eth_idr"].base_qty == Decimal("0.002")
    assert restored.positions["eth_idr"].cost_basis == Decimal("200000")
    assert restored.to_dict() == ledger.to_dict()
    assert all(tx.is_balanced for tx in restored.transactions)


def test_ledger_state_tamper_fails_closed() -> None:
    ledger = ResearchLedger(
        initial_cash=Decimal("500000"),
        valuation_currency="IDR",
        init_timestamp=BASE_TS,
    )
    state = ledger.to_dict()
    state["cash"] = "999999"

    with pytest.raises(ValueError, match="LEDGER_STATE_CASH_MISMATCH"):
        ResearchLedger.from_dict(state)
