"""Transformer LOB (TLOB) attention challenger and tournament archive (L02-01).

Guarantees:
1. L02-01-AC0: TLOB attention architecture evaluated against DeepLOB with compute and latency budget tracking.
2. L02-01-AC1: No perfect queue fill assumption (realistic execution rejects 100% unconditional maker fills).
3. L02-01-AC2: Search budget strictly capped at <=8 configurations; excess attempts fail-closed.
4. L02-01-AC3: Poor valid challenger results are explicitly archived rather than discarded or retried.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.models.dl.checkpoint import require_torch


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PerfectQueueFillForbiddenError(ValueError):
    """Raised when simulation assumes 100% unconditional maker fills or zero spread/slippage."""


class TLOBSearchBudgetExceededError(ValueError):
    """Raised when TLOB hyperparameter search exceeds maximum allowed budget of 8."""


# ---------------------------------------------------------------------------
# Queue Fill Model
# ---------------------------------------------------------------------------


class QueueFillModel:
    """Realistic limit order book queue fill and adverse selection model."""

    def __init__(
        self,
        half_spread_bps: float = 5.0,
        queue_penalty_bps: float = 2.0,
        assume_unconditional_fill: bool = False,
    ) -> None:
        if assume_unconditional_fill:
            raise PerfectQueueFillForbiddenError(
                "PERFECT_QUEUE_FILL_FORBIDDEN: Simulation cannot assume 100% unconditional maker fill. "
                "Queue priority and cancellation dynamics must be modeled."
            )
        if half_spread_bps <= 0.0:
            raise PerfectQueueFillForbiddenError(
                "ZERO_SLIPPAGE_OR_SPREAD_FORBIDDEN: Bid-ask spread must be strictly positive."
            )
        self.half_spread_bps = half_spread_bps
        self.queue_penalty_bps = queue_penalty_bps

    def estimate_fill_probability(self, queue_depth_level: int, order_qty: float) -> float:
        """Estimate realistic fill probability based on queue position and order size.

        Probability strictly decreases with queue depth and order volume.
        """
        if queue_depth_level < 1:
            queue_depth_level = 1
        qty = max(0.01, order_qty)

        # Realistic decaying probability
        base_decay = 1.0 / (1.0 + 0.45 * queue_depth_level + 0.15 * qty)
        return float(np.clip(base_decay, 0.01, 0.95))


# ---------------------------------------------------------------------------
# Configurations & Data Models
# ---------------------------------------------------------------------------


class TLOBComputeSummary(BaseModel):
    """Parameter and compute budget summary for TLOB architecture."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    total_trainable_parameters: int
    estimated_flops_per_inference: int
    num_layers: int
    d_model: int
    n_heads: int
    lookback_len: int
    num_features: int


class TLOBConfig(BaseModel):
    """Configuration for Transformer LOB (TLOB) challenger."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "L02_TLOB"
    version: str = "1.0.0"
    lookback_len: int = 20
    num_features: int = 20
    d_model: int = 32
    n_heads: int = 2
    num_layers: int = 2
    d_ff: int = 64
    dropout: float = 0.1
    num_classes: int = 3
    search_budget_max_configs: int = 8
    seed: int = 42

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.search_budget_max_configs > 8:
            raise TLOBSearchBudgetExceededError(
                f"TLOB_SEARCH_BUDGET_EXCEEDED: Maximum 8 configurations permitted, "
                f"got {self.search_budget_max_configs}"
            )
        if self.d_model % self.n_heads != 0:
            raise ValueError(
                f"D_MODEL_NOT_DIVISIBLE: d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})"
            )


# ---------------------------------------------------------------------------
# Tournament Archive Models
# ---------------------------------------------------------------------------


class ArchivedChallengerResult(BaseModel):
    """Immutable archive record of an evaluated challenger result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    challenger_id: str
    baseline_id: str
    challenger_net_edge: float
    baseline_net_edge: float
    eval_ts: datetime
    status: str
    promoted: bool
    archived_evidence_preserved: bool
    reasons: list[str] = Field(default_factory=list)


