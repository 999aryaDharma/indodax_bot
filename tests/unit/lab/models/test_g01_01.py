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
    GraphSnapshotUnderdeterminedError,
    MissingGraphColumnError,
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


def test_g01_01_snapshot_requires_forward_return_column() -> None:
    """Critical: a missing `forward_return` column silently became a 0.0 target.

    `last_row.get("forward_return", 0.0)` produced a constant zero target, so every
    Spearman correlation reported 0.0 and the baseline comparison looked like a
    legitimate "no graph benefit" result. A missing target column must be rejected.
    """
    df, listing_dates = _generate_synthetic_panel_data()
    no_target = df.drop(columns=["forward_return"])

    builder = PointInTimeGraphBuilder(
        config=PointInTimeGraphConfig(rolling_window=10), listing_dates=listing_dates
    )
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)

    with pytest.raises(MissingGraphColumnError, match="MISSING_GRAPH_COLUMN"):
        builder.build_snapshot(df=no_target, eval_ts=eval_ts)


def test_g01_01_constant_target_reports_undefined_correlation_not_zero() -> None:
    """Critical: an undefined Spearman correlation was reported as a real 0.0.

    Reporting `0.0` conflates "perfectly uncorrelated" with "not computable", which is
    exactly the evidence a graph-vs-baseline promotion decision reads. It must be `None`.
    """
    df, listing_dates = _generate_synthetic_panel_data()
    df = df.copy()
    df["forward_return"] = 0.0

    builder = PointInTimeGraphBuilder(
        config=PointInTimeGraphConfig(rolling_window=10), listing_dates=listing_dates
    )
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts)

    comparison = GraphBaselineComparator().compare(snapshot)

    assert comparison.graph_score_correlation is None
    assert comparison.no_edge_mlp_correlation is None
    assert comparison.panel_regression_correlation is None


def test_g01_01_comparison_requires_at_least_three_nodes() -> None:
    """Important: Spearman over 2 assets cannot separate signal from coincidence."""
    df, listing_dates = _generate_synthetic_panel_data(assets=["BTC_IDR", "ETH_IDR"])
    listing_dates = {k: v for k, v in listing_dates.items() if k in {"BTC_IDR", "ETH_IDR"}}

    builder = PointInTimeGraphBuilder(
        config=PointInTimeGraphConfig(rolling_window=10), listing_dates=listing_dates
    )
    eval_ts = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts)
    assert len(snapshot.active_nodes) == 2

    with pytest.raises(GraphSnapshotUnderdeterminedError, match="UNDERDETERMINED_GRAPH_SNAPSHOT"):
        GraphBaselineComparator().compare(snapshot)


def test_g01_01_forced_node_without_observations_is_rejected() -> None:
    """Critical: a listed-but-dateless node produced a malformed snapshot.

    The node got zeroed node features and a zero target while still consuming a row and
    column of the adjacency matrix, so the shape guarantee broke downstream in matmul.
    """
    df, listing_dates = _generate_synthetic_panel_data()
    # Drop every SOL observation so it is listed but has no data at eval_ts.
    df = df[df["asset"] != "SOL_IDR"].reset_index(drop=True)

    builder = PointInTimeGraphBuilder(
        config=PointInTimeGraphConfig(rolling_window=10), listing_dates=listing_dates
    )
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)

    with pytest.raises(PrematureNodeInclusionError, match="NO_OBSERVATIONS_AT_EVAL_TS"):
        builder.build_snapshot(
            df=df, eval_ts=eval_ts, forced_nodes=["BTC_IDR", "ETH_IDR", "SOL_IDR"]
        )


def test_g01_01_snapshot_binds_edge_provenance_metadata() -> None:
    """Important: snapshot carried no edge provenance (spec 15 line 15).

    "Graph metadata binds edge method/window/train cutoff and availability" -- without
    these, a snapshot cannot be shown to have been built from pre-cutoff edges only.
    """
    df, listing_dates = _generate_synthetic_panel_data()
    config = PointInTimeGraphConfig(rolling_window=10, correlation_threshold=0.2, top_k=2)
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)

    snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts)

    assert snapshot.edge_method == "rolling_pearson_thresholded_symmetric"
    assert snapshot.edge_window == 10
    assert snapshot.edge_train_cutoff == eval_ts
    assert snapshot.edges_available_at == eval_ts
    assert snapshot.edges_available_at <= snapshot.edge_train_cutoff


