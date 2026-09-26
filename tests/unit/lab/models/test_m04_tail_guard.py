"""Regression: M04-01 tail-target guard must be robust (variants blocked)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.m04_quantile_risk import M04Config, M04QuantileTrainer, TailTargetLeakageError


def _frames(n: int = 60) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(11)
    X = pd.DataFrame(rng.normal(size=(n, 2)), columns=["f0", "f1"])
    y = rng.normal(size=n)
    return X, y


@pytest.mark.parametrize(
    "leaky",
    ["my_target", "Tail-Target", "TAIL TARGET", "future_return", "Label", "REALIZED_RETURN", "y_true", "Outcome"],
)
def test_m04_tail_guard_variants_blocked(leaky: str) -> None:
    X, y = _frames()
    X_leaky = X.copy()
    X_leaky[leaky] = np.abs(y)
    trainer = M04QuantileTrainer(config=M04Config())
    with pytest.raises(TailTargetLeakageError):
        trainer.train(X_leaky, y, feature_names=["f0", "f1", leaky])
