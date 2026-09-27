"""Integration smoke tests and contract verification for D01-01 Tabular MLP baseline.

Acceptance Criteria:
- D01-01-AC0 (test_d01_01_valid_contract): MLP menguji manfaat nonlinearitas dengan fitur tabular yang sama seperti M01/M02 via common mapper.
- D01-01-AC1 (test_d01_01_contract_1): Same sample comparator dijaga, menolak mismatch sample fail-closed.
- D01-01-AC2 (test_d01_01_contract_2): Tiga finalist seed tidak cherry-pick dengan search budget <= 12 configs.
- D01-01-AC3 (test_d01_01_contract_3): Training interrupted dapat resume pada best checkpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from indodax_lab.models.dl.d01_mlp import (
    D01FinalistEvaluation,
    D01MLPConfig,
    D01MLPTrainer,
    D01MultiSeedEvaluator,
    SameSampleComparator,
    SampleComparatorMismatchError,
    SearchBudgetExceededError,
)
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
)
from indodax_lab.models.m01_logistic import M01Config, M01LogisticTrainer


def _generate_synthetic_tabular_data(
    n_train: int = 150,
    n_val: int = 60,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Generate reproducible synthetic tabular dataset identical in schema to M01/M02."""
    rng = np.random.default_rng(seed)
    feature_names = ["momentum_5", "volatility_20", "volume_ratio"]

    X_train_vals = rng.normal(0.0, 1.0, size=(n_train, 3))
    X_val_vals = rng.normal(0.0, 1.0, size=(n_val, 3))

    # Nonlinear target generation (X0 * X1 interaction + sinusoidal)
    logits_train = (
        X_train_vals[:, 0] * X_train_vals[:, 1]
        + np.sin(X_train_vals[:, 2] * 2.0)
        + rng.normal(0.0, 0.1, size=n_train)
    )
    y_train_vals = (logits_train > np.median(logits_train)).astype(int)

    logits_val = (
        X_val_vals[:, 0] * X_val_vals[:, 1]
        + np.sin(X_val_vals[:, 2] * 2.0)
        + rng.normal(0.0, 0.1, size=n_val)
    )
    y_val_vals = (logits_val > np.median(logits_val)).astype(int)

    X_train = pd.DataFrame(X_train_vals, columns=feature_names)
    y_train = pd.Series(y_train_vals, name="label")
    X_val = pd.DataFrame(X_val_vals, columns=feature_names)
    y_val = pd.Series(y_val_vals, name="label")

    return X_train, y_train, X_val, y_val


def test_d01_01_valid_contract() -> None:
    """D01-01-AC0: MLP menguji manfaat nonlinearitas dengan fitur tabular yang sama via common mapper."""
    X_train, y_train, X_val, y_val = _generate_synthetic_tabular_data()

    config = D01MLPConfig(
        hidden_dims=(32, 16),
        activation="relu",
        dropout=0.05,
        learning_rate=0.01,
        batch_size=32,
        max_epochs=15,
        patience=5,
        seed=42,
    )
    trainer = D01MLPTrainer(config=config)
    bundle = trainer.fit(X_train, y_train, X_val, y_val)

    assert bundle is not None
    assert bundle.best_epoch >= 0
    assert bundle.bundle_hash != ""
    assert bundle.input_dim == 3

    # Predict probabilities
    probs = trainer.predict_proba(X_val)
    assert len(probs) == len(X_val)
    assert np.all(probs >= 0.0) and np.all(probs <= 1.0)

    # Route through common CostAwareExecutionMapper
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    decisions = trainer.predict_forecasts(
        X_val,
        pair="BTC_IDR",
        decision_ts=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        mapper=mapper,
        desired_qty=Decimal("0.05"),
    )

    assert len(decisions) == len(X_val)
    for dec in decisions:
        assert dec.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)
        assert dec.net_edge is not None


