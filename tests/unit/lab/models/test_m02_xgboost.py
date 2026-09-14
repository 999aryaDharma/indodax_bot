"""Unit tests for M02-01 XGBoost challenger model.

Acceptance Criteria:
- M02-01-AC0 (test_m02_01_valid_contract): M02 dibandingkan secara fair dengan linear dan classical pada outer folds yang sama.
- M02-01-AC1 (test_m02_01_contract_1): Early stop tidak melihat sealed labels.
- M02-01-AC2 (test_m02_01_contract_2): Finalist median dan worst tiga seed dicatat.
- M02-01-AC3 (test_m02_01_contract_3): Tree pipeline tetap menjaga feature order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.m01_logistic import M01Config, M01LogisticTrainer
from indodax_lab.models.m02_xgboost import (
    M02Config,
    M02FittedBundle,
    M02MultiSeedAudit,
    M02XGBoostTrainer,
    SealedPartitionLeakageError,
)
from indodax_lab.models.preprocessing import FeatureAlignmentError


def _generate_tabular_dataset(
    n_train: int = 300,
    n_val: int = 150,
    n_test: int = 150,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    feature_names = ["momentum_5", "volatility_20", "volume_ratio", "spread_ratio"]

    def _make_split(n: int) -> tuple[pd.DataFrame, pd.Series]:
        X_mat = rng.normal(0.0, 1.0, size=(n, 4))
        # Non-linear relationship suitable for tree models
        logits = (
            0.6 * X_mat[:, 0]
            - 0.4 * (X_mat[:, 1] ** 2)
            + 0.5 * (X_mat[:, 2] * X_mat[:, 3])
            + rng.normal(0.0, 0.2, size=n)
        )
        labels = (logits > np.median(logits)).astype(int)
        return pd.DataFrame(X_mat, columns=feature_names), pd.Series(labels, name="target")

    X_train, y_train = _make_split(n_train)
    X_val, y_val = _make_split(n_val)
    X_test, y_test = _make_split(n_test)
    return X_train, y_train, X_val, y_val, X_test, y_test


def test_m02_01_valid_contract() -> None:
    """M02-01-AC0: M02 dibandingkan secara fair dengan linear dan classical pada outer folds yang sama."""
    X_train, y_train, X_val, y_val, X_test, y_test = _generate_tabular_dataset(seed=42)
    feature_names = ["momentum_5", "volatility_20", "volume_ratio", "spread_ratio"]

    # 1. Fit M02 Challenger
    m02_config = M02Config(
        max_depth=3,
        n_estimators=100,
        learning_rate=0.05,
        early_stopping_rounds=10,
        seed=42,
    )
    m02_trainer = M02XGBoostTrainer(config=m02_config)
    m02_bundle = m02_trainer.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=feature_names,
    )

    assert isinstance(m02_bundle, M02FittedBundle)
    assert m02_bundle.best_iteration >= 0
    assert m02_bundle.calibrator.is_fitted
    assert len(m02_bundle.feature_names) == 4

    # 2. Fit M01 Baseline on identical train/val
    m01_config = M01Config(penalty="l2", solver="saga", C=0.5, seed=42)
    m01_trainer = M01LogisticTrainer(config=m01_config)
    m01_trainer.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=feature_names,
    )

    # 3. Fair comparison on identical outer test fold
    realized_test_returns = np.where(y_test == 1, 0.02, -0.015)
    round_trip_cost = 0.0040

    m02_utility = m02_trainer.evaluate_utility(
        X=X_test,
        realized_returns=realized_test_returns,
        round_trip_cost=round_trip_cost,
    )
    m01_utility = m01_trainer.evaluate_utility(
        X_val=X_test,
        y_val=y_test,
        realized_returns=realized_test_returns,
        round_trip_cost=round_trip_cost,
    )

    assert isinstance(m02_utility.model_net_utility, float)
    assert isinstance(m01_utility.model_net_utility, float)
    assert m02_utility.cash_utility == 0.0


def test_m02_01_contract_1() -> None:
    """M02-01-AC1: Early stop tidak melihat sealed labels."""
    X_train, y_train, X_val, y_val, _, _ = _generate_tabular_dataset()
    feature_names = ["momentum_5", "volatility_20", "volume_ratio", "spread_ratio"]
    config = M02Config(max_depth=3, n_estimators=50, early_stopping_rounds=5)
    trainer = M02XGBoostTrainer(config=config)

    # Invariant: Early stopping partition must NOT target sealed or test data
    with pytest.raises(SealedPartitionLeakageError, match="SEALED_PARTITION_LEAKAGE"):
        trainer.train_and_calibrate(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_names=feature_names,
            val_partition_type="sealed_test",
        )

    with pytest.raises(SealedPartitionLeakageError, match="SEALED_PARTITION_LEAKAGE"):
        trainer.train_and_calibrate(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_names=feature_names,
            val_partition_type="test",
        )

    # Valid inner validation partition succeeds
    bundle = trainer.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=feature_names,
        val_partition_type="inner_heldout",
    )
    assert bundle.best_iteration >= 0


def test_m02_01_contract_2() -> None:
    """M02-01-AC2: Finalist median dan worst tiga seed dicatat."""
    X_train, y_train, X_val, y_val, X_test, y_test = _generate_tabular_dataset()
    feature_names = ["momentum_5", "volatility_20", "volume_ratio", "spread_ratio"]
    realized_test_returns = np.where(y_test == 1, 0.02, -0.015)

    config = M02Config(max_depth=3, n_estimators=30, early_stopping_rounds=5)
    trainer = M02XGBoostTrainer(config=config)

    audit = trainer.audit_multi_seed(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_eval=X_test,
        realized_returns=realized_test_returns,
        feature_names=feature_names,
        seeds=[42, 43, 44],
        round_trip_cost=0.0040,
    )

    assert isinstance(audit, M02MultiSeedAudit)
    assert len(audit.seed_results) == 3
    assert audit.seeds == [42, 43, 44]
    assert audit.median_utility is not None
    assert audit.worst_utility is not None
    # Worst utility must be less than or equal to median utility
    assert audit.worst_utility <= audit.median_utility


def test_m02_01_contract_3() -> None:
    """M02-01-AC3: Tree pipeline tetap menjaga feature order."""
    X_train, y_train, X_val, y_val, X_test, _ = _generate_tabular_dataset()
    canonical_features = ["momentum_5", "volatility_20", "volume_ratio", "spread_ratio"]

    config = M02Config(max_depth=3, n_estimators=30, early_stopping_rounds=5, seed=42)
    trainer = M02XGBoostTrainer(config=config)
    bundle = trainer.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=canonical_features,
    )
    assert bundle.feature_names == canonical_features

    # 1. Predict with canonical order
    probs_canonical = trainer.predict_proba(X_test[canonical_features])

    # 2. Predict with reordered columns: pipeline must align to canonical order and produce identical predictions
    reordered_features = ["volume_ratio", "spread_ratio", "momentum_5", "volatility_20"]
    X_test_reordered = X_test[reordered_features]
    probs_reordered = trainer.predict_proba(X_test_reordered)
    np.testing.assert_allclose(probs_canonical, probs_reordered, rtol=1e-5)

    # 3. Missing required feature strictly rejected
    X_test_missing = X_test.drop(columns=["momentum_5"])
    with pytest.raises(FeatureAlignmentError, match="MISSING_FEATURES"):
        trainer.predict_proba(X_test_missing)


def test_m02_01_config_yaml_and_unfitted_guards() -> None:
    """Edge cases: loading from config YAML and unfitted trainer exceptions."""
    from pathlib import Path
    import yaml

    config_path = Path("configs/models/M02_xgboost_v1.yaml")
    assert config_path.exists(), "configs/models/M02_xgboost_v1.yaml must exist"

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    config = M02Config(
        model_id=data["model_id"],
        version=data["version"],
        max_depth=data["parameters"]["max_depth"],
        n_estimators=data["parameters"]["n_estimators"],
        learning_rate=data["parameters"]["learning_rate"],
        subsample=data["parameters"]["subsample"],
        colsample_bytree=data["parameters"]["colsample_bytree"],
        early_stopping_rounds=data["parameters"]["early_stopping_rounds"],
        eval_metric=data["parameters"]["eval_metric"],
        seed=data["parameters"]["seed"],
    )
    assert config.model_id == "M02"
    assert config.max_depth == 3

    # Unfitted trainer calling bundle or predict_proba raises RuntimeError
    trainer = M02XGBoostTrainer(config=config)
    with pytest.raises(RuntimeError, match="M02XGBoostTrainer is not fitted"):
        _ = trainer.bundle

    with pytest.raises(RuntimeError, match="M02XGBoostTrainer is not fitted"):
        trainer.predict_proba(pd.DataFrame({"x": [1]}))

