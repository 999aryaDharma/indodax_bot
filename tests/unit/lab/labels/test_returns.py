"""Unit tests for execution-aligned net return labels (LABEL-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest

from indodax_lab.backtest.costs import (
    CostScheduleInterval,
    CostScheduleResolution,
    CostScheduleTable,
    OrderRole,
    OrderSide,
)
from indodax_lab.backtest.execution import ConservativeExecutionSimulator
from indodax_lab.labels.returns import (
    NetReturnConfig,
    NetReturnLabel,
    build_net_return_label,
    build_net_return_labels_frame,
)


BASE_TIME = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
PAIR = "btc_idr"


def test_open_price_proxy_cannot_claim_verified_simulator_fills():
    label = build_net_return_label("proxy", PAIR, BASE_TIME + timedelta(hours=1),
        _make_market_bars(10), NetReturnConfig(cost_schedule_table=_make_schedule_table()))
    assert label.execution_model_version == "open_price_proxy_v2"
    assert label.execution_fidelity == "RESEARCH_PRICE_PROXY_ONLY"
    assert not label.promotion_eligible
    with pytest.raises(ValueError, match="UNSUPPORTED_EXECUTION_MODEL"):
        NetReturnConfig(execution_model_version="conservative_v1")


def test_delayed_entry_observation_delays_label_availability():
    bars = _make_market_bars(10)
    bars[1]["available_at"] = BASE_TIME + timedelta(days=2)
    label = build_net_return_label(
        "delayed", PAIR, BASE_TIME + timedelta(hours=1), bars,
        NetReturnConfig(cost_schedule_table=_make_schedule_table()),
    )
    assert label.label_available_at == BASE_TIME + timedelta(days=2)


def test_other_pair_cannot_supply_label_prices():
    bars = _make_market_bars(10)
    other = [dict(bar, pair="eth_idr", open=Decimal("1")) for bar in bars]
    label = build_net_return_label(
        "mixed", PAIR, BASE_TIME + timedelta(hours=1), other + bars,
        NetReturnConfig(cost_schedule_table=_make_schedule_table()),
    )
    assert label.entry_price == Decimal("501000000")
    assert label.exit_price == Decimal("505000000")


@pytest.mark.parametrize("bar_index", [1, 3, 5])
def test_unclosed_outcome_source_excludes_label(bar_index):
    bars = _make_market_bars(10)
    bars[bar_index]["is_closed"] = False
    label = build_net_return_label(
        "partial", PAIR, BASE_TIME + timedelta(hours=1), bars,
        NetReturnConfig(cost_schedule_table=_make_schedule_table()),
    )
    assert label.status == "EXCLUDED"
    assert label.net_return is None


def test_gap_inside_outcome_horizon_excludes_label():
    bars = _make_market_bars(10)
    del bars[3]
    label = build_net_return_label(
        "gap", PAIR, BASE_TIME + timedelta(hours=1), bars,
        NetReturnConfig(cost_schedule_table=_make_schedule_table()),
    )
    assert label.status == "EXCLUDED"


def test_non_utc_outcome_availability_is_rejected():
    from datetime import timezone

    bars = _make_market_bars(10)
    bars[1]["available_at"] = bars[1]["available_at"].astimezone(
        timezone(timedelta(hours=8))
    )
    with pytest.raises(ValueError, match="UTC"):
        build_net_return_label(
            "tz", PAIR, BASE_TIME + timedelta(hours=1), bars,
            NetReturnConfig(cost_schedule_table=_make_schedule_table()),
        )


def test_duplicate_outcome_bar_cannot_choose_arbitrary_price():
    bars = _make_market_bars(10)
    bars.append(dict(bars[1], open=Decimal("1")))
    with pytest.raises(ValueError, match="DUPLICATE"):
        build_net_return_label(
            "duplicate", PAIR, BASE_TIME + timedelta(hours=1), bars,
            NetReturnConfig(cost_schedule_table=_make_schedule_table()),
        )


def test_closed_outcome_cannot_be_available_before_close():
    bars = _make_market_bars(10)
    bars[5]["available_at"] = bars[5]["open_time"]
    with pytest.raises(ValueError, match="AVAILABILITY"):
        build_net_return_label(
            "early", PAIR, BASE_TIME + timedelta(hours=1), bars,
            NetReturnConfig(cost_schedule_table=_make_schedule_table()),
        )


def test_partial_bar_with_early_availability_remains_auditable():
    bars = _make_market_bars(10)
    bars[5]["available_at"] = bars[5]["open_time"]
    bars[5]["is_closed"] = False
    label = build_net_return_label(
        "partial-early", PAIR, BASE_TIME + timedelta(hours=1), bars,
        NetReturnConfig(cost_schedule_table=_make_schedule_table()),
    )
    assert label.status == "EXCLUDED"
    assert label.exclusion_reason == "UNCLOSED_OUTCOME_SOURCE"


def test_generated_label_frame_flows_through_split_and_training():
    import pandas as pd

    from indodax_lab.labels.materializer import materialize_training_dataset
    from indodax_lab.labels.splits import (
        FoldWindow, SampleRecord, SampleRole, SplitPolicy, assign_folds,
    )

    decision = BASE_TIME + timedelta(hours=1)
    labels = build_net_return_labels_frame(
        [{"sample_id": "real-label", "pair": PAIR, "decision_ts": decision}],
        _make_market_bars(10), NetReturnConfig(cost_schedule_table=_make_schedule_table()),
    )
    assert "label_end_ts" in labels.columns
    records = [SampleRecord(**row) for row in labels[
        ["sample_id", "pair", "decision_ts", "label_end_ts", "label_available_at"]
    ].to_dict("records")]
    splits = assign_folds(records, SplitPolicy(policy_id="real", version="1", folds=[
        FoldWindow(role=SampleRole.TRAIN, start_ts=BASE_TIME,
                   end_ts=BASE_TIME + timedelta(days=1)),
    ]))
    features = pd.DataFrame([{
        "sample_id": "real-label", "pair": PAIR, "decision_ts": decision,
        "row_ready_at": decision, "ret_1": 0.01,
        "eligible": True,
    }])
    artifact = materialize_training_dataset(
        features, labels, splits, "net_return", ["ret_1"], "snapshot", "1", "cs-v1",
    )
    train = artifact.get_role_data("TRAIN")
    assert train["sample_id"].tolist() == ["real-label"]
    assert train["label_end_ts"].tolist() == [BASE_TIME + timedelta(hours=5)]
    assert train["label_available_at"].tolist() == [BASE_TIME + timedelta(hours=6)]


def _make_schedule_table() -> CostScheduleTable:
    intervals = []
    for side in (OrderSide.BUY, OrderSide.SELL):
        intervals.append(
            CostScheduleInterval(
                schedule_id="cs-2024",
                market=PAIR,
                side=side,
                role=OrderRole.TAKER,
                valid_from=BASE_TIME - timedelta(days=10),
                valid_to=None,
                service_fee_rate=Decimal("0.001"),
                tax_rate=Decimal("0.0"),
                exchange_fee_rate=Decimal("0.0"),
                min_notional=Decimal("10000"),
                precision=0,
                sources=("indodax",),
                evidence_verified=True,
            )
        )
    return CostScheduleTable(
        schedule_set_id="cs-v1",
        version="1.0.0",
        intervals=tuple(intervals),
    )


def _make_market_bars(count: int = 15, base_price: Decimal = Decimal("500000000")) -> list[dict]:
    bars = []
    for i in range(count):
        open_time = BASE_TIME + timedelta(hours=i)
        close_time = open_time + timedelta(hours=1)
        price = base_price + Decimal(str(i * 1000000))
        bars.append(
            {
                "pair": PAIR,
                "interval": "1h",
                "bar_id": f"bar-{i}",
                "open_time": open_time,
                "close_time": close_time,
                "available_at": close_time,
                "is_closed": True,
                "open": price,
                "high": price + Decimal("500000"),
                "low": price - Decimal("500000"),
                "close": price + Decimal("200000"),
                "base_volume": Decimal("10"),
                "quote_volume": Decimal("5000000000"),
                "quality_flags": (),
            }
        )
    return bars


def test_label_01_valid_contract() -> None:
    """LABEL-01-AC0: Target return measures net proceeds relative to gross cash debit from execution model."""
    cost_table = _make_schedule_table()
    config = NetReturnConfig(
        label_set_id="net_return",
        version="1.0.0",
        horizon=timedelta(hours=4),
        edge_margin=Decimal("0.001"),
        cost_schedule_table=cost_table,
    )

    bars = _make_market_bars(count=10)
    decision_ts = BASE_TIME + timedelta(hours=1)  # bar-0 closes at BASE + 1h

    label = build_net_return_label(
        sample_id="sample-001",
        pair=PAIR,
        decision_ts=decision_ts,
        bars=bars,
        config=config,
    )

    assert label.status == "VALID"
    assert label.sample_id == "sample-001"
    assert label.decision_ts == decision_ts

    # Entry is at next bar (bar-1) open
    assert label.entry_ts == decision_ts
    assert label.exit_ts == decision_ts + timedelta(hours=4)

    # Net return formula: net_sell_proceeds / total_buy_cash_debit - 1
    # Entry price is bar-1 open: 501,000,000. Buy fee taker 0.001 -> 501,000
    # Buy debit = 501,501,000
    # Exit price is bar-5 open: 505,000,000. Sell fee taker 0.001 -> 505,000
    # Sell proceeds = 504,495,000
    expected_net = (Decimal("504495000") / Decimal("501501000")) - Decimal("1")
    assert label.net_return == expected_net
    assert label.gross_return == (Decimal("505000000") / Decimal("501000000")) - Decimal("1")
    assert label.buy_cost == Decimal("501000")
    assert label.sell_cost == Decimal("505000")

    # Binary label: net_return > 0.001 -> 1
    assert label.binary_label == (1 if label.net_return > config.edge_margin else 0)

    # Availability: label_available_at >= exit_ts
    assert label.label_available_at >= label.exit_ts


def test_label_01_contract_1() -> None:
    """LABEL-01-AC1: Entry at or before decision timestamp is strictly rejected."""
    cost_table = _make_schedule_table()
    config = NetReturnConfig(
        label_set_id="net_return",
        version="1.0.0",
        horizon=timedelta(hours=4),
        cost_schedule_table=cost_table,
    )
    bars = _make_market_bars(count=5)

    # Decision timestamp placed after all bars, so entry would be in the past
    with pytest.raises(ValueError, match="ENTRY_BEFORE_OR_AT_DECISION"):
        build_net_return_label(
            sample_id="sample-causal-err",
            pair=PAIR,
            decision_ts=BASE_TIME + timedelta(hours=10),
            bars=bars,
            config=config,
        )


def test_label_01_contract_2() -> None:
    """LABEL-01-AC2: Incomplete horizon does not become a zero return label."""
    cost_table = _make_schedule_table()
    config = NetReturnConfig(
        label_set_id="net_return",
        version="1.0.0",
        horizon=timedelta(hours=10),  # Horizon requires 10 hours
        cost_schedule_table=cost_table,
    )
    # Provide only 4 bars
    bars = _make_market_bars(count=4)
    decision_ts = BASE_TIME + timedelta(hours=1)

    label = build_net_return_label(
        sample_id="sample-incomplete",
        pair=PAIR,
        decision_ts=decision_ts,
        bars=bars,
        config=config,
    )

    # Must be excluded/censored, NEVER 0.0 or 0
    assert label.status == "EXCLUDED"
    assert label.net_return is None
    assert label.gross_return is None
    assert label.binary_label is None
    assert label.exclusion_reason == "INCOMPLETE_HORIZON"


def test_label_01_contract_3() -> None:
    """LABEL-01-AC3: Unavailable cost schedule or fill produces an excluded sample."""
    # Empty cost schedule table -> cannot look up costs
    empty_cost_table = CostScheduleTable(
        schedule_set_id="cs-empty",
        version="1.0.0",
        intervals=(),
    )
    config = NetReturnConfig(
        label_set_id="net_return",
        version="1.0.0",
        horizon=timedelta(hours=2),
        cost_schedule_table=empty_cost_table,
    )
    bars = _make_market_bars(count=5)
    decision_ts = BASE_TIME + timedelta(hours=1)

    label = build_net_return_label(
        sample_id="sample-cost-unavail",
        pair=PAIR,
        decision_ts=decision_ts,
        bars=bars,
        config=config,
    )

    # Must be excluded
    assert label.status == "EXCLUDED"
    assert label.net_return is None
    assert label.exclusion_reason == "COST_SCHEDULE_UNAVAILABLE"


def test_unverified_cost_schedule_excludes_label() -> None:
    verified = _make_schedule_table()
    unverified = CostScheduleTable(
        schedule_set_id="cs-unverified",
        version="1.0.0",
        intervals=tuple(
            interval.model_copy(update={"evidence_verified": False})
            for interval in verified.intervals
        ),
    )
    config = NetReturnConfig(
        label_set_id="net_return",
        version="1.0.0",
        horizon=timedelta(hours=2),
        cost_schedule_table=unverified,
    )

    label = build_net_return_label(
        sample_id="sample-cost-unverified",
        pair=PAIR,
        decision_ts=BASE_TIME + timedelta(hours=1),
        bars=_make_market_bars(count=5),
        config=config,
    )

    assert label.status == "EXCLUDED"
    assert label.net_return is None
    assert label.exclusion_reason == "COST_SCHEDULE_UNAVAILABLE"


# ---------------------------------------------------------------------------
# TASK E: Cost-aware label materialization contract tests
# ---------------------------------------------------------------------------


def test_label_changes_when_cost_changes() -> None:
    """TASK E: Label net return and costs change when cost schedule table changes."""

    def _make_table_with_fee(fee: Decimal) -> CostScheduleTable:
        intervals = [
            CostScheduleInterval(
                schedule_id=f"cs-{fee}",
                market=PAIR,
                side=side,
                role=OrderRole.TAKER,
                valid_from=BASE_TIME - timedelta(days=10),
                valid_to=None,
                service_fee_rate=fee,
                tax_rate=Decimal("0.0"),
                exchange_fee_rate=Decimal("0.0"),
                min_notional=Decimal("10000"),
                precision=0,
                sources=("indodax",),
                evidence_verified=True,
            )
            for side in (OrderSide.BUY, OrderSide.SELL)
        ]
        return CostScheduleTable(
            schedule_set_id=f"cs-fee-{fee}", version="1.0.0", intervals=tuple(intervals)
        )

    bars = _make_market_bars(10)
    decision = BASE_TIME + timedelta(hours=1)
    cfg_low = NetReturnConfig(cost_schedule_table=_make_table_with_fee(Decimal("0.001")))
    cfg_high = NetReturnConfig(cost_schedule_table=_make_table_with_fee(Decimal("0.005")))

    label_low = build_net_return_label("low", PAIR, decision, bars, cfg_low)
    label_high = build_net_return_label("high", PAIR, decision, bars, cfg_high)

    assert label_low.status == "VALID" and label_high.status == "VALID"
    assert label_low.gross_return == label_high.gross_return
    assert label_low.buy_cost < label_high.buy_cost
    assert label_low.sell_cost < label_high.sell_cost
    assert label_low.net_return > label_high.net_return


def test_delayed_label_excluded_from_training_cutoff() -> None:
    """TASK E: A delayed label with availability after training cutoff is purged from training fold."""
    from indodax_lab.labels.splits import (
        FoldWindow,
        SampleRecord,
        SampleRole,
        SplitPolicy,
        assign_folds,
    )

    decision = BASE_TIME + timedelta(hours=1)
    # exit is at decision + 4h = BASE_TIME + 5h. Delay available_at to BASE_TIME + 25h
    bars = _make_market_bars(10)
    bars[5]["available_at"] = BASE_TIME + timedelta(hours=25)

    label = build_net_return_label(
        "delayed-sample",
        PAIR,
        decision,
        bars,
        NetReturnConfig(cost_schedule_table=_make_schedule_table()),
    )
    assert label.status == "VALID"
    assert label.label_available_at == BASE_TIME + timedelta(hours=25)

    # Train fold ends at BASE_TIME + 24h
    train_fold = FoldWindow(
        role=SampleRole.TRAIN,
        start_ts=BASE_TIME,
        end_ts=BASE_TIME + timedelta(hours=24),
    )
    policy = SplitPolicy(
        policy_id="test-p",
        version="1.0.0",
        max_horizon_hours=4,
        embargo_hours=4,
        folds=[train_fold],
    )

    record = SampleRecord(
        sample_id=label.sample_id,
        decision_ts=label.decision_ts,
        label_end_ts=label.exit_ts,
        pair=label.pair,
        label_available_at=label.label_available_at,
    )
    manifest = assign_folds([record], policy)
    assignment = manifest.assignments[label.sample_id]
    assert assignment.role == SampleRole.PURGED
    assert assignment.purge_reason == "LABEL_OVERLAPS_FOLD_BOUNDARY"


def test_no_future_input_affects_earlier_labels() -> None:
    """TASK E: Changing bars beyond the outcome horizon has zero causal effect on earlier labels."""
    bars_orig = _make_market_bars(10)
    decision = BASE_TIME + timedelta(hours=1)
    cfg = NetReturnConfig(cost_schedule_table=_make_schedule_table())

    label_orig = build_net_return_label("sample-causality", PAIR, decision, bars_orig, cfg)

    # Alter bars after the exit bar (exit bar is index 5 at decision + 4h)
    bars_mutated = [dict(b) for b in bars_orig]
    bars_mutated[7]["open"] = Decimal("999999999")
    bars_mutated[7]["close"] = Decimal("999999999")
    bars_mutated[8]["open"] = Decimal("1")
    bars_mutated[8]["close"] = Decimal("1")

    label_mutated = build_net_return_label("sample-causality", PAIR, decision, bars_mutated, cfg)

    assert label_orig.net_return == label_mutated.net_return
    assert label_orig.gross_return == label_mutated.gross_return
    assert label_orig.entry_price == label_mutated.entry_price
    assert label_orig.exit_price == label_mutated.exit_price
    assert label_orig.buy_cost == label_mutated.buy_cost
    assert label_orig.sell_cost == label_mutated.sell_cost
    assert label_orig.label_available_at == label_mutated.label_available_at


def test_proxy_cannot_be_promoted() -> None:
    """TASK E: Open-price research proxy must remain promotion_eligible=False and cannot claim simulator alignment."""
    cfg = NetReturnConfig(cost_schedule_table=_make_schedule_table())
    label = build_net_return_label(
        "proxy-audit", PAIR, BASE_TIME + timedelta(hours=1), _make_market_bars(10), cfg
    )

    assert label.promotion_eligible is False
    assert label.execution_fidelity == "RESEARCH_PRICE_PROXY_ONLY"
    assert label.execution_model_version == "open_price_proxy_v2"

    with pytest.raises(ValueError, match="UNSUPPORTED_EXECUTION_MODEL"):
        NetReturnConfig(execution_model_version="simulator_v1")
