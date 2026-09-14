"""ResNet LSTM challenger combining residual temporal convolutions and recurrent heads (D03-01).

Guarantees:
1. D03-01-AC0: Predicts registered triple-barrier targets and routes through common CostAwareExecutionMapper.
2. D03-01-AC1: Strictly forbids bidirectional recurrent architectures to prevent future lookahead leakage.
3. D03-01-AC2: Mask-aware readout guarantees that padded tokens do not corrupt hidden state representations.
4. D03-01-AC3: Evaluates net edge against standardized transaction cost basis.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
import hashlib
import json
from typing import Any
import numpy as np
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
# Errors
# ---------------------------------------------------------------------------


class BidirectionalLeakageError(ValueError):
    """Raised when bidirectional recurrent processing is configured, violating temporal causality."""


# ---------------------------------------------------------------------------
# Configurations and Models
# ---------------------------------------------------------------------------


class ResNetLSTMConfig(BaseModel):
    """Configuration for ResNet LSTM challenger model."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "D03_RESNET_LSTM"
    version: str = "1.0.0"
    input_dim: int = 4
    conv_channels: tuple[int, ...] = (32, 32)
    kernel_size: int = 3
    lstm_hidden_dim: int = 32
    lstm_layers: int = 1
    bidirectional: bool = False
    dropout: float = 0.1
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    batch_size: int = 32
    max_epochs: int = 50
    patience: int = 7
    min_delta: float = 0.001
    seed: int = 42

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.bidirectional:
            raise BidirectionalLeakageError(
                "BIDIRECTIONAL_LEAKAGE_FORBIDDEN: Bidirectional recurrent networks introduce "
                "lookahead leakage and are strictly forbidden."
            )
        if self.max_epochs > 50:
            raise ValueError(f"MAX_EPOCHS_EXCEEDED: Max epochs is 50, got {self.max_epochs}")
        if self.patience > 7:
            raise ValueError(f"PATIENCE_EXCEEDED: Max patience is 7, got {self.patience}")


class ResNetLSTMUtilityComparison(BaseModel):
    """Outcome of utility evaluation under transaction costs."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    sample_count: int
    model_net_utility: float
    cost_basis_evaluated: float
    evaluated_at_utc: datetime


class ResNetLSTMTrainedBundle(BaseModel):
    """Immutable bundle containing trained weights and configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    config: ResNetLSTMConfig
    total_parameters: int
    best_epoch: int
    best_val_loss: float
    bundle_hash: str
    fitted_at_utc: datetime


# ---------------------------------------------------------------------------
# PyTorch Architecture
# ---------------------------------------------------------------------------


