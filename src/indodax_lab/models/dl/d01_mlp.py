"""Tabular MLP nonlinear baseline model (D01-01).

Guarantees:
1. D01-01-AC0: Evaluates nonlinearity benefit using same tabular features as M01/M02 via common mapper.
2. D01-01-AC1: Enforces same sample comparator fail-closed on sample/column mismatch.
3. D01-01-AC2: Evaluates 3 fixed finalist seeds without cherry-picking; enforces <= 12 config budget.
4. D01-01-AC3: Supports interruption and seamless resumption on best validation checkpoint.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
import hashlib
import json
import random
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics import brier_score_loss, log_loss

BEST_CHECKPOINT_FILENAME = "best_checkpoint.json"


def _tensor_to_json(value: Any) -> Any:
    """Recursively convert torch tensors inside optimizer state to JSON-safe payloads."""
    torch = require_torch()
    if torch.is_tensor(value):
        return {
            "__tensor__": True,
            "dtype": str(value.dtype).replace("torch.", ""),
            "shape": list(value.shape),
            "data": value.detach().cpu().tolist(),
        }
    if isinstance(value, dict):
        return {str(k): _tensor_to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_tensor_to_json(v) for v in value]
    return value


def _json_to_tensor(payload: Any) -> Any:
    """Recursively rebuild torch tensors serialized by _tensor_to_json."""
    torch = require_torch()
    if isinstance(payload, dict) and payload.get("__tensor__") is True:
        dtype = getattr(torch, payload["dtype"])
        return torch.tensor(payload["data"], dtype=dtype).reshape(payload["shape"])
    if isinstance(payload, dict):
        restored: dict[Any, Any] = {}
        for k, v in payload.items():
            restored[int(k) if k.lstrip("-").isdigit() else k] = _json_to_tensor(v)
        return restored
    if isinstance(payload, list):
        return [_json_to_tensor(v) for v in payload]
    return payload


def _serialize_model_state(state_dict: Any) -> dict[str, Any]:
    torch = require_torch()
    return {
        k: _tensor_to_json(v.detach().cpu()) if torch.is_tensor(v) else v
        for k, v in state_dict.items()
    }


def _capture_rng_state(seed: int) -> dict[str, Any]:
    """Snapshot torch/numpy/python RNG state so resume reproduces the exact trajectory."""
    torch = require_torch()
    numpy_state = np.random.get_state()
    python_state = random.getstate()
    snapshot: dict[str, Any] = {
        "seed": seed,
        "torch_rng": torch.get_rng_state().cpu().tolist(),
        "numpy_rng": {
            "kind": numpy_state[0],
            "state": numpy_state[1].tolist(),
            "pos": int(numpy_state[2]),
            "has_gauss": int(numpy_state[3]),
            "cached_gaussian": float(numpy_state[4]),
        },
        "python_rng": {
            "version": int(python_state[0]),
            "state": list(python_state[1]),
            "gauss_next": python_state[2],
        },
    }
    if torch.cuda.is_available():
        snapshot["cuda_rng"] = [g.cpu().tolist() for g in torch.cuda.get_rng_state_all()]
    return snapshot


def _restore_rng_state(snapshot: dict[str, Any]) -> None:
    """Restore torch/numpy/python RNG state captured by _capture_rng_state."""
    torch = require_torch()
    torch.set_rng_state(torch.tensor(snapshot["torch_rng"], dtype=torch.uint8))
    numpy_rng = snapshot["numpy_rng"]
    np.random.set_state(
        (
            numpy_rng["kind"],
            np.asarray(numpy_rng["state"], dtype=np.uint32),
            int(numpy_rng["pos"]),
            int(numpy_rng["has_gauss"]),
            float(numpy_rng["cached_gaussian"]),
        )
    )
    python_rng = snapshot["python_rng"]
    random.setstate(
        (int(python_rng["version"]), tuple(python_rng["state"]), python_rng["gauss_next"])
    )
    if "cuda_rng" in snapshot and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(
            [torch.tensor(g, dtype=torch.uint8) for g in snapshot["cuda_rng"]]
        )

from indodax_lab.models.dl.checkpoint import (
    NeuralTrainingCheckpoint,
    load_checkpoint,
    require_torch,
    save_checkpoint,
)
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


class SearchBudgetExceededError(ValueError):
    """Raised when hyperparameter tuning budget exceeds the permitted 12 configurations."""


class SampleComparatorMismatchError(ValueError):
    """Raised when sample rows, feature schemas, or index structures mismatch between comparator models."""


# ---------------------------------------------------------------------------
# Configuration & Bundle Models
# ---------------------------------------------------------------------------


class D01MLPConfig(BaseModel):
    """Configuration for Tabular MLP baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "D01_MLP"
    version: str = "1.0.0"
    hidden_dims: tuple[int, ...] = (64, 32)
    activation: str = "relu"  # "relu" or "gelu"
    dropout: float = 0.1
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    batch_size: int = 64
    max_epochs: int = 50
    patience: int = 7
    min_delta: float = 0.001
    seed: int = 42
    search_budget_max_configs: int = 12

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.max_epochs > 50:
            raise ValueError(f"MAX_EPOCHS_EXCEEDED: Maximum allowed epochs is 50, got {self.max_epochs}")
        if self.patience > 7:
            raise ValueError(f"PATIENCE_EXCEEDED: Maximum allowed patience is 7, got {self.patience}")
        if self.activation not in ("relu", "gelu"):
            raise ValueError(f"UNSUPPORTED_ACTIVATION: Must be 'relu' or 'gelu', got {self.activation}")


