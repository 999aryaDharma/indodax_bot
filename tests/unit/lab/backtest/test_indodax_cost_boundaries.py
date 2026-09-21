"""Regression tests for point-in-time Indodax IDR cost boundaries."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from indodax_lab.backtest.costs import (
    OrderRole,
    OrderSide,
    load_cost_schedule_table,
    lookup_cost,
)


TABLE = load_cost_schedule_table(Path("configs/costs/indodax_idr_v1.yaml"))


def _cost(ts: datetime, side: OrderSide = OrderSide.BUY, role: OrderRole = OrderRole.MAKER):
    return lookup_cost(TABLE, market="spot_idr", side=side, role=role, event_ts=ts)


def test_cfx_activation_boundary() -> None:
    before = _cost(datetime(2024, 10, 31, 16, 59, 59, tzinfo=UTC))
    after = _cost(datetime(2024, 10, 31, 17, 0, 0, tzinfo=UTC))
    assert before.exchange_fee_rate == Decimal("0")
    assert after.exchange_fee_rate == Decimal("0.000222")


def test_2025_tax_boundary() -> None:
    before = _cost(datetime(2025, 7, 31, 16, 59, 59, tzinfo=UTC))
    after_buy = _cost(datetime(2025, 7, 31, 17, 0, 0, tzinfo=UTC))
    after_sell = _cost(
        datetime(2025, 7, 31, 17, 0, 0, tzinfo=UTC),
        side=OrderSide.SELL,
    )
    assert before.tax_rate == Decimal("0.001200")
    assert before.exchange_fee_rate == Decimal("0.000224")
    assert after_buy.tax_rate == Decimal("0")
    assert after_buy.exchange_fee_rate == Decimal("0.000222")
    assert after_sell.tax_rate == Decimal("0.002100")


def test_2026_cfx_reduction_boundary() -> None:
    before = _cost(datetime(2026, 2, 28, 16, 59, 59, tzinfo=UTC))
    after = _cost(datetime(2026, 2, 28, 17, 0, 0, tzinfo=UTC))
    assert before.exchange_fee_rate == Decimal("0.000222")
    assert after.exchange_fee_rate == Decimal("0.000111")



def test_observed_current_pro_minimum_boundary() -> None:
    before = _cost(datetime(2026, 9, 20, 23, 59, 59, tzinfo=UTC))
    current = _cost(datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC))
    assert before.min_notional == Decimal("10000")
    assert current.min_notional == Decimal("25000")
