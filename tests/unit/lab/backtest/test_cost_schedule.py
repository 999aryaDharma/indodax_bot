"""Strict time-valid exchange cost schedule contract tests (COST-01)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from indodax_lab.backtest.costs import (
    CostScheduleResolution,
    OrderRole,
    OrderSide,
    UnknownCostScheduleError,
    load_cost_schedule_table,
    lookup_cost,
)

ROOT = Path(__file__).parents[4]
CANONICAL_COST_CONFIG = ROOT / "configs" / "costs" / "indodax_idr_v1.yaml"


def _sample_schedule_yaml(extra_interval: str = "") -> str:
    return (
        "schedule_set_id: indodax_idr\n"
        "version: 2.0.0\n"
        "intervals:\n"
        "  - schedule_id: indodax_idr_2022_h2\n"
        "    evidence_verified: true\n"
        "    market: spot_idr\n"
        "    side: buy\n"
        "    role: taker\n"
        "    valid_from: '2022-05-01T00:00:00Z'\n"
        "    valid_to: '2024-01-01T00:00:00Z'\n"
        "    service_fee_rate: '0.002000'\n"
        "    tax_rate: '0.001100'\n"
        "    exchange_fee_rate: '0.000000'\n"
        "    min_notional: '10000'\n"
        "    precision: 0\n"
        "    sources:\n"
        "      - 'COST-01 deterministic contract fixture'\n"
        "  - schedule_id: indodax_idr_2024_current\n"
        "    evidence_verified: true\n"
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
        "    sources:\n"
        "      - 'COST-01 deterministic contract fixture'\n"
        f"{extra_interval}"
    )


def test_cost_01_valid_contract(tmp_path: Path) -> None:
    """COST-01-AC0: Lookup fee memilih schedule historis yang tepat atau memblokir klaim promosi."""
    fixture = tmp_path / "verified-costs.yaml"
    fixture.write_text(_sample_schedule_yaml(), encoding="utf-8")
    table = load_cost_schedule_table(fixture)
    assert table.schedule_set_id == "indodax_idr"
    assert table.version == "2.0.0"
    assert len(table.intervals) > 0

    # Historical lookup during 2023
    fee_basis_ts = datetime(2023, 6, 15, 12, 0, 0, tzinfo=UTC)
    res_buy = lookup_cost(
        table,
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        fee_basis_ts=fee_basis_ts,
    )
    assert isinstance(res_buy, CostScheduleResolution)
    assert res_buy.schedule_id == "indodax_idr_2022_h2"
    assert res_buy.market == "spot_idr"
    assert res_buy.side is OrderSide.BUY
    assert res_buy.role is OrderRole.TAKER
    assert res_buy.valid_from <= fee_basis_ts
    assert res_buy.valid_to is None or fee_basis_ts < res_buy.valid_to
    assert isinstance(res_buy.service_fee_rate, Decimal)
    assert isinstance(res_buy.tax_rate, Decimal)
    assert isinstance(res_buy.exchange_fee_rate, Decimal)
    assert isinstance(res_buy.total_rate, Decimal)
    assert res_buy.total_rate == (
        res_buy.service_fee_rate + res_buy.tax_rate + res_buy.exchange_fee_rate
    )
    assert res_buy.service_fee_rate == Decimal("0.002000")
    assert res_buy.tax_rate == Decimal("0.001100")
    assert res_buy.exchange_fee_rate == Decimal("0.000000")
    assert res_buy.total_rate == Decimal("0.003100")
    assert res_buy.min_notional > Decimal(0)
    assert len(res_buy.sources) > 0

    # Current lookup during 2025
    now_ts = datetime(2025, 3, 1, 0, 0, 0, tzinfo=UTC)
    res_now = lookup_cost(
        table,
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        fee_basis_ts=now_ts,
    )
    assert isinstance(res_now, CostScheduleResolution)
    assert res_now.schedule_id == "indodax_idr_2024_current"
    assert res_now.total_rate == Decimal("0.003411")
    assert res_now.side is OrderSide.BUY
    assert res_now.valid_from <= now_ts
    assert res_now.valid_to is None or now_ts < res_now.valid_to


def test_unverified_canonical_schedule_is_not_resolved() -> None:
    """Unverified fee assumptions must not look like approved schedule data."""
    with pytest.raises(ValueError, match="UNVERIFIED_COST_SCHEDULE"):
        lookup_cost(
            load_cost_schedule_table(CANONICAL_COST_CONFIG),
            market="spot_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            fee_basis_ts=datetime(2023, 6, 15, 12, 0, 0, tzinfo=UTC),
        )


def test_cost_01_contract_1(tmp_path: Path) -> None:
    """COST-01-AC1: Overlap schedule key sama ditolak."""
    overlap_interval = (
        "  - schedule_id: indodax_idr_overlapping\n"
        "    market: spot_idr\n"
        "    side: buy\n"
        "    role: taker\n"
        "    valid_from: '2023-01-01T00:00:00Z'\n"
        "    valid_to: '2024-06-01T00:00:00Z'\n"
        "    service_fee_rate: '0.001000'\n"
        "    tax_rate: '0.001000'\n"
        "    exchange_fee_rate: '0.000000'\n"
        "    min_notional: '10000'\n"
        "    precision: 0\n"
        "    sources:\n"
        "      - 'Conflict test'\n"
    )
    overlap_file = tmp_path / "overlap.yaml"
    overlap_file.write_text(
        _sample_schedule_yaml(extra_interval=overlap_interval), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="OVERLAPPING_COST_SCHEDULE"):
        load_cost_schedule_table(overlap_file)


def test_cost_01_contract_2(tmp_path: Path) -> None:
    """COST-01-AC2: Boundary end memilih interval berikutnya."""
    boundary_file = tmp_path / "boundary.yaml"
    boundary_file.write_text(_sample_schedule_yaml(), encoding="utf-8")
    table = load_cost_schedule_table(boundary_file)

    # At exactly 2024-01-01T00:00:00Z, [2022-05-01, 2024-01-01) has ended,
    # and [2024-01-01, null) starts.
    boundary_ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    res = lookup_cost(
        table,
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        fee_basis_ts=boundary_ts,
    )
    assert res.schedule_id == "indodax_idr_2024_current"
    assert res.service_fee_rate == Decimal("0.002111")

    # One microsecond before 2024-01-01 still belongs to 2022_h2
    before_ts = datetime(2023, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    res_before = lookup_cost(
        table,
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        fee_basis_ts=before_ts,
    )
    assert res_before.schedule_id == "indodax_idr_2022_h2"
    assert res_before.service_fee_rate == Decimal("0.002000")


def test_limit_order_uses_creation_time_across_fee_boundary(tmp_path: Path) -> None:
    """A limit order created before a fee change keeps the older schedule."""
    boundary_file = tmp_path / "boundary.yaml"
    boundary_file.write_text(_sample_schedule_yaml(), encoding="utf-8")
    table = load_cost_schedule_table(boundary_file)
    created_at = datetime(2023, 12, 31, 23, 59, 59, tzinfo=UTC)
    executed_at = datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC)

    result = lookup_cost(
        table,
        market="spot_idr",
        side=OrderSide.BUY,
        role=OrderRole.TAKER,
        fee_basis_ts=created_at,
    )

    assert executed_at > datetime(2024, 1, 1, tzinfo=UTC)
    assert result.schedule_id == "indodax_idr_2022_h2"


def test_cost_01_contract_3(tmp_path: Path) -> None:
    """COST-01-AC3: Periode unknown tidak memakai fee hari ini."""
    uncovered_file = tmp_path / "uncovered.yaml"
    uncovered_file.write_text(_sample_schedule_yaml(), encoding="utf-8")
    table = load_cost_schedule_table(uncovered_file)

    # 2020 is not covered in the schedule table
    unknown_ts = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    with pytest.raises(UnknownCostScheduleError, match="UNKNOWN_COST_SCHEDULE"):
        lookup_cost(
            table,
            market="spot_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            fee_basis_ts=unknown_ts,
        )


def test_cost_schedule_rejects_negative_rate_and_naive_datetime(tmp_path: Path) -> None:
    """Rates must be nonnegative and fee_basis_ts must be timezone-aware UTC."""
    negative_file = tmp_path / "negative.yaml"
    negative_file.write_text(
        _sample_schedule_yaml().replace(
            "service_fee_rate: '0.002000'", "service_fee_rate: '-0.001'"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="NON_NEGATIVE_RATE_REQUIRED"):
        load_cost_schedule_table(negative_file)

    valid_file = tmp_path / "valid.yaml"
    valid_file.write_text(_sample_schedule_yaml(), encoding="utf-8")
    table = load_cost_schedule_table(valid_file)
    naive_ts = datetime(2024, 6, 1, 0, 0, 0)
    with pytest.raises(ValueError, match="UTC_TIMEZONE_AWARE_REQUIRED"):
        lookup_cost(
            table,
            market="spot_idr",
            side=OrderSide.BUY,
            role=OrderRole.TAKER,
            fee_basis_ts=naive_ts,
        )
