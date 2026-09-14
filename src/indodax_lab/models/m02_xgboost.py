"""XGBoost gradient boosting challenger model with early stopping and calibration (M02-01).

Guarantees:
1. M02-01-AC0: M02 compared fairly with linear and baseline on identical outer test folds.
2. M02-01-AC1: Early stopping strictly prohibited from observing sealed/test partition labels.
3. M02-01-AC2: Finalist evaluation audits multi-seed robustness, recording both median and worst seed utility.
4. M02-01-AC3: Tree pipeline preserves canonical feature order; reorders inputs and rejects missing features.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any, Sequence
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
import xgboost as xgb

from indodax_lab.models.calibration import FittedCalibratorArtifact, HeldOutCalibrator
from indodax_lab.models.m01_logistic import ModelUtilityComparison
from indodax_lab.models.preprocessing import FeatureAlignmentError


class SealedPartitionLeakageError(ValueError):
    """Raised when early stopping evaluation targets sealed or test partitions."""


class M02Config(BaseModel):
    """Configuration for M02 XGBoost challenger model."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "M02"
    version: str = "1.0.0"
    max_depth: int = 3
    n_estimators: int = 100
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    early_stopping_rounds: int = 10
    eval_metric: str = "logloss"
    seed: int = 42


class M02FittedBundle(BaseModel):
    """Immutable bundle containing fitted XGBoost challenger and held-out calibration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: M02Config
    best_iteration: int
    feature_names: list[str]
    calibrator: FittedCalibratorArtifact
    bundle_hash: str
    fitted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class M02SeedResult(BaseModel):
    """Execution outcome for an individual seed run in the robustness audit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: int
    best_iteration: int
    utility: float