def test_g01_01_future_perturbation_does_not_change_snapshot() -> None:
    """AC1 positive evidence: a full-sample frame equals the pre-truncated frame.

    The rejection path proves the guard fires; this proves the guard is also satisfied
    automatically, i.e. no later bar can reach an earlier snapshot.
    """
    df, listing_dates = _generate_synthetic_panel_data()
    config = PointInTimeGraphConfig(rolling_window=10)
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)

    full_frame = builder.build_snapshot(df=df, eval_ts=eval_ts)
    truncated = builder.build_snapshot(
        df=df[df["timestamp"] <= eval_ts].reset_index(drop=True), eval_ts=eval_ts
    )

    assert full_frame.active_nodes == truncated.active_nodes
    np.testing.assert_array_equal(full_frame.node_features, truncated.node_features)
    np.testing.assert_allclose(full_frame.adjacency_matrix, truncated.adjacency_matrix)
    np.testing.assert_allclose(full_frame.forward_returns, truncated.forward_returns)


def test_g01_01_comparator_benchmarks_the_ranker_in_use() -> None:
    """Important: compare() hardcoded its own config, benchmarking a different model.

    Passing a ranker trained with a different seed/window must change the graph
    correlation, otherwise the AC3 benchmark is not about the model under test.
    """
    df, listing_dates = _generate_synthetic_panel_data()
    config = PointInTimeGraphConfig(rolling_window=10, top_k=2)
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts)

    ranker_a = CrossAssetGNNRanker(config=PointInTimeGraphConfig(rolling_window=10, seed=1))
    ranker_b = CrossAssetGNNRanker(config=PointInTimeGraphConfig(rolling_window=10, seed=7))

    with_a = GraphBaselineComparator(ranker=ranker_a).compare(snapshot)
    with_b = GraphBaselineComparator(ranker=ranker_b).compare(snapshot)

    assert (with_a.graph_score_correlation, with_a.no_edge_mlp_correlation) != (
        with_b.graph_score_correlation,
        with_b.no_edge_mlp_correlation,
    )
    assert with_a.ranker_seed == 1
    assert with_b.ranker_seed == 7


def test_g01_01_search_budget_cannot_exceed_eight() -> None:
    """Spec 15: "<=8 configurations"; a declared budget above 8 must fail closed."""
    assert PointInTimeGraphConfig(max_configurations=8).max_configurations == 8
    with pytest.raises(GraphBudgetExceededError, match="GRAPH_BUDGET_EXCEEDED"):
        PointInTimeGraphConfig(max_configurations=9)


def test_g01_01_rolling_window_floor_is_enforced() -> None:
    """A window below 5 bars cannot support a correlation edge and is rejected."""
    with pytest.raises(ValueError, match="ROLLING_WINDOW_TOO_SMALL"):
        PointInTimeGraphConfig(rolling_window=4)


def test_g01_01_reports_compute_budget() -> None:
    """Important: no parameter/compute budget was reported for the graph model."""
    df, listing_dates = _generate_synthetic_panel_data()
    config = PointInTimeGraphConfig(rolling_window=10)
    builder = PointInTimeGraphBuilder(config=config, listing_dates=listing_dates)
    eval_ts = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
    snapshot = builder.build_snapshot(df=df, eval_ts=eval_ts)

    ranker = CrossAssetGNNRanker(config=config)
    budget = ranker.compute_budget

    assert budget.total_learned_parameters == 3 * 8 + 3 * 8 + 8 * 1
    assert budget.hidden_dim == 8
    assert budget.input_dim == 3
    assert budget.estimated_flops_per_inference > 0

    comparison = GraphBaselineComparator(ranker=ranker).compare(snapshot)
    assert comparison.compute_budget is not None
    assert comparison.compute_budget.total_learned_parameters == budget.total_learned_parameters
    assert comparison.benchmark_sample_count == len(snapshot.active_nodes)
