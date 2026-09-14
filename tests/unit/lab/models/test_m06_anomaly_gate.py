"""Tests for M06-01: Market anomaly risk gate.

RED tests written before implementation.

Contract: Train-only liquidity distribution -> anomaly score and abstain threshold.

AC boundaries:
- AC0: Train-only liquidity distribution produces anomaly score and abstain threshold.
- AC1: Threshold is fitted strictly on train data and does NOT fit future data.
- AC2: No anomaly target claims return direction (unsupervised risk gating only).
- AC3: Missing data is strictly distinguished from market anomalies (raises MissingDataDistinctFromAnomalyError).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.models.m06_anomaly_gate import (
    AnomalyDecision,
    DirectionalClaimForbiddenError,
    M06AnomalyGate,
    M06Config,
    M06FittedBundle,
    MissingDataDistinctFromAnomalyError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_liquidity_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "volume_base": rng.lognormal(mean=2.0, sigma=0.5, size=n),
            "spread_bps": rng.uniform(5.0, 30.0, size=n),
            "depth_idr": rng.lognormal(mean=15.0, sigma=0.4, size=n),
            "trade_count": rng.integers(10, 500, size=n),
        }
    )


# ---------------------------------------------------------------------------
# AC0: Train-only liquidity distribution -> anomaly score and abstain threshold
# ---------------------------------------------------------------------------

def test_m06_01_valid_contract():
    """M06-01-AC0: Train on liquidity features; evaluate returns AnomalyDecision with scores."""
    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    df_train = _make_liquidity_df(n=200, seed=42)

    config = M06Config(
        model_id="M06",
        version="1.0.0",
        contamination=0.05,
        seed=42,
    )
    gate = M06AnomalyGate(config=config)
    bundle = gate.train(df_train, feature_names=feature_names)

    assert isinstance(bundle, M06FittedBundle)
    assert bundle.config.model_id == "M06"
    assert bundle.anomaly_threshold is not None

    df_test = _make_liquidity_df(n=20, seed=99)
    decisions = gate.evaluate(df_test)

    assert len(decisions) == 20
    for d in decisions:
        assert isinstance(d, AnomalyDecision)
        assert hasattr(d, "anomaly_score")
        assert hasattr(d, "is_anomaly")
        assert d.action in ("PASS", "ABSTAIN")


# ---------------------------------------------------------------------------
# AC1: Threshold tidak fit future
# ---------------------------------------------------------------------------

def test_m06_01_contract_1():
    """M06-01-AC1: Threshold is frozen at train time; scoring future data does not alter threshold."""
    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    df_train = _make_liquidity_df(n=200, seed=42)

    config = M06Config(model_id="M06", version="1.0.0", contamination=0.05, seed=42)
    gate = M06AnomalyGate(config=config)
    bundle = gate.train(df_train, feature_names=feature_names)

    frozen_threshold = bundle.anomaly_threshold

    # Simulate future extreme crash/anomaly data
    df_future = _make_liquidity_df(n=50, seed=123)
    df_future["volume_base"] *= 100.0  # massive shock
    df_future["spread_bps"] *= 10.0

    # Evaluate future data
    gate.evaluate(df_future)

    # Threshold in bundle and gate must be strictly identical to train threshold
    assert gate.threshold == frozen_threshold
    assert gate.bundle.anomaly_threshold == frozen_threshold


# ---------------------------------------------------------------------------
# AC2: No anomaly target mengklaim arah return
# ---------------------------------------------------------------------------

def test_m06_01_contract_2():
    """M06-01-AC2: Anomaly gate is unsupervised risk gate; rejects directional return claims."""
    config = M06Config(model_id="M06", version="1.0.0")
    gate = M06AnomalyGate(config=config)

    # Attempting to claim directional forecast or passing return labels raises DirectionalClaimForbiddenError
    with pytest.raises(DirectionalClaimForbiddenError):
        gate.train(
            _make_liquidity_df(n=50),
            feature_names=["volume_base", "spread_bps", "depth_idr", "trade_count"],
            target_direction="BULLISH",  # Directional claim forbidden!
        )


# ---------------------------------------------------------------------------
# AC3: Missing data berbeda dari anomaly market
# ---------------------------------------------------------------------------

def test_m06_01_contract_3():
    """M06-01-AC3: Missing data is strictly rejected with MissingDataDistinctFromAnomalyError."""
    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    df_train = _make_liquidity_df(n=200, seed=42)

    config = M06Config(model_id="M06", version="1.0.0", contamination=0.05, seed=42)
    gate = M06AnomalyGate(config=config)
    gate.train(df_train, feature_names=feature_names)

    # Create input with missing values (NaNs)
    df_missing = _make_liquidity_df(n=20, seed=77)
    df_missing.loc[5, "spread_bps"] = np.nan

    # Must raise MissingDataDistinctFromAnomalyError instead of silently assigning anomaly score
    with pytest.raises(MissingDataDistinctFromAnomalyError):
        gate.evaluate(df_missing)
