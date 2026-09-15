"""Audit regressions: failed allocations must never change accounting state."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

import indodax_lab.paper.portfolio as paper_portfolio
from indodax_lab.backtest.events import SignalIntent
from indodax_lab.backtest.ledger import LedgerTransaction, Position, ResearchLedger
from indodax_lab.backtest.orders import Fill
from indodax_lab.backtest.risk import PortfolioRiskManager, RiskPolicy
from indodax_lab.paper.portfolio import PaperOrderIntent, SharedCapitalLedger


@pytest.mark.parametrize("field,value", [
    ("entry_price", "0"), ("entry_price", "-1"),
    ("allocated_cash", "0"), ("allocated_cash", "-100000"),
    ("allocated_cash", "NaN"), ("entry_price", "Infinity"),
    ("side", "SELL"),
])
def test_invalid_paper_allocation_never_changes_cash(field, value):
    ledger = SharedCapitalLedger()
    payload = dict(event_id="e", candidate_id="c", pair="btc_idr",
                   allocated_cash="100000", entry_price="100")
    payload[field] = value
    with pytest.raises(ValueError):
        ledger.process_intent(PaperOrderIntent(**payload))
    assert ledger.available_cash == Decimal("500000")
    assert ledger.open_position_count == 0
    assert ledger.processed_event_ids == set()


def make_fill():
    return Fill(fill_id="f", order_id="o", event_id="e", pair="btc_idr",
                side="buy", qty=Decimal("10"), price=Decimal("100"),
                fees=Decimal("10"), timestamp=datetime(2024, 1, 1, tzinfo=UTC))


def test_paper_position_failure_keeps_event_retryable(monkeypatch):
    ledger = SharedCapitalLedger()
    intent = PaperOrderIntent(event_id="e", candidate_id="c", pair="btc_idr",
                              allocated_cash="100000", entry_price="100")

    def fail_position(**kwargs):
        raise ValueError("INJECTED_POSITION_FAILURE")

    with monkeypatch.context() as patch:
        patch.setattr(paper_portfolio, "PaperPosition", fail_position)
        with pytest.raises(ValueError, match="INJECTED_POSITION_FAILURE"):
            ledger.process_intent(intent)
    assert ledger.available_cash == Decimal("500000")
    assert ledger.open_position_count == 0
    assert ledger.processed_event_ids == set()
    assert ledger.process_intent(intent).approved
    assert ledger.available_cash == Decimal("400000")


def test_paper_rejects_naive_decision_time():
    with pytest.raises(ValueError, match="UTC_TIMEZONE_AWARE_REQUIRED"):
        PaperOrderIntent(event_id="e", candidate_id="c", pair="btc_idr",
                         allocated_cash="1", entry_price="1",
                         timestamp=datetime(2024, 1, 1))


def test_fee_inclusive_overdraft_rejected_without_postings():
    ledger = ResearchLedger(initial_cash=Decimal("1000"))
    for _ in range(2):
        with pytest.raises(ValueError):
            ledger.process_fill(make_fill())
        assert ledger.cash == Decimal("1000")
        assert not ledger.positions
        assert len(ledger.transactions) == 1
        assert ledger.total_fees_paid == 0


def test_failed_balance_check_does_not_consume_fill(monkeypatch):
    ledger = ResearchLedger(initial_cash=Decimal("2000"))
    with monkeypatch.context() as patch:
        patch.setattr(LedgerTransaction, "is_balanced", property(lambda self: False))
        with pytest.raises(RuntimeError, match="UNBALANCED_TRANSACTION"):
            ledger.process_fill(make_fill())
    assert ledger.cash == Decimal("2000")
    assert not ledger.positions
    assert ledger.total_fees_paid == 0
    assert len(ledger.transactions) == 1
    ledger.process_fill(make_fill())
    assert ledger.cash == Decimal("990")
    assert ledger.total_fees_paid == Decimal("10")


@pytest.mark.parametrize("held_qty,expected", [("2", "0"), ("1", "100")])
def test_risk_cap_counts_existing_position(held_qty, expected):
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    manager = PortfolioRiskManager(
        RiskPolicy(policy_id="p", version="1", min_order_notional=Decimal("1")),
        Decimal("1000"), ts,
    )
    result = manager.assess_order(
        SignalIntent(intent_id="i", decision_ts=ts, pair="btc_idr",
                     side="buy", desired_qty=Decimal("2")),
        Decimal("1000"), {"btc_idr": Position(pair="btc_idr", base_qty=Decimal(held_qty))},
        {"btc_idr": Decimal("100")}, ts, Decimal("800"),
    )
    assert result.approved_notional == Decimal(expected)
    assert result.approved == (expected != "0")
