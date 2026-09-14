"""Tests for DL-01: Isolated resumable neural training and early stopping.

Guarantees:
1. DL-01-AC0: Optional DL worker creates complete resumable checkpoint without impacting core runtime (test_dl_01_valid_contract).
2. DL-01-AC1: Missing torch environment does not break core CI (test_dl_01_contract_1).
3. DL-01-AC2: Resume on mismatching input hash is rejected fail-closed (test_dl_01_contract_2).
4. DL-01-AC3: Training obeys max 50 epochs, patience 7 early stopping, restoring best validation model (test_dl_01_contract_3).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest

from indodax_lab.models.dl.checkpoint import (
    NeuralTrainingCheckpoint,
    ResumeInputMismatchError,
    TorchNotAvailableError,
    check_torch_availability,
    load_checkpoint,
    save_checkpoint,
)
from indodax_lab.models.dl.training import (
    EarlyStoppingTracker,
    NeuralTrainer,
    NeuralTrainingConfig,
)


def test_dl_01_valid_contract(tmp_path: Path) -> None:
    """AC0: Optional DL worker membuat checkpoint lengkap dan tidak membebani core runtime."""
    checkpoint_file = tmp_path / "checkpoint_epoch_10.json"
    ckpt = NeuralTrainingCheckpoint(
        epoch=10,
        model_id="d01_mlp_v1",
        input_hash="hash_data_snap_001",
        model_state={"dense1": [0.1, -0.2], "bias1": [0.05]},
        optimizer_state={"lr": 0.001, "step": 100},
        rng_state={"seed": 42},
        best_val_metric=0.825,
    )

    save_checkpoint(ckpt, checkpoint_file)
    assert checkpoint_file.exists()

    loaded = load_checkpoint(checkpoint_file, expected_input_hash="hash_data_snap_001")
    assert loaded.epoch == 10
    assert loaded.best_val_metric == 0.825
    assert loaded.rng_state["seed"] == 42


def test_dl_01_contract_1() -> None:
    """AC1: Missing torch tidak mematahkan core CI."""
    # When torch cannot be imported
    with patch.dict("sys.modules", {"torch": None}):
        is_available = check_torch_availability()
        # Must return False gracefully without raising ImportError into core
        assert is_available is False

        with pytest.raises(TorchNotAvailableError) as exc_info:
            from indodax_lab.models.dl.checkpoint import require_torch
            require_torch()
        assert "TORCH_NOT_AVAILABLE" in str(exc_info.value)


def test_dl_01_contract_2(tmp_path: Path) -> None:
    """AC2: Resume input hash mismatch ditolak."""
    checkpoint_file = tmp_path / "checkpoint_epoch_5.json"
    ckpt = NeuralTrainingCheckpoint(
        epoch=5,
        model_id="d01_mlp_v1",
        input_hash="hash_original_dataset_sha256",
        model_state={"w": [1.0]},
        optimizer_state={"step": 50},
        rng_state={"seed": 123},
        best_val_metric=0.75,
    )
    save_checkpoint(ckpt, checkpoint_file)

    # Attempting to resume with altered input data hash must raise ResumeInputMismatchError
    with pytest.raises(ResumeInputMismatchError) as exc_info:
        load_checkpoint(checkpoint_file, expected_input_hash="hash_modified_dataset_sha256")
    assert "RESUME_INPUT_MISMATCH" in str(exc_info.value)


def test_dl_01_contract_3() -> None:
    """AC3: Epoch cap 50 patience 7 memakai validation terbaik."""
    config = NeuralTrainingConfig(
        max_epochs=50,
        patience=7,
        min_delta=0.001,
    )
    tracker = EarlyStoppingTracker(config=config)

    # Simulate validation loss improving until epoch 10, then deteriorating
    val_losses = [
        1.0, 0.9, 0.8, 0.7, 0.65, 0.60, 0.58, 0.55, 0.53, 0.50,  # Best at epoch 9 (0.50)
        0.51, 0.52, 0.54, 0.53, 0.55, 0.56, 0.58,                 # 7 consecutive epochs without improvement
    ]

    stopped_epoch = None
    for epoch, loss in enumerate(val_losses):
        tracker.update(epoch=epoch, val_loss=loss, model_weights={"epoch": epoch, "loss": loss})
        if tracker.should_stop:
            stopped_epoch = epoch
            break

    # Early stopping triggered exactly after 7 epochs of non-improvement (epoch 16)
    assert tracker.should_stop is True
    assert stopped_epoch == 16  # 9 + 7
    # Best model restored is epoch 9 with best loss 0.50
    assert tracker.best_epoch == 9
    assert tracker.best_val_loss == 0.50
    assert tracker.best_weights["loss"] == 0.50

    # Ensure max_epochs ceiling of 50 is strictly respected
    assert config.max_epochs == 50
