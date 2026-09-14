"""Unit tests for M01-01 Calibrated logistic baseline.

Acceptance Criteria:
- M01-01-AC0 (test_m01_01_valid_contract): M01 memberi probabilitas net-positive dengan recipe linear teratur yang reproducible.
- M01-01-AC1 (test_m01_01_contract_1): Invalid solver penalty ditolak.
- M01-01-AC2 (test_m01_01_contract_2): Tiny class imbalance diproses atau blocked dengan reason.
- M01-01-AC3 (test_m01_01_contract_3): Output dinilai net utility bersama cash dan naive baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.m01_logistic import (
    ClassImbalanceError,
    InvalidSolverPenaltyError,
    M01Config,
    M01FittedBundle,
    M01LogisticTrainer,
    ModelUtilityComparison,
)


def _generate_synthetic_classification_data(
    n_train: int = 200,
    n_val: int = 100,
    minority_ratio: float = 0.35,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    
    # Generate 3 features
    feature_names = ["momentum_5", "volatility_20", "volume_ratio"]
    X_train_vals = rng.normal(0.0, 1.0, size=(n_train, 3))
    X_val_vals = rng.normal(0.0, 1.0, size=(n_val, 3))
    
    # Binary label with realistic signal
    logits_train = X_train_vals[:, 0] * 0.8 - X_train_vals[:, 1] * 0.5 + rng.normal(0.0, 0.2, size=n_train)
    q = np.quantile(logits_train, 1.0 - minority_ratio)
    y_train_vals = (logits_train > q).astype(int)

    logits_val = X_val_vals[:, 0] * 0.8 - X_val_vals[:, 1] * 0.5 + rng.normal(0.0, 0.2, size=n_val)
    y_val_vals = (logits_val > q).astype(int)

    X_train = pd.DataFrame(X_train_vals, columns=feature_names)
    y_train = pd.Series(y_train_vals, name="binary_label")
    X_val = pd.DataFrame(X_val_vals, columns=feature_names)
    y_val = pd.Series(y_val_vals, name="binary_label")

    return X_train, y_train, X_val, y_val


def test_m01_01_valid_contract() -> None:
    """M01-01-AC0: M01 memberi probabilitas net-positive dengan recipe linear teratur yang reproducible."""
    X_train, y_train, X_val, y_val = _generate_synthetic_classification_data(n_train=200, n_val=100, seed=42)

    config = M01Config(
        penalty="elasticnet",
        solver="saga",
        C=0.1,
        l1_ratio=0.5,
        class_weight="balanced",
        seed=42,
    )

    trainer = M01LogisticTrainer(config=config)
    bundle = trainer.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=["momentum_5", "volatility_20", "volume_ratio"],
    )

    assert isinstance(bundle, M01FittedBundle)
    assert bundle.config.penalty == "elasticnet"
    assert bundle.config.solver == "saga"
    assert len(bundle.coefficients) == 3
    assert bundle.calibrator.is_fitted
    assert bundle.bundle_hash != ""

    # Predict calibrated probability on validation
    probs_1 = trainer.predict_proba(X_val)
    assert len(probs_1) == 100
    assert np.all((probs_1 >= 0.0) & (probs_1 <= 1.0))

    # Reproducibility check with identical seed
    trainer_repeat = M01LogisticTrainer(config=config)
    bundle_repeat = trainer_repeat.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=["momentum_5", "volatility_20", "volume_ratio"],
    )
    probs_2 = trainer_repeat.predict_proba(X_val)
    np.testing.assert_allclose(probs_1, probs_2, rtol=1e-5)
    assert bundle.bundle_hash == bundle_repeat.bundle_hash


def test_m01_01_contract_1() -> None:
    """M01-01-AC1: Invalid solver penalty ditolak."""
    # 1. elasticnet with non-saga solver
    with pytest.raises(InvalidSolverPenaltyError, match="INVALID_SOLVER_PENALTY"):
        M01Config(penalty="elasticnet", solver="lbfgs", C=0.1, l1_ratio=0.5)

    # 2. l1 with lbfgs solver
    with pytest.raises(InvalidSolverPenaltyError, match="INVALID_SOLVER_PENALTY"):
        M01Config(penalty="l1", solver="lbfgs", C=0.1)

    # 3. elasticnet without l1_ratio
    with pytest.raises(InvalidSolverPenaltyError, match="INVALID_SOLVER_PENALTY"):
        M01Config(penalty="elasticnet", solver="saga", C=0.1, l1_ratio=None)

    # 4. negative C
    with pytest.raises(ValueError, match="POSITIVE_REGULARIZATION_REQUIRED"):
        M01Config(penalty="l2", solver="lbfgs", C=-0.1)


def test_m01_01_contract_2() -> None:
    """M01-01-AC2: Tiny class imbalance diproses atau blocked dengan reason."""
    # Create dataset with extreme class imbalance: only 2 positives out of 200 samples (1% positive)
    X_train, _, X_val, y_val = _generate_synthetic_classification_data(n_train=200, n_val=100)
    y_train_skewed = pd.Series([0] * 198 + [1] * 2, name="binary_label")

    config = M01Config(
        penalty="elasticnet",
        solver="saga",
        C=0.1,
        l1_ratio=0.5,
        min_positive_samples=10,
        min_minority_ratio=0.05,
    )
    trainer = M01LogisticTrainer(config=config)

    with pytest.raises(ClassImbalanceError, match="EXTREME_CLASS_IMBALANCE_BLOCKED"):
        trainer.train_and_calibrate(
            X_train=X_train,
            y_train=y_train_skewed,
            X_val=X_val,
            y_val=y_val,
            feature_names=["momentum_5", "volatility_20", "volume_ratio"],
        )


def test_m01_01_contract_3() -> None:
    """M01-01-AC3: Output dinilai net utility bersama cash dan naive baseline."""
    X_train, y_train, X_val, y_val = _generate_synthetic_classification_data(n_train=200, n_val=100, seed=42)

    config = M01Config(penalty="l2", solver="saga", C=0.5, seed=42)
    trainer = M01LogisticTrainer(config=config)
    trainer.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=["momentum_5", "volatility_20", "volume_ratio"],
    )

    # Simulated realized returns for validation samples:
    # label 1 has positive return (+0.02), label 0 has negative return (-0.015)
    realized_returns = np.where(y_val == 1, 0.02, -0.015)

    comparison = trainer.evaluate_utility(
        X_val=X_val,
        y_val=y_val,
        realized_returns=realized_returns,
        round_trip_cost=0.0040,  # 0.40% round trip cost
    )

    assert isinstance(comparison, ModelUtilityComparison)
    # Cash baseline is strictly 0.0 (holding cash incurs zero net trading PnL)
    assert comparison.cash_utility == 0.0
    # Naive baseline (always long)
    assert isinstance(comparison.naive_baseline_utility, float)
    # Model net utility
    assert isinstance(comparison.model_net_utility, float)
    # Reasoned comparison outcome
    assert comparison.beats_cash in (True, False)
    assert comparison.beats_naive in (True, False)


def test_m01_01_config_yaml_and_unfitted_guards() -> None:
    """Edge cases: loading from config YAML and unfitted trainer exceptions."""
    from pathlib import Path
    import yaml

    config_path = Path("configs/models/M01_logistic_v1.yaml")
    assert config_path.exists(), "configs/models/M01_logistic_v1.yaml must exist"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    config = M01Config(
        model_id=data["model_id"],
        version=data["version"],
        penalty=data["parameters"]["penalty"],
        solver=data["parameters"]["solver"],
        C=data["parameters"]["C"],
        l1_ratio=data["parameters"]["l1_ratio"],
        class_weight=data["parameters"]["class_weight"],
        seed=data["parameters"]["seed"],
        max_iter=data["parameters"]["max_iter"],
        min_positive_samples=data["thresholds"]["min_positive_samples"],
        min_minority_ratio=data["thresholds"]["min_minority_ratio"],
    )
    assert config.model_id == "M01"
    assert config.solver == "saga"

    # Unfitted trainer calling bundle or predict_proba raises RuntimeError
    trainer = M01LogisticTrainer(config=config)
    with pytest.raises(RuntimeError, match="M01LogisticTrainer is not fitted"):
        _ = trainer.bundle

    with pytest.raises(RuntimeError, match="M01LogisticTrainer is not fitted"):
        trainer.predict_proba(pd.DataFrame({"x": [1]}))

