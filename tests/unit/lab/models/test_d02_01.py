"""Unit tests for D02-01 Causal TCN baseline.

Guarantees:
1. D02-01-AC0: Causal dilated convolutions + mask-safe pooling menghasilkan multi-horizon forecast via common mapper (test_d02_01_valid_contract).
2. D02-01-AC1: Future token perturbation tidak mengubah output historis (test_d02_01_contract_1).
3. D02-01-AC2: Finite loss pada tiny fixture tanpa NaN/Inf (test_d02_01_contract_2).
4. D02-01-AC3: Parameter count dan compute budget tercatat lengkap dalam fitted bundle (test_d02_01_contract_3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import numpy as np
import pytest

from indodax_lab.models.dl.d02_tcn import (
    CausalTCNConfig,
    CausalTCNModel,
    CausalTCNTrainedBundle,
    CausalTCNTrainer,
)
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
)


def _generate_synthetic_sequences(
    n_samples: int = 40,
    seq_len: int = 16,
    n_features: int = 3,
    n_horizons: int = 3,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    inputs = rng.normal(0.0, 1.0, size=(n_samples, seq_len, n_features))
    # Create realistic masks (first few elements may be padded)
    masks = np.ones((n_samples, seq_len), dtype=bool)
    for i in range(n_samples // 4):
        pad_len = rng.integers(1, 4)
        masks[i, :pad_len] = False

    # Multi-horizon binary labels
    targets = rng.integers(0, 2, size=(n_samples, n_horizons)).astype(float)
    return inputs, masks, targets


def test_d02_01_valid_contract() -> None:
    """D02-01-AC0: Eksperimen D02-01 menghasilkan forecast yang tunduk pada evaluator bersama."""
    inputs, masks, targets = _generate_synthetic_sequences()

    config = CausalTCNConfig(
        input_dim=3,
        num_channels=(16, 16),
        kernel_size=3,
        dropout=0.05,
        horizons=(1, 4, 12),
        max_epochs=10,
        patience=4,
        seed=42,
    )
    trainer = CausalTCNTrainer(config=config)
    bundle = trainer.fit(
        train_inputs=inputs[:30],
        train_masks=masks[:30],
        train_targets=targets[:30],
        val_inputs=inputs[30:],
        val_masks=masks[30:],
        val_targets=targets[30:],
    )

    assert isinstance(bundle, CausalTCNTrainedBundle)
    assert bundle.total_parameters > 0
    assert bundle.best_val_loss > 0.0

    # Multi-horizon predictions
    preds = trainer.predict_proba(inputs[30:], masks[30:])
    assert preds.shape == (10, 3)  # 10 samples, 3 horizons
    assert np.all(preds >= 0.0) and np.all(preds <= 1.0)

    # Route primary horizon forecast through common CostAwareExecutionMapper
    cost_basis = CostBasis(estimated_round_trip_cost=0.0040, safety_margin=0.0015)
    mapper = CostAwareExecutionMapper(cost_basis=cost_basis)
    decisions = trainer.predict_forecasts_for_horizon(
        inputs=inputs[30:],
        masks=masks[30:],
        horizon_idx=0,
        pair="BTC_IDR",
        decision_ts=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        mapper=mapper,
        desired_qty=Decimal("0.05"),
    )

    assert len(decisions) == 10
    for dec in decisions:
        assert dec.action in (DecisionAction.INTENT, DecisionAction.ABSTAIN)


def test_d02_01_contract_1() -> None:
    """D02-01-AC1: Future token perturbation tidak mengubah output historis (Strict Causality)."""
    torch = pytest.importorskip("torch")

    config = CausalTCNConfig(
        input_dim=4,
        num_channels=(16, 16, 16),
        kernel_size=3,
        dilations=(1, 2, 4),
        horizons=(1,),
    )
    model = CausalTCNModel(config=config)
    model.eval()

    seq_len = 20
    tau = 10  # Historical cutoff step

    rng = np.random.default_rng(123)
    base_seq = rng.normal(0.0, 1.0, size=(1, seq_len, 4))
    perturbed_seq = base_seq.copy()
    # Heavily perturb the future steps (t > tau)
    perturbed_seq[:, tau + 1 :, :] += 1000.0

    with torch.no_grad():
        x_base = torch.tensor(base_seq, dtype=torch.float32)
        x_pert = torch.tensor(perturbed_seq, dtype=torch.float32)

        # Get sequence-level hidden representations at all timesteps
        rep_base = model.forward_sequence(x_base).numpy()
        rep_pert = model.forward_sequence(x_pert).numpy()

    # Representations for all t <= tau MUST BE IDENTICAL
    diff_historical = np.max(np.abs(rep_base[:, : tau + 1, :] - rep_pert[:, : tau + 1, :]))
    assert diff_historical < 1e-6, f"Future perturbation leaked into history! Diff={diff_historical}"


def test_d02_01_contract_2() -> None:
    """D02-01-AC2: Finite loss pada tiny fixture tanpa NaN/Inf."""
    inputs, masks, targets = _generate_synthetic_sequences(n_samples=20, seq_len=12)

    config = CausalTCNConfig(
        input_dim=3,
        num_channels=(8, 8),
        kernel_size=2,
        horizons=(1, 2, 3),
        max_epochs=5,
        patience=3,
    )
    trainer = CausalTCNTrainer(config=config)
    bundle = trainer.fit(
        train_inputs=inputs[:15],
        train_masks=masks[:15],
        train_targets=targets[:15],
        val_inputs=inputs[15:],
        val_masks=masks[15:],
        val_targets=targets[15:],
    )

    assert np.isfinite(bundle.best_val_loss)
    assert not np.isnan(bundle.best_val_loss)


def test_d02_01_contract_3() -> None:
    """D02-01-AC3: Parameter count dan compute budget tercatat lengkap."""
    config = CausalTCNConfig(
        input_dim=5,
        num_channels=(16, 32),
        kernel_size=3,
        dilations=(1, 2),
        horizons=(1, 4),
    )
    model = CausalTCNModel(config=config)
    summary = model.get_compute_budget_summary(seq_len=30)

    assert summary.total_trainable_parameters > 0
    assert summary.estimated_flops_per_sequence > 0
    assert len(summary.dilations) == 2
    assert summary.kernel_size == 3