class ResidualTemporalBlock:
    """1D residual convolutional block with causal padding."""

    def __new__(cls, in_channels: int, out_channels: int, kernel_size: int = 3) -> Any:
        torch = require_torch()

        class _ResidualBlockModule(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.padding = kernel_size - 1
                self.conv = torch.nn.Conv1d(
                    in_channels,
                    out_channels,
                    kernel_size=kernel_size,
                    padding=self.padding,
                )
                self.act = torch.nn.GELU()
                self.residual = (
                    torch.nn.Conv1d(in_channels, out_channels, 1)
                    if in_channels != out_channels
                    else torch.nn.Identity()
                )

            def forward(self, x: Any) -> Any:
                res = self.residual(x)
                out = self.conv(x)
                if self.padding > 0:
                    out = out[:, :, : -self.padding]
                return self.act(out) + res

        return _ResidualBlockModule()


class ResNetLSTMModel:
    """Combines residual temporal convolutional blocks with a causal LSTM head."""

    def __new__(cls, config: ResNetLSTMConfig) -> Any:
        torch = require_torch()

        class _ResNetLSTMModelModule(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.config = config

                # Residual temporal convolution blocks
                conv_layers: list[Any] = []
                in_ch = config.input_dim
                for ch in config.conv_channels:
                    conv_layers.append(ResidualTemporalBlock(in_ch, ch, kernel_size=config.kernel_size))
                    in_ch = ch
                self.conv_stack = torch.nn.Sequential(*conv_layers)

                # Unidirectional LSTM
                self.lstm = torch.nn.LSTM(
                    input_size=in_ch,
                    hidden_size=config.lstm_hidden_dim,
                    num_layers=config.lstm_layers,
                    batch_first=True,
                    bidirectional=False,
                )

                # Readout head for triple barrier binary target
                self.head = torch.nn.Linear(config.lstm_hidden_dim, 1)

            def forward(self, x: Any, mask: Any = None) -> Any:
                # x: [batch, seq_len, in_dim]
                batch_size, seq_len, _ = x.shape

                # Zero out padded steps if mask provided to ensure zero noise enters network
                if mask is not None:
                    x_clean = x * mask.unsqueeze(-1).float()
                else:
                    x_clean = x

                # Conv temporal feature extraction
                x_trans = x_clean.transpose(1, 2)  # [batch, in_dim, seq_len]
                conv_out = self.conv_stack(x_trans)  # [batch, conv_ch, seq_len]
                lstm_in = conv_out.transpose(1, 2)   # [batch, seq_len, conv_ch]

                # If mask provided, zero out conv features at padded positions
                if mask is not None:
                    lstm_in = lstm_in * mask.unsqueeze(-1).float()

                # LSTM recurrent pass
                lstm_out, _ = self.lstm(lstm_in)  # [batch, seq_len, lstm_hidden_dim]

                # Mask-aware readout: extract hidden state at last valid historical step
                if mask is not None:
                    valid_counts = mask.sum(dim=1).long()
                    last_indices = (valid_counts - 1).clamp(min=0)
                    batch_idx = torch.arange(batch_size, device=x.device)
                    rep = lstm_out[batch_idx, last_indices]
                else:
                    rep = lstm_out[:, -1, :]

                return self.head(rep).squeeze(-1)

        return _ResNetLSTMModelModule()


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------


class ResNetLSTMTrainer:
    """Trainer for ResNet LSTM challenger model."""

    def __init__(self, config: ResNetLSTMConfig) -> None:
        self.config = config
        self._model: Any = None
        self._bundle: ResNetLSTMTrainedBundle | None = None

    def fit(
        self,
        train_inputs: np.ndarray,
        train_masks: np.ndarray,
        train_targets: np.ndarray,
        val_inputs: np.ndarray,
        val_masks: np.ndarray,
        val_targets: np.ndarray,
    ) -> ResNetLSTMTrainedBundle:
        """Fit model using BCE loss and early stopping."""
        torch = require_torch()

        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)

        model = ResNetLSTMModel(config=self.config)
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

        total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "best_epoch": tracker.best_epoch,
            "best_val_loss": tracker.best_val_loss,
            "total_params": total_params,
        }
        bundle_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True).encode("utf-8")).hexdigest()

        self._bundle = ResNetLSTMTrainedBundle(
            config=self.config,
            total_parameters=total_params,
            best_epoch=tracker.best_epoch,
            best_val_loss=tracker.best_val_loss,
            bundle_hash=bundle_hash,
            fitted_at_utc=datetime.now(UTC),
        )
        return self._bundle

    def predict_proba(self, inputs: np.ndarray, masks: np.ndarray | None = None) -> np.ndarray:
        """Predict sigmoid probabilities of positive barrier outcome."""
        torch = require_torch()
        if self._model is None:
            raise RuntimeError("ResNetLSTMTrainer is not fitted yet.")

        self._model.eval()
        with torch.no_grad():
            x_t = torch.tensor(inputs, dtype=torch.float32)
            m_t = torch.tensor(masks, dtype=torch.bool) if masks is not None else None
            logits = self._model(x_t, mask=m_t)
            probs = torch.sigmoid(logits).cpu().numpy()
        return np.asarray(probs, dtype=float)

    def predict_forecasts(
        self,
        inputs: np.ndarray,
        masks: np.ndarray | None,
        pair: str,
        decision_ts: datetime,
        mapper: CostAwareExecutionMapper,
        desired_qty: Any = None,
        payoff: PayoffStructure | None = None,
    ) -> list[ExecutionDecision]:
        """Route predictions into execution decisions via common mapper."""
        probs = self.predict_proba(inputs, masks)
        decisions: list[ExecutionDecision] = []
        eff_payoff = payoff or PayoffStructure(win_return=0.015, loss_return=-0.010)

        for prob in probs:
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

    def evaluate_cost_aware_utility(
        self,
        inputs: np.ndarray,
        masks: np.ndarray | None,
        targets: np.ndarray,
        mapper: CostAwareExecutionMapper,
        round_trip_cost: float | None = None,
    ) -> ResNetLSTMUtilityComparison:
        """Evaluate net utility of decisions against cost basis."""
        probs = self.predict_proba(inputs, masks)
        cost = round_trip_cost if round_trip_cost is not None else mapper.cost_basis.estimated_round_trip_cost

        # Decisions: long when prob > 0.5
        trades = (probs > 0.5).astype(float)
        # Realized payoff: targets are binary (1 = win +1.5%, 0 = loss -1.0%)
        realized_returns = np.where(targets == 1.0, 0.015, -0.010)
        net_returns = trades * (realized_returns - cost)
        net_utility = float(np.mean(net_returns))

        return ResNetLSTMUtilityComparison(
            sample_count=len(inputs),
            model_net_utility=net_utility,
            cost_basis_evaluated=cost,
            evaluated_at_utc=datetime.now(UTC),
        )
