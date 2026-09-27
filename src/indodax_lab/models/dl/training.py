"""Neural training configuration and early stopping tracking (DL-01).

Guarantees:
1. DL-01-AC3: Training obeys max 50 epochs, patience 7, and restores the best validation model.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
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

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.max_epochs > 50:
            raise ValueError(f"MAX_EPOCHS_EXCEEDED: Maximum allowed epochs is 50, got {self.max_epochs}")
        if self.patience > 7:
            raise ValueError(f"PATIENCE_EXCEEDED: Maximum allowed patience is 7, got {self.patience}")


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
    """Coordinates neural model training with isolated optional environment.

    Framework-agnostic loop: callers supply a per-epoch function returning
    (val_loss, model_weights); the trainer enforces the config epoch cap and
    patience via EarlyStoppingTracker and restores the best weights (DL-01-AC3).
    No torch import here so non-DL core paths stay isolated (DL-01-AC1).
    """

    def __init__(self, config: NeuralTrainingConfig) -> None:
        self.config = config
        self.tracker = EarlyStoppingTracker(config=config)
        self.epochs_run: int = 0

    def run_epoch(self, epoch: int, val_loss: float, model_weights: Any) -> bool:
        """Feed one epoch result to the tracker; returns True when training must stop."""
        self.tracker.update(epoch=epoch, val_loss=val_loss, model_weights=model_weights)
        self.epochs_run = epoch + 1
        return self.tracker.should_stop

    def fit(self, epoch_fn: Callable[[int], tuple[float, Any]]) -> None:
        """Run epochs up to config.max_epochs, stopping early per tracker patience."""
        for epoch in range(self.config.max_epochs):
            val_loss, model_weights = epoch_fn(epoch)
            if self.run_epoch(epoch, val_loss, model_weights):
                break

    def restore_best_weights(self) -> Any:
        """Return a copy of the best validation weights seen so far."""
        if self.tracker.best_weights is None:
            raise RuntimeError(
                "NO_BEST_WEIGHTS: No epoch has been recorded yet; run fit() before restoring."
            )
        return copy.deepcopy(self.tracker.best_weights)
