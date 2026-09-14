"""Compact iTransformer challenger for cross-variate panel forecasting (D04-01).

Inverted Transformer (iTransformer) processes each time series variate as an individual
token vector over the entire lookback window. Cross-variate self-attention enables modeling
multivariate dependencies while strictly isolating time vs feature dimension semantics.

Guarantees:
1. D04-01-AC0: Compact iTransformer produces panel forecasts connected to CostAwareExecutionMapper.
2. D04-01-AC1: Shape time-feature tidak tertukar (validates inverted variate-as-token semantics).
3. D04-01-AC2: Missing variate masking diuji (cross-variate attention masking guarantees unobserved variate isolation).
4. D04-01-AC3: Tidak memakai future universe (point-in-time universe filtering rejects premature/future asset listings).
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


class InvertedDimensionError(ValueError):
    """Raised when time and variate/feature dimensions are inverted or conflated."""


class FutureUniverseError(ValueError):
    """Raised when an asset listed in the future relative to eval_ts is included in universe."""


# ---------------------------------------------------------------------------
# Configurations & Data Models
# ---------------------------------------------------------------------------


class ITransformerComputeBudgetSummary(BaseModel):
    """Parameter and FLOP compute budget for Compact iTransformer."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    total_trainable_parameters: int
    estimated_flops_per_panel: int
    num_layers: int
    d_model: int
    n_heads: int
    d_ff: int
    lookback_len: int
    num_variates: int


class CompactITransformerConfig(BaseModel):
    """Configuration for Compact iTransformer architecture."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "D04_ITRANSFORMER"
    version: str = "1.0.0"
    lookback_len: int = 24
    num_variates: int = 4
    d_model: int = 32
    n_heads: int = 2
    e_layers: int = 2
    d_ff: int = 64
    dropout: float = 0.1
    horizons: tuple[int, ...] = (1, 4, 12)
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    batch_size: int = 32
    max_epochs: int = 50
    patience: int = 7
    min_delta: float = 0.001
    max_configurations: int = 12
    seed: int = 42

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.lookback_len < 4:
            raise ValueError(f"LOOKBACK_TOO_SHORT: Minimum 4 bars required, got {self.lookback_len}")
        if self.num_variates < 1:
            raise ValueError(f"NUM_VARIATES_TOO_LOW: Minimum 1 variate required, got {self.num_variates}")
        if self.d_model % self.n_heads != 0:
            raise ValueError(
                f"D_MODEL_NOT_DIVISIBLE: d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})"
            )
        if self.max_configurations > 12:
            raise ValueError(
                f"BUDGET_EXCEEDED: Maximum 12 configurations permitted, got {self.max_configurations}"
            )


class PointInTimePanelSnapshot(BaseModel):
    """Verified point-in-time cross-asset panel snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    eval_ts: datetime
    active_assets: list[str]
    lookback_len: int


class PointInTimeUniverseGate:
    """Point-in-time universe gating preventing lookahead and future asset leaks."""

    def __init__(self, listing_registry: dict[str, datetime]) -> None:
        self.listing_registry = {k: v.astimezone(UTC) for k, v in listing_registry.items()}

    def get_active_universe(self, eval_ts: datetime) -> list[str]:
        """Return assets listed strictly on or before eval_ts."""
        t_eval = eval_ts.astimezone(UTC)
        return [
            asset
            for asset, listing_ts in sorted(self.listing_registry.items())
            if listing_ts <= t_eval
        ]

    def validate_universe_snapshot(self, eval_ts: datetime, requested_assets: list[str]) -> None:
        """Validate that all requested assets were actively listed at eval_ts."""
        t_eval = eval_ts.astimezone(UTC)
        for asset in requested_assets:
            listing_ts = self.listing_registry.get(asset)
            if listing_ts is None:
                raise FutureUniverseError(f"FUTURE_UNIVERSE_LEAKAGE: Asset {asset} not found in listing registry")
            if listing_ts > t_eval:
                raise FutureUniverseError(
                    f"FUTURE_UNIVERSE_LEAKAGE: Asset {asset} listed on {listing_ts.isoformat()} "
                    f"cannot be included at historical evaluation ts {t_eval.isoformat()}"
                )

    def validate_temporal_timestamps(self, eval_ts: datetime, timestamps: list[datetime]) -> None:
        """Validate that no observation timestamps exceed eval_ts."""
        t_eval = eval_ts.astimezone(UTC)
        for ts in timestamps:
            if ts.astimezone(UTC) > t_eval:
                raise ValueError(
                    f"LOOKAHEAD_DATA_DETECTED: Observation timestamp {ts.isoformat()} "
                    f"is in the future relative to eval_ts {t_eval.isoformat()}"
                )

    def create_panel_snapshot(
        self,
        eval_ts: datetime,
        requested_assets: list[str],
        lookback_len: int,
    ) -> PointInTimePanelSnapshot:
        """Create a validated point-in-time panel snapshot."""
        self.validate_universe_snapshot(eval_ts, requested_assets)
        return PointInTimePanelSnapshot(
            eval_ts=eval_ts.astimezone(UTC),
            active_assets=list(requested_assets),
            lookback_len=lookback_len,
        )


