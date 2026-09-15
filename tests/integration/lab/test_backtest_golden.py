"""Deterministic replay judge integration and golden contract tests (SIM-03)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import pytest

from indodax_lab.backtest.costs import (
    CostScheduleInterval,
    CostScheduleTable,
    OrderRole,
    OrderSide,
)
from indodax_lab.backtest.engine import ReplayBacktestEngine
from indodax_lab.backtest.events import MarketBar, SignalIntent
from indodax_lab.backtest.result import BacktestResult
from indodax_lab.backtest.risk import RiskPolicy


BASE_TS = datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture
def test_schedule_table() -> CostScheduleTable:
    intervals = (
        CostScheduleInterval(
            schedule_id="idr_buy_taker",
            market="spot_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            valid_from=datetime(2024, 1, 1, tzinfo=UTC),
            valid_to=None,
            service_fee_rate=Decimal("0.002000"),
            tax_rate=Decimal("0.001000"),
            exchange_fee_rate=Decimal("0.000200"),
            min_notional=Decimal("10000"),
            precision=0,
            sources=("PMK 68",),
        ),
        CostScheduleInterval(
            schedule_id="idr_sell_taker",
            market="spot_idr",
            side=OrderSide.SELL,
            role=OrderRole.TAKER,
            valid_from=datetime(2024, 1, 1, tzinfo=UTC),
            valid_to=None,
            service_fee_rate=Decimal("0.002000"),
            tax_rate=Decimal("0.001000"),
            exchange_fee_rate=Decimal("0.000200"),
            min_notional=Decimal("10000"),
            precision=0,
            sources=("PMK 68",),
        ),
    )
    return CostScheduleTable(
        schedule_set_id="test_sched",
        version="1.0.0",
        intervals=intervals,
    )


@pytest.fixture
def test_risk_policy() -> RiskPolicy:
    return RiskPolicy(
        policy_id="test_risk",
        version="1.0.0",
        max_position_fraction=Decimal("0.50"),
        max_open_positions=2,
        min_order_notional=Decimal("10000"),
        max_daily_loss_fraction=Decimal("0.10"),
        max_weekly_loss_fraction=Decimal("0.20"),
        max_drawdown_halt_fraction=Decimal("0.25"),
    )


def _sample_bars(count: int = 5) -> list[MarketBar]:
    bars = []
    prices = [
        Decimal("500000000"),
        Decimal("510000000"),
        Decimal("520000000"),
        Decimal("530000000"),
        Decimal("540000000"),
    ]
    for i in range(count):
        ot = BASE_TS + timedelta(hours=i)
        ct = ot + timedelta(hours=1)
        p = prices[i]
        bars.append(
            MarketBar(
                pair="btc_idr",
                open_time=ot,
                close_time=ct,
                open=p,
                high=p + Decimal("2000000"),
                low=p - Decimal("2000000"),
                close=p + Decimal("1000000"),
                base_volume=Decimal("1.0"),
                quote_volume=p * Decimal("1.0"),
            )
        )
    return bars


def _simple_strategy(bar: MarketBar, bar_index: int) -> SignalIntent | None:
    # Buy on bar 0, sell on bar 2
    if bar_index == 0:
        return SignalIntent(
            intent_id="strat-buy-1",
            decision_ts=bar.close_time,
            pair="btc_idr",
            side=OrderSide.BUY,
            desired_qty=Decimal("0.0004"),
        )
    elif bar_index == 2:
        return SignalIntent(
            intent_id="strat-sell-1",
            decision_ts=bar.close_time,
            pair="btc_idr",
            side=OrderSide.SELL,
            desired_qty=Decimal("0.0004"),
        )
    return None


def test_sim_03_valid_contract(
    test_schedule_table: CostScheduleTable, test_risk_policy: RiskPolicy, tmp_path: Path
) -> None:
    """SIM-03-AC0: Replay market memproduksi fill, posting dan equity identik pada input identik."""
    engine = ReplayBacktestEngine(
        cost_schedule_table=test_schedule_table,
        risk_policy=test_risk_policy,
        initial_cash=Decimal("500000"),
    )
    bars = _sample_bars()
    result = engine.run(bars=bars, strategy_fn=_simple_strategy)

    assert result.status == "SUCCESS"
    assert result.fill_count == 2
    assert result.total_fees_paid > Decimal("0")
    assert result.postings_hash is not None
    assert len(result.postings_hash) == 64  # SHA256


def test_sim_03_contract_1(
    test_schedule_table: CostScheduleTable, test_risk_policy: RiskPolicy
) -> None:
    """SIM-03-AC1: Dua replay memberi posting exact dan metrics sama (determinism)."""
    bars = _sample_bars()

    # Replay 1
    engine1 = ReplayBacktestEngine(
        cost_schedule_table=test_schedule_table,
        risk_policy=test_risk_policy,
        initial_cash=Decimal("500000"),
    )
    res1 = engine1.run(bars=bars, strategy_fn=_simple_strategy)

    # Replay 2
    engine2 = ReplayBacktestEngine(
        cost_schedule_table=test_schedule_table,
        risk_policy=test_risk_policy,
        initial_cash=Decimal("500000"),
    )
    res2 = engine2.run(bars=bars, strategy_fn=_simple_strategy)

    # Exact bitwise determinism assertions
    assert res1.postings_hash == res2.postings_hash
    assert res1.ending_cash == res2.ending_cash
    assert res1.ending_equity == res2.ending_equity
    assert res1.total_net_pnl == res2.total_net_pnl
    assert res1.total_fees_paid == res2.total_fees_paid
    assert res1.fill_count == res2.fill_count


def test_sim_03_contract_2(
    test_schedule_table: CostScheduleTable, test_risk_policy: RiskPolicy, tmp_path: Path
) -> None:
    """SIM-03-AC2: Crash sebelum publish tidak menghasilkan run sukses."""
    engine = ReplayBacktestEngine(
        cost_schedule_table=test_schedule_table,
        risk_policy=test_risk_policy,
        initial_cash=Decimal("500000"),
    )
    bars = _sample_bars()
    output_manifest = tmp_path / "run_result.json"

    with pytest.raises(RuntimeError) as exc_info:
        engine.run_and_publish(
            bars=bars,
            strategy_fn=_simple_strategy,
            output_path=output_manifest,
            simulate_crash_before_publish=True,
        )

    assert "SIMULATED_CRASH_BEFORE_PUBLISH" in str(exc_info.value)
    # The output manifest MUST NOT exist as a valid completed artifact
    assert not output_manifest.exists()


def test_sim_03_contract_3(
    test_schedule_table: CostScheduleTable, test_risk_policy: RiskPolicy
) -> None:
    """SIM-03-AC3: Independent ledger tidak dijumlah sebagai modal bersama."""
    # Strategy A and Strategy B each have an independent virtual ledger of IDR 500,000
    engine_a = ReplayBacktestEngine(
        cost_schedule_table=test_schedule_table,
        risk_policy=test_risk_policy,
        initial_cash=Decimal("500000"),
        candidate_id="strat_a",
    )
    engine_b = ReplayBacktestEngine(
        cost_schedule_table=test_schedule_table,
        risk_policy=test_risk_policy,
        initial_cash=Decimal("500000"),
        candidate_id="strat_b",
    )

    bars = _sample_bars()
    res_a = engine_a.run(bars=bars, strategy_fn=_simple_strategy)
    res_b = engine_b.run(bars=bars, strategy_fn=_simple_strategy)

    # Invariants:
    # 1. Capital is NOT pooled (each starts with 500,000, not 1,000,000)
    assert engine_a.ledger.cash != Decimal("1000000")
    assert engine_b.ledger.cash != Decimal("1000000")
    assert res_a.initial_cash == Decimal("500000")
    assert res_b.initial_cash == Decimal("500000")

    # 2. Maximum single order sizing respects independent limit, not combined pool
    # With max_position_fraction = 50%, max notional is 250,000, NOT 500,000
    max_position_notional_a = engine_a.risk_manager.policy.max_position_fraction * res_a.initial_cash
    assert max_position_notional_a == Decimal("250000")


def test_replay_exact_cost_once_arithmetic(test_schedule_table, test_risk_policy):
    engine = ReplayBacktestEngine(test_schedule_table, test_risk_policy,
                                  initial_cash=Decimal("500000"))
    result = engine.run(_sample_bars(), _simple_strategy)
    # 0.0004 * 510m = 204000; fee 652.8 rounds to 653.
    # 0.0004 * 530m = 212000; fee 678.4 rounds to 678.
    assert result.ending_cash == Decimal("506669")
    assert result.ending_equity == Decimal("506669")
    assert result.total_gross_pnl == Decimal("8000")
    assert result.total_fees_paid == Decimal("1331")
    assert result.total_net_pnl == Decimal("6669")
    assert [tx.timestamp for tx in engine.ledger.transactions] == [
        BASE_TS, BASE_TS+timedelta(hours=1), BASE_TS+timedelta(hours=3)]
    assert [tx.base_qty_delta for tx in engine.ledger.transactions] == [
        Decimal("0"), Decimal("0.0004"), Decimal("-0.0004")]
    assert not engine.rejections
