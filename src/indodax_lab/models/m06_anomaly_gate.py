"""Market anomaly risk gate model (M06-01).

Contract: Train-only liquidity distribution -> anomaly score and abstain threshold.

Guarantees:
1. M06-01-AC0: Train on liquidity features; evaluate returns AnomalyDecision with scores.
2. M06-01-AC1: Anomaly threshold is frozen at train time and does not fit future data.
3. M06-01-AC2: No anomaly target claims return direction (DirectionalClaimForbiddenError).
4. M06-01-AC3: Missing data is strictly distinguished from market anomalies (MissingDataDistinctFromAnomalyError).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.ensemble import IsolationForest


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MissingDataDistinctFromAnomalyError(ValueError):
    """Raised when input features contain missing/NaN values.

    Missing data is a data pipeline failure, not a market anomaly (M06-01-AC3).
    """


class DirectionalClaimForbiddenError(ValueError):
    """Raised when an attempt is made to use the anomaly gate for directional return forecasting.

    The anomaly gate is strictly an unsupervised risk filter (M06-01-AC2).
    """


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class M06Config(BaseModel):
    """Configuration for M06 Market Anomaly Risk Gate."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "M06"
    version: str = "1.0.0"
    contamination: float = 0.05
    n_estimators: int = 50
    seed: int = 42


class M06FittedBundle(BaseModel):
    """Immutable bundle containing metadata, feature list, and frozen threshold."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: M06Config
    feature_names: list[str]
    anomaly_threshold: float
    bundle_hash: str
    fitted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnomalyDecision(BaseModel):
    """Decision output for an observation evaluated against the anomaly gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    anomaly_score: float
    is_anomaly: bool
    threshold: float
    action: str = Field(description="'PASS' if normal, 'ABSTAIN' if anomaly detected")


# ---------------------------------------------------------------------------
# M06AnomalyGate
# ---------------------------------------------------------------------------


class M06AnomalyGate:
    """Unsupervised market anomaly gate using liquidity and order flow distributions."""

    def __init__(self, config: M06Config) -> None:
        self.config = config
        self._clf: IsolationForest | None = None
        self._bundle: M06FittedBundle | None = None
        self._threshold: float | None = None

    @property
    def bundle(self) -> M06FittedBundle:
        if self._bundle is None:
            raise RuntimeError("M06AnomalyGate is not fitted yet. Call train() first.")
        return self._bundle

    @property
    def threshold(self) -> float:
        if self._threshold is None:
            raise RuntimeError("M06AnomalyGate is not fitted yet. Call train() first.")
        return self._threshold

    def train(
        self,
        X_train: pd.DataFrame,
        feature_names: list[str],
        target_direction: Any | None = None,
    ) -> M06FittedBundle:
        """Fit anomaly detection model on training liquidity distribution (M06-01-AC0, AC1, AC2).

        Args:
            X_train: Training feature DataFrame.
            feature_names: Canonical ordered list of feature column names.
            target_direction: Must be None. Any directional label raises an error.

        Returns:
            An immutable ``M06FittedBundle``.

        Raises:
            DirectionalClaimForbiddenError: If ``target_direction`` is provided (M06-01-AC2).
            MissingDataDistinctFromAnomalyError: If ``X_train`` contains NaNs (M06-01-AC3).
        """
        # AC2: Reject any directional claim
        if target_direction is not None:
            raise DirectionalClaimForbiddenError(
                "DIRECTIONAL_CLAIM_FORBIDDEN: M06 Anomaly Gate is an unsupervised risk filter. "
                "It cannot be trained on or claim directional return targets (M06-01-AC2)."
            )

        X_tr = X_train[feature_names]

        # AC3: Check for missing data
        if X_tr.isna().any().any():
            raise MissingDataDistinctFromAnomalyError(
                "MISSING_DATA_IN_TRAINING: Training features contain NaN/missing values. "
                "Missing data must be resolved before training and is distinct from market anomalies."
            )

        clf = IsolationForest(
            n_estimators=self.config.n_estimators,
            contamination=self.config.contamination,
            random_state=self.config.seed,
            n_jobs=1,
        )
        clf.fit(X_tr)
        self._clf = clf

        # AC1: Anomaly score = -score_samples (higher score = more anomalous)
        train_scores = -clf.score_samples(X_tr)
        threshold = float(np.percentile(train_scores, (1.0 - self.config.contamination) * 100))
        self._threshold = threshold

        # Deterministic bundle hash
        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "feature_names": feature_names,
            "threshold": threshold,
        }
        raw_hash = json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        bundle_hash = hashlib.sha256(raw_hash).hexdigest()

        self._bundle = M06FittedBundle(
            config=self.config,
            feature_names=feature_names,
            anomaly_threshold=threshold,
            bundle_hash=bundle_hash,
        )
        return self._bundle

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """Compute raw anomaly scores for observations (higher = more anomalous).

        Args:
            X: Feature DataFrame.

        Returns:
            1-D float64 array of anomaly scores.

        Raises:
            MissingDataDistinctFromAnomalyError: If input data contains missing/NaN values (M06-01-AC3).
        """
        if self._clf is None or self._bundle is None or self._threshold is None:
            raise RuntimeError("M06AnomalyGate is not fitted yet. Call train() first.")

        X_ord = X[self._bundle.feature_names]

        # AC3: Check for missing data in evaluation
        if X_ord.isna().any().any():
            raise MissingDataDistinctFromAnomalyError(
                "MISSING_DATA_DISTINCT_FROM_ANOMALY: Input features contain NaN/missing values. "
                "Data pipeline gaps must be flagged as missing data errors, NOT treated as market anomalies (M06-01-AC3)."
            )

        # -score_samples: standard convention where higher values are more anomalous
        return -self._clf.score_samples(X_ord)

    def evaluate(self, X: pd.DataFrame) -> list[AnomalyDecision]:
        """Evaluate observations against the frozen training anomaly threshold (M06-01-AC0, AC1).

        Args:
            X: Feature DataFrame.

        Returns:
            List of ``AnomalyDecision`` records.
        """
        scores = self.score(X)
        threshold = self.threshold

        decisions: list[AnomalyDecision] = []
        for s in scores:
            score_val = float(s)
            is_anomaly = bool(score_val > threshold)
            action = "ABSTAIN" if is_anomaly else "PASS"
            decisions.append(
                AnomalyDecision(
                    anomaly_score=score_val,
                    is_anomaly=is_anomaly,
                    threshold=threshold,
                    action=action,
                )
            )
        return decisions
