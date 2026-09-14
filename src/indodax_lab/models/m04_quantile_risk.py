"""Quantile risk regression model for interval forecasts (M04-01).

Contract: Registered return volatility or tail quantile target -> interval forecast.

Guarantees:
1. M04-01-AC0: Train separate quantile models; predict returns (lower, upper) intervals.
2. M04-01-AC1: Quantile crossing handled explicitly (lower <= upper validated in config and enforced on predictions).
3. M04-01-AC2: Out-of-sample coverage recorded (nominal vs actual coverage in QuantileCoverageReport).
4. M04-01-AC3: Tail target leakage prevented fail-closed (TailTargetLeakageError).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.ensemble import GradientBoostingRegressor


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class QuantileCrossingError(ValueError):
    """Raised when lower quantile is greater than or equal to upper quantile."""


class TailTargetLeakageError(ValueError):
    """Raised when target or tail-target columns are passed as input features."""


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

FORBIDDEN_FEATURE_KEYWORDS = {
    "tail_target",
    "target",
    "label",
    "realized_return",
    "future_return",
    "y_true",
    "outcome",
}


class M04Config(BaseModel):
    """Configuration for M04 Quantile Risk Regression."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "M04"
    version: str = "1.0.0"
    lower_quantile: float = 0.10
    upper_quantile: float = 0.90
    n_estimators: int = 50
    max_depth: int = 3
    seed: int = 42

    @model_validator(mode="after")
    def validate_quantiles(self) -> "M04Config":
        if self.lower_quantile >= self.upper_quantile:
            raise QuantileCrossingError(
                f"QUANTILE_CROSSING_DETECTED: lower_quantile ({self.lower_quantile}) "
                f"must be strictly less than upper_quantile ({self.upper_quantile})."
            )
        if not (0.0 < self.lower_quantile < 1.0) or not (0.0 < self.upper_quantile < 1.0):
            raise QuantileCrossingError(
                f"INVALID_QUANTILES: Quantiles must be in (0, 1). Got "
                f"lower={self.lower_quantile}, upper={self.upper_quantile}."
            )
        return self


class M04FittedBundle(BaseModel):
    """Immutable bundle containing metadata and hashes for fitted M04 models."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: M04Config
    feature_names: list[str]
    bundle_hash: str
    fitted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QuantileCoverageReport(BaseModel):
    """Report evaluating empirical coverage against nominal prediction interval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nominal_coverage: float
    actual_coverage: float
    n_samples: int
    violations_count: int


# ---------------------------------------------------------------------------
# M04QuantileTrainer
# ---------------------------------------------------------------------------


class M04QuantileTrainer:
    """Trainer for dual quantile regressors providing interval forecasts."""

    def __init__(self, config: M04Config) -> None:
        self.config = config
        self._model_lower: GradientBoostingRegressor | None = None
        self._model_upper: GradientBoostingRegressor | None = None
        self._bundle: M04FittedBundle | None = None

    @property
    def bundle(self) -> M04FittedBundle:
        if self._bundle is None:
            raise RuntimeError("M04QuantileTrainer is not fitted yet. Call train() first.")
        return self._bundle

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray | pd.Series,
        feature_names: list[str],
    ) -> M04FittedBundle:
        """Fit lower and upper quantile regressors on training split.

        Args:
            X_train: Training features DataFrame.
            y_train: Target values (returns, volatility, etc.).
            feature_names: Canonical list of feature column names.

        Returns:
            An immutable ``M04FittedBundle``.

        Raises:
            TailTargetLeakageError: If any feature name matches forbidden target keywords.
        """
        # AC3: Check for tail target or label leakage in features
        for col in feature_names:
            col_lower = col.strip().lower()
            if col_lower in FORBIDDEN_FEATURE_KEYWORDS or "tail_target" in col_lower:
                raise TailTargetLeakageError(
                    f"TAIL_TARGET_LEAKAGE: Feature '{col}' contains target or tail information. "
                    "Tail target must not be used as an input feature (M04-01-AC3)."
                )

        X_tr = X_train[feature_names]
        y_tr = np.asarray(y_train, dtype=np.float64)

        model_lower = GradientBoostingRegressor(
            loss="quantile",
            alpha=self.config.lower_quantile,
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            random_state=self.config.seed,
        )
        model_upper = GradientBoostingRegressor(
            loss="quantile",
            alpha=self.config.upper_quantile,
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            random_state=self.config.seed,
        )

        model_lower.fit(X_tr, y_tr)
        model_upper.fit(X_tr, y_tr)

        self._model_lower = model_lower
        self._model_upper = model_upper

        # Deterministic bundle hash
        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "feature_names": feature_names,
        }
        raw_hash = json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        bundle_hash = hashlib.sha256(raw_hash).hexdigest()

        self._bundle = M04FittedBundle(
            config=self.config,
            feature_names=feature_names,
            bundle_hash=bundle_hash,
        )
        return self._bundle

    def predict_interval(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Predict lower and upper quantile bounds for the input features.

        Quantile crossing is explicitly handled by ensuring lower <= upper on predictions.

        Args:
            X: Input DataFrame containing features.

        Returns:
            Tuple of (lower_bound, upper_bound) 1-D numpy arrays.
        """
        if self._model_lower is None or self._model_upper is None or self._bundle is None:
            raise RuntimeError("M04QuantileTrainer is not fitted yet. Call train() first.")

        X_ord = X[self._bundle.feature_names]
        raw_lower = self._model_lower.predict(X_ord)
        raw_upper = self._model_upper.predict(X_ord)

        # AC1: Explicit quantile crossing resolution (monotonic bounds)
        lower = np.minimum(raw_lower, raw_upper)
        upper = np.maximum(raw_lower, raw_upper)

        return lower, upper

    def evaluate_coverage(
        self,
        X_val: pd.DataFrame,
        y_val: np.ndarray | pd.Series,
    ) -> QuantileCoverageReport:
        """Evaluate empirical out-of-sample coverage against nominal interval.

        Args:
            X_val: Validation feature DataFrame.
            y_val: True realized target values.

        Returns:
            A ``QuantileCoverageReport``.
        """
        lower, upper = self.predict_interval(X_val)
        y_arr = np.asarray(y_val, dtype=np.float64)

        covered = (y_arr >= lower) & (y_arr <= upper)
        actual_cov = float(np.mean(covered))
        nominal_cov = float(self.config.upper_quantile - self.config.lower_quantile)
        violations = int(np.sum(~covered))

        return QuantileCoverageReport(
            nominal_coverage=nominal_cov,
            actual_coverage=actual_cov,
            n_samples=len(y_arr),
            violations_count=violations,
        )
