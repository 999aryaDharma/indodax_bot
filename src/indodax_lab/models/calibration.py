"""Held-out probability calibration for tabular and classifier models (ML-02).

Guarantees:
1. ML-02-AC1: Calibrator strictly requires inner held-out segment; train and test segments are forbidden.
2. ML-02-AC2: Calibration dataset too small or lacking minimum class representation blocks fail-closed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.optimize import minimize


class CalibrationSegmentError(ValueError):
    """Raised when an invalid or forbidden segment (e.g. train/test) is used for calibration."""


class InsufficientCalibrationDataError(ValueError):
    """Raised when the calibration dataset is too small or has insufficient class counts."""


class NotFittedError(RuntimeError):
    """Raised when predict_probability is invoked on an unfitted calibrator."""


class FittedCalibratorArtifact(BaseModel):
    """Immutable record of fitted calibration parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: str = "sigmoid"
    a: float
    b: float
    segment_type: str
    n_samples: int
    n_positives: int
    n_negatives: int
    fitted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HeldOutCalibrator:
    """Platt scaling sigmoid calibrator fitted strictly on inner held-out validation data."""

    FORBIDDEN_SEGMENTS = {
        "train",
        "training",
        "test",
        "sealed_test",
        "outer_test",
        "outer_val",
        "outer_validation",
    }

    VALID_SEGMENTS = {
        "inner_heldout",
        "inner_val",
        "inner_validation",
        "validation",
        "heldout",
    }

    def __init__(
        self,
        method: str = "sigmoid",
        min_calibration_samples: int = 50,
        min_positives: int = 10,
    ) -> None:
        self.method = method
        self.min_calibration_samples = min_calibration_samples
        self.min_positives = min_positives
        self._fitted_artifact: FittedCalibratorArtifact | None = None

    @property
    def is_fitted(self) -> bool:
        return self._fitted_artifact is not None

    @property
    def fitted_artifact(self) -> FittedCalibratorArtifact:
        if self._fitted_artifact is None:
            raise NotFittedError("HeldOutCalibrator is not fitted.")
        return self._fitted_artifact

    def fit(
        self,
        heldout_scores: Sequence[float],
        heldout_labels: Sequence[int | float],
        segment_type: str = "inner_heldout",
    ) -> FittedCalibratorArtifact:
        """Fit calibration mapping on inner held-out validation segment."""
        norm_segment = segment_type.strip().lower()

        if norm_segment in self.FORBIDDEN_SEGMENTS or norm_segment not in self.VALID_SEGMENTS:
            raise CalibrationSegmentError(
                f"CALIBRATOR_MUST_USE_INNER_HELDOUT_SEGMENT: segment '{segment_type}' is invalid or forbidden. "
                f"Allowed inner held-out segments: {sorted(self.VALID_SEGMENTS)}"
            )

        scores_arr = np.asarray(heldout_scores, dtype=np.float64)
        labels_arr = np.asarray(heldout_labels, dtype=np.float64)

        if len(scores_arr) != len(labels_arr):
            raise ValueError("LENGTH_MISMATCH: scores and labels must have the same length")

        n_samples = len(scores_arr)
        if n_samples < self.min_calibration_samples:
            raise InsufficientCalibrationDataError(
                f"CALIBRATION_DATASET_TOO_SMALL: sample count {n_samples} is below minimum {self.min_calibration_samples}"
            )

        n_positives = int(np.sum(labels_arr == 1.0))
        n_negatives = int(np.sum(labels_arr == 0.0))

        if n_positives < self.min_positives or n_negatives < self.min_positives:
            raise InsufficientCalibrationDataError(
                f"INSUFFICIENT_CLASS_REPRESENTATION: positives={n_positives}, negatives={n_negatives}, "
                f"each must be at least {self.min_positives}"
            )

        # Platt scaling targets with Bayesian smoothing to avoid divergence
        t_pos = (n_positives + 1.0) / (n_positives + 2.0)
        t_neg = 1.0 / (n_negatives + 2.0)
        target = np.where(labels_arr == 1.0, t_pos, t_neg)

        def _loss(params: np.ndarray) -> float:
            a, b = params[0], params[1]
            logits = np.clip(a * scores_arr + b, -50.0, 50.0)
            # Binary cross-entropy: log(1 + exp(logits)) - target * logits
            return float(np.sum(np.logaddexp(0.0, logits) - target * logits))

        res = minimize(_loss, x0=np.array([1.0, 0.0]), method="Nelder-Mead")
        a_fit, b_fit = float(res.x[0]), float(res.x[1])

        self._fitted_artifact = FittedCalibratorArtifact(
            method=self.method,
            a=a_fit,
            b=b_fit,
            segment_type=segment_type,
            n_samples=n_samples,
            n_positives=n_positives,
            n_negatives=n_negatives,
            fitted_at_utc=datetime.now(UTC),
        )
        return self._fitted_artifact

    def predict_probability(self, scores: Sequence[float]) -> np.ndarray:
        """Transform raw continuous model scores into well-calibrated posterior probabilities."""
        if self._fitted_artifact is None:
            raise NotFittedError("HeldOutCalibrator is not fitted.")

        scores_arr = np.asarray(scores, dtype=np.float64)
        logits = np.clip(self._fitted_artifact.a * scores_arr + self._fitted_artifact.b, -50.0, 50.0)
        return 1.0 / (1.0 + np.exp(-logits))
