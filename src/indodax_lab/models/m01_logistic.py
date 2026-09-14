"""Calibrated elastic-net logistic regression baseline model (M01-01).

Guarantees:
1. M01-01-AC0: Generates reproducible net-positive probabilities with regularized linear model.
2. M01-01-AC1: Rejects invalid solver and penalty configurations fail-closed.
3. M01-01-AC2: Blocks training on extreme class imbalance with explicit diagnostic.
4. M01-01-AC3: Evaluates output net utility against cash baseline (0.0) and naive always-long baseline.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.linear_model import LogisticRegression

from indodax_lab.models.calibration import FittedCalibratorArtifact, HeldOutCalibrator


class InvalidSolverPenaltyError(ValueError):
    """Raised when an incompatible solver-penalty combination or invalid regularization is specified."""


class ClassImbalanceError(ValueError):
    """Raised when training data exhibits extreme minority class starvation."""


class M01Config(BaseModel):
    """Configuration for M01 regularized logistic regression baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "M01"
    version: str = "1.0.0"
    penalty: str = "elasticnet"
    solver: str = "saga"
    C: float = 0.1
    l1_ratio: float | None = 0.5
    class_weight: str | dict[Any, Any] | None = "balanced"
    seed: int = 42
    max_iter: int = 1000
    min_positive_samples: int = 10
    min_minority_ratio: float = 0.05

    def __init__(self, **data: Any) -> None:
        penalty = data.get("penalty", "elasticnet")
        solver = data.get("solver", "saga")
        c_val = float(data.get("C", 0.1))
        l1_ratio = data.get("l1_ratio", 0.5)

        if c_val <= 0.0:
            raise ValueError("POSITIVE_REGULARIZATION_REQUIRED: C parameter must be strictly positive")

        if penalty == "elasticnet":
            if solver != "saga":
                raise InvalidSolverPenaltyError(
                    f"INVALID_SOLVER_PENALTY: elasticnet penalty requires 'saga' solver, but got '{solver}'"
                )
            if l1_ratio is None or not (0.0 <= float(l1_ratio) <= 1.0):
                raise InvalidSolverPenaltyError(
                    "INVALID_SOLVER_PENALTY: elasticnet penalty requires l1_ratio in range [0.0, 1.0]"
                )

        if penalty == "l1" and solver not in ("saga", "liblinear"):
            raise InvalidSolverPenaltyError(
                f"INVALID_SOLVER_PENALTY: l1 penalty is not supported by solver '{solver}'"
            )

        if penalty == "l2" and solver not in ("saga", "lbfgs", "liblinear", "newton-cg", "sag"):
            raise InvalidSolverPenaltyError(
                f"INVALID_SOLVER_PENALTY: l2 penalty is not supported by solver '{solver}'"
            )

        super().__init__(**data)


class M01FittedBundle(BaseModel):
    """Immutable model bundle pairing fitted logistic weights with held-out calibration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: M01Config
    coefficients: list[float]
    intercept: float
    feature_names: list[str]
    calibrator: FittedCalibratorArtifact
    bundle_hash: str
    fitted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ModelUtilityComparison(BaseModel):
    """Net utility comparison of model decisions against cash and naive baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_net_utility: float
    cash_utility: float = 0.0
    naive_baseline_utility: float
    beats_cash: bool
    beats_naive: bool


class M01LogisticTrainer:
    """Trains and calibrates M01 logistic baseline on tabular features."""

    def __init__(self, config: M01Config) -> None:
        self.config = config
        self._clf: LogisticRegression | None = None
        self._calibrator: HeldOutCalibrator | None = None
        self._bundle: M01FittedBundle | None = None

    @property
    def bundle(self) -> M01FittedBundle:
        if self._bundle is None:
            raise RuntimeError("M01LogisticTrainer is not fitted yet.")
        return self._bundle

    def train_and_calibrate(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        feature_names: list[str],
    ) -> M01FittedBundle:
        """Fit linear model on train features, then calibrate on held-out validation segment."""
        # 1. Check class balance
        y_train_arr = np.asarray(y_train)
        positives = int(np.sum(y_train_arr == 1))
        negatives = int(np.sum(y_train_arr == 0))
        minority = min(positives, negatives)
        minority_ratio = minority / len(y_train_arr) if len(y_train_arr) > 0 else 0.0

        if minority < self.config.min_positive_samples or minority_ratio < self.config.min_minority_ratio:
            raise ClassImbalanceError(
                f"EXTREME_CLASS_IMBALANCE_BLOCKED: Minority class count={minority} "
                f"(threshold={self.config.min_positive_samples}), ratio={minority_ratio:.4f} "
                f"(threshold={self.config.min_minority_ratio})"
            )

        # 2. Fit regularized logistic regression
        clf = LogisticRegression(
            penalty=self.config.penalty,
            solver=self.config.solver,
            C=self.config.C,
            l1_ratio=self.config.l1_ratio if self.config.penalty == "elasticnet" else None,
            class_weight=self.config.class_weight,
            random_state=self.config.seed,
            max_iter=self.config.max_iter,
        )
        clf.fit(X_train[feature_names], y_train)
        self._clf = clf

        # 3. Fit probability calibrator strictly on held-out validation segment
        raw_val_scores = clf.decision_function(X_val[feature_names])
        calibrator = HeldOutCalibrator()
        calibrator_artifact = calibrator.fit(
            heldout_scores=raw_val_scores,
            heldout_labels=y_val.values,
            segment_type="inner_heldout",
        )
        self._calibrator = calibrator

        # 4. Generate deterministic bundle hash (semantic properties only, excluding wall-clock timestamp)
        coef_list = [float(c) for c in clf.coef_[0]]
        intercept_val = float(clf.intercept_[0])
        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "coefficients": coef_list,
            "intercept": intercept_val,
            "feature_names": feature_names,
            "calibrator": {
                "method": calibrator_artifact.method,
                "a": calibrator_artifact.a,
                "b": calibrator_artifact.b,
                "n_samples": calibrator_artifact.n_samples,
                "n_positives": calibrator_artifact.n_positives,
                "n_negatives": calibrator_artifact.n_negatives,
            },
        }
        raw_hash_bytes = json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        bundle_hash = hashlib.sha256(raw_hash_bytes).hexdigest()

        self._bundle = M01FittedBundle(
            config=self.config,
            coefficients=coef_list,
            intercept=intercept_val,
            feature_names=feature_names,
            calibrator=calibrator_artifact,
            bundle_hash=bundle_hash,
            fitted_at_utc=datetime.now(UTC),
        )
        return self._bundle

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict calibrated probabilities on new features."""
        if self._clf is None or self._calibrator is None or self._bundle is None:
            raise RuntimeError("M01LogisticTrainer is not fitted yet.")

        raw_scores = self._clf.decision_function(X[self._bundle.feature_names])
        return self._calibrator.predict_probability(raw_scores)

    def evaluate_utility(
        self,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        realized_returns: np.ndarray,
        round_trip_cost: float = 0.0040,
    ) -> ModelUtilityComparison:
        """Evaluate net utility of calibrated decisions against cash and naive baselines."""
        probs = self.predict_proba(X_val)
        # Decision: go long when probability of positive outcome exceeds neutral threshold
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