class D01MLPFittedBundle(BaseModel):
    """Immutable fitted bundle for D01 MLP."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    config: D01MLPConfig
    feature_names: list[str]
    input_dim: int
    best_epoch: int
    best_val_loss: float
    bundle_hash: str
    fitted_at_utc: datetime


class SameSampleComparisonResult(BaseModel):
    """Comparative outcome between M01 linear baseline and D01 MLP on identical samples."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    sample_count: int
    m01_brier_score: float
    d01_brier_score: float
    brier_improvement: float
    m01_net_utility: float | None = None
    d01_net_utility: float | None = None
    utility_improvement: float | None = None
    evaluated_at_utc: datetime


class D01FinalistEvaluation(BaseModel):
    """Aggregate evaluation across fixed finalist seeds without cherry-picking."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    seed_results: dict[int, float]
    val_loss_mean: float
    val_loss_std: float
    is_cherry_picked: bool = False
    evaluated_at_utc: datetime


# ---------------------------------------------------------------------------
# PyTorch Tabular Architecture
# ---------------------------------------------------------------------------


def _build_mlp_module(input_dim: int, config: D01MLPConfig) -> Any:
    """Build torch.nn.Sequential MLP module."""
    torch = require_torch()

    layers: list[Any] = []
    current_dim = input_dim

    for h_dim in config.hidden_dims:
        layers.append(torch.nn.Linear(current_dim, h_dim))
        if config.activation == "relu":
            layers.append(torch.nn.ReLU())
        elif config.activation == "gelu":
            layers.append(torch.nn.GELU())
        if config.dropout > 0.0:
            layers.append(torch.nn.Dropout(config.dropout))
        current_dim = h_dim

    # Output logit for binary classification
    layers.append(torch.nn.Linear(current_dim, 1))
    return torch.nn.Sequential(*layers)


# ---------------------------------------------------------------------------
# D01 MLP Trainer
# ---------------------------------------------------------------------------


class D01MLPTrainer:
    """Trainer for D01 Tabular MLP with isolated PyTorch execution and checkpointing."""

    def __init__(self, config: D01MLPConfig) -> None:
        self.config = config
        self._model: Any = None
        self._bundle: D01MLPFittedBundle | None = None
        self._feature_names: list[str] = []

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        checkpoint_dir: Path | None = None,
        interrupt_after_epoch: int | None = None,
        resume_from: Path | None = None,
    ) -> D01MLPFittedBundle:
        """Fit MLP model with early stopping, optional resumption, and checkpointing."""
        torch = require_torch()

        # Set seeds
        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)
        random.seed(self.config.seed)

        self._feature_names = list(X_train.columns)
        input_dim = len(self._feature_names)

        # Prepare tensors
        x_tr_t = torch.tensor(X_train.values, dtype=torch.float32)
        y_tr_t = torch.tensor(y_train.values, dtype=torch.float32).unsqueeze(1)
        x_val_t = torch.tensor(X_val.values, dtype=torch.float32)
        y_val_t = torch.tensor(y_val.values, dtype=torch.float32).unsqueeze(1)

        train_dataset = torch.utils.data.TensorDataset(x_tr_t, y_tr_t)
        train_loader = torch.utils.data.DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
        )

        model = _build_mlp_module(input_dim, self.config)
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        criterion = torch.nn.BCEWithLogitsLoss()

        tracker = EarlyStoppingTracker(
            NeuralTrainingConfig(
                max_epochs=self.config.max_epochs,
                patience=self.config.patience,
                min_delta=self.config.min_delta,
            )
        )

        start_epoch = 0

        # Input data fingerprint for resume validation
        input_hash = hashlib.sha256(
            (str(X_train.shape) + str(self._feature_names) + str(y_train.sum())).encode("utf-8")
        ).hexdigest()

        # Handle resumption if requested
        if resume_from is not None:
            checkpoint = load_checkpoint(resume_from, expected_input_hash=input_hash)
            start_epoch = checkpoint.epoch + 1
            # Restore latest model weights + optimizer state for exact continuation.
            weights_tensor = {
                k: _json_to_tensor(v) if isinstance(v, dict) and v.get("__tensor__") is True
                else (torch.tensor(v, dtype=torch.float32) if isinstance(v, list) else v)
                for k, v in checkpoint.model_state.items()
            }
            model.load_state_dict(weights_tensor)
            optimizer.load_state_dict(_json_to_tensor(checkpoint.optimizer_state))
            _restore_rng_state(checkpoint.rng_state)
            # Restore the true best checkpoint (never the interrupted latest weights).
            best_sidecar = resume_from.parent / BEST_CHECKPOINT_FILENAME
            if best_sidecar.exists():
                best_payload = json.loads(best_sidecar.read_text(encoding="utf-8"))
                if best_payload.get("input_hash") != input_hash:
                    raise ValueError(
                        "RESUME_INPUT_MISMATCH: best checkpoint input hash does not match "
                        "current training data; refusing to resume on altered data."
                    )
                tracker.best_val_loss = float(best_payload["best_val_loss"])
                tracker.best_epoch = int(best_payload["best_epoch"])
                tracker.patience_counter = int(best_payload.get("patience_counter", 0))
                tracker.best_weights = copy.deepcopy(
                    _json_to_tensor(best_payload["best_model_state"])
                )
            else:
                # Legacy checkpoint without best sidecar: fail safe to latest weights.
                tracker.best_val_loss = checkpoint.best_val_metric
                tracker.best_epoch = checkpoint.epoch
                tracker.best_weights = copy.deepcopy(model.state_dict())

        # Training loop
        for epoch in range(start_epoch, self.config.max_epochs):
            model.train()
            for batch_x, batch_y in train_loader:
                optimizer.zero_grad()
                logits = model(batch_x)
                loss = criterion(logits, batch_y)
                loss.backward()
                optimizer.step()

            # Validation evaluation
            model.eval()
            with torch.no_grad():
                val_logits = model(x_val_t)
                val_loss = float(criterion(val_logits, y_val_t).item())

            tracker.update(epoch, val_loss, model.state_dict())

            # Save latest checkpoint if directory provided
            if checkpoint_dir is not None:
                checkpoint_dir.mkdir(parents=True, exist_ok=True)
                ckpt = NeuralTrainingCheckpoint(
                    epoch=epoch,
                    model_id=self.config.model_id,
                    input_hash=input_hash,
                    model_state=_serialize_model_state(model.state_dict()),
                    optimizer_state=_tensor_to_json(optimizer.state_dict()),
                    rng_state=_capture_rng_state(self.config.seed),
                    best_val_metric=tracker.best_val_loss,
                )
                save_checkpoint(ckpt, checkpoint_dir / "latest_checkpoint.json")
                # Persist the true best weights beside the latest checkpoint so
                # resume restores the best validation model, not interrupted weights.
                if tracker.best_weights is not None:
                    best_payload = {
                        "model_id": self.config.model_id,
                        "input_hash": input_hash,
                        "best_epoch": tracker.best_epoch,
                        "best_val_loss": tracker.best_val_loss,
                        "patience_counter": tracker.patience_counter,
                        "best_model_state": _serialize_model_state(tracker.best_weights),
                    }
                    best_path = checkpoint_dir / BEST_CHECKPOINT_FILENAME
                    tmp_best = best_path.with_suffix(best_path.suffix + ".tmp")
                    tmp_best.write_text(json.dumps(best_payload), encoding="utf-8")
                    tmp_best.replace(best_path)

            # Check interruption simulation
            if interrupt_after_epoch is not None and epoch >= interrupt_after_epoch:
                break

            if tracker.should_stop:
                break

        # Load best weights
        if tracker.best_weights is not None:
            model.load_state_dict(tracker.best_weights)
        self._model = model

        # Deterministic bundle hash
        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "feature_names": self._feature_names,
            "best_epoch": tracker.best_epoch,
            "best_val_loss": tracker.best_val_loss,
        }
        bundle_hash = hashlib.sha256(
            json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        self._bundle = D01MLPFittedBundle(
            config=self.config,
            feature_names=self._feature_names,
            input_dim=input_dim,
            best_epoch=tracker.best_epoch,
            best_val_loss=tracker.best_val_loss,
            bundle_hash=bundle_hash,
            fitted_at_utc=datetime.now(UTC),
        )
        return self._bundle

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities on new features."""
        torch = require_torch()
        if self._model is None or self._bundle is None:
            raise RuntimeError("D01MLPTrainer is not fitted yet.")

        self._model.eval()
        with torch.no_grad():
            x_t = torch.tensor(X[self._feature_names].values, dtype=torch.float32)
            logits = self._model(x_t)
            probs = torch.sigmoid(logits).squeeze(1).cpu().numpy()
        return np.asarray(probs, dtype=float)

    def predict_forecasts(
        self,
        X: pd.DataFrame,
        pair: str,
        decision_ts: datetime,
        mapper: CostAwareExecutionMapper,
        desired_qty: Any = None,
        payoff: PayoffStructure | None = None,
    ) -> list[ExecutionDecision]:
        """Convert predictions into execution decisions via common mapper."""
        probs = self.predict_proba(X)
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


