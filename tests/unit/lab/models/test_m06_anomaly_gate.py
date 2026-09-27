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


# ---------------------------------------------------------------------------
# M06-01 regression: absent feature columns and forward-return leakage
# ---------------------------------------------------------------------------

def test_m06_01_absent_feature_column_fails_closed_in_train() -> None:
    """M06-01-AC3: a missing feature column is missing data, not a raw pandas KeyError.

    ``X_train[feature_names]`` raised a bare ``KeyError: "['spread_bps'] not in index"``.
    That escapes the module's own typed error contract, so a caller that only handles
    ``MissingDataDistinctFromAnomalyError`` (the documented failure mode for incomplete
    data) would not catch it.
    """
    df_train = _make_liquidity_df(n=60, seed=42)
    gate = M06AnomalyGate(config=M06Config(contamination=0.1, n_estimators=20, seed=42))

    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    assert "spread_bps" in df_train.columns

    with pytest.raises(MissingDataDistinctFromAnomalyError, match="MISSING_FEATURE_COLUMNS"):
        gate.train(df_train.drop(columns=["spread_bps"]), feature_names=feature_names)


def test_m06_01_absent_feature_column_fails_closed_in_score() -> None:
    """M06-01: the same typed error must come out of the scoring path."""
    df_train = _make_liquidity_df(n=60, seed=42)
    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    gate = M06AnomalyGate(config=M06Config(contamination=0.1, n_estimators=20, seed=42))
    gate.train(df_train, feature_names=feature_names)

    df_eval = _make_liquidity_df(n=20, seed=77)
    with pytest.raises(MissingDataDistinctFromAnomalyError, match="MISSING_FEATURE_COLUMNS"):
        gate.score(df_eval.drop(columns=["spread_bps"]))


def test_m06_01_forward_return_feature_is_rejected() -> None:
    """M06-01-AC2: an unsupervised risk gate must not accept a directional target column.

    M06 is an unsupervised anomaly filter. Feeding it ``forward_return`` (or any other
    forward target) is exactly the directional claim AC2 forbids, but the name passed
    straight through to the IsolationForest.
    """
    df_train = _make_liquidity_df(n=60, seed=42)
    gate = M06AnomalyGate(config=M06Config(contamination=0.1, n_estimators=20, seed=42))

    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    with pytest.raises(DirectionalClaimForbiddenError, match="DIRECTIONAL_CLAIM_FORBIDDEN"):
        gate.train(df_train, feature_names=feature_names + ["forward_return"])


def test_m06_01_legitimate_liquidity_features_are_still_accepted() -> None:
    """M06-01: the leakage guard must not refuse the documented liquidity feature set."""
    df_train = _make_liquidity_df(n=60, seed=42)
    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    gate = M06AnomalyGate(config=M06Config(contamination=0.1, n_estimators=20, seed=42))
    bundle = gate.train(df_train, feature_names=feature_names)
    assert bundle.feature_names == feature_names


@pytest.mark.parametrize("sneaky", ["direction", "bull", "bear", "signal"])
def test_m06_01_directional_feature_name_rejected(sneaky: str) -> None:
    """M06-01-AC2 REGRESSION: bare directional words must be refused, not just compounds.

    The substring guard covered forward_return/target/label but a feature literally
    named ``direction`` (or bull/bear/signal) trained successfully, letting
    future-derived directional info into the fitted distribution.
    """
    df_train = _make_liquidity_df(n=60, seed=42)
    df_train[sneaky] = 1.0  # present so the name guard itself is exercised
    gate = M06AnomalyGate(config=M06Config(contamination=0.1, n_estimators=20, seed=42))

    feature_names = ["volume_base", "spread_bps", "depth_idr", "trade_count"]
    with pytest.raises(DirectionalClaimForbiddenError, match="DIRECTIONAL_CLAIM_FORBIDDEN"):
        gate.train(df_train, feature_names=feature_names + [sneaky])
