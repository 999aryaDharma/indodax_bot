"""Tests for M03-01: Random forest regime gate.

RED tests written before implementation.

Contract: Train-only regime labels -> calibrated risk classification.

AC boundaries:
- AC0: Train-only regime labels produce calibrated risk classification (positive contract).
- AC1: Test/inference regime data does NOT retrain the model.
- AC2: Abstain (return UNKNOWN) for unseen/unknown regime class.
- AC3: Report downside and net utility (not just raw predictions).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.models.m03_rf_regime import (
    M03Config,
    M03FittedBundle,
    M03RFRegimeTrainer,
    RegimeAbstainError,
    RegimeLabel,
    RegimeUtilityReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_feature_df(n: int = 200, n_features: int = 4, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = [f"feat_{i}" for i in range(n_features)]
    return pd.DataFrame(rng.standard_normal((n, n_features)), columns=cols)


def _make_regime_labels(n: int = 200, seed: int = 42) -> pd.Series:
    """Three classes: 0=BEAR, 1=SIDEWAYS, 2=BULL — never 'unknown' in training."""
    rng = np.random.default_rng(seed)
    return pd.Series(rng.integers(0, 3, size=n, dtype=int))


def _build_trainer_and_bundle(feature_names: list[str]) -> tuple["M03RFRegimeTrainer", "M03FittedBundle"]:
    """Helper: build a fitted M03RFRegimeTrainer with a valid training split."""
    X = _make_feature_df(n=200, n_features=len(feature_names))
    X.columns = feature_names  # type: ignore[assignment]
    y = _make_regime_labels(n=200)

    config = M03Config(
        model_id="M03",
        version="1.0.0",
        n_estimators=20,
        max_depth=3,
        seed=42,
    )
    trainer = M03RFRegimeTrainer(config=config)
    bundle = trainer.train(
        X_train=X.iloc[:160],
        y_train=y.iloc[:160],
        feature_names=feature_names,
    )
    return trainer, bundle


# ---------------------------------------------------------------------------
# AC0: Train-only regime labels produce calibrated risk classification
# ---------------------------------------------------------------------------

def test_m03_01_valid_contract():
    """M03-01-AC0: Train on regime labels; predict returns calibrated class probabilities."""
    feature_names = [f"feat_{i}" for i in range(4)]
    trainer, bundle = _build_trainer_and_bundle(feature_names)

    X_test = _make_feature_df(n=40, n_features=4, seed=77)
    X_test.columns = feature_names  # type: ignore[assignment]

    proba = trainer.predict_regime_proba(X_test)

    assert proba.shape[0] == 40, "Must return one row per sample"
    assert proba.shape[1] == 3, "Must return probability for each of 3 regime classes"
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6), "Probabilities must sum to 1.0"

    # Bundle captures feature names and config
    assert bundle.feature_names == feature_names
    assert bundle.config.model_id == "M03"


# ---------------------------------------------------------------------------
# AC1: Test/inference does NOT retrain the model
# ---------------------------------------------------------------------------

def test_m03_01_contract_1():
    """M03-01-AC1: Calling predict on test data does not modify the fitted model."""
    feature_names = [f"feat_{i}" for i in range(4)]
    trainer, bundle = _build_trainer_and_bundle(feature_names)

    # Record bundle hash before inference
    bundle_hash_before = bundle.bundle_hash

    # Predict on test/regime data
    X_test = _make_feature_df(n=40, n_features=4, seed=99)
    X_test.columns = feature_names  # type: ignore[assignment]
    trainer.predict_regime_proba(X_test)

    # Bundle hash must be unchanged — test data cannot trigger retraining
    assert trainer.bundle.bundle_hash == bundle_hash_before, (
        "Bundle hash must not change after inference on test data. "
        "Inference must NOT retrain the model."
    )


# ---------------------------------------------------------------------------
# AC2: Abstain for unknown/unseen regime class
# ---------------------------------------------------------------------------

def test_m03_01_contract_2():
    """M03-01-AC2: RegimeLabel.UNKNOWN triggers abstain; not silently mapped to nearest class."""
    feature_names = [f"feat_{i}" for i in range(4)]
    trainer, bundle = _build_trainer_and_bundle(feature_names)

    # Model trained on 3 classes (0,1,2). Pass in an "unknown_regime" query flag.
    with pytest.raises(RegimeAbstainError):
        trainer.predict_regime_for_unknown(
            feature_names=feature_names,
            unknown_class_label=99,  # class 99 never seen in training
        )


# ---------------------------------------------------------------------------
# AC3: Report downside and net utility
# ---------------------------------------------------------------------------

def test_m03_01_contract_3():
    """M03-01-AC3: RegimeUtilityReport captures downside risk and net utility."""
    feature_names = [f"feat_{i}" for i in range(4)]
    trainer, bundle = _build_trainer_and_bundle(feature_names)

    X_eval = _make_feature_df(n=40, n_features=4, seed=55)
    X_eval.columns = feature_names  # type: ignore[assignment]
    rng = np.random.default_rng(55)
    realized_returns = rng.normal(0.001, 0.01, size=40)

    report = trainer.evaluate_utility(
        X_eval=X_eval,
        realized_returns=realized_returns,
        round_trip_cost=0.004,
    )

    assert isinstance(report, RegimeUtilityReport)
    assert hasattr(report, "net_utility"), "Report must include net_utility"
    assert hasattr(report, "downside_risk"), "Report must include downside_risk"
    assert report.downside_risk >= 0.0, "Downside risk must be non-negative"
    # net_utility can be negative; just must be a finite float
    assert np.isfinite(report.net_utility), "net_utility must be a finite float"


# ---------------------------------------------------------------------------
# Edge case: Predict before training raises error
# ---------------------------------------------------------------------------

def test_m03_01_not_fitted_error():
    """Edge case: predict_regime_proba before train() raises RuntimeError."""
    config = M03Config(model_id="M03", version="1.0.0", n_estimators=10, max_depth=3, seed=42)
    trainer = M03RFRegimeTrainer(config=config)
    X = _make_feature_df(n=10, n_features=4)
    X.columns = [f"feat_{i}" for i in range(4)]  # type: ignore[assignment]

    with pytest.raises(RuntimeError):
        trainer.predict_regime_proba(X)
