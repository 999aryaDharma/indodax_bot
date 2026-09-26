"""Unit tests for D03-01 ResNet LSTM challenger.

Guarantees:
1. D03-01-AC0: Residual temporal blocks + recurrent head memprediksi triple-barrier outcome via common mapper (test_d03_01_valid_contract).
2. D03-01-AC1: No bidirectional future leakage; bidirectional RNN ditolak fail-closed (test_d03_01_contract_1).
3. D03-01-AC2: Mask menjaga padded sequence; padding tidak merusak hidden state (test_d03_01_contract_2).
4. D03-01-AC3: Common evaluation cost dan folds digunakan (test_d03_01_contract_3).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.models.dl.d03_resnet_lstm import (
    BidirectionalLeakageError,
    ResNetLSTMConfig,
    ResNetLSTMModel,
    ResNetLSTMTrainer,
    ResNetLSTMComputeBudgetSummary,
)
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
)
from indodax_lab.labels.splits import (
    SampleRole,
    SplitPolicy,
    FoldWindow,
    assign_folds,
)


def _generate_synthetic_sequences(
    n_samples: int = 40,
    seq_len: int = 16,
    n_features: int = 4,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    inputs = rng.normal(0.0, 1.0, size=(n_samples, seq_len, n_features))
    masks = np.ones((n_samples, seq_len), dtype=bool)
    for i in range(n_samples // 3):
        pad_len = rng.integers(1, 5)
        masks[i, :pad_len] = False

    # Binary label representing triple-barrier upper hit (1.0) vs stop/timeout (0.0)
    targets = (rng.normal(0.0, 1.0, size=n_samples) > 0.0).astype(float)
    return inputs, masks, targets


def test_d03_01_valid_contract() -> None:
    """D03-01-AC0: Residual temporal blocks + recurrent head memprediksi triple-barrier outcome via common mapper."""
    inputs, masks, targets = _generate_synthetic_sequences()

    config = ResNetLSTMConfig(
        input_dim=4,
        conv_channels=(16, 16),
        lstm_hidden_dim=16,
        max_epochs=8,
        patience=4,
        seed=42,
    )
    trainer = ResNetLSTMTrainer(config=config)
    bundle = trainer.fit(
        train_inputs=inputs[:30],
        train_masks=masks[:30],
        train_targets=targets[:30],
        val_inputs=inputs[30:],
        val_masks=masks[30:],
        val_targets=targets[30:],
    )

    assert bundle is not None
    assert bundle.best_val_loss > 0.0
    assert bundle.total_parameters > 0

    probs = trainer.predict_proba(inputs[30:], masks[30:])
    assert len(probs) == 10
    assert np.all(probs >= 0.0) and np.all(probs <= 1.0)

    # Route through common CostAwareExecutionMapper
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    decisions = trainer.predict_forecasts(
        inputs=inputs[30:],
        masks=masks[30:],
        pair="BTC_IDR",
        decision_ts=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        mapper=mapper,
        desired_qty=Decimal("0.05"),
    )

    assert len(decisions) == 10
    for dec in decisions:
        assert dec.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)


def test_d03_01_contract_1() -> None:
    """D03-01-AC1: No bidirectional future leakage; bidirectional RNN ditolak fail-closed."""
    # Attempting to configure bidirectional RNN must be rejected fail-closed
    with pytest.raises(BidirectionalLeakageError, match="BIDIRECTIONAL_LEAKAGE_FORBIDDEN"):
        ResNetLSTMConfig(
            input_dim=4,
            bidirectional=True,  # Forbidden future lookahead!
        )


def test_d03_01_contract_2() -> None:
    """D03-01-AC2: Mask menjaga padded sequence; padding tidak merusak hidden state."""
    torch = pytest.importorskip("torch")

    config = ResNetLSTMConfig(
        input_dim=3,
        conv_channels=(8, 8),
        lstm_hidden_dim=8,
    )
    model = ResNetLSTMModel(config=config)
    model.eval()

    # Create sequence where first 5 steps are padded
    seq_len = 12
    x = torch.randn(1, seq_len, 3)
    mask = torch.ones(1, seq_len, dtype=torch.bool)
    mask[0, :5] = False  # Mask out first 5 steps

    # Alter the padded values arbitrarily (e.g. huge noise in padded region)
    x_tampered = x.clone()
    x_tampered[0, :5, :] += 999.0

    with torch.no_grad():
        out_clean = model(x, mask=mask)
        out_tampered = model(x_tampered, mask=mask)

    # Output with proper masking must ignore values in padded region
    diff = torch.max(torch.abs(out_clean - out_tampered)).item()
    assert diff < 1e-5, f"Padded inputs leaked into masked sequence output! Diff={diff}"


def test_d03_01_contract_3() -> None:
    """D03-01-AC3: Common evaluation cost dan folds digunakan."""
    inputs, masks, targets = _generate_synthetic_sequences(n_samples=20)

    config = ResNetLSTMConfig(
        input_dim=4,
        conv_channels=(8,),
        lstm_hidden_dim=8,
        max_epochs=4,
        patience=2,
    )
    trainer = ResNetLSTMTrainer(config=config)
    trainer.fit(
        train_inputs=inputs[:14],
        train_masks=masks[:14],
        train_targets=targets[:14],
        val_inputs=inputs[14:],
        val_masks=masks[14:],
        val_targets=targets[14:],
    )

    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    utility_comp = trainer.evaluate_cost_aware_utility(
        inputs=inputs[14:],
        masks=masks[14:],
        targets=targets[14:],
        mapper=mapper,
    )

    assert utility_comp.sample_count == 6
    assert isinstance(utility_comp.model_net_utility, float)
    assert utility_comp.cost_basis_evaluated == 0.0040


def test_d03_01_folds_evaluation() -> None:
    """REGRESSION: D03-01-AC3 evaluates on common folds using SPLIT-01 assign_folds.
    
    Folds should filter out PURGED/EMBARGOED samples and fail-closed on empty clean slice.
    """
    from datetime import timedelta
    inputs, masks, targets = _generate_synthetic_sequences(n_samples=30, seq_len=16, n_features=4, seed=42)
    
    config = ResNetLSTMConfig(
        input_dim=4,
        conv_channels=(8,),
        lstm_hidden_dim=8,
        max_epochs=3,
        patience=2,
    )
    trainer = ResNetLSTMTrainer(config=config)
    trainer.fit(
        train_inputs=inputs[:20],
        train_masks=masks[:20],
        train_targets=targets[:20],
        val_inputs=inputs[20:],
        val_masks=masks[20:],
        val_targets=targets[20:],
    )
    
    # Build SPLIT-01 policy with folds covering the test decision timestamps
    # Use smaller horizon so label_end_ts stays within fold
    base_ts = datetime(2025, 1, 12, 0, 0, tzinfo=UTC)
    policy = SplitPolicy(
        policy_id="test_policy_v1",
        version="1.0.0",
        max_horizon_hours=6,  # Smaller horizon so label_end_ts stays within fold
        embargo_hours=6,
        folds=[
            FoldWindow(role=SampleRole.TRAIN, start_ts=base_ts - timedelta(days=10), end_ts=base_ts),
            FoldWindow(role=SampleRole.VALIDATION, start_ts=base_ts, end_ts=base_ts + timedelta(days=5)),
        ],
    )
    
    # Build decision timestamps for test samples (last 10) - within VALIDATION fold
    test_inputs = inputs[20:]
    test_masks = masks[20:]
    test_targets = targets[20:]
    decision_ts_list = [base_ts + timedelta(hours=i) for i in range(len(test_inputs))]
    pairs = ["BTC_IDR"] * len(test_inputs)
    
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    
    # Should evaluate on clean folds only (VALIDATION fold)
    utility_comp = trainer.evaluate_on_common_folds(
        inputs=test_inputs,
        masks=test_masks,
        targets=test_targets,
        decision_ts_list=decision_ts_list,
        pairs=pairs,
        split_policy=policy,
        mapper=mapper,
    )
    
    assert utility_comp.sample_count > 0
    assert isinstance(utility_comp.model_net_utility, float)
    assert utility_comp.cost_basis_evaluated == 0.0040


def test_d03_01_compute_budget_logging() -> None:
    """REGRESSION: D03-01 bundle includes ResNetLSTMComputeBudgetSummary with params/FLOPs/channels.
    
    Mirrors D02 TCNComputeBudgetSummary and D04 ITransformerComputeBudgetSummary pattern.
    """
    inputs, masks, targets = _generate_synthetic_sequences(n_samples=20)
    
    config = ResNetLSTMConfig(
        input_dim=4,
        conv_channels=(16, 16),
        lstm_hidden_dim=16,
        max_epochs=2,
        patience=1,
    )
    trainer = ResNetLSTMTrainer(config=config)
    bundle = trainer.fit(
        train_inputs=inputs[:14],
        train_masks=masks[:14],
        train_targets=targets[:14],
        val_inputs=inputs[14:],
        val_masks=masks[14:],
        val_targets=targets[14:],
    )
    
    # Bundle should have compute_budget field
    assert hasattr(bundle, 'compute_budget'), "Bundle missing compute_budget field"
    budget = bundle.compute_budget
    assert budget.total_trainable_parameters > 0
    assert budget.estimated_flops_per_sequence > 0
    assert budget.num_conv_layers == 2
    assert budget.conv_channels == [16, 16]
    assert budget.kernel_size == 3
    assert budget.lstm_hidden_dim == 16
    assert budget.lstm_layers == 1
    assert budget.receptive_field > 0
