"""DeepLOB convolutional and recurrent baseline for order book microstructure (L01-01).

Guarantees:
1. L01-01-AC0: DeepLOB produces short-horizon forecast mapped through CostAwareExecutionMapper with spread and latency accounting.
2. L01-01-AC1: High raw mid-price accuracy does not imply net profitability when spread and fees dominate.
3. L01-01-AC2: Gapped book sequences block execution fail-closed.
4. L01-01-AC3: Benchmarked against baseline MLP on strictly identical out-of-fold samples.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from indodax_lab.models.dl.checkpoint import require_torch
from indodax_lab.models.lob.dataset import BookSnapshot


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GappedBookBlockedError(ValueError):
    """Raised when an order book sequence contains a temporal gap exceeding threshold."""


class SampleComparatorMismatchError(ValueError):
    """Raised when sample indices or counts mismatch between model evaluations."""


class DeepLOBSampleComparisonResult(BaseModel):
    """Result of identical sample verification between DeepLOB and baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    indices_match: bool
    total_samples: int


class DeepLOBSampleComparator:
    """Verifies that DeepLOB and baseline models evaluate on strictly identical sample sets."""

    def __init__(self, test_sample_indices: list[Any] | None = None) -> None:
        self.test_sample_indices = test_sample_indices

    def verify_same_samples(
        self,
        model_a_indices: list[Any],
        model_b_indices: list[Any],
    ) -> DeepLOBSampleComparisonResult:
        """Verify that two models evaluated on the exact same sample sequence."""
        if list(model_a_indices) != list(model_b_indices):
            raise SampleComparatorMismatchError(
                f"SAMPLE_INDICES_MISMATCH: Model A has {len(model_a_indices)} indices, "
                f"Model B has {len(model_b_indices)} indices. They must match strictly."
            )
        if self.test_sample_indices is not None and list(model_a_indices) != list(self.test_sample_indices):
            raise SampleComparatorMismatchError("SAMPLE_INDICES_MISMATCH: Indices do not match declared test indices")

        return DeepLOBSampleComparisonResult(
            indices_match=True,
            total_samples=len(model_a_indices),
        )


# ---------------------------------------------------------------------------
# Spread & Cost Assessment
# ---------------------------------------------------------------------------


class SpreadAwareAssessment(BaseModel):
    """Assessment of short-horizon edge after spread, latency, and transaction costs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_net_profitable: bool
    net_edge: float
    expected_gross_edge: float
    hurdle: float
    high_accuracy_flag: bool
    reasons: list[str] = Field(default_factory=list)


class SpreadAwareEdgeEvaluator:
    """Evaluates short-horizon order book edge against spread and round-trip fee hurdles."""

    def __init__(
        self,
        estimated_round_trip_cost: float = 0.0040,
        safety_margin: float = 0.0010,
    ) -> None:
        self.estimated_round_trip_cost = estimated_round_trip_cost
        self.safety_margin = safety_margin

    def assess_net_profitability(
        self,
        directional_accuracy: float,
        avg_gross_win: float,
        avg_gross_loss: float,
        avg_half_spread: float,
    ) -> SpreadAwareAssessment:
        """Evaluate if expected gross return overcomes spread and transaction fee hurdles."""
        expected_gross = (
            directional_accuracy * avg_gross_win
            + (1.0 - directional_accuracy) * avg_gross_loss
        )
        # Total hurdle includes exchange taker fees, crossing the bid-ask spread, and safety margin
        total_hurdle = self.estimated_round_trip_cost + avg_half_spread + self.safety_margin
        net_edge = expected_gross - total_hurdle

        high_acc = directional_accuracy >= 0.60
        reasons: list[str] = []
        is_profitable = net_edge > 0.0

        if high_acc and not is_profitable:
            reasons.append("COST_AND_SPREAD_OVERWHELMS_EDGE")

        return SpreadAwareAssessment(
            is_net_profitable=is_profitable,
            net_edge=net_edge,
            expected_gross_edge=expected_gross,
            hurdle=total_hurdle,
            high_accuracy_flag=high_acc,
            reasons=reasons,
        )


# ---------------------------------------------------------------------------
# Configurations
# ---------------------------------------------------------------------------


class DeepLOBConfig(BaseModel):
    """Configuration for DeepLOB convolutional neural network."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "L01_DEEPLOB"
    version: str = "1.0.0"
    lookback_len: int = 20
    num_features: int = 20
    conv_filters: int = 16
    lstm_hidden: int = 32
    num_classes: int = 3
    max_gap_seconds: float = 60.0
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    batch_size: int = 32
    max_epochs: int = 50
    patience: int = 7
    seed: int = 42