# ---------------------------------------------------------------------------
# Same Sample Comparator (D01-01-AC1)
# ---------------------------------------------------------------------------


class SameSampleComparator:
    """Enforces identical sample and feature verification when comparing M01 and D01."""

    def compare(
        self,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        m01_trainer: Any,
        d01_trainer: D01MLPTrainer,
        realized_returns: np.ndarray | None = None,
        round_trip_cost: float = 0.0040,
    ) -> SameSampleComparisonResult:
        """Compare M01 baseline and D01 MLP on exact same sample validation rows."""
        # 1. Row count validation
        if len(X_val) != len(y_val):
            raise SampleComparatorMismatchError(
                f"SAMPLE_COUNT_MISMATCH: X_val rows={len(X_val)} != y_val rows={len(y_val)}"
            )

        # 2. Feature column validation
        expected_cols = set(d01_trainer._feature_names)
        actual_cols = set(X_val.columns)
        if not expected_cols.issubset(actual_cols):
            missing = expected_cols - actual_cols
            raise SampleComparatorMismatchError(
                f"FEATURE_COLUMNS_MISMATCH: Missing required features in comparator: {missing}"
            )

        # 3. Compute probability forecasts
        m01_probs = m01_trainer.predict_proba(X_val)
        d01_probs = d01_trainer.predict_proba(X_val)

        y_true = y_val.values.astype(int)

        m01_brier = float(brier_score_loss(y_true, m01_probs))
        d01_brier = float(brier_score_loss(y_true, d01_probs))
        brier_improvement = m01_brier - d01_brier  # Positive means D01 is better (lower error)

        m01_utility = None
        d01_utility = None
        utility_improvement = None

        if realized_returns is not None:
            if len(realized_returns) != len(X_val):
                raise SampleComparatorMismatchError(
                    f"SAMPLE_COUNT_MISMATCH: realized_returns length={len(realized_returns)} != {len(X_val)}"
                )
            net_ret = realized_returns - round_trip_cost
            m01_trades = (m01_probs > 0.5).astype(float)
            d01_trades = (d01_probs > 0.5).astype(float)
            m01_utility = float(np.mean(m01_trades * net_ret))
            d01_utility = float(np.mean(d01_trades * net_ret))
            utility_improvement = d01_utility - m01_utility

        return SameSampleComparisonResult(
            sample_count=len(X_val),
            m01_brier_score=m01_brier,
            d01_brier_score=d01_brier,
            brier_improvement=brier_improvement,
            m01_net_utility=m01_utility,
            d01_net_utility=d01_utility,
            utility_improvement=utility_improvement,
            evaluated_at_utc=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Multi-Seed Evaluator (D01-01-AC2)
# ---------------------------------------------------------------------------


class D01MultiSeedEvaluator:
    """Evaluates fixed finalist seeds under <= 12 configuration budget without cherry-picking."""

    def validate_search_budget(self, configs: list[D01MLPConfig]) -> bool:
        """Validate that search configs do not exceed maximum budget of 12."""
        if len(configs) > 12:
            raise SearchBudgetExceededError(
                f"SEARCH_BUDGET_EXCEEDED: Maximum allowed search configurations is 12, got {len(configs)}"
            )
        return True

    def evaluate_finalist_seeds(
        self,
        base_config: D01MLPConfig,
        seeds: tuple[int, ...],
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> D01FinalistEvaluation:
        """Train across 3 fixed finalist seeds without cherry-picking and record aggregate stability."""
        if len(seeds) != 3:
            raise ValueError(f"FINALIST_SEEDS_REQUIRED: Exactly 3 fixed finalist seeds required, got {len(seeds)}")

        seed_results: dict[int, float] = {}
        for seed in seeds:
            config = D01MLPConfig(
                hidden_dims=base_config.hidden_dims,
                activation=base_config.activation,
                dropout=base_config.dropout,
                learning_rate=base_config.learning_rate,
                weight_decay=base_config.weight_decay,
                batch_size=base_config.batch_size,
                max_epochs=base_config.max_epochs,
                patience=base_config.patience,
                seed=seed,
            )
            trainer = D01MLPTrainer(config=config)
            bundle = trainer.fit(X_train, y_train, X_val, y_val)
            seed_results[seed] = bundle.best_val_loss

        val_losses = list(seed_results.values())
        return D01FinalistEvaluation(
            seed_results=seed_results,
            val_loss_mean=float(np.mean(val_losses)),
            val_loss_std=float(np.std(val_losses)),
            is_cherry_picked=False,
            evaluated_at_utc=datetime.now(UTC),
        )
