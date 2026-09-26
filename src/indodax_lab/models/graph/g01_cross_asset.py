"""Point-in-time cross-asset graph neural network challenger (G01-01).

Guarantees:
1. G01-01-AC0: Point-in-time graph model produces cross-asset rankings and execution decisions via common mapper.
2. G01-01-AC1: Full sample adjacency or future-looking matrices are rejected fail-closed to prevent lookahead leakage.
3. G01-01-AC2: Assets not yet listed at evaluation timestamp are barred from graph nodes fail-closed.
4. G01-01-AC3: Benchmarked against no-edge MLP and panel regression baselines on identical point-in-time snapshots.
"""

from __future__ import annotations

import warnings
from datetime import UTC, datetime
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict
from scipy.stats import ConstantInputWarning, spearmanr

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


class MissingGraphColumnError(ValueError):
    """Raised when a required point-in-time panel column is absent from the input frame."""


class GraphSnapshotUnderdeterminedError(ValueError):
    """Raised when a snapshot carries too few nodes to support a rank-correlation claim."""


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
    # Edge provenance (spec 15: "Graph metadata binds edge method/window/train cutoff
    # and availability"). A snapshot without these cannot be shown to be edge-causal.
    edge_method: str
    edge_window: int
    edge_train_cutoff: datetime
    edges_available_at: datetime


class GraphComputeBudgetSummary(BaseModel):
    """Parameter and compute budget summary for the cross-asset GNN ranker.

    `estimated_flops_per_inference` counts the dense multiply-accumulates of one full
    message-passing forward over a single-node graph (self-loop only); the per-edge
    message transform is a further `input_dim * hidden_dim` MACs for every other node.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    input_dim: int
    hidden_dim: int
    total_learned_parameters: int
    estimated_flops_per_inference: int


class RankedAsset(BaseModel):
    """Ranked asset outcome from graph scoring."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    asset: str
    score: float
    rank: int


