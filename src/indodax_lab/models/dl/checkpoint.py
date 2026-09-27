"""Checkpoint persistence, environment isolation, and input hash verification (DL-01).

Guarantees:
1. DL-01-AC0: Complete checkpoint serializes model, optimizer, scheduler, RNG, and metric state.
2. DL-01-AC1: Missing PyTorch environment fails cleanly without breaking non-DL core CI.
3. DL-01-AC2: Resuming checkpoint with mismatched input data hash is rejected fail-closed.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TorchNotAvailableError(ImportError):
    """Raised when an optional DL operation requires torch but torch is not installed."""


class ResumeInputMismatchError(ValueError):
    """Raised when attempting to resume a checkpoint whose input hash differs from current data."""


# ---------------------------------------------------------------------------
# Environment Isolation (DL-01-AC1)
# ---------------------------------------------------------------------------


def check_torch_availability() -> bool:
    """Check whether PyTorch is available in current python environment without raising."""
    if "torch" in sys.modules and sys.modules["torch"] is None:
        return False
    try:
        import torch  # type: ignore[import-not-found]
        return torch is not None
    except ImportError:
        return False


def require_torch() -> Any:
    """Import and return torch, or raise TorchNotAvailableError fail-closed."""
    if not check_torch_availability():
        raise TorchNotAvailableError(
            "TORCH_NOT_AVAILABLE: Optional PyTorch environment is not installed. "
            "Deep learning workers require torch>=2.0.0 (DL-01-AC1)."
        )
    import torch  # type: ignore[import-not-found]
    return torch


# ---------------------------------------------------------------------------
# Checkpoint Model & Persistence (DL-01-AC0, AC2)
# ---------------------------------------------------------------------------


class NeuralTrainingCheckpoint(BaseModel):
    """Immutable checkpoint containing complete model, optimizer, scheduler, and RNG state."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    epoch: int
    model_id: str
    input_hash: str
    model_state: dict[str, Any]
    optimizer_state: dict[str, Any]
    scheduler_state: dict[str, Any] | None = None
    rng_state: dict[str, Any]
    best_val_metric: float
    best_weights: dict[str, Any] | None = None
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


def save_checkpoint(checkpoint: NeuralTrainingCheckpoint, path: Path) -> None:
    """Save a checkpoint atomically to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = path.with_suffix(path.suffix + ".tmp")
    raw = checkpoint.model_dump_json(indent=2)
    tmp_file.write_text(raw, encoding="utf-8")
    tmp_file.replace(path)


def load_checkpoint(
    path: Path,
    expected_input_hash: str | None = None,
    *,
    allow_unverified: bool = False,
) -> NeuralTrainingCheckpoint:
    """Load and validate a training checkpoint from disk.

    Raises:
        ResumeInputMismatchError: If checkpoint's input hash differs from expected_input_hash,
            or if no expected hash is given without explicit allow_unverified=True opt-in (DL-01-AC2).
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)

    ckpt = NeuralTrainingCheckpoint(**data)

    if expected_input_hash is not None:
        if ckpt.input_hash != expected_input_hash:
            raise ResumeInputMismatchError(
                f"RESUME_INPUT_MISMATCH: Checkpoint input hash '{ckpt.input_hash}' does not match "
                f"current expected input hash '{expected_input_hash}'. Training cannot be resumed on altered data (DL-01-AC2)."
            )
    elif not allow_unverified:
        raise ResumeInputMismatchError(
            "RESUME_INPUT_UNVERIFIED: No expected_input_hash provided for checkpoint resume. "
            "Refusing fail-open resume; pass the current input dataset hash or acknowledge "
            "explicitly with allow_unverified=True (DL-01-AC2)."
        )

    return ckpt
