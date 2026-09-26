"""Regression: M02-01 sealed partition guard must be robust (variants blocked)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.m02_xgboost import M02Config, M02XGBoostTrainer, SealedPartitionLeakageError


def _tiny_frames() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(7)
    cols = ["f0", "f1"]
    X_train = pd.DataFrame(rng.normal(size=(60, 2)), columns=cols)
    y_train = pd.Series(rng.integers(0, 2, size=60))
    X_val = pd.DataFrame(rng.normal(size=(60, 2)), columns=cols)
    y_val = pd.Series(rng.integers(0, 2, size=60))
    return X_train, y_train, X_val, y_val


@pytest.mark.parametrize(
    "partition",
    ["Sealed-Test", "sealed test", " SEALED_TEST ", "outer-test", "TEST", "sealed_test_extra", "Outer_Test"],
)
def test_m02_robust_partition_variants_blocked(partition: str) -> None:
    X_train, y_train, X_val, y_val = _tiny_frames()
    trainer = M02XGBoostTrainer(config=M02Config(n_estimators=5, early_stopping_rounds=2))
    with pytest.raises(SealedPartitionLeakageError, match="SEALED_PARTITION_LEAKAGE"):
        trainer.train_and_calibrate(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_names=["f0", "f1"],
            val_partition_type=partition,
        )