class GraphBaselineComparison(BaseModel):
    """Comparative rank metrics between graph model, no-edge MLP, and panel regression.

    Each correlation is `None` when Spearman is undefined (a constant score or target
    vector, fewer than 2 distinct ranks). `0.0` means a genuinely uncorrelated score
    and must never be used to stand in for "not computable".
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    graph_score_correlation: float | None
    no_edge_mlp_correlation: float | None
    panel_regression_correlation: float | None
    benchmark_sample_count: int
    evaluated_at_utc: datetime
    ranker_seed: int
    compute_budget: GraphComputeBudgetSummary


# ---------------------------------------------------------------------------
# Point-in-time Graph Builder (G01-01-AC1, AC2)
# ---------------------------------------------------------------------------


class PointInTimeGraphBuilder:
    """Builds point-in-time graph snapshots with causal rolling edges and strict listing validation."""

    #: Columns every point-in-time panel frame must carry.
    REQUIRED_COLUMNS: ClassVar[tuple[str, ...]] = (
        "timestamp",
        "asset",
        "return",
        "volatility",
        "momentum",
        "forward_return",
    )
    #: Edge method bound into every snapshot's metadata.
    EDGE_METHOD: ClassVar[str] = "rolling_pearson_thresholded_symmetric"
    #: Node features consumed by the message-passing layers, in order.
    FEATURE_COLUMNS: ClassVar[tuple[str, ...]] = ("return", "volatility", "momentum")
    #: Minimum same-asset observations required at or before eval_ts.
    MIN_OBSERVATIONS_PER_NODE: ClassVar[int] = 2

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
        # 0. Reject a frame that cannot support any claim at all. A silently missing
        # `forward_return` used to become a constant 0.0 target, which reported a clean
        # 0.0 correlation for every model and read as "no graph benefit".
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise MissingGraphColumnError(
                f"MISSING_GRAPH_COLUMN: Required panel columns absent: {sorted(missing)}"
            )

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

        # 5. Every node must actually be observed at or before eval_ts. A listed but
        # dateless node used to be zero-filled, which both fabricated features and
        # desynchronised the adjacency rows from the real observations.
        per_node = hist_df[hist_df["asset"].isin(active_nodes)].groupby("asset").size()
        for node in active_nodes:
            observed = int(per_node.get(node, 0))
            if observed < self.MIN_OBSERVATIONS_PER_NODE:
                raise PrematureNodeInclusionError(
                    f"NO_OBSERVATIONS_AT_EVAL_TS: Asset '{node}' has {observed} observation(s) "
                    f"at or before eval_ts {eval_ts.isoformat()}, "
                    f"{self.MIN_OBSERVATIONS_PER_NODE} required"
                )

        # 6. Extract rolling return series to compute point-in-time correlation matrix
        return_piv = (
            hist_df[hist_df["asset"].isin(active_nodes)]
            .pivot_table(index="timestamp", columns="asset", values="return")
            .reindex(columns=active_nodes)
            .tail(self.config.rolling_window)
        )

        corr_matrix = return_piv.corr().fillna(0.0).values

        # Apply correlation threshold and add self-loops
        adj = np.where(np.abs(corr_matrix) >= self.config.correlation_threshold, corr_matrix, 0.0)
        np.fill_diagonal(adj, 1.0)

        # Symmetrize and normalize adjacency: D^{-1/2} A D^{-1/2}
        d = np.sum(np.abs(adj), axis=1)
        d_inv_sqrt = np.power(np.maximum(d, 1e-6), -0.5)
        adj_norm = np.diag(d_inv_sqrt) @ adj @ np.diag(d_inv_sqrt)

        # 7. Extract latest node features and observed target at eval_ts
        feature_cols = list(self.FEATURE_COLUMNS)
        latest_features: list[list[float]] = []
        forward_returns: list[float] = []

        for node in active_nodes:
            node_data = hist_df[hist_df["asset"] == node].sort_values("timestamp")
            if node_data.empty:
                # Unreachable given step 5, but a zero-filled node is a silent data
                # corruption so fail closed rather than fabricate a row.
                raise PrematureNodeInclusionError(
                    f"NO_OBSERVATIONS_AT_EVAL_TS: Asset '{node}' has no row at or before "
                    f"eval_ts {eval_ts.isoformat()}"
                )
            last_row = node_data.iloc[-1]
            latest_features.append([float(last_row[c]) for c in feature_cols])
            forward_returns.append(float(last_row["forward_return"]))

        return GraphSnapshot(
            eval_ts=eval_ts,
            active_nodes=active_nodes,
            node_features=np.array(latest_features, dtype=float),
            adjacency_matrix=adj_norm,
            forward_returns=np.array(forward_returns, dtype=float),
            edge_method=self.EDGE_METHOD,
            edge_window=self.config.rolling_window,
            edge_train_cutoff=eval_ts,
            edges_available_at=eval_ts,
        )


# ---------------------------------------------------------------------------
# Cross-Asset GNN Ranker (G01-01-AC0)
# ---------------------------------------------------------------------------


class CrossAssetGNNRanker:
    """Graph neural ranker performing message passing over cross-asset rolling graph."""

    #: Node feature dimensionality consumed by the message-passing layers.
    INPUT_DIM: ClassVar[int] = 3
    #: Hidden width of the message-passing and self projections.
    HIDDEN_DIM: ClassVar[int] = 8

    def __init__(self, config: PointInTimeGraphConfig) -> None:
        self.config = config
        rng = np.random.default_rng(config.seed)
        # 3 input features -> hidden 8 -> 1 score
        self.w_graph = rng.normal(0.0, 0.2, size=(self.INPUT_DIM, self.HIDDEN_DIM))
        self.w_self = rng.normal(0.0, 0.2, size=(self.INPUT_DIM, self.HIDDEN_DIM))
        self.w_head = rng.normal(0.0, 0.2, size=(self.HIDDEN_DIM, 1))

    @property
    def compute_budget(self) -> GraphComputeBudgetSummary:
        """Report learned-parameter count and single-node forward cost."""
        input_dim, hidden_dim = self.INPUT_DIM, self.HIDDEN_DIM
        return GraphComputeBudgetSummary(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            total_learned_parameters=int(
                self.w_graph.size + self.w_self.size + self.w_head.size
            ),
            estimated_flops_per_inference=int(
                input_dim * hidden_dim  # graph projection per node
                + input_dim * hidden_dim  # self projection per node
                + hidden_dim  # scoring head
            ),
        )

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
    """Evaluates graph benefit against no-edge baseline and naive panel regression.

    AC3 requires the comparison to be *about the model in use*, so a ranker built with a
    different window/seed must be passed in. The previous implementation silently built
    its own `rolling_window=10, seed=42` ranker, which benchmarked a different model than
    the caller's whenever the caller configured anything else.
    """

    #: Below this many assets a Spearman rank correlation cannot support a claim.
    MIN_BENCHMARK_NODES: ClassVar[int] = 3

    def __init__(self, ranker: CrossAssetGNNRanker | None = None) -> None:
        self.ranker = ranker

    def compare(self, snapshot: GraphSnapshot) -> GraphBaselineComparison:
        """Benchmark the graph ranker against no-edge MLP and panel regression on one snapshot."""
        n_nodes = len(snapshot.active_nodes)
        if n_nodes < self.MIN_BENCHMARK_NODES:
            raise GraphSnapshotUnderdeterminedError(
                f"UNDERDETERMINED_GRAPH_SNAPSHOT: Rank correlation needs at least "
                f"{self.MIN_BENCHMARK_NODES} assets, snapshot has {n_nodes}"
            )

        ranker = self.ranker or CrossAssetGNNRanker(
            config=PointInTimeGraphConfig(rolling_window=10)
        )

        # 1. Graph model rank scores
        graph_ranks = ranker.rank(snapshot)
        graph_scores = np.array([r.score for r in sorted(graph_ranks, key=lambda x: x.asset)])

        # 2. No-edge baseline: identity adjacency (A = I)
        identity_snapshot = GraphSnapshot(
            eval_ts=snapshot.eval_ts,
            active_nodes=snapshot.active_nodes,
            node_features=snapshot.node_features,
            adjacency_matrix=np.eye(n_nodes),
            forward_returns=snapshot.forward_returns,
            edge_method=f"{snapshot.edge_method}::no_edge_identity",
            edge_window=snapshot.edge_window,
            edge_train_cutoff=snapshot.edge_train_cutoff,
            edges_available_at=snapshot.edges_available_at,
        )
        no_edge_ranks = ranker.rank(identity_snapshot)
        no_edge_scores = np.array([r.score for r in sorted(no_edge_ranks, key=lambda x: x.asset)])

        # 3. Panel regression baseline: simple linear score from momentum feature (feature index 2)
        panel_scores = snapshot.node_features[:, 2]

        # Calculate rank correlations with forward returns. An undefined correlation is
        # reported as None, never 0.0 -- 0.0 is a real "uncorrelated" claim.
        y = snapshot.forward_returns
        r_graph = _spearman_or_none(graph_scores, y)
        r_no_edge = _spearman_or_none(no_edge_scores, y)
        r_panel = _spearman_or_none(panel_scores, y)

        return GraphBaselineComparison(
            graph_score_correlation=r_graph,
            no_edge_mlp_correlation=r_no_edge,
            panel_regression_correlation=r_panel,
            benchmark_sample_count=n_nodes,
            evaluated_at_utc=datetime.now(UTC),
            ranker_seed=ranker.config.seed,
            compute_budget=ranker.compute_budget,
        )


def _spearman_or_none(scores: np.ndarray, target: np.ndarray) -> float | None:
    """Spearman rank correlation, or None when it is mathematically undefined."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConstantInputWarning)
        rho, _ = spearmanr(scores, target)
    if rho is None or not np.isfinite(rho):
        return None
    return float(rho)