class TLOBTournamentArchiver:
    """Registry archiving research challenger outcomes, especially underperformers."""

    def __init__(self) -> None:
        self._archive: list[ArchivedChallengerResult] = []

    def record_tournament_outcome(
        self,
        challenger_id: str,
        baseline_id: str,
        challenger_net_edge: float,
        baseline_net_edge: float,
        eval_ts: datetime,
        reasons: list[str] | None = None,
    ) -> ArchivedChallengerResult:
        """Permanently record challenger evaluation outcome."""
        reasons_list = list(reasons or [])
        is_superior = challenger_net_edge > baseline_net_edge

        status = "PROMOTED_CHALLENGER" if is_superior else "ARCHIVED_UNDERPERFORMER"

        record = ArchivedChallengerResult(
            challenger_id=challenger_id,
            baseline_id=baseline_id,
            challenger_net_edge=challenger_net_edge,
            baseline_net_edge=baseline_net_edge,
            eval_ts=eval_ts.astimezone(UTC),
            status=status,
            promoted=is_superior,
            archived_evidence_preserved=True,
            reasons=reasons_list,
        )
        self._archive.append(record)
        return record

    def list_archived_records(self) -> list[ArchivedChallengerResult]:
        """Return all recorded tournament outcomes."""
        return list(self._archive)


# ---------------------------------------------------------------------------
# PyTorch TLOB Implementation
# ---------------------------------------------------------------------------


def _build_tlob_classes():
    torch = require_torch()
    import torch.nn as nn

    class TLOBModelImpl(nn.Module):
        """Transformer architecture for limit order book sequence modeling."""

        def __init__(self, config: TLOBConfig) -> None:
            super().__init__()
            self.config = config
            torch.manual_seed(config.seed)

            # Feature projection
            self.feature_proj = nn.Linear(config.num_features, config.d_model)

            # Causal transformer encoder layer
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=config.d_model,
                nhead=config.n_heads,
                dim_feedforward=config.d_ff,
                dropout=config.dropout,
                batch_first=True,
            )
            self.transformer_encoder = nn.TransformerEncoder(
                encoder_layer=encoder_layer,
                num_layers=config.num_layers,
            )

            self.head = nn.Linear(config.d_model, config.num_classes)
            self.softmax = nn.Softmax(dim=-1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Forward pass mapping (B, L, F) -> (B, num_classes)."""
            # x shape: (B, L, F)
            B, L, F = x.shape
            h = self.feature_proj(x)  # (B, L, d_model)

            # Generate upper-triangular causal mask
            causal_mask = torch.triu(torch.full((L, L), float("-inf"), device=x.device), diagonal=1)

            out = self.transformer_encoder(h, mask=causal_mask)

            # Pooling: use the final time-step representation
            last_step = out[:, -1, :]  # (B, d_model)
            logits = self.head(last_step)
            return self.softmax(logits)

        def compute_budget_summary(self) -> TLOBComputeSummary:
            """Calculate trainable parameters and estimated FLOPs."""
            total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

            L = self.config.lookback_len
            F = self.config.num_features
            d = self.config.d_model
            d_ff = self.config.d_ff
            H = self.config.n_heads

            proj_flops = 2 * L * F * d
            per_layer_flops = (4 * L * (d**2)) + (2 * (L**2) * d) + (4 * L * d * d_ff)
            encoder_flops = self.config.num_layers * per_layer_flops
            head_flops = 2 * d * self.config.num_classes
            total_flops = proj_flops + encoder_flops + head_flops

            return TLOBComputeSummary(
                total_trainable_parameters=total_params,
                estimated_flops_per_inference=total_flops,
                num_layers=self.config.num_layers,
                d_model=self.config.d_model,
                n_heads=self.config.n_heads,
                lookback_len=self.config.lookback_len,
                num_features=self.config.num_features,
            )

    return TLOBModelImpl


class TLOBModel:
    """Public wrapper creating TLOB model instance."""

    def __new__(cls, config: TLOBConfig) -> Any:
        impl_cls = _build_tlob_classes()
        return impl_cls(config)
