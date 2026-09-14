"""Tests for M05-01: Meta-label signal filter.

RED tests written before implementation.

Contract: Automatic base-strategy decisions and outcomes -> TAKE/SKIP probability.

AC boundaries:
- AC0: Fit meta-model on base-strategy outcomes; predict returns TAKE/SKIP probability.
- AC1: Manual clicks/intent strictly rejected as labels (ManualLabelForbiddenError).
- AC2: Meta split purge base label overlap (temporal overlap between train and test purged).
- AC3: Compare base vs filtered performance on identical candidate trades (MetaFilterComparisonReport).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import numpy as np
import pandas as pd
import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.models.m05_meta_label import (
    M05Config,
    M05FittedBundle,
    M05MetaLabelTrainer,
    ManualLabelForbiddenError,
    MetaFilterComparisonReport,
    MetaTradeSample,
    purge_overlapping_trades,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_base_trades(n: int = 100, seed: int = 42) -> list[MetaTradeSample]:
    """Generate synthetic base-strategy trades."""
    rng = np.random.default_rng(seed)
    base_time = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    samples = []
    for i in range(n):
        entry_time = base_time + timedelta(hours=i * 2)
        exit_time = entry_time + timedelta(hours=2)
        ret = float(rng.normal(0.002, 0.02))
        label = 1 if ret > 0 else 0
        features = {
            "volatility": float(rng.uniform(0.01, 0.05)),
            "volume_z": float(rng.standard_normal()),
            "breakout_strength": float(rng.uniform(0.5, 2.0)),
        }
        samples.append(
            MetaTradeSample(
                trade_id=f"trade_{i}",
                entry_time=entry_time,
                exit_time=exit_time,
                features=features,
                realized_return=ret,
                label=label,
                is_manual=False,
            )
        )
    return samples


# ---------------------------------------------------------------------------
# AC0: Automatic base-strategy decisions and outcomes -> TAKE/SKIP probability
# ---------------------------------------------------------------------------

def test_m05_01_valid_contract():
    """M05-01-AC0: Train meta-label model; predict returns probability of TAKE in [0, 1]."""
    trades = _make_base_trades(n=100)
    config = M05Config(
        model_id="M05",
        version="1.0.0",
        take_threshold=0.55,
        n_estimators=30,
        max_depth=3,
        seed=42,
    )
    trainer = M05MetaLabelTrainer(config=config)
    bundle = trainer.train(trades[:80])

    assert isinstance(bundle, M05FittedBundle)
    assert bundle.config.model_id == "M05"

    test_trades = trades[80:]
    probabilities = trainer.predict_take_proba(test_trades)

    assert len(probabilities) == len(test_trades)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)


# ---------------------------------------------------------------------------
# AC1: Manual click tidak menjadi label
# ---------------------------------------------------------------------------

def test_m05_01_contract_1():
    """M05-01-AC1: Manual click or human intent rejected as training label."""
    trades = _make_base_trades(n=10)
    # Inject a manual click trade
    trades[3] = MetaTradeSample(
        trade_id="trade_manual_3",
        entry_time=trades[3].entry_time,
        exit_time=trades[3].exit_time,
        features=trades[3].features,
        realized_return=trades[3].realized_return,
        label=1,
        is_manual=True,  # Manual click!
    )

    config = M05Config(model_id="M05", version="1.0.0")
    trainer = M05MetaLabelTrainer(config=config)

    with pytest.raises(ManualLabelForbiddenError):
        trainer.train(trades)


# ---------------------------------------------------------------------------
# AC2: Meta split purge base label overlap
# ---------------------------------------------------------------------------

def test_m05_01_contract_2():
    """M05-01-AC2: Overlapping trades between train and test splits are purged."""
    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    # Train trade: spans t0 to t0 + 4h
    train_trade = MetaTradeSample(
        trade_id="train_1",
        entry_time=t0,
        exit_time=t0 + timedelta(hours=4),
        features={"vol": 0.01},
        realized_return=0.01,
        label=1,
    )
    # Test trade 1: enters at t0 + 2h (overlaps with train_1 exit at t0 + 4h)
    test_overlapping = MetaTradeSample(
        trade_id="test_overlap",
        entry_time=t0 + timedelta(hours=2),
        exit_time=t0 + timedelta(hours=6),
        features={"vol": 0.02},
        realized_return=0.02,
        label=1,
    )
    # Test trade 2: enters at t0 + 5h (strictly after train_1 exit)
    test_clean = MetaTradeSample(
        trade_id="test_clean",
        entry_time=t0 + timedelta(hours=5),
        exit_time=t0 + timedelta(hours=8),
        features={"vol": 0.015},
        realized_return=-0.005,
        label=0,
    )

    test_samples = [test_overlapping, test_clean]
    train_samples = [train_trade]

    purged_test = purge_overlapping_trades(
        reference_trades=train_samples,
        target_trades=test_samples,
    )

    # test_overlapping should be purged; only test_clean remains
    assert len(purged_test) == 1
    assert purged_test[0].trade_id == "test_clean"


# ---------------------------------------------------------------------------
# AC3: Compare base vs filtered pada same candidates
# ---------------------------------------------------------------------------

def test_m05_01_contract_3():
    """M05-01-AC3: compare_base_vs_filtered evaluates base and filtered strategy on same candidates."""
    trades = _make_base_trades(n=100)
    config = M05Config(
        model_id="M05",
        version="1.0.0",
        take_threshold=0.50,
        n_estimators=30,
        seed=42,
    )
    trainer = M05MetaLabelTrainer(config=config)
    trainer.train(trades[:70])

    candidates = trades[70:]
    report = trainer.compare_base_vs_filtered(candidates)

    assert isinstance(report, MetaFilterComparisonReport)
    assert report.total_candidates == len(candidates)
    assert report.filtered_trades_count <= report.base_trades_count
    assert hasattr(report, "base_win_rate")
    assert hasattr(report, "filtered_win_rate")
    assert hasattr(report, "base_mean_return")
    assert hasattr(report, "filtered_mean_return")
    assert report.base_trades_count == len(candidates)
