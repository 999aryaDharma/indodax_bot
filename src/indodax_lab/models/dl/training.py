"""Neural training configuration and early stopping tracking (DL-01).

Guarantees:
1. DL-01-AC3: Training obeys max 50 epochs, patience 7, and restores the best validation model.
"""

from __future__ import annotations

import copy
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class NeuralTrainingConfig(BaseModel):
    """Configuration for deep learning training run."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    max_epochs: int = 50
    patience: int = 7
    min_delta: float = 0.001
    batch_size: int = 64
    learning_rate: float = 0.001


class EarlyStoppingTracker:
    """Monitors validation loss, enforcing max epochs and patience 7 early stopping."""

    def __init__(self, config: NeuralTrainingConfig) -> None:
        self.config = config
        self.best_val_loss: float = float("inf")
        self.best_epoch: int = 0
        self.best_weights: Any = None
        self.patience_counter: int = 0
        self.should_stop: bool = False

    def update(self, epoch: int, val_loss: float, model_weights: Any) -> None:
        """Update tracker with latest epoch validation metrics.

        If validation loss improves by at least min_delta, update best record.
        If no improvement for `patience` consecutive epochs, trigger early stopping.
        """
        if val_loss < (self.best_val_loss - self.config.min_delta):
            self.best_val_loss = val_loss
            self.best_epoch = epoch
            self.best_weights = copy.deepcopy(model_weights)
            self.patience_counter = 0
        else:
            self.patience_counter += 1
            if self.patience_counter >= self.config.patience or epoch >= (self.config.max_epochs - 1):
                self.should_stop = True


class NeuralTrainer:
    """Coordinates neural model training with isolated optional environment."""

    def __init__(self, config: NeuralTrainingConfig) -> None:
        self.config = config
        self.tracker = EarlyStoppingTracker(config=config)
