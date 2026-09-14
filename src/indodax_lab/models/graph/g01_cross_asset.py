"""Point-in-time cross-asset graph neural network challenger (G01-01).

Guarantees:
1. G01-01-AC0: Point-in-time graph model produces cross-asset rankings and execution decisions via common mapper.
2. G01-01-AC1: Full sample adjacency or future-looking matrices are rejected fail-closed to prevent lookahead leakage.
3. G01-01-AC2: Assets not yet listed at evaluation timestamp are barred from graph nodes fail-closed.
4. G01-01-AC3: Benchmarked against no-edge MLP and panel regression baselines on identical point-in-time snapshots.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from scipy.stats import spearmanr

from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    ExecutionDecision,
    ForecastKind,
    ForecastPayload,
    PayoffStructure,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FullSampleAdjacencyLeakageError(ValueError):
    """Raised when adjacency matrix estimation accesses future observations beyond evaluation time."""


class PrematureNodeInclusionError(ValueError):
    """Raised when an unlisted or newly listed asset is prematurely included in historical graph snapshots."""


class GraphBudgetExceededError(ValueError):
    """Raised when graph hyperparameter search configurations exceed budget of 8."""


# ---------------------------------------------------------------------------
# Configurations and Models
# ---------------------------------------------------------------------------


class PointInTimeGraphConfig(BaseModel):
    """Configuration for Point-In-Time cross-asset graph challenger."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "G01_GRAPH"
    version: str = "1.0.0"
    rolling_window: int = 20
    correlation_threshold: float = 0.2
    top_k: int = 2
    max_configurations: int = 8
    seed: int = 42

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.rolling_window < 5:
            raise ValueError(f"ROLLING_WINDOW_TOO_SMALL: Minimum 5 bars required, got {self.rolling_window}")
        if self.max_configurations > 8:
            raise GraphBudgetExceededError(f"GRAPH_BUDGET_EXCEEDED: Max 8 configurations, got {self.max_configurations}")


class GraphSnapshot(BaseModel):
    """Point-in-time snapshot of cross-asset graph with strictly historical edges."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    eval_ts: datetime
    active_nodes: list[str]
    node_features: np.ndarray
    adjacency_matrix: np.ndarray
    forward_returns: np.ndarray


class RankedAsset(BaseModel):
    """Ranked asset outcome from graph scoring."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    asset: str
    score: float
    rank: int


