"""Unit tests for G01-01 Point-in-time graph challenger.

Guarantees:
1. G01-01-AC0: PIT graph model menghasilkan cross-asset forecast via common mapper (test_g01_01_valid_contract).
2. G01-01-AC1: Full sample adjacency ditolak fail-closed (test_g01_01_contract_1).
3. G01-01-AC2: New listing tidak masuk graph lama; premature node ditolak fail-closed (test_g01_01_contract_2).
4. G01-01-AC3: Dibandingkan no-edge MLP dan panel regression (test_g01_01_contract_3).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
)
from indodax_lab.models.graph.g01_cross_asset import (
    CrossAssetGNNRanker,
    FullSampleAdjacencyLeakageError,
    GraphBaselineComparator,
    GraphBudgetExceededError,
    PointInTimeGraphBuilder,
    PointInTimeGraphConfig,
    PrematureNodeInclusionError,
)


def _generate_synthetic_panel_data(
    n_bars: int = 50,
    assets: list[str] | None = None,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict[str, datetime]]:
    assets = assets or ["BTC_IDR", "ETH_IDR", "SOL_IDR", "XRP_IDR"]
    rng = np.random.default_rng(seed)

    start_ts = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    listing_dates = {
        "BTC_IDR": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        "ETH_IDR": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        "SOL_IDR": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        "XRP_IDR": datetime(2025, 1, 2, 0, 0, tzinfo=UTC),  # Listed after 24 bars!
    }

    records: list[dict] = []
    for t in range(n_bars):
        bar_ts = start_ts + timedelta(hours=t)
        for asset in assets:
            if bar_ts >= listing_dates[asset]:
                ret = rng.normal(0.001, 0.02)
                vol = rng.uniform(0.01, 0.05)
                mom = rng.normal(0.0, 1.0)
                records.append(
                    {
                        "timestamp": bar_ts,
                        "asset": asset,
                        "return": ret,
                        "volatility": vol,
                        "momentum": mom,
                        "forward_return": rng.normal(0.002, 0.015),
                    }
                )

    df = pd.DataFrame(records)
    return df, listing_dates


def test_g01_01_valid_contract() -> None:
    """G01-01-AC0: PIT graph model menghasilkan cross-asset forecast via common mapper."""
    df, listing_dates = _generate_synthetic_panel_data()

    config = PointInTimeGraphConfig(
        rolling_window=10,
        correlation_threshold=0.2,
        top_k=2,
    )
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)

    # Evaluate at bar 35 (all assets listed)
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    graph_snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts)

    assert len(graph_snapshot.active_nodes) == 4
    assert graph_snapshot.adjacency_matrix.shape == (4, 4)

    ranker = CrossAssetGNNRanker(config=config)
    ranked_assets = ranker.rank(graph_snapshot)

    assert len(ranked_assets) == 4
    assert ranked_assets[0].score >= ranked_assets[1].score

    # Route top-K picks to CostAwareExecutionMapper
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    decisions = ranker.generate_execution_decisions(
        ranked_assets=ranked_assets[:config.top_k],
        decision_ts=eval_ts,
        mapper=mapper,
        desired_qty=Decimal("0.05"),
    )

    assert len(decisions) == 2
    for dec in decisions:
        assert dec.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)


def test_g01_01_contract_1() -> None:
    """G01-01-AC1: Full sample adjacency ditolak fail-closed."""
    df, listing_dates = _generate_synthetic_panel_data()

    config = PointInTimeGraphConfig(rolling_window=10)
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)

    eval_ts = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

    # Attempting to pass future data (timestamps > eval_ts) to adjacency calculation must fail
    future_data = df[df["timestamp"] > eval_ts]
    with pytest.raises(FullSampleAdjacencyLeakageError, match="FULL_SAMPLE_LEAKAGE_FORBIDDEN"):
        builder.build_snapshot(df=future_data, eval_ts=eval_ts)


def test_g01_01_contract_2() -> None:
    """G01-01-AC2: New listing tidak masuk graph lama; premature node ditolak fail-closed."""
    df, listing_dates = _generate_synthetic_panel_data()

    config = PointInTimeGraphConfig(rolling_window=10)
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)

    # XRP_IDR is listed at 2025-01-02 00:00:00
    # Evaluate at 2025-01-01 10:00:00 (before XRP listing)
    eval_ts_early = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
    snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts_early)

    # XRP must not be in active nodes
    assert "XRP_IDR" not in snapshot.active_nodes
    assert len(snapshot.active_nodes) == 3

    # Attempting to explicitly force an unlisted node must be rejected
    with pytest.raises(PrematureNodeInclusionError, match="PREMATURE_NODE_INCLUSION"):
        builder.build_snapshot(df=df, eval_ts=eval_ts_early, forced_nodes=["BTC_IDR", "XRP_IDR"])


def test_g01_01_contract_3() -> None:
    """G01-01-AC3: Dibandingkan no-edge MLP dan panel regression."""
    df, listing_dates = _generate_synthetic_panel_data()

    config = PointInTimeGraphConfig(rolling_window=10, top_k=2)
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)

    eval_ts = datetime(2025, 1, 2, 15, 0, tzinfo=UTC)
    snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts)

    comparator = GraphBaselineComparator()
    comparison = comparator.compare(snapshot)

    assert comparison.graph_score_correlation is not None
    assert comparison.no_edge_mlp_correlation is not None
    assert comparison.panel_regression_correlation is not None
    assert comparison.benchmark_sample_count == len(snapshot.active_nodes)
