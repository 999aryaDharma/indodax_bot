"""Tests for PM-07 reviewed account portfolio adoption.

Acceptance criteria:
- PM-07-AC0: Stale snapshot or unresolved existing order prevents adoption.
- PM-07-AC1: Unknown cost basis stays unknown while post-adoption baseline is separately attributed.
- PM-07-AC2: Unadopted assets affect exposure but cannot be sold by a strategy.
- PM-07-AC3: Unexplained external account change blocks new entry until reviewed reconciliation.
- PM-07-AC4: Duplicate adoption and restart have one position ownership effect.
- PM-07-AC5: Verified deposits do not appear as trading profit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import OrderSide
from indodax_lab.backtest.ledger import ResearchLedger
from indodax_lab.backtest.orders import Fill
from indodax_lab.contracts.workbench import MetricValidity
from indodax_lab.execution.indodax_readonly import (
    VenueAccountSnapshot,
    VenueBalance,
    VenueOrder,
)
from indodax_lab.execution.reconciliation import (
    ReconciliationEngine,
    ReconciliationPolicy,
)
from indodax_lab.portfolio.adoption import (
    AdoptionError,
    AdoptionStore,
    AssetAssignment,
    CostBasisValidity,
    CostBasisValidityError,
    PortfolioAdoptionService,
    RevisionMismatchError,
    StaleSnapshotError,
    UnadoptedAssetError,
    UnresolvedOrdersError,
    approve_adoption,
    can_strategy_sell,
    compute_portfolio_exposure,
    is_new_entry_allowed,
    propose_adoption,
    record_verified_deposit,
    review_reconciliation,
    validate_strategy_sell,
)


def _make_snapshot(
    *,
    server_time: datetime,
    idr_total: Decimal = Decimal("500000000"),
    btc_total: Decimal = Decimal("1.5"),
    btc_hold: Decimal = Decimal("0"),
    eth_total: Decimal = Decimal("10.0"),
    eth_hold: Decimal = Decimal("0"),
) -> VenueAccountSnapshot:
    balances = {
        "idr": VenueBalance(currency="idr", available=idr_total, hold=Decimal("0")),
        "btc": VenueBalance(currency="btc", available=btc_total - btc_hold, hold=btc_hold),
        "eth": VenueBalance(currency="eth", available=eth_total - eth_hold, hold=eth_hold),
    }
    return VenueAccountSnapshot(server_time=server_time, balances=balances)


def test_pm_07_0(tmp_path: Path) -> None:
    """PM-07-AC0: Stale snapshot or unresolved existing order prevents adoption."""
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    store = AdoptionStore(tmp_path / "adoption_ac0.db")

    # 1. Stale snapshot (> 30 seconds old)
    stale_time = eval_time - timedelta(seconds=45)
    stale_snapshot = _make_snapshot(server_time=stale_time)
    assignments = [
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="btc_trend_c07",
            quantity=Decimal("1.0"),
        )
    ]
    with pytest.raises((StaleSnapshotError, AdoptionError), match="STALE_ACCOUNT_SNAPSHOT"):
        propose_adoption(
            snapshot_ref="snap-stale-001",
            assignments=assignments,
            snapshot=stale_snapshot,
            evaluation_time=eval_time,
            store=store,
        )

    # 2. Fresh snapshot with unresolved open order
    fresh_time = eval_time - timedelta(seconds=5)
    fresh_snapshot = _make_snapshot(server_time=fresh_time)
    open_orders = [
        VenueOrder(
            order_id="venue-ord-999",
            client_order_id="cl-ord-999",
            pair="btc_idr",
            side=OrderSide.BUY,
            order_type="limit",
            status="OPEN",
            price=Decimal("950000000"),
            original_qty=Decimal("0.5"),
            executed_qty=Decimal("0.0"),
            remaining_qty=Decimal("0.5"),
            submitted_at=fresh_time - timedelta(minutes=1),
        )
    ]
    with pytest.raises((UnresolvedOrdersError, AdoptionError), match="UNRESOLVED_EXISTING_ORDERS"):
        propose_adoption(
            snapshot_ref="snap-fresh-001",
            assignments=assignments,
            snapshot=fresh_snapshot,
            venue_open_orders=open_orders,
            evaluation_time=eval_time,
            store=store,
        )

    # 3. Clean snapshot with no open orders succeeds
    proposal = propose_adoption(
        snapshot_ref="snap-fresh-001",
        assignments=assignments,
        snapshot=fresh_snapshot,
        venue_open_orders=(),
        mark_prices={"btc_idr": Decimal("1000000000"), "eth_idr": Decimal("50000000")},
        evaluation_time=eval_time,
        store=store,
    )
    assert proposal.status == "PROPOSED"
    assert len(proposal.assignments) == 1
    assert proposal.assignments[0].pair == "btc_idr"


def test_pm_07_1(tmp_path: Path) -> None:
    """PM-07-AC1: Unknown cost basis stays unknown; baseline separately attributed."""
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    store = AdoptionStore(tmp_path / "adoption_ac1.db")
    snapshot = _make_snapshot(server_time=eval_time - timedelta(seconds=2))

    # Asset 1: BTC with unknown cost basis
    # Asset 2: ETH with known cost basis and evidence
    assignments = [
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="btc_c07",
            quantity=Decimal("1.0"),
            cost_basis=None,
            cost_basis_validity=CostBasisValidity.UNKNOWN,
        ),
        AssetAssignment(
            pair="eth_idr",
            asset="eth",
            strategy_id="eth_c02",
            quantity=Decimal("5.0"),
            cost_basis=Decimal("200000000"),
            cost_basis_validity=CostBasisValidity.KNOWN,
            cost_basis_evidence="receipt-tx-eth-buy-001",
        ),
    ]

    # Reject KNOWN validity without evidence or value
    with pytest.raises(
        (CostBasisValidityError, ValueError), match="KNOWN_COST_BASIS_REQUIRES_VALUE_AND_EVIDENCE"
    ):
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="btc_c07",
            quantity=Decimal("1.0"),
            cost_basis=None,
            cost_basis_validity=CostBasisValidity.KNOWN,
        )

    # Reject UNKNOWN validity with a fabricated non-None cost basis
    with pytest.raises(
        (CostBasisValidityError, ValueError), match="UNKNOWN_COST_BASIS_MUST_BE_NONE"
    ):
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="btc_c07",
            quantity=Decimal("1.0"),
            cost_basis=Decimal("500000000"),
            cost_basis_validity=CostBasisValidity.UNKNOWN,
        )

    mark_prices = {
        "btc_idr": Decimal("1000000000"),
        "eth_idr": Decimal("50000000"),
    }

    proposal = propose_adoption(
        snapshot_ref="snap-ac1-001",
        assignments=assignments,
        snapshot=snapshot,
        mark_prices=mark_prices,
        evaluation_time=eval_time,
        store=store,
    )

    record = approve_adoption(
        proposal_id=proposal.proposal_id,
        expected_revision=0,
        actor="operator_lead",
        reason="Initial account adoption",
        request_id="req-adopt-001",
        store=store,
    )

    # Inspect BTC adopted asset: cost basis MUST be None and UNKNOWN
    btc_adopted = next(a for a in record.adopted_assets if a.pair == "btc_idr")
    assert btc_adopted.cost_basis is None
    assert btc_adopted.cost_basis_validity == CostBasisValidity.UNKNOWN
    assert btc_adopted.adoption_baseline_price == Decimal("1000000000")
    assert btc_adopted.adoption_baseline_notional == Decimal("1000000000")

    # Inspect ETH adopted asset: cost basis is KNOWN and preserved
    eth_adopted = next(a for a in record.adopted_assets if a.pair == "eth_idr")
    assert eth_adopted.cost_basis == Decimal("200000000")
    assert eth_adopted.cost_basis_validity == CostBasisValidity.KNOWN
    assert eth_adopted.cost_basis_evidence == "receipt-tx-eth-buy-001"
    assert eth_adopted.adoption_baseline_price == Decimal("50000000")
    assert eth_adopted.adoption_baseline_notional == Decimal("250000000")

    # Evaluate post-adoption baseline attribution vs lifetime PnL:
    # BTC current price increases to 1,050,000,000 IDR (+50,000,000 IDR)
    current_marks = {
        "btc_idr": Decimal("1050000000"),
        "eth_idr": Decimal("50000000"),
    }
    btc_perf = store.evaluate_adopted_asset_performance("btc_idr", current_marks["btc_idr"])
    # Lifetime PnL is UNAVAILABLE because historical cost basis is unknown
    assert btc_perf.lifetime_pnl.validity == MetricValidity.UNAVAILABLE
    assert btc_perf.lifetime_pnl.value is None
    assert "UNKNOWN_HISTORICAL_COST_BASIS" in (btc_perf.lifetime_pnl.reason or "")
    # Post-adoption PnL is VALID and separately attributed against adoption baseline
    assert btc_perf.post_adoption_pnl.validity == MetricValidity.VALID
    assert btc_perf.post_adoption_pnl.value == Decimal("50000000")


def test_pm_07_2(tmp_path: Path) -> None:
    """PM-07-AC2: Unadopted assets affect exposure but cannot be sold by a strategy."""
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    store = AdoptionStore(tmp_path / "adoption_ac2.db")
    # Snapshot holds: 500M IDR cash, 1.0 BTC, 10.0 ETH
    snapshot = _make_snapshot(
        server_time=eval_time - timedelta(seconds=1),
        idr_total=Decimal("500000000"),
        btc_total=Decimal("1.0"),
        eth_total=Decimal("10.0"),
    )
    mark_prices = {
        "btc_idr": Decimal("1000000000"),  # 1 BTC = 1,000,000,000 IDR
        "eth_idr": Decimal("50000000"),  # 10 ETH = 500,000,000 IDR
    }

    # Only BTC is adopted into strategy btc_c07; ETH is UNADOPTED
    assignments = [
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="btc_c07",
            quantity=Decimal("1.0"),
        )
    ]

    proposal = propose_adoption(
        snapshot_ref="snap-ac2-001",
        assignments=assignments,
        snapshot=snapshot,
        mark_prices=mark_prices,
        evaluation_time=eval_time,
        store=store,
    )
    record = approve_adoption(
        proposal_id=proposal.proposal_id,
        expected_revision=0,
        actor="operator_lead",
        reason="Adopt BTC only",
        request_id="req-adopt-ac2",
        store=store,
    )

    # 1. Unadopted ETH affects total account exposure and marked equity
    exposure_report = compute_portfolio_exposure(
        record=record, mark_prices=mark_prices, cash_balance=Decimal("500000000")
    )
    assert exposure_report.adopted_exposure == Decimal("1000000000")  # 1 BTC * 1B
    assert exposure_report.unadopted_exposure == Decimal("500000000")  # 10 ETH * 50M
    assert exposure_report.total_account_exposure == Decimal("1500000000")
    assert exposure_report.total_equity == Decimal("2000000000")  # 500M cash + 1.5B assets
    assert len(record.unadopted_assets) == 1
    assert record.unadopted_assets[0].asset == "eth"
    assert record.unadopted_assets[0].total_qty == Decimal("10.0")

    # 2. Strategy cannot sell unadopted ETH
    assert not can_strategy_sell("strategy_eth", "eth_idr", store=store)
    assert not can_strategy_sell("btc_c07", "eth_idr", store=store)
    with pytest.raises(UnadoptedAssetError, match="UNADOPTED_ASSET_CANNOT_BE_SOLD"):
        validate_strategy_sell("strategy_eth", "eth_idr", Decimal("1.0"), store=store)
    with pytest.raises(UnadoptedAssetError, match="UNADOPTED_ASSET_CANNOT_BE_SOLD"):
        validate_strategy_sell("btc_c07", "eth_idr", Decimal("1.0"), store=store)

    # Adopted BTC CAN be sold by owning strategy
    assert can_strategy_sell("btc_c07", "btc_idr", store=store)
    validate_strategy_sell("btc_c07", "btc_idr", Decimal("0.5"), store=store)


def test_pm_07_3(tmp_path: Path) -> None:
    """PM-07-AC3: Unexplained account change blocks entry until reviewed reconciliation."""
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    store = AdoptionStore(tmp_path / "adoption_ac3.db")
    reconciler = ReconciliationEngine(ReconciliationPolicy(quote_balance_tolerance=Decimal("0")))

    # Internal ledger has 100M IDR cash
    ledger = ResearchLedger(initial_cash=Decimal("100000000"), valuation_currency="IDR")

    # Venue snapshot has 150M IDR (an unexplained external change/transfer occurred)
    unexplained_snapshot = _make_snapshot(
        server_time=eval_time - timedelta(seconds=2),
        idr_total=Decimal("150000000"),
        btc_total=Decimal("0"),
        eth_total=Decimal("0"),
    )

    # Run reconciliation
    report = reconciler.reconcile(
        ledger=ledger,
        account=unexplained_snapshot,
        evaluation_time=eval_time,
    )
    assert not report.healthy
    assert any(issue.code == "QUOTE_BALANCE_MISMATCH" for issue in report.issues)

    # Unexplained discrepancy blocks new entry
    assert not is_new_entry_allowed(reconciliation_report=report, store=store)

    # Operator explicitly reviews and acknowledges the reconciliation discrepancy
    review = review_reconciliation(
        report=report,
        actor="operator_lead",
        reason="External deposit IDR 50M confirmed at bank, ledger top-up pending",
        store=store,
    )
    assert review.resolved

    # After reviewed reconciliation, new entry is permitted
    assert is_new_entry_allowed(reconciliation_report=report, store=store)

    # If a new unexpected issue arises, it is blocked until separately reviewed
    asset_mismatch_snapshot = _make_snapshot(
        server_time=eval_time - timedelta(seconds=1),
        idr_total=Decimal("150000000"),
        btc_total=Decimal("2.0"),  # Unexpected unadopted BTC appears
        eth_total=Decimal("0"),
    )
    new_report = reconciler.reconcile(
        ledger=ledger,
        account=asset_mismatch_snapshot,
        tracked_pairs=["btc_idr"],
        evaluation_time=eval_time,
    )
    assert not new_report.healthy
    assert not is_new_entry_allowed(reconciliation_report=new_report, store=store)


def test_pm_07_4(tmp_path: Path) -> None:
    """PM-07-AC4: Duplicate adoption and restart have one position ownership effect."""
    db_file = tmp_path / "adoption_ac4.db"
    store = AdoptionStore(db_file)
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    snapshot = _make_snapshot(
        server_time=eval_time - timedelta(seconds=2),
        btc_total=Decimal("0.5"),
    )

    assignments = [
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="btc_trend_c07",
            quantity=Decimal("0.5"),
        )
    ]
    proposal = propose_adoption(
        snapshot_ref="snap-ac4-001",
        assignments=assignments,
        snapshot=snapshot,
        mark_prices={"btc_idr": Decimal("1000000000"), "eth_idr": Decimal("50000000")},
        evaluation_time=eval_time,
        store=store,
    )

    # 1. First approval commits adoption
    record1 = approve_adoption(
        proposal_id=proposal.proposal_id,
        expected_revision=0,
        actor="operator_1",
        reason="Initial adoption",
        request_id="req-unique-ac4",
        store=store,
    )
    assert record1.effective_revision == 1
    assert store.current_revision == 1
    assert store.get_pair_owner("btc_idr") == "btc_trend_c07"
    assert store.get_adopted_quantity("btc_idr") == Decimal("0.5")

    # 2. Duplicate approval with same request_id returns identical record
    record2 = approve_adoption(
        proposal_id=proposal.proposal_id,
        expected_revision=0,  # Or stale revision
        actor="operator_1",
        reason="Retry duplicate adoption",
        request_id="req-unique-ac4",
        store=store,
    )
    assert record2.adoption_id == record1.adoption_id
    assert store.current_revision == 1
    assert store.get_adopted_quantity("btc_idr") == Decimal("0.5")

    # 3. Simulate process restart by reloading from disk
    restarted_store = AdoptionStore(db_file)
    assert restarted_store.current_revision == 1
    assert restarted_store.get_pair_owner("btc_idr") == "btc_trend_c07"
    assert restarted_store.get_adopted_quantity("btc_idr") == Decimal("0.5")

    # Calling approve on restarted store with same request_id remains idempotent
    record3 = approve_adoption(
        proposal_id=proposal.proposal_id,
        expected_revision=1,
        actor="operator_1",
        reason="Retry after restart",
        request_id="req-unique-ac4",
        store=restarted_store,
    )
    assert record3.adoption_id == record1.adoption_id
    assert restarted_store.current_revision == 1
    assert restarted_store.get_adopted_quantity("btc_idr") == Decimal("0.5")


def test_pm_07_5(tmp_path: Path) -> None:
    """PM-07-AC5: Verified deposits do not appear as trading profit."""
    store = AdoptionStore(tmp_path / "adoption_ac5.db")
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)

    # Initial cash: IDR 500,000
    ledger = ResearchLedger(initial_cash=Decimal("500000"), valuation_currency="IDR")
    assert ledger.cash == Decimal("500000")
    assert ledger.total_realized_gross_pnl == Decimal("0")
    assert ledger.total_net_pnl == Decimal("0")
    assert ledger.total_fees_paid == Decimal("0")

    # Record verified deposit: IDR 200,000
    deposit_rec = record_verified_deposit(
        amount=Decimal("200000"),
        currency="IDR",
        evidence_ref="bank-trx-verify-001",
        actor="operator_lead",
        reason="Operational account top-up",
        store=store,
        ledger=ledger,
        timestamp=eval_time,
    )
    assert deposit_rec.amount == Decimal("200000")

    # 1. In the double-entry ledger:
    # Cash increased, but realized gross and net PnL remain strictly 0!
    assert ledger.cash == Decimal("700000")
    assert ledger.total_realized_gross_pnl == Decimal("0")
    assert ledger.total_net_pnl == Decimal("0")
    assert ledger.total_fees_paid == Decimal("0")

    # 2. In cash-flow baseline tracking:
    # Baseline is adjusted by +200,000, so trading profit is 0!
    baseline = store.get_cash_flow_adjusted_baseline(initial_capital=Decimal("500000"))
    assert baseline == Decimal("700000")

    current_equity = ledger.equity(mark_prices={})
    trading_profit = current_equity - baseline
    assert trading_profit == Decimal("0")

    # 3. Subsequent real trade generates genuine trading profit:
    # Buy 0.0001 BTC at 1,000,000,000 (100,000 IDR), sell at 1,100,000,000 (110,000 IDR)
    fill_buy = Fill(
        fill_id="f-buy-1",
        order_id="o-buy-1",
        event_id="ev-buy-1",
        pair="btc_idr",
        side=OrderSide.BUY,
        price=Decimal("1000000000"),
        qty=Decimal("0.0001"),
        fees=Decimal("100"),
        timestamp=eval_time + timedelta(minutes=1),
    )
    ledger.process_fill(fill_buy)

    fill_sell = Fill(
        fill_id="f-sell-1",
        order_id="o-sell-1",
        event_id="ev-sell-1",
        pair="btc_idr",
        side=OrderSide.SELL,
        price=Decimal("1100000000"),
        qty=Decimal("0.0001"),
        fees=Decimal("110"),
        timestamp=eval_time + timedelta(minutes=5),
    )
    ledger.process_fill(fill_sell)

    # Gross PnL: 110,000 - 100,000 = 10,000 IDR
    # Net PnL: 10,000 - 210 = 9,790 IDR
    assert ledger.total_realized_gross_pnl == Decimal("10000")
    assert ledger.total_net_pnl == Decimal("9790")

    # Trading profit over flow-adjusted baseline equals exact net PnL,
    # deposit of 200,000 does NOT appear as trading profit!
    current_equity_after = ledger.equity(mark_prices={})
    trading_profit_after = current_equity_after - baseline
    assert trading_profit_after == Decimal("9790")


def test_pm_07_edge_cases(tmp_path: Path) -> None:
    """Exercise malformed inputs, missing identity, revision mismatch, and boundary edge cases."""
    store = AdoptionStore(tmp_path / "adoption_edges.db")
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)

    # 1. Non-finite or negative quantity in AssetAssignment
    with pytest.raises((ValueError, AdoptionError)):
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="s1",
            quantity=Decimal("-1.0"),
        )
    with pytest.raises((ValueError, AdoptionError)):
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="s1",
            quantity=Decimal("NaN"),
        )

    # 2. Blank identifiers
    with pytest.raises((ValueError, AdoptionError)):
        AssetAssignment(
            pair="",
            asset="btc",
            strategy_id="s1",
            quantity=Decimal("1.0"),
        )
    with pytest.raises((ValueError, AdoptionError)):
        AssetAssignment(
            pair="btc_idr",
            asset="",
            strategy_id="s1",
            quantity=Decimal("1.0"),
        )
    with pytest.raises((ValueError, AdoptionError)):
        AssetAssignment(
            pair="btc_idr",
            asset="btc",
            strategy_id="",
            quantity=Decimal("1.0"),
        )

    # 3. Clock ahead error
    ahead_snapshot = _make_snapshot(server_time=eval_time + timedelta(seconds=5))
    with pytest.raises((StaleSnapshotError, AdoptionError), match="VENUE_CLOCK_AHEAD"):
        propose_adoption(
            snapshot_ref="snap-ahead",
            assignments=[
                AssetAssignment(
                    pair="btc_idr", asset="btc", strategy_id="s1", quantity=Decimal("0.1")
                )
            ],
            snapshot=ahead_snapshot,
            evaluation_time=eval_time,
            store=store,
        )

    # 4. Naive timestamp on snapshot
    naive_snapshot = VenueAccountSnapshot(
        server_time=datetime(2026, 9, 30, 12, 0, 0),  # tzinfo=None
        balances={},
    )
    with pytest.raises((StaleSnapshotError, AdoptionError), match="VENUE_TIMESTAMP_INVALID"):
        propose_adoption(
            snapshot_ref="snap-naive",
            assignments=[],
            snapshot=naive_snapshot,
            evaluation_time=eval_time,
            store=store,
        )

    # 5. Duplicate pair assignment in proposal
    valid_snapshot = _make_snapshot(server_time=eval_time - timedelta(seconds=1))
    with pytest.raises(AdoptionError, match="DUPLICATE_PAIR_ASSIGNMENT"):
        propose_adoption(
            snapshot_ref="snap-dup",
            assignments=[
                AssetAssignment(
                    pair="btc_idr", asset="btc", strategy_id="s1", quantity=Decimal("0.1")
                ),
                AssetAssignment(
                    pair="btc_idr", asset="btc", strategy_id="s2", quantity=Decimal("0.2")
                ),
            ],
            snapshot=valid_snapshot,
            evaluation_time=eval_time,
            store=store,
        )

    # 6. Insufficient available balance
    with pytest.raises(AdoptionError, match="INSUFFICIENT_AVAILABLE_BALANCE"):
        propose_adoption(
            snapshot_ref="snap-insuff",
            assignments=[
                AssetAssignment(
                    pair="btc_idr", asset="btc", strategy_id="s1", quantity=Decimal("9999.0")
                )
            ],
            snapshot=valid_snapshot,
            evaluation_time=eval_time,
            store=store,
        )

    # 7. Missing mark price for adopted asset
    with pytest.raises(AdoptionError, match="MISSING_MARK_PRICE"):
        propose_adoption(
            snapshot_ref="snap-nomark",
            assignments=[
                AssetAssignment(
                    pair="btc_idr", asset="btc", strategy_id="s1", quantity=Decimal("0.1")
                )
            ],
            snapshot=valid_snapshot,
            mark_prices={},  # Missing btc_idr
            evaluation_time=eval_time,
            store=store,
        )

    # 8. Stale revision on approve_adoption
    prop = propose_adoption(
        snapshot_ref="snap-valid",
        assignments=[
            AssetAssignment(pair="btc_idr", asset="btc", strategy_id="s1", quantity=Decimal("0.1"))
        ],
        snapshot=valid_snapshot,
        mark_prices={"btc_idr": Decimal("1000000000"), "eth_idr": Decimal("50000000")},
        evaluation_time=eval_time,
        store=store,
    )
    with pytest.raises(RevisionMismatchError, match="REVISION_MISMATCH"):
        approve_adoption(
            proposal_id=prop.proposal_id,
            expected_revision=999,  # Mismatched revision
            actor="op",
            reason="reason",
            request_id="req-edge-1",
            store=store,
        )

    # 9. Blank actor / reason / request_id
    with pytest.raises(AdoptionError, match="ACTOR_REQUIRED"):
        approve_adoption(
            proposal_id=prop.proposal_id,
            expected_revision=0,
            actor="",
            reason="reason",
            request_id="req-edge-2",
            store=store,
        )
    with pytest.raises(AdoptionError, match="REASON_REQUIRED"):
        approve_adoption(
            proposal_id=prop.proposal_id,
            expected_revision=0,
            actor="op",
            reason="  ",
            request_id="req-edge-3",
            store=store,
        )
    with pytest.raises(AdoptionError, match="REQUEST_ID_REQUIRED"):
        approve_adoption(
            proposal_id=prop.proposal_id,
            expected_revision=0,
            actor="op",
            reason="reason",
            request_id="",
            store=store,
        )

    # 10. Non-existent proposal approval
    with pytest.raises(AdoptionError, match="PROPOSAL_NOT_FOUND"):
        approve_adoption(
            proposal_id="non-existent-prop-999",
            expected_revision=0,
            actor="op",
            reason="reason",
            request_id="req-edge-4",
            store=store,
        )

    # 11. Selling more quantity than adopted
    rec = approve_adoption(
        proposal_id=prop.proposal_id,
        expected_revision=0,
        actor="op",
        reason="Approve 0.1 BTC",
        request_id="req-edge-5",
        store=store,
    )
    assert rec.effective_revision == 1
    with pytest.raises(UnadoptedAssetError, match="SELL_QUANTITY_EXCEEDS_ADOPTED"):
        validate_strategy_sell("s1", "btc_idr", Decimal("0.5"), store=store)

    # 12. Invalid deposit amount / actor / evidence
    with pytest.raises(AdoptionError, match="INVALID_DEPOSIT_AMOUNT"):
        record_verified_deposit(
            amount=Decimal("-100"),
            currency="IDR",
            evidence_ref="ev-1",
            actor="op",
            reason="topup",
            store=store,
        )
    with pytest.raises(AdoptionError, match="ACTOR_REQUIRED"):
        record_verified_deposit(
            amount=Decimal("100"),
            currency="IDR",
            evidence_ref="ev-1",
            actor="",
            reason="topup",
            store=store,
        )
    with pytest.raises(AdoptionError, match="EVIDENCE_REF_REQUIRED"):
        record_verified_deposit(
            amount=Decimal("100"),
            currency="IDR",
            evidence_ref="",
            actor="op",
            reason="topup",
            store=store,
        )


def test_pm_07_service_wrapper(tmp_path: Path) -> None:
    """Verify PortfolioAdoptionService high-level methods."""
    store = AdoptionStore(tmp_path / "adoption_service.db")
    service = PortfolioAdoptionService(store)
    eval_time = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    snapshot = _make_snapshot(server_time=eval_time - timedelta(seconds=2))

    proposal = service.propose(
        snapshot_ref="snap-svc-001",
        assignments=[
            AssetAssignment(pair="btc_idr", asset="btc", strategy_id="s1", quantity=Decimal("0.2"))
        ],
        snapshot=snapshot,
        mark_prices={"btc_idr": Decimal("1000000000"), "eth_idr": Decimal("50000000")},
        evaluation_time=eval_time,
    )
    assert proposal.status == "PROPOSED"

    record = service.approve(
        proposal_id=proposal.proposal_id,
        expected_revision=0,
        actor="operator_lead",
        reason="Service wrapper test",
        request_id="req-svc-001",
    )
    assert record.effective_revision == 1
    assert store.get_pair_owner("btc_idr") == "s1"
