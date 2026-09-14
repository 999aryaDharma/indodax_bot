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