class ITransformerOutput(BaseModel):
    """Output structure of Compact iTransformer."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    horizon_forecasts: Any
    probabilities: Any
    active_mask: Any


# ---------------------------------------------------------------------------
# PyTorch Architecture
# ---------------------------------------------------------------------------


def _build_itransformer_classes():
    torch = require_torch()
    import torch.nn as nn
    import torch.nn.functional as F

    class InvertedTransformerLayer(nn.Module):
        """Transformer encoder layer attending across variate tokens."""

        def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float = 0.1) -> None:
            super().__init__()
            self.d_model = d_model
            self.n_heads = n_heads
            self.self_attn = nn.MultiheadAttention(
                embed_dim=d_model,
                num_heads=n_heads,
                dropout=dropout,
                batch_first=True,
            )
            self.norm1 = nn.LayerNorm(d_model)
            self.norm2 = nn.LayerNorm(d_model)

            self.ffn = nn.Sequential(
                nn.Linear(d_model, d_ff),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(d_ff, d_model),
                nn.Dropout(dropout),
            )
            self.dropout = nn.Dropout(dropout)

        def forward(
            self,
            x: torch.Tensor,
            key_padding_mask: torch.Tensor | None = None,
            return_attn: bool = False,
        ) -> tuple[torch.Tensor, torch.Tensor | None]:
            # x shape: (B, V, d_model)
            # key_padding_mask shape: (B, V) where True = masked / unobserved
            attn_weights = None
            if return_attn:
                attn_out, attn_weights = self.self_attn(
                    x,
                    x,
                    x,
                    key_padding_mask=key_padding_mask,
                    need_weights=True,
                    average_attn_weights=False,
                )
            else:
                attn_out, _ = self.self_attn(
                    x,
                    x,
                    x,
                    key_padding_mask=key_padding_mask,
                    need_weights=False,
                )

            # Isolate unobserved variates: zero out attention out where masked
            if key_padding_mask is not None:
                attn_out = attn_out.masked_fill(key_padding_mask.unsqueeze(-1), 0.0)

            x = self.norm1(x + self.dropout(attn_out))
            ffn_out = self.ffn(x)
            if key_padding_mask is not None:
                ffn_out = ffn_out.masked_fill(key_padding_mask.unsqueeze(-1), 0.0)

            x = self.norm2(x + ffn_out)
            if key_padding_mask is not None:
                x = x.masked_fill(key_padding_mask.unsqueeze(-1), 0.0)

            return x, attn_weights

    class CompactITransformerImpl(nn.Module):
        """Inverted Transformer network for cross-variate panel forecasting."""

        def __init__(self, config: CompactITransformerConfig) -> None:
            super().__init__()
            self.config = config
            torch.manual_seed(config.seed)

            # Inverted tokenization: each variate's entire lookback window L is mapped to d_model
            self.variate_embed = nn.Linear(config.lookback_len, config.d_model)

            self.layers = nn.ModuleList(
                [
                    InvertedTransformerLayer(
                        d_model=config.d_model,
                        n_heads=config.n_heads,
                        d_ff=config.d_ff,
                        dropout=config.dropout,
                    )
                    for _ in range(config.e_layers)
                ]
            )

            # Projection heads
            self.forecast_head = nn.Linear(config.d_model, len(config.horizons))
            self.prob_head = nn.Sequential(
                nn.Linear(config.d_model, 1),
                nn.Sigmoid(),
            )

        def embed_variates(self, x: torch.Tensor) -> torch.Tensor:
            """Map temporal sequences (B, L, V) into variate tokens (B, V, d_model)."""
            self._validate_input_shape(x)
            # Transpose (B, L, V) -> (B, V, L) so that variates become tokens
            x_inv = x.transpose(1, 2)
            return self.variate_embed(x_inv)

        def get_cross_variate_attention(self, x: torch.Tensor) -> torch.Tensor:
            """Extract cross-variate attention matrix of shape (B, n_heads, V, V)."""
            self._validate_input_shape(x)
            tokens = self.embed_variates(x)
            _, attn = self.layers[0](tokens, return_attn=True)
            return attn

        def forward(
            self,
            x: torch.Tensor,
            variate_mask: torch.Tensor | None = None,
        ) -> ITransformerOutput:
            """Forward pass mapping panel inputs (B, L, V) to panel forecasts.

            Args:
                x: Input tensor of shape (B, lookback_len, num_variates).
                variate_mask: Optional boolean mask of shape (B, num_variates)
                    where True indicates active/observed variate and False indicates missing.
            """
            self._validate_input_shape(x)
            b_size, _, v_size = x.shape

            # Variate tokens: (B, V, d_model)
            tokens = self.embed_variates(x)

            # Key padding mask: True means unobserved/masked in PyTorch MHA
            if variate_mask is not None:
                if variate_mask.shape != (b_size, v_size):
                    raise ValueError(
                        f"VARIATE_MASK_SHAPE_MISMATCH: expected ({b_size}, {v_size}), got {tuple(variate_mask.shape)}"
                    )
                key_padding_mask = ~variate_mask
                # Zero out unobserved token embeddings before attention
                tokens = tokens.masked_fill(key_padding_mask.unsqueeze(-1), 0.0)
            else:
                key_padding_mask = None
                variate_mask = torch.ones((b_size, v_size), dtype=torch.bool, device=x.device)

            h = tokens
            for layer in self.layers:
                h, _ = layer(h, key_padding_mask=key_padding_mask)

            # Forecast projection: (B, V, num_horizons)
            horizon_forecasts = self.forecast_head(h)

            # Directional probability projection: (B, V)
            probs = self.prob_head(h).squeeze(-1)

            # Strictly mask missing variates
            if key_padding_mask is not None:
                horizon_forecasts = horizon_forecasts.masked_fill(key_padding_mask.unsqueeze(-1), 0.0)
                probs = probs.masked_fill(key_padding_mask, 0.0)

            return ITransformerOutput(
                horizon_forecasts=horizon_forecasts,
                probabilities=probs,
                active_mask=variate_mask,
            )

        def _validate_input_shape(self, x: torch.Tensor) -> None:
            if x.ndim != 3:
                raise ValueError(f"EXPECTED_3D_TENSOR: expected (B, L, V), got ndim={x.ndim}")
            _, l_dim, v_dim = x.shape
            if l_dim != self.config.lookback_len:
                if l_dim == self.config.num_variates and v_dim == self.config.lookback_len:
                    raise InvertedDimensionError(
                        f"TIME_FEATURE_SHAPE_INVERTED: expected temporal length L={self.config.lookback_len} "
                        f"on dim 1, but received {l_dim} matching num_variates. Inverted Transformer expects "
                        f"(B, lookback_len, num_variates) as input, with variates inverted internally to tokens."
                    )
                raise InvertedDimensionError(
                    f"TIME_FEATURE_SHAPE_INVERTED: expected temporal length L={self.config.lookback_len}, got {l_dim}"
                )
            if v_dim != self.config.num_variates:
                raise ValueError(
                    f"VARIATE_DIM_MISMATCH: expected num_variates={self.config.num_variates}, got {v_dim}"
                )

        def compute_budget_summary(self) -> ITransformerComputeBudgetSummary:
            """Compute parameter count and FLOP budget per panel."""
            total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

            # FLOP estimation:
            # 1. Variate embedding: B * V * L * d_model
            # 2. Per layer:
            #    Self-attention: Q, K, V projections (3 * V * d_model^2) + Attn scores (n_heads * V * V * d_head) + Attn out (V * d_model^2)
            #    FFN: 2 * V * d_model * d_ff
            # 3. Forecast + prob heads: V * d_model * (H + 1)
            V = self.config.num_variates
            L = self.config.lookback_len
            d = self.config.d_model
            d_ff = self.config.d_ff
            H = len(self.config.horizons)

            embed_flops = 2 * V * L * d
            layer_flops = self.config.e_layers * (4 * V * (d**2) + 2 * (V**2) * d + 4 * V * d * d_ff)
            head_flops = 2 * V * d * (H + 1)
            total_flops = embed_flops + layer_flops + head_flops

            return ITransformerComputeBudgetSummary(
                total_trainable_parameters=total_params,
                estimated_flops_per_panel=total_flops,
                num_layers=self.config.e_layers,
                d_model=self.config.d_model,
                n_heads=self.config.n_heads,
                d_ff=self.config.d_ff,
                lookback_len=self.config.lookback_len,
                num_variates=self.config.num_variates,
            )

    return CompactITransformerImpl


class CompactITransformer:
    """Public wrapper creating CompactITransformer instance."""

    def __new__(cls, config: CompactITransformerConfig) -> Any:
        impl_cls = _build_itransformer_classes()
        return impl_cls(config)
