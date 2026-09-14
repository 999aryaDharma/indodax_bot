"""Tests for ML-04: Portable model bundles and replay.

RED tests written before implementation. Each test targets a specific acceptance criterion.
"""

from __future__ import annotations

import hashlib
import json
import numpy as np
import pandas as pd
import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.models.artifacts import (
    BundleChecksumMismatchError,
    MissingCalibrationMetadataError,
    PortableBundle,
    PortableBundleLoader,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_feature_df(n: int = 200, n_features: int = 5, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = [f"feat_{i}" for i in range(n_features)]
    return pd.DataFrame(rng.standard_normal((n, n_features)), columns=cols)


def _make_labels(n: int = 200, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.integers(0, 2, size=n, dtype=int))


def _build_portable_bundle(feature_names: list[str]) -> PortableBundle:
    """Helper: build a minimal PortableBundle for testing."""
    from indodax_lab.models.m01_logistic import M01Config, M01LogisticTrainer

    n = 300  # 240 train / 60 val — satisfies calibrator min_calibration_samples=50
    X = _make_feature_df(n=n, n_features=len(feature_names))
    X.columns = feature_names  # type: ignore[assignment]
    y = _make_labels(n=n)

    # Use first 240 rows for train, last 60 for val
    X_train, X_val = X.iloc[:240], X.iloc[240:]
    y_train, y_val = y.iloc[:240], y.iloc[240:]

    config = M01Config(
        model_id="M01",
        version="1.0.0",
        penalty="elasticnet",
        solver="saga",
        C=0.1,
        l1_ratio=0.5,
        class_weight="balanced",
        seed=42,
        max_iter=50,
    )
    trainer = M01LogisticTrainer(config=config)
    bundle = trainer.train_and_calibrate(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        feature_names=feature_names,
    )

    # Wrap as PortableBundle (using the trainer's fitted state)
    return PortableBundle.from_m01(bundle=bundle, trainer=trainer)


# ---------------------------------------------------------------------------
# AC0: Trainer publishes complete reloadable bundle; replay gives identical inference
# ---------------------------------------------------------------------------

def test_ml_04_valid_contract():
    """ML-04-AC0: Trainer publishes complete bundle; reload gives identical calibrated predictions."""
    feature_names = [f"feat_{i}" for i in range(5)]
    portable = _build_portable_bundle(feature_names)

    # Round-trip: serialize and reload
    raw_bytes = portable.to_bytes()
    loader = PortableBundleLoader()
    reloaded = loader.load_from_bytes(raw_bytes)

    # Inference on fixture data
    X_fixture = _make_feature_df(n=50, n_features=5, seed=99)
    X_fixture.columns = feature_names  # type: ignore[assignment]

    proba_original = portable.predict_proba(X_fixture)
    proba_reloaded = reloaded.predict_proba(X_fixture)

    # Must produce bit-exact or numerically identical predictions
    np.testing.assert_allclose(proba_original, proba_reloaded, rtol=1e-6, atol=1e-8,
                                err_msg="Reload must produce equivalent calibrated probabilities")
    assert proba_reloaded.shape == (50,), "Output shape must match fixture row count"


# ---------------------------------------------------------------------------
# AC1: Checksum weights mismatch rejects load
# ---------------------------------------------------------------------------

def test_ml_04_contract_1():
    """ML-04-AC1: Checksum mismatch on model weights causes BundleChecksumMismatchError."""
    feature_names = [f"feat_{i}" for i in range(5)]
    portable = _build_portable_bundle(feature_names)

    raw_bytes = portable.to_bytes()

    # Corrupt the raw bytes (flip a byte near the end of the payload)
    corrupted = bytearray(raw_bytes)
    # Find and tamper specifically with the weights section
    payload = json.loads(corrupted.decode("utf-8"))
    # Tamper with stored checksum to simulate mismatch
    payload["weights_checksum"] = "deadbeef" * 8  # wrong sha256 hex
    corrupted_bytes = json.dumps(payload).encode("utf-8")

    loader = PortableBundleLoader()
    with pytest.raises(BundleChecksumMismatchError):
        loader.load_from_bytes(corrupted_bytes)


# ---------------------------------------------------------------------------
# AC2: Missing calibration metadata blocks load
# ---------------------------------------------------------------------------

def test_ml_04_contract_2():
    """ML-04-AC2: Absent calibration metadata (a, b, method) blocks loading with explicit error."""
    feature_names = [f"feat_{i}" for i in range(5)]
    portable = _build_portable_bundle(feature_names)

    raw_bytes = portable.to_bytes()
    payload = json.loads(raw_bytes.decode("utf-8"))

    # Remove calibration block entirely
    payload.pop("calibration", None)
    missing_cal_bytes = json.dumps(payload).encode("utf-8")

    loader = PortableBundleLoader()
    with pytest.raises(MissingCalibrationMetadataError):
        loader.load_from_bytes(missing_cal_bytes)


# ---------------------------------------------------------------------------
# AC3: Reload gives equivalent predictions on fixture (canonical feature order)
# ---------------------------------------------------------------------------

def test_ml_04_contract_3():
    """ML-04-AC3: Reloaded bundle enforces canonical feature order and gives identical predictions."""
    feature_names = [f"feat_{i}" for i in range(6)]
    portable = _build_portable_bundle(feature_names)

    raw_bytes = portable.to_bytes()
    loader = PortableBundleLoader()
    reloaded = loader.load_from_bytes(raw_bytes)

    # Deliberately supply features in REVERSED order
    X_fixture = _make_feature_df(n=30, n_features=6, seed=77)
    X_fixture.columns = feature_names  # type: ignore[assignment]
    X_shuffled = X_fixture[list(reversed(feature_names))]  # wrong order

    proba_canonical = portable.predict_proba(X_fixture)
    proba_reordered = reloaded.predict_proba(X_shuffled)  # must reorder internally

    np.testing.assert_allclose(proba_canonical, proba_reordered, rtol=1e-6, atol=1e-8,
                                err_msg="Reloaded bundle must self-correct feature order on inference")


# ---------------------------------------------------------------------------
# Edge case: bundle hash matches feature_names contract
# ---------------------------------------------------------------------------

def test_ml_04_bundle_hash_includes_feature_names():
    """Edge case: Two bundles with different feature names have different bundle hashes."""
    names_a = [f"feat_{i}" for i in range(5)]
    names_b = [f"xfeat_{i}" for i in range(5)]

    bundle_a = _build_portable_bundle(names_a)
    bundle_b = _build_portable_bundle(names_b)

    assert bundle_a.bundle_hash != bundle_b.bundle_hash, (
        "Bundles with different feature names must produce different hashes"
    )