def test_d01_01_contract_1() -> None:
    """D01-01-AC1: Same sample comparator dijaga, menolak mismatch sample fail-closed."""
    X_train, y_train, X_val, y_val = _generate_synthetic_tabular_data()

    # Train M01 baseline
    m01_config = M01Config(penalty="l2", solver="lbfgs", C=1.0, seed=42)
    m01_trainer = M01LogisticTrainer(config=m01_config)
    m01_trainer.train_and_calibrate(X_train, y_train, X_val, y_val, list(X_train.columns))

    # Train D01 MLP
    mlp_config = D01MLPConfig(hidden_dims=(16,), max_epochs=10, patience=4, seed=42)
    mlp_trainer = D01MLPTrainer(config=mlp_config)
    mlp_trainer.fit(X_train, y_train, X_val, y_val)

    comparator = SameSampleComparator()

    # 1. Valid identical samples: comparison succeeds
    rng = np.random.default_rng(42)
    realized_returns = rng.normal(0.002, 0.01, size=len(X_val))
    comp_result = comparator.compare(
        X_val=X_val,
        y_val=y_val,
        m01_trainer=m01_trainer,
        d01_trainer=mlp_trainer,
        realized_returns=realized_returns,
    )
    assert comp_result.sample_count == len(X_val)
    assert comp_result.m01_brier_score >= 0.0
    assert comp_result.d01_brier_score >= 0.0
    assert isinstance(comp_result.brier_improvement, float)

    # 2. Reject mismatched row count fail-closed
    X_val_mismatched = X_val.iloc[:-5]
    y_val_mismatched = y_val.iloc[:-5]
    with pytest.raises(SampleComparatorMismatchError, match="SAMPLE_COUNT_MISMATCH"):
        comparator.compare(
            X_val=X_val_mismatched,
            y_val=y_val,  # length mismatch
            m01_trainer=m01_trainer,
            d01_trainer=mlp_trainer,
        )

    # 3. Reject mismatched feature columns fail-closed
    X_val_wrong_cols = X_val.rename(columns={"momentum_5": "wrong_feature"})
    with pytest.raises(SampleComparatorMismatchError, match="FEATURE_COLUMNS_MISMATCH"):
        comparator.compare(
            X_val=X_val_wrong_cols,
            y_val=y_val,
            m01_trainer=m01_trainer,
            d01_trainer=mlp_trainer,
        )


def test_d01_01_contract_3_resume_restores_global_best(tmp_path: Path) -> None:
    """D01-01-AC3 (IMPORTANT): resume-from-latest restores best weights/epoch, not just best loss value.

    RED: latest checkpoint persists best_val_metric but best_weights=null and resume sets
    tracker.best_epoch to the latest epoch, so the post-resume model differs from the global best.
    """
    X_train, y_train, X_val, y_val = _generate_synthetic_tabular_data()

    config = D01MLPConfig(
        hidden_dims=(16,),
        learning_rate=0.05,
        batch_size=32,
        max_epochs=10,
        patience=7,
        seed=1,
    )

    # Uninterrupted reference run defines the global best.
    ref_trainer = D01MLPTrainer(config=config)
    ref_bundle = ref_trainer.fit(X_train, y_train, X_val, y_val)
    ref_probs = ref_trainer.predict_proba(X_val)

    # Guard: the best epoch must be interior so the interrupt can strictly follow it.
    assert ref_bundle.best_epoch + 2 < config.max_epochs
    interrupt_at = ref_bundle.best_epoch + 2

    checkpoint_dir = tmp_path / "checkpoints"
    first_trainer = D01MLPTrainer(config=config)
    first_trainer.fit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        checkpoint_dir=checkpoint_dir,
        interrupt_after_epoch=interrupt_at,
    )
    assert (checkpoint_dir / "latest_checkpoint.json").exists()

    resumed_trainer = D01MLPTrainer(config=config)
    resumed_bundle = resumed_trainer.fit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        checkpoint_dir=checkpoint_dir,
        resume_from=checkpoint_dir / "latest_checkpoint.json",
    )

    assert resumed_bundle.best_epoch == ref_bundle.best_epoch
    assert resumed_bundle.best_val_loss == pytest.approx(ref_bundle.best_val_loss)
    np.testing.assert_allclose(
        resumed_trainer.predict_proba(X_val), ref_probs, rtol=1e-5, atol=1e-6
    )


