"""Causal Temporal Convolutional Network (TCN) baseline for multi-horizon sequence forecasting (D02-01).

Guarantees:
1. D02-01-AC0: Causal dilated convolutions and mask-safe pooling generate multi-horizon forecasts via common mapper.
2. D02-01-AC1: Strict causality: future token perturbation produces zero change in historical representations.
3. D02-01-AC2: Finite loss convergence on tiny fixtures without NaN or Inf under masked sequences.
4. D02-01-AC3: Detailed parameter count and FLOP compute budget recorded in bundle metadata.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.models.dl.checkpoint import require_torch
from indodax_lab.models.dl.training import EarlyStoppingTracker, NeuralTrainingConfig
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    ExecutionDecision,
    ForecastKind,
    ForecastPayload,
    PayoffStructure,
)


# ---------------------------------------------------------------------------
# Models and Configurations
# ---------------------------------------------------------------------------


class TCNComputeBudgetSummary(BaseModel):
    """Parameter and compute budget summary for TCN architecture."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    total_trainable_parameters: int
    estimated_flops_per_sequence: int
    num_layers: int
    channels: list[int]
    kernel_size: int
    dilations: list[int]
    receptive_field: int


class CausalTCNConfig(BaseModel):
    """Configuration for Causal TCN baseline model."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "D02_TCN"
    version: str = "1.0.0"
    input_dim: int = 4
    num_channels: tuple[int, ...] = (32, 32, 32)
    kernel_size: int = 3
    dilations: tuple[int, ...] | None = None
    dropout: float = 0.1
    horizons: tuple[int, ...] = (1, 4, 12)
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    batch_size: int = 32
    max_epochs: int = 50
    patience: int = 7
    min_delta: float = 0.001
    seed: int = 42

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.kernel_size < 2:
            raise ValueError(f"KERNEL_SIZE_MUST_BE_GE_2: Got {self.kernel_size}")
        if self.max_epochs > 50:
            raise ValueError(f"MAX_EPOCHS_EXCEEDED: Maximum allowed epochs is 50, got {self.max_epochs}")
        if self.patience > 7:
            raise ValueError(f"PATIENCE_EXCEEDED: Maximum allowed patience is 7, got {self.patience}")


class CausalTCNTrainedBundle(BaseModel):
    """Immutable trained bundle containing model parameters and compute diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    config: CausalTCNConfig
    total_parameters: int
    best_epoch: int
    best_val_loss: float
    compute_budget: TCNComputeBudgetSummary
    bundle_hash: str
    fitted_at_utc: datetime


# ---------------------------------------------------------------------------
# PyTorch Causal Dilated Architecture
# ---------------------------------------------------------------------------


