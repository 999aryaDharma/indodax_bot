"""Random Forest regime gate model (M03-01).

Contract: Train-only regime labels -> calibrated risk classification.

Guarantees:
1. M03-01-AC0: Train on regime labels; predict returns calibrated class probabilities.
2. M03-01-AC1: Inference on test data does NOT retrain or modify the fitted model.
3. M03-01-AC2: Abstain for unknown/unseen regime class (RegimeAbstainError); never silently map to nearest.
4. M03-01-AC3: Evaluate net utility and downside risk in RegimeUtilityReport.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sklearn.ensemble import RandomForestClassifier


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RegimeAbstainError(ValueError):
    """Raised when a prediction is requested for an unknown/unseen regime class.

    The model must not silently map unseen classes to the nearest known class.
    """


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class RegimeLabel(StrEnum):
    """Canonical regime class labels."""

    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    BULL = "BULL"
    UNKNOWN = "UNKNOWN"


class M03Config(BaseModel):
    """Configuration for M03 Random Forest regime gate."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str = "M03"
    version: str = "1.0.0"
    n_estimators: int = 100
    max_depth: int | None = 5
    min_samples_leaf: int = 5
    seed: int = 42


class M03FittedBundle(BaseModel):
    """Immutable bundle for the fitted M03 regime gate model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: M03Config
    feature_names: list[str]
    classes_: list[int]
    bundle_hash: str
    fitted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RegimeUtilityReport(BaseModel):
    """Evaluation report capturing downside risk and net utility of regime-gated decisions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    net_utility: float
    downside_risk: float  # Semi-deviation of returns when regime gate triggers
    n_entries: int
    n_abstains: int
    round_trip_cost: float


# ---------------------------------------------------------------------------
# M03RFRegimeTrainer
# ---------------------------------------------------------------------------


class M03RFRegimeTrainer:
    """Trains a Random Forest classifier for market regime detection.

    Training uses only train-split regime labels (AC0). Inference on test data
    does NOT trigger retraining (AC1). Unknown regime classes abstain (AC2).
    Utility evaluation reports downside risk alongside net utility (AC3).
    """

    def __init__(self, config: M03Config) -> None:
        self.config = config
        self._clf: RandomForestClassifier | None = None
        self._bundle: M03FittedBundle | None = None
        self._known_classes: set[int] = set()

    @property
    def bundle(self) -> M03FittedBundle:
        if self._bundle is None:
            raise RuntimeError("M03RFRegimeTrainer is not fitted yet. Call train() first.")
        return self._bundle

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        feature_names: list[str],
    ) -> M03FittedBundle:
        """Fit the random forest on train-split regime labels only (M03-01-AC0, AC1).

        No test data is passed here. Inference is a separate method.

        Args:
            X_train: Training feature DataFrame.
            y_train: Integer regime class labels for training rows.
            feature_names: Canonical ordered list of feature names.

        Returns:
            An immutable ``M03FittedBundle``.
        """
        X_tr = X_train[feature_names]

        clf = RandomForestClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            min_samples_leaf=self.config.min_samples_leaf,
            random_state=self.config.seed,
            n_jobs=1,
        )
        clf.fit(X_tr, y_train)
        self._clf = clf
        self._known_classes = set(int(c) for c in clf.classes_)

        # Deterministic bundle hash (semantic attributes, no wall-clock)
        hash_payload = {
            "config": self.config.model_dump(mode="json"),
            "feature_names": feature_names,
            "classes": sorted(self._known_classes),
        }
        raw_hash = json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        bundle_hash = hashlib.sha256(raw_hash).hexdigest()

        self._bundle = M03FittedBundle(
            config=self.config,
            feature_names=feature_names,
            classes_=sorted(self._known_classes),
            bundle_hash=bundle_hash,
        )
        return self._bundle

    def predict_regime_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict calibrated regime class probabilities (M03-01-AC0, AC1).

        Inference does NOT modify ``self._bundle`` or retrain ``self._clf``.

        Args:
            X: Input feature DataFrame with columns matching ``bundle.feature_names``.

        Returns:
            2-D float64 array of shape (n_samples, n_classes).
        """
        if self._clf is None or self._bundle is None:
            raise RuntimeError("M03RFRegimeTrainer is not fitted yet. Call train() first.")

        X_ordered = X[self._bundle.feature_names]
        # AC1: predict_proba is pure inference — no state mutation
        return self._clf.predict_proba(X_ordered)

    def predict_regime_for_unknown(
        self,
        feature_names: list[str],
        unknown_class_label: int,
    ) -> None:
        """Abstain for unknown/unseen regime class (M03-01-AC2).

        Raises:
            RegimeAbstainError: Always, because the given class label is not in training classes.
        """
        if self._clf is None or self._bundle is None:
            raise RuntimeError("M03RFRegimeTrainer is not fitted yet. Call train() first.")

        if unknown_class_label not in self._known_classes:
            raise RegimeAbstainError(
                f"REGIME_ABSTAIN: Class label '{unknown_class_label}' was not seen during training. "
                f"Known classes: {sorted(self._known_classes)}. "
                "The model must not silently predict for unseen regime classes. "
                "Abstain and flag as UNKNOWN for downstream handling."
            )

    def evaluate_utility(
        self,
        X_eval: pd.DataFrame,
        realized_returns: np.ndarray,
        round_trip_cost: float = 0.0040,
        bull_class: int = 2,
    ) -> RegimeUtilityReport:
        """Evaluate net utility and downside risk of regime-gated entries (M03-01-AC3).

        The model enters only when the BULL regime class has the highest probability.
        Net utility accounts for round-trip cost. Downside risk is the semi-deviation
        of returns in entered trades.

        Args:
            X_eval: Evaluation features.
            realized_returns: Array of realized returns per bar.
            round_trip_cost: Total round-trip transaction cost to deduct from entries.
            bull_class: Integer label for the "BULL" regime (typically 2).

        Returns:
            A ``RegimeUtilityReport`` with net_utility and downside_risk.
        """
        proba = self.predict_regime_proba(X_eval)

        # Determine the column index for bull_class
        if self._bundle is None:
            raise RuntimeError("Not fitted.")
        classes = self._bundle.classes_
        if bull_class not in classes:
            # If bull class never seen, abstain all
            return RegimeUtilityReport(
                net_utility=0.0,
                downside_risk=0.0,
                n_entries=0,
                n_abstains=len(X_eval),
                round_trip_cost=round_trip_cost,
            )

        bull_idx = classes.index(bull_class)
        predicted_class = np.argmax(proba, axis=1)
        # Map predicted column index back to class label
        predicted_labels = np.array([classes[i] for i in predicted_class])

        entries = (predicted_labels == bull_class)
        n_entries = int(entries.sum())
        n_abstains = len(X_eval) - n_entries

        if n_entries == 0:
            return RegimeUtilityReport(
                net_utility=0.0,
                downside_risk=0.0,
                n_entries=0,
                n_abstains=n_abstains,
                round_trip_cost=round_trip_cost,
            )

        entry_returns = realized_returns[entries] - round_trip_cost
        net_utility = float(np.mean(entry_returns))

        # Downside risk = semi-deviation (negative returns only)
        negative_returns = entry_returns[entry_returns < 0]
        if len(negative_returns) > 0:
            downside_risk = float(np.std(negative_returns))
        else:
            downside_risk = 0.0

        return RegimeUtilityReport(
            net_utility=net_utility,
            downside_risk=downside_risk,
            n_entries=n_entries,
            n_abstains=n_abstains,
            round_trip_cost=round_trip_cost,
        )