class M02MultiSeedAudit(BaseModel):
    """Multi-seed evaluation record documenting median and worst seed performance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seeds: list[int]
    seed_results: list[M02SeedResult]
    median_utility: float
    worst_utility: float


class M02XGBoostTrainer:
    """Trains, early-stops, calibrates, and audits M02 XGBoost challenger models."""

    FORBIDDEN_EVAL_PARTITIONS = {
        "sealed_test",
        "test",
        "outer_test",
        "outer_val",
        "outer_validation",
    }

    def __init__(self, config: M02Config) -> None:
        self.config = config
        self._model: xgb.XGBClassifier | None = None
        self._calibrator: HeldOutCalibrator | None = None
        self._bundle: M02FittedBundle | None = None

    @property
    def bundle(self) -> M02FittedBundle:
        if self._bundle is None:
            raise RuntimeError("M02XGBoostTrainer is not fitted yet.")
        return self._bundle

    def train_and_calibrate(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        feature_names: list[str],
        val_partition_type: str = "inner_heldout",
    ) -> M02FittedBundle:
        """Fit XGBoost model with early stopping on inner validation, then calibrate on held-out scores."""
        # 1. Reject sealed test evaluation partition leakage (M02-01-AC1)
        norm_part = val_partition_type.strip().lower()
        if norm_part in self.FORBIDDEN_EVAL_PARTITIONS:
            raise SealedPartitionLeakageError(
                f"SEALED_PARTITION_LEAKAGE: Early stopping partition '{val_partition_type}' is forbidden. "
                "Early stopping must strictly observe inner validation partitions."
            )

        # 2. Strict feature column ordering (M02-01-AC3)
        X_tr = X_train[feature_names]
        X_v = X_val[feature_names]

        # 3. Fit XGBoost classifier with early stopping
        model = xgb.XGBClassifier(
            max_depth=self.config.max_depth,
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            early_stopping_rounds=self.config.early_stopping_rounds,
            eval_metric=self.config.eval_metric,
            random_state=self.config.seed,
            n_jobs=1,
        )
        model.fit(
            X_tr,
            y_train,
            eval_set=[(X_v, y_val)],
            verbose=False,
        )
        self._model = model

        # 4. Calibrate raw margin scores on held-out validation segment
        raw_val_scores = model.predict(X_v, output_margin=True)
        calibrator = HeldOutCalibrator()
        calibrator_artifact = calibrator.fit(
            heldout_scores=raw_val_scores,
            heldout_labels=y_val.values,
            segment_type="inner_heldout",
        )
        self._calibrator = calibrator

        # 5. Deterministic bundle hash (semantic attributes only, excluding timestamp)
        best_iter = int(model.best_iteration) if hasattr(model, "best_iteration") and model.best_iteration is not None else self.config.n_estimators
        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "best_iteration": best_iter,
            "feature_names": feature_names,
            "calibrator": {
                "method": calibrator_artifact.method,
                "a": calibrator_artifact.a,
                "b": calibrator_artifact.b,
                "n_samples": calibrator_artifact.n_samples,
            },
        }
        raw_hash_bytes = json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        bundle_hash = hashlib.sha256(raw_hash_bytes).hexdigest()

        self._bundle = M02FittedBundle(
            config=self.config,
            best_iteration=best_iter,
            feature_names=feature_names,
            calibrator=calibrator_artifact,
            bundle_hash=bundle_hash,
            fitted_at_utc=datetime.now(UTC),
        )
        return self._bundle

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict calibrated probabilities, verifying and enforcing canonical feature order (M02-01-AC3)."""
        if self._model is None or self._calibrator is None or self._bundle is None:
            raise RuntimeError("M02XGBoostTrainer is not fitted yet.")

        # Check for missing features
        missing = [f for f in self._bundle.feature_names if f not in X.columns]
        if missing:
            raise FeatureAlignmentError(f"MISSING_FEATURES: Input data is missing required features: {missing}")

        # Reorder to canonical feature names
        X_ordered = X[self._bundle.feature_names]
        raw_scores = self._model.predict(X_ordered, output_margin=True)
        return self._calibrator.predict_probability(raw_scores)

    def evaluate_utility(
        self,
        X: pd.DataFrame,
        realized_returns: np.ndarray,
        round_trip_cost: float = 0.0040,
    ) -> ModelUtilityComparison:
        """Evaluate net utility on test fold against cash and naive baseline."""
        probs = self.predict_proba(X)
        model_trades = (probs > 0.5).astype(float)
        net_returns_if_traded = realized_returns - round_trip_cost

        model_net_utility = float(np.mean(model_trades * net_returns_if_traded))
        cash_utility = 0.0

        naive_trades = np.ones_like(model_trades)
        naive_utility = float(np.mean(naive_trades * net_returns_if_traded))

        return ModelUtilityComparison(
            model_net_utility=model_net_utility,
            cash_utility=cash_utility,
            naive_baseline_utility=naive_utility,
            beats_cash=(model_net_utility > cash_utility),
            beats_naive=(model_net_utility > naive_utility),
        )

    def audit_multi_seed(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        X_eval: pd.DataFrame,
        realized_returns: np.ndarray,
        feature_names: list[str],
        seeds: Sequence[int] = (42, 43, 44),
        round_trip_cost: float = 0.0040,
    ) -> M02MultiSeedAudit:
        """Train across multiple seeds and document median and worst seed utility (M02-01-AC2)."""
        seed_results: list[M02SeedResult] = []

        for seed in seeds:
            seed_config = self.config.model_copy(update={"seed": seed})
            trainer = M02XGBoostTrainer(config=seed_config)
            bundle = trainer.train_and_calibrate(
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                feature_names=feature_names,
            )
            utility_comp = trainer.evaluate_utility(
                X=X_eval,
                realized_returns=realized_returns,
                round_trip_cost=round_trip_cost,
            )
            seed_results.append(
                M02SeedResult(
                    seed=seed,
                    best_iteration=bundle.best_iteration,
                    utility=utility_comp.model_net_utility,
                )
            )

        utilities = [r.utility for r in seed_results]
        median_utility = float(np.median(utilities))
        worst_utility = float(np.min(utilities))

        return M02MultiSeedAudit(
            seeds=list(seeds),
            seed_results=seed_results,
            median_utility=median_utility,
            worst_utility=worst_utility,
        )