def test_d01_01_contract_1_rejects_divergent_features_and_index() -> None:
    """D01-01-AC1 (IMPORTANT): comparator asserts M01 vs D01 feature identity order-sensitively.

    RED: M01 trained on ['a','b'] vs D01 on ['a','b','c'] still compares OK, and shifted
    sample indexes compare OK.
    """
    X_train, y_train, X_val, y_val = _generate_synthetic_tabular_data()
    feature_names = list(X_train.columns)
    subset = feature_names[:2]

    # M01 on feature subset vs D01 on full features must fail-closed.
    m01_narrow = M01LogisticTrainer(config=M01Config(penalty="l2", solver="lbfgs", C=1.0, seed=42))
    m01_narrow.train_and_calibrate(X_train[subset], y_train, X_val[subset], y_val, subset)

    d01_full = D01MLPTrainer(config=D01MLPConfig(hidden_dims=(16,), max_epochs=10, patience=4, seed=42))
    d01_full.fit(X_train, y_train, X_val, y_val)

    comparator = SameSampleComparator()
    with pytest.raises(SampleComparatorMismatchError, match="FEATURE"):
        comparator.compare(
            X_val=X_val,
            y_val=y_val,
            m01_trainer=m01_narrow,
            d01_trainer=d01_full,
        )

    # Same feature set but different order must fail-closed order-sensitively.
    m01_reordered = M01LogisticTrainer(config=M01Config(penalty="l2", solver="lbfgs", C=1.0, seed=42))
    reversed_names = list(reversed(feature_names))
    m01_reordered.train_and_calibrate(
        X_train[reversed_names], y_train, X_val[reversed_names], y_val, reversed_names
    )
    with pytest.raises(SampleComparatorMismatchError, match="FEATURE"):
        comparator.compare(
            X_val=X_val,
            y_val=y_val,
            m01_trainer=m01_reordered,
            d01_trainer=d01_full,
        )

    # Shifted sample index identity must fail-closed.
    m01_full = M01LogisticTrainer(config=M01Config(penalty="l2", solver="lbfgs", C=1.0, seed=42))
    m01_full.train_and_calibrate(X_train, y_train, X_val, y_val, feature_names)
    X_val_reindexed = X_val.copy()
    X_val_reindexed.index = X_val.index + 1000
    with pytest.raises(SampleComparatorMismatchError, match="INDEX"):
        comparator.compare(
            X_val=X_val_reindexed,
            y_val=y_val,
            m01_trainer=m01_full,
            d01_trainer=d01_full,
        )


def test_d01_01_contract_2() -> None:
    """D01-01-AC2: Tiga finalist seed tidak cherry-pick dengan search budget <= 12 configs."""
    X_train, y_train, X_val, y_val = _generate_synthetic_tabular_data()

    evaluator = D01MultiSeedEvaluator()

    # 1. Search budget > 12 configs rejected fail-closed
    oversized_configs = [
        D01MLPConfig(hidden_dims=(16,), learning_rate=0.001 * (i + 1))
        for i in range(13)
    ]
    with pytest.raises(SearchBudgetExceededError, match="SEARCH_BUDGET_EXCEEDED"):
        evaluator.validate_search_budget(oversized_configs)

    # 2. Valid configs <= 12 passes budget check
    valid_configs = [
        D01MLPConfig(hidden_dims=(16,), learning_rate=0.01),
        D01MLPConfig(hidden_dims=(32, 16), learning_rate=0.005),
    ]
    assert evaluator.validate_search_budget(valid_configs) is True

    # 3. Evaluate 3 fixed finalist seeds (42, 43, 44) without cherry-picking
    fixed_seeds = (42, 43, 44)
    multi_eval = evaluator.evaluate_finalist_seeds(
        base_config=D01MLPConfig(hidden_dims=(16,), max_epochs=8, patience=3),
        seeds=fixed_seeds,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
    )

    assert len(multi_eval.seed_results) == 3
    assert set(multi_eval.seed_results.keys()) == set(fixed_seeds)
    assert multi_eval.val_loss_mean > 0.0
    assert multi_eval.val_loss_std >= 0.0
    assert multi_eval.is_cherry_picked is False


def test_d01_01_contract_3(tmp_path: Path) -> None:
    """D01-01-AC3: Training interrupted dapat resume pada best checkpoint."""
    X_train, y_train, X_val, y_val = _generate_synthetic_tabular_data()

    checkpoint_dir = tmp_path / "checkpoints"
    config = D01MLPConfig(
        hidden_dims=(16,),
        learning_rate=0.01,
        batch_size=32,
        max_epochs=10,
        patience=5,
        seed=42,
    )
    trainer = D01MLPTrainer(config=config)

    # Train first stage with interrupt simulation at epoch 3
    bundle_initial = trainer.fit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        checkpoint_dir=checkpoint_dir,
        interrupt_after_epoch=3,
    )
    assert (checkpoint_dir / "latest_checkpoint.json").exists()

    # Resume training from checkpoint
    trainer_resumed = D01MLPTrainer(config=config)
    bundle_resumed = trainer_resumed.fit(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        checkpoint_dir=checkpoint_dir,
        resume_from=checkpoint_dir / "latest_checkpoint.json",
    )

    assert bundle_resumed is not None
    assert bundle_resumed.best_epoch >= 0
    assert bundle_resumed.best_val_loss <= bundle_initial.best_val_loss