class CausalConv1dBlock:
    """Causal dilated 1D convolution block with left padding and residual connection."""

    def __new__(cls, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float = 0.0) -> Any:
        torch = require_torch()

        class _CausalConv1dBlockModule(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.padding = (kernel_size - 1) * dilation
                self.conv1 = torch.nn.Conv1d(
                    in_channels,
                    out_channels,
                    kernel_size=kernel_size,
                    padding=self.padding,
                    dilation=dilation,
                )
                self.act = torch.nn.GELU()
                self.dropout = torch.nn.Dropout(dropout) if dropout > 0.0 else torch.nn.Identity()
                self.residual = (
                    torch.nn.Conv1d(in_channels, out_channels, 1)
                    if in_channels != out_channels
                    else torch.nn.Identity()
                )

            def forward(self, x: Any) -> Any:
                # x shape: [batch, channels, seq_len]
                res = self.residual(x)
                # Conv output has length seq_len + padding
                out = self.conv1(x)
                # Remove right padding to enforce strict causality:
                if self.padding > 0:
                    out = out[:, :, : -self.padding]
                out = self.act(out)
                out = self.dropout(out)
                return out + res

        return _CausalConv1dBlockModule()


class CausalTCNModel:
    """Multi-horizon Causal TCN with mask-safe pooling."""

    def __new__(cls, config: CausalTCNConfig) -> Any:
        torch = require_torch()

        dilations = config.dilations or tuple(2**i for i in range(len(config.num_channels)))
        if len(dilations) != len(config.num_channels):
            raise ValueError("DILATIONS_LENGTH_MUST_MATCH_NUM_CHANNELS")

        class _CausalTCNModelModule(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.config = config
                self.dilations = dilations

                blocks: list[Any] = []
                in_ch = config.input_dim
                for out_ch, d in zip(config.num_channels, dilations):
                    blocks.append(
                        CausalConv1dBlock(
                            in_channels=in_ch,
                            out_channels=out_ch,
                            kernel_size=config.kernel_size,
                            dilation=d,
                            dropout=config.dropout,
                        )
                    )
                    in_ch = out_ch
                self.network = torch.nn.Sequential(*blocks)

                # Head: maps final channel representation to multi-horizon outputs
                self.head = torch.nn.Linear(config.num_channels[-1], len(config.horizons))

            def forward_sequence(self, x: Any) -> Any:
                # x shape: [batch, seq_len, in_dim] -> transpose to [batch, in_dim, seq_len]
                x_trans = x.transpose(1, 2)
                h = self.network(x_trans)
                # h shape: [batch, out_dim, seq_len] -> transpose back to [batch, seq_len, out_dim]
                return h.transpose(1, 2)

            def forward(self, x: Any, mask: Any = None) -> Any:
                # Get sequence representations [batch, seq_len, out_dim]
                seq_rep = self.forward_sequence(x)

                if mask is not None:
                    # Mask-safe readout: mask is [batch, seq_len], bool
                    mask_f = mask.unsqueeze(-1).float()
                    # Calculate masked average over valid historical steps
                    sum_rep = (seq_rep * mask_f).sum(dim=1)
                    denom = mask_f.sum(dim=1).clamp(min=1.0)
                    pooled = sum_rep / denom
                else:
                    # Last step readout
                    pooled = seq_rep[:, -1, :]

                # Multi-horizon logits [batch, len(horizons)]
                return self.head(pooled)

            def get_compute_budget_summary(self, seq_len: int = 30) -> TCNComputeBudgetSummary:
                total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

                # Calculate receptive field: 1 + sum((kernel_size - 1) * d)
                receptive_field = 1 + sum((config.kernel_size - 1) * d for d in dilations)

                # Estimate FLOPs per sequence
                flops = 0
                in_ch = config.input_dim
                for out_ch in config.num_channels:
                    # Conv1d MACs: in_ch * out_ch * kernel_size * seq_len
                    flops += 2 * in_ch * out_ch * config.kernel_size * seq_len
                    in_ch = out_ch
                # Head FLOPs
                flops += 2 * config.num_channels[-1] * len(config.horizons)

                return TCNComputeBudgetSummary(
                    total_trainable_parameters=total_params,
                    estimated_flops_per_sequence=flops,
                    num_layers=len(config.num_channels),
                    channels=list(config.num_channels),
                    kernel_size=config.kernel_size,
                    dilations=list(dilations),
                    receptive_field=receptive_field,
                )

        return _CausalTCNModelModule()


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------


class CausalTCNTrainer:
    """Trainer for multi-horizon Causal TCN."""

    def __init__(self, config: CausalTCNConfig) -> None:
        self.config = config
        self._model: Any = None
        self._bundle: CausalTCNTrainedBundle | None = None

    def fit(
        self,
        train_inputs: np.ndarray,
        train_masks: np.ndarray,
        train_targets: np.ndarray,
        val_inputs: np.ndarray,
        val_masks: np.ndarray,
        val_targets: np.ndarray,
    ) -> CausalTCNTrainedBundle:
        """Fit Causal TCN using early stopping and mask-safe loss."""
        torch = require_torch()

        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)

        model = CausalTCNModel(config=self.config)
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        criterion = torch.nn.BCEWithLogitsLoss()

        tr_x = torch.tensor(train_inputs, dtype=torch.float32)
        tr_m = torch.tensor(train_masks, dtype=torch.bool)
        tr_y = torch.tensor(train_targets, dtype=torch.float32)

        val_x = torch.tensor(val_inputs, dtype=torch.float32)
        val_m = torch.tensor(val_masks, dtype=torch.bool)
        val_y = torch.tensor(val_targets, dtype=torch.float32)

        dataset = torch.utils.data.TensorDataset(tr_x, tr_m, tr_y)
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)

        tracker = EarlyStoppingTracker(
            NeuralTrainingConfig(
                max_epochs=self.config.max_epochs,
                patience=self.config.patience,
                min_delta=self.config.min_delta,
            )
        )

        for epoch in range(self.config.max_epochs):
            model.train()
            for bx, bm, by in loader:
                optimizer.zero_grad()
                logits = model(bx, mask=bm)
                loss = criterion(logits, by)
                loss.backward()
                optimizer.step()

            # Validation loss
            model.eval()
            with torch.no_grad():
                val_logits = model(val_x, mask=val_m)
                val_loss = float(criterion(val_logits, val_y).item())

            tracker.update(epoch, val_loss, model.state_dict())
            if tracker.should_stop:
                break

        if tracker.best_weights is not None:
            model.load_state_dict(tracker.best_weights)
        self._model = model

        compute_summary = model.get_compute_budget_summary(seq_len=train_inputs.shape[1])

        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "best_epoch": tracker.best_epoch,
            "best_val_loss": tracker.best_val_loss,
            "total_params": compute_summary.total_trainable_parameters,
        }
        bundle_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True).encode("utf-8")).hexdigest()

        self._bundle = CausalTCNTrainedBundle(
            config=self.config,
            total_parameters=compute_summary.total_trainable_parameters,
            best_epoch=tracker.best_epoch,
            best_val_loss=tracker.best_val_loss,
            compute_budget=compute_summary,
            bundle_hash=bundle_hash,
            fitted_at_utc=datetime.now(UTC),
        )
        return self._bundle

    def predict_proba(self, inputs: np.ndarray, masks: np.ndarray | None = None) -> np.ndarray:
        """Predict sigmoid probabilities across all horizons."""
        torch = require_torch()
        if self._model is None:
            raise RuntimeError("CausalTCNTrainer is not fitted yet.")

        self._model.eval()
        with torch.no_grad():
            x_t = torch.tensor(inputs, dtype=torch.float32)
            m_t = torch.tensor(masks, dtype=torch.bool) if masks is not None else None
            logits = self._model(x_t, mask=m_t)
            probs = torch.sigmoid(logits).cpu().numpy()
        return np.asarray(probs, dtype=float)

    def predict_forecasts_for_horizon(
        self,
        inputs: np.ndarray,
        masks: np.ndarray | None,
        horizon_idx: int,
        pair: str,
        decision_ts: datetime,
        mapper: CostAwareExecutionMapper,
        desired_qty: Any = None,
        payoff: PayoffStructure | None = None,
    ) -> list[ExecutionDecision]:
        """Route predictions for specific horizon index through common CostAwareExecutionMapper."""
        probs = self.predict_proba(inputs, masks)
        horizon_probs = probs[:, horizon_idx]

        decisions: list[ExecutionDecision] = []
        eff_payoff = payoff or PayoffStructure(win_return=0.015, loss_return=-0.010)

        for prob in horizon_probs:
            payload = ForecastPayload(
                kind=ForecastKind.PROBABILITY,
                value=float(prob),
                pair=pair,
                decision_ts=decision_ts,
                desired_qty=desired_qty or 1.0,
                payoff=eff_payoff,
            )
            decisions.append(mapper.evaluate_forecast(payload))
        return decisions