# ---------------------------------------------------------------------------
# PyTorch DeepLOB Implementation
# ---------------------------------------------------------------------------


def _build_deeplob_classes():
    torch = require_torch()
    import torch.nn as nn
    import torch.nn.functional as F

    class InceptionModule(nn.Module):
        """Inception-style multi-scale temporal convolutions over LOB features."""

        def __init__(self, in_channels: int, out_channels: int) -> None:
            super().__init__()
            self.branch1 = nn.Conv2d(in_channels, out_channels, kernel_size=(3, 1), padding=(1, 0))
            self.branch2 = nn.Conv2d(in_channels, out_channels, kernel_size=(5, 1), padding=(2, 0))
            self.branch3 = nn.Sequential(
                nn.MaxPool2d(kernel_size=(3, 1), stride=1, padding=(1, 0)),
                nn.Conv2d(in_channels, out_channels, kernel_size=1),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            b1 = F.leaky_relu(self.branch1(x))
            b2 = F.leaky_relu(self.branch2(x))
            b3 = F.leaky_relu(self.branch3(x))
            return torch.cat([b1, b2, b3], dim=1)

    class DeepLOBModelImpl(nn.Module):
        """DeepLOB architecture combining spatial convolutions, Inception blocks, and LSTM."""

        def __init__(self, config: DeepLOBConfig) -> None:
            super().__init__()
            self.config = config
            torch.manual_seed(config.seed)

            # Conv block: combine prices and volumes across depth levels
            self.conv1 = nn.Conv2d(1, config.conv_filters, kernel_size=(1, 2), stride=(1, 2))
            self.conv2 = nn.Conv2d(
                config.conv_filters,
                config.conv_filters,
                kernel_size=(4, 1),
                padding=(3, 0),  # Causal-like padding along time
            )

            # Inception block
            self.inception = InceptionModule(config.conv_filters, config.conv_filters)

            # Width after conv1 is num_features / 2
            feat_width = config.num_features // 2
            lstm_input_dim = (3 * config.conv_filters) * feat_width

            self.lstm = nn.LSTM(
                input_size=lstm_input_dim,
                hidden_size=config.lstm_hidden,
                batch_first=True,
            )

            self.fc = nn.Linear(config.lstm_hidden, config.num_classes)
            self.softmax = nn.Softmax(dim=-1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Forward pass mapping (B, 1, L, F) -> (B, num_classes)."""
            # x: (B, 1, L, F)
            c1 = F.leaky_relu(self.conv1(x))
            c2 = F.leaky_relu(self.conv2(c1))
            # Slice back to lookback_len if causal padding expanded it
            if c2.shape[2] > self.config.lookback_len:
                c2 = c2[:, :, : self.config.lookback_len, :]

            inc = self.inception(c2)

            # Permute and flatten for LSTM: (B, L, Channels * Width)
            B, C, L, W = inc.shape
            inc_flat = inc.permute(0, 2, 1, 3).reshape(B, L, C * W)

            lstm_out, _ = self.lstm(inc_flat)
            last_step = lstm_out[:, -1, :]  # Take final lookback timestep
            logits = self.fc(last_step)
            return self.softmax(logits)

    return DeepLOBModelImpl


class DeepLOBModel:
    """Public wrapper creating DeepLOB model instance."""

    def __new__(cls, config: DeepLOBConfig) -> Any:
        impl_cls = _build_deeplob_classes()
        return impl_cls(config)


class DeepLOBTrainer:
    """Trainer and validator for DeepLOB baseline."""

    def __init__(self, config: DeepLOBConfig) -> None:
        self.config = config

    def validate_unbroken_sequence(self, snapshots: list[BookSnapshot]) -> None:
        """Validate that book snapshots form an unbroken sequence without gaps."""
        for i in range(1, len(snapshots)):
            delta = (snapshots[i].timestamp - snapshots[i - 1].timestamp).total_seconds()
            if delta > self.config.max_gap_seconds:
                raise GappedBookBlockedError(
                    f"GAPPED_BOOK_BLOCKED: Sequence gap of {delta:.1f}s between index {i-1} and {i} "
                    f"exceeds allowable max_gap_seconds={self.config.max_gap_seconds}"
                )
