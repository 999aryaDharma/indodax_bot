"""Tests for M04-01: Quantile risk regression.

RED tests written before implementation.

Contract: Registered return volatility or tail quantile target -> interval forecast.

AC boundaries:
- AC0: Fit returns interval forecast (lower and upper quantile bounds).
- AC1: Quantile crossing handled explicitly (lower <= upper enforced or raised explicitly).
- AC2: Out-of-sample coverage recorded (actual vs nominal).
- AC3: Tail target not used as input feature (causal leakage prevention).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.models.m04_quantile_risk import (
    M04Config,
    M04QuantileTrainer,
    QuantileCoverageReport,
    QuantileCrossingError,
    TailTargetLeakageError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_returns(n: int = 200, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.001, 0.01, size=n)


def _make_features(n: int = 200, n_features: int = 4, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = [f"feat_{i}" for i in range(n_features)]
    return pd.DataFrame(rng.standard_normal((n, n_features)), columns=cols)


# ---------------------------------------------------------------------------
# AC0: Fit returns interval forecast (lower, upper quantile bounds)
# ---------------------------------------------------------------------------

def test_m04_01_valid_contract():
    """M04-01-AC0: Train quantile regression; predict returns (lower, upper) interval."""
    feature_names = [f"feat_{i}" for i in range(4)]
    X = _make_features(n=200, n_features=4)
    X.columns = feature_names  # type: ignore[assignment]
    y = _make_returns(n=200)

    config = M04Config(
        model_id="M04",
        version="1.0.0",
        lower_quantile=0.10,
        upper_quantile=0.90,
        seed=42,
    )
    trainer = M04QuantileTrainer(config=config)
    bundle = trainer.train(
        X_train=X.iloc[:160],
        y_train=y[:160],
        feature_names=feature_names,
    )

    X_test = _make_features(n=40, n_features=4, seed=77)
    X_test.columns = feature_names  # type: ignore[assignment]

    lower, upper = trainer.predict_interval(X_test)

    assert len(lower) == 40
    assert len(upper) == 40
    assert bundle.config.model_id == "M04"
    assert bundle.feature_names == feature_names


# ---------------------------------------------------------------------------
# AC1: Quantile crossing handled explicitly
# ---------------------------------------------------------------------------

def test_m04_01_contract_1():
    """M04-01-AC1: Config with lower_quantile > upper_quantile raises QuantileCrossingError."""
    # Case A: Config validation detects crossing immediately
    with pytest.raises((QuantileCrossingError, ValueError)):
        M04Config(
            model_id="M04",
            version="1.0.0",
            lower_quantile=0.90,  # intentionally swapped (lower > upper)
            upper_quantile=0.10,
            seed=42,
        )

    # Case B: Valid config but predictions must have lower <= upper (by construction)
    feature_names = [f"feat_{i}" for i in range(4)]
    X = _make_features(n=200)
    X.columns = feature_names  # type: ignore[assignment]
    y = _make_returns(n=200)

    config = M04Config(model_id="M04", version="1.0.0", lower_quantile=0.10, upper_quantile=0.90, seed=42)
    trainer = M04QuantileTrainer(config=config)
    trainer.train(X.iloc[:160], y[:160], feature_names)

    X_test = _make_features(n=40, seed=99)
    X_test.columns = feature_names  # type: ignore[assignment]
    lower, upper = trainer.predict_interval(X_test)

    assert np.all(lower <= upper), "lower quantile must never exceed upper quantile in predictions"


# ---------------------------------------------------------------------------
# AC2: Out-of-sample coverage recorded
# ---------------------------------------------------------------------------

def test_m04_01_contract_2():
    """M04-01-AC2: evaluate_coverage records actual vs nominal coverage fraction."""
    feature_names = [f"feat_{i}" for i in range(4)]
    X = _make_features(n=200)
    X.columns = feature_names  # type: ignore[assignment]
    y = _make_returns(n=200)

    config = M04Config(model_id="M04", version="1.0.0", lower_quantile=0.10, upper_quantile=0.90, seed=42)
    trainer = M04QuantileTrainer(config=config)
    trainer.train(X.iloc[:160], y[:160], feature_names)

    X_val = _make_features(n=40, seed=55)
    X_val.columns = feature_names  # type: ignore[assignment]
    y_val = _make_returns(n=40, seed=55)

    report = trainer.evaluate_coverage(X_val, y_val)

    assert isinstance(report, QuantileCoverageReport)
    assert hasattr(report, "nominal_coverage")
    assert hasattr(report, "actual_coverage")
    assert 0.0 <= report.actual_coverage <= 1.0
    assert report.nominal_coverage == pytest.approx(0.80, abs=0.01)  # 0.90 - 0.10 = 0.80


@pytest.mark.parametrize(
    ("labels", "reason"),
    [
        (np.zeros(39), "COVERAGE_LABEL_COUNT_MISMATCH"),
        (np.zeros((40, 1)), "COVERAGE_LABELS_MUST_BE_1D"),
        (np.full(40, np.nan), "COVERAGE_LABELS_NON_FINITE"),
        (np.full(40, np.inf), "COVERAGE_LABELS_NON_FINITE"),
        (np.full(40, -np.inf), "COVERAGE_LABELS_NON_FINITE"),
    ],
)
def test_m04_01_ac2_rejects_invalid_coverage_labels(labels, reason: str) -> None:
    feature_names = [f"feat_{i}" for i in range(4)]
    X = _make_features(n=200, n_features=4)
    X.columns = feature_names  # type: ignore[assignment]
    trainer = M04QuantileTrainer(M04Config(n_estimators=10))
    trainer.train(X.iloc[:160], _make_returns(160), feature_names)
    X_val = X.iloc[160:]

    with pytest.raises(ValueError, match=reason):
        trainer.evaluate_coverage(X_val, labels)


def test_m04_01_bundle_identity_binds_fitted_state_and_training_data() -> None:
    feature_names = [f"feat_{i}" for i in range(4)]
    X = _make_features(n=200, n_features=4)
    X.columns = feature_names  # type: ignore[assignment]
    y = _make_returns(200)
    config = M04Config(n_estimators=10, seed=13)

    baseline = M04QuantileTrainer(config).train(X.iloc[:160], y[:160], feature_names)
    repeated = M04QuantileTrainer(config).train(X.iloc[:160], y[:160], feature_names)
    shifted = M04QuantileTrainer(config).train(X.iloc[:160], y[:160] + 100.0, feature_names)

    assert baseline.bundle_hash == repeated.bundle_hash
    assert baseline.training_data_hash == repeated.training_data_hash
    assert baseline.fitted_state_hash == repeated.fitted_state_hash
    assert baseline.training_data_hash != shifted.training_data_hash
    assert baseline.fitted_state_hash != shifted.fitted_state_hash
    assert baseline.bundle_hash != shifted.bundle_hash


# ---------------------------------------------------------------------------
# AC3: Tail target not used as input feature
# ---------------------------------------------------------------------------

def test_m04_01_contract_3():
    """M04-01-AC3: Passing tail target column as feature raises TailTargetLeakageError."""
    feature_names = [f"feat_{i}" for i in range(4)]
    # Attacker injects 'tail_target' as a feature column
    leaky_features = feature_names + ["tail_target"]

    config = M04Config(model_id="M04", version="1.0.0", lower_quantile=0.10, upper_quantile=0.90, seed=42)
    trainer = M04QuantileTrainer(config=config)

    X = _make_features(n=200, n_features=4)
    X.columns = feature_names  # type: ignore[assignment]
    y = _make_returns(n=200)
    # Fabricate leaky DataFrame with tail_target column
    X_leaky = X.copy()
    X_leaky["tail_target"] = np.abs(y)

    with pytest.raises(TailTargetLeakageError):
        trainer.train(X_leaky, y, feature_names=leaky_features)


# ---------------------------------------------------------------------------
# Edge case: Predict before training raises RuntimeError
# ---------------------------------------------------------------------------

def test_m04_01_not_fitted_error():
    """Edge case: predict_interval before train() raises RuntimeError."""
    config = M04Config(model_id="M04", version="1.0.0", lower_quantile=0.10, upper_quantile=0.90, seed=42)
    trainer = M04QuantileTrainer(config=config)
    X = _make_features(n=10)
    X.columns = [f"feat_{i}" for i in range(4)]  # type: ignore[assignment]

    with pytest.raises(RuntimeError):
        trainer.predict_interval(X)


# ---------------------------------------------------------------------------
# M04-01-AC3 regression: tail/target leakage guard must match the target family
# ---------------------------------------------------------------------------

def test_m04_01_ac3_target_family_leakage_columns_are_rejected() -> None:
    """M04-01-AC3: the leakage guard must catch derived spellings of a forbidden target.

    The previous guard used exact set membership, so only a literal ``target``/
    ``label``/``outcome`` column was refused. Every derived name a feature builder would
    realistically emit - ``fwd_target_vol``, ``target_vol``, ``label_win``,
    ``next_return``, ``forward_return``, ``realized_vol``, ``outcome_up`` - passed the
    guard and let the tail target back into the model's own inputs.
    """
    base_features = [f"feat_{i}" for i in range(4)]
    leaky_names = [
        "fwd_target_vol",
        "target_vol",
        "label_win",
        "next_return",
        "forward_return",
        "realized_vol",
        "outcome_up",
        "future_return_5m",
    ]
    X = _make_features(n=200, n_features=4, seed=42)
    X.columns = base_features  # type: ignore[assignment]
    y = pd.Series(np.random.default_rng(0).standard_normal(200), name="target")

    trainer = M04QuantileTrainer(
        config=M04Config(model_id="M04", version="1.0.0", lower_quantile=0.10, upper_quantile=0.90, seed=42)
    )

    for leaky in leaky_names:
        X_leaky = X.copy()
        X_leaky[leaky] = np.random.default_rng(1).standard_normal(len(X))
        with pytest.raises(TailTargetLeakageError, match="TAIL_TARGET_LEAKAGE"):
            trainer.train(X_leaky, y, feature_names=base_features + [leaky])


def test_m04_01_ac3_legitimate_market_features_are_still_accepted() -> None:
    """M04-01-AC3: broadening the guard must not refuse genuine risk features."""
    legit_features = ["volatility_20", "volume_ratio", "spread_bps", "depth_imbalance"]

    X = _make_features(n=200, n_features=4, seed=42)
    X.columns = legit_features  # type: ignore[assignment]
    y = pd.Series(np.random.default_rng(0).standard_normal(200), name="target")

    trainer = M04QuantileTrainer(
        config=M04Config(model_id="M04", version="1.0.0", lower_quantile=0.10, upper_quantile=0.90, seed=42)
    )
    bundle = trainer.train(X, y, feature_names=legit_features)
    assert bundle.feature_names == legit_features