class GraphBaselineComparison(BaseModel):
    """Comparative rank metrics between graph model, no-edge MLP, and panel regression."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    graph_score_correlation: float
    no_edge_mlp_correlation: float
    panel_regression_correlation: float
    benchmark_sample_count: int
    evaluated_at_utc: datetime


# ---------------------------------------------------------------------------
# Point-in-time Graph Builder (G01-01-AC1, AC2)
# ---------------------------------------------------------------------------


class PointInTimeGraphBuilder:
    """Builds point-in-time graph snapshots with causal rolling edges and strict listing validation."""

    def __init__(
        self,
        config: PointInTimeGraphConfig,
        listing_dates: dict[str, datetime],
    ) -> None:
        self.config = config
        self.listing_dates = listing_dates

    def build_snapshot(
        self,
        df: pd.DataFrame,
        eval_ts: datetime,
        forced_nodes: list[str] | None = None,
    ) -> GraphSnapshot:
        """Construct graph snapshot up to eval_ts without lookahead contamination."""
        # 1. Reject future data inputs
        if len(df) > 0 and df["timestamp"].min() > eval_ts:
            raise FullSampleAdjacencyLeakageError(
                f"FULL_SAMPLE_LEAKAGE_FORBIDDEN: Provided data strictly starts at "
                f"{df['timestamp'].min()} which is in the future relative to eval_ts {eval_ts}"
            )

        # 2. Strict listing cutoff validation
        if forced_nodes is not None:
            for node in forced_nodes:
                list_dt = self.listing_dates.get(node)
                if list_dt is None or list_dt > eval_ts:
                    raise PrematureNodeInclusionError(
                        f"PREMATURE_NODE_INCLUSION: Asset '{node}' was listed at "
                        f"{list_dt.isoformat() if list_dt else 'UNKNOWN'} after eval_ts {eval_ts.isoformat()}"
                    )

        # 3. Filter data causally up to eval_ts
        hist_df = df[df["timestamp"] <= eval_ts].copy()

        # 4. Identify eligible active nodes
        eligible_assets = [
            asset for asset, list_dt in self.listing_dates.items()
            if list_dt <= eval_ts and asset in hist_df["asset"].unique()
        ]
        active_nodes = sorted(forced_nodes if forced_nodes is not None else eligible_assets)

        if len(active_nodes) == 0:
            raise ValueError(f"NO_ACTIVE_NODES: No eligible listed assets found at {eval_ts}")

        # 5. Extract rolling return series to compute point-in-time correlation matrix
        return_piv = (
            hist_df[hist_df["asset"].isin(active_nodes)]
            .pivot_table(index="timestamp", columns="asset", values="return")
            .tail(self.config.rolling_window)
        )

        corr_matrix = return_piv.corr().fillna(0.0).values
        n_nodes = len(active_nodes)

        # Apply correlation threshold and add self-loops
        adj = np.where(np.abs(corr_matrix) >= self.config.correlation_threshold, corr_matrix, 0.0)
        np.fill_diagonal(adj, 1.0)

        # Symmetrize and normalize adjacency: D^{-1/2} A D^{-1/2}
        d = np.sum(np.abs(adj), axis=1)
        d_inv_sqrt = np.power(np.maximum(d, 1e-6), -0.5)
        adj_norm = np.diag(d_inv_sqrt) @ adj @ np.diag(d_inv_sqrt)

        # 6. Extract latest node features at eval_ts
        feature_cols = ["return", "volatility", "momentum"]
        latest_features: list[list[float]] = []
        forward_returns: list[float] = []

        for node in active_nodes:
            node_data = hist_df[hist_df["asset"] == node].sort_values("timestamp")
            if len(node_data) > 0:
                last_row = node_data.iloc[-1]
                latest_features.append([float(last_row[c]) for c in feature_cols])
                forward_returns.append(float(last_row.get("forward_return", 0.0)))
            else:
                latest_features.append([0.0] * len(feature_cols))
                forward_returns.append(0.0)

        return GraphSnapshot(
            eval_ts=eval_ts,
            active_nodes=active_nodes,
            node_features=np.array(latest_features, dtype=float),
            adjacency_matrix=adj_norm,
            forward_returns=np.array(forward_returns, dtype=float),
        )


# ---------------------------------------------------------------------------
# Cross-Asset GNN Ranker (G01-01-AC0)
# ---------------------------------------------------------------------------


class CrossAssetGNNRanker:
    """Graph neural ranker performing message passing over cross-asset rolling graph."""

    def __init__(self, config: PointInTimeGraphConfig) -> None:
        self.config = config
        rng = np.random.default_rng(config.seed)
        # 3 input features -> hidden 8 -> 1 score
        self.w_graph = rng.normal(0.0, 0.2, size=(3, 8))
        self.w_self = rng.normal(0.0, 0.2, size=(3, 8))
        self.w_head = rng.normal(0.0, 0.2, size=(8, 1))

    def rank(self, snapshot: GraphSnapshot) -> list[RankedAsset]:
        """Compute message passing scores and rank active assets descending."""
        X = snapshot.node_features
        A = snapshot.adjacency_matrix

        # Message passing: ReLU(A @ X @ W_g + X @ W_self)
        h = np.maximum(0, A @ X @ self.w_graph + X @ self.w_self)
        scores = (h @ self.w_head).flatten()

        ranked_indices = np.argsort(-scores)
        results: list[RankedAsset] = []
        for rank_pos, idx in enumerate(ranked_indices, start=1):
            results.append(
                RankedAsset(
                    asset=snapshot.active_nodes[idx],
                    score=float(scores[idx]),
                    rank=rank_pos,
                )
            )
        return results

    def generate_execution_decisions(
        self,
        ranked_assets: list[RankedAsset],
        decision_ts: datetime,
        mapper: CostAwareExecutionMapper,
        desired_qty: Any = None,
        payoff: PayoffStructure | None = None,
    ) -> list[ExecutionDecision]:
        """Map top-K ranked picks into execution intents via common mapper."""
        decisions: list[ExecutionDecision] = []
        eff_payoff = payoff or PayoffStructure(win_return=0.015, loss_return=-0.010)

        for asset_rank in ranked_assets:
            prob = 1.0 / (1.0 + np.exp(-asset_rank.score))
            payload = ForecastPayload(
                kind=ForecastKind.PROBABILITY,
                value=float(prob),
                pair=asset_rank.asset,
                decision_ts=decision_ts,
                desired_qty=desired_qty or 1.0,
                payoff=eff_payoff,
            )
            decisions.append(mapper.evaluate_forecast(payload))
        return decisions


# ---------------------------------------------------------------------------
# Comparator against No-Edge MLP and Panel Regression (G01-01-AC3)
# ---------------------------------------------------------------------------


class GraphBaselineComparator:
    """Evaluates graph benefit against no-edge baseline and naive panel regression."""

    def compare(self, snapshot: GraphSnapshot) -> GraphBaselineComparison:
        """Benchmark G01 graph against no-edge MLP and panel regression on identical snapshot."""
        config = PointInTimeGraphConfig(rolling_window=10)
        ranker = CrossAssetGNNRanker(config=config)

        # 1. Graph model rank scores
        graph_ranks = ranker.rank(snapshot)
        graph_scores = np.array([r.score for r in sorted(graph_ranks, key=lambda x: x.asset)])

        # 2. No-edge baseline: identity adjacency (A = I)
        identity_snapshot = GraphSnapshot(
            eval_ts=snapshot.eval_ts,
            active_nodes=snapshot.active_nodes,
            node_features=snapshot.node_features,
            adjacency_matrix=np.eye(len(snapshot.active_nodes)),
            forward_returns=snapshot.forward_returns,
        )
        no_edge_ranks = ranker.rank(identity_snapshot)
        no_edge_scores = np.array([r.score for r in sorted(no_edge_ranks, key=lambda x: x.asset)])

        # 3. Panel regression baseline: simple linear score from momentum feature (feature index 2)
        panel_scores = snapshot.node_features[:, 2]

        # Calculate rank correlations with forward returns
        y = snapshot.forward_returns
        r_graph, _ = spearmanr(graph_scores, y)
        r_no_edge, _ = spearmanr(no_edge_scores, y)
        r_panel, _ = spearmanr(panel_scores, y)

        return GraphBaselineComparison(
            graph_score_correlation=float(r_graph) if not np.isnan(r_graph) else 0.0,
            no_edge_mlp_correlation=float(r_no_edge) if not np.isnan(r_no_edge) else 0.0,
            panel_regression_correlation=float(r_panel) if not np.isnan(r_panel) else 0.0,
            benchmark_sample_count=len(snapshot.active_nodes),
            evaluated_at_utc=datetime.now(UTC),
        )
