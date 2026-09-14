"""Portable model bundle serialization, checksum verification and replay (ML-04).

Guarantees:
1. ML-04-AC0: Trainer publishes complete bundle serializable to bytes; reload gives identical inference.
2. ML-04-AC1: Checksum mismatch on stored weights rejects load fail-closed.
3. ML-04-AC2: Missing calibration metadata blocks load with explicit diagnostic.
4. ML-04-AC3: Reloaded bundle enforces canonical feature order; predictions are equivalent.

Security note: No pickle deserialization of arbitrary external data. All persistence uses
JSON with explicit field validation; model weights are stored as plain float lists.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BundleChecksumMismatchError(ValueError):
    """Raised when the stored weights checksum does not match the recomputed checksum on load."""


class MissingCalibrationMetadataError(ValueError):
    """Raised when a bundle's calibration block is absent or missing required fields (a, b, method)."""


class BundleFeatureMismatchError(ValueError):
    """Raised when inference input is missing required features declared in the bundle."""


# ---------------------------------------------------------------------------
# Required calibration fields
# ---------------------------------------------------------------------------

_REQUIRED_CALIBRATION_FIELDS = {"method", "a", "b", "n_samples", "n_positives", "n_negatives", "segment_type"}


# ---------------------------------------------------------------------------
# PortableBundle — serializable, self-contained, replay-ready
# ---------------------------------------------------------------------------


class PortableBundle(BaseModel):
    """Immutable, serializable model bundle.

    Stores logistic weights (coefficients + intercept) and Platt calibration
    parameters as plain JSON-compatible data.  Supports:
    - Serialization to/from bytes (JSON, no pickle)
    - Checksum-guarded reload
    - Canonical feature ordering on inference
    - Equivalent replay predictions after round-trip
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_id: str
    version: str
    feature_names: list[str]
    # Logistic weights
    coefficients: list[float]
    intercept: float
    # Platt calibration parameters
    calibration: dict[str, Any]
    # Config snapshot (arbitrary JSON-serializable dict)
    config_snapshot: dict[str, Any]
    # Deterministic content hash (excludes wall-clock)
    bundle_hash: str
    # Weights checksum (SHA-256 of coefficients+intercept JSON for integrity guard)
    weights_checksum: str
    fitted_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_m01(cls, bundle: Any, trainer: Any) -> "PortableBundle":
        """Construct a PortableBundle from an M01FittedBundle and its fitted trainer.

        Args:
            bundle: An ``M01FittedBundle`` produced by ``M01LogisticTrainer.train_and_calibrate``.
            trainer: The ``M01LogisticTrainer`` instance that produced the bundle.

        Returns:
            A ``PortableBundle`` ready for serialization and replay.
        """
        coefs = bundle.coefficients  # list[float]
        intercept = bundle.intercept  # float
        feature_names = list(bundle.feature_names)

        # Compute weights checksum from raw weights JSON (deterministic)
        weights_payload = json.dumps(
            {"coefficients": coefs, "intercept": intercept},
            sort_keys=True,
        ).encode("utf-8")
        weights_checksum = hashlib.sha256(weights_payload).hexdigest()

        # Extract calibration metadata from the immutable artifact
        cal = bundle.calibrator
        calibration_dict: dict[str, Any] = {
            "method": cal.method,
            "a": cal.a,
            "b": cal.b,
            "segment_type": cal.segment_type,
            "n_samples": cal.n_samples,
            "n_positives": cal.n_positives,
            "n_negatives": cal.n_negatives,
        }

        config_snapshot = bundle.config.model_dump(mode="json")

        return cls(
            model_id=bundle.config.model_id,
            version=bundle.config.version,
            feature_names=feature_names,
            coefficients=coefs,
            intercept=intercept,
            calibration=calibration_dict,
            config_snapshot=config_snapshot,
            bundle_hash=bundle.bundle_hash,
            weights_checksum=weights_checksum,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialize bundle to UTF-8 JSON bytes for storage or transmission."""
        payload = self.model_dump(mode="json")
        # Ensure datetime is ISO string
        if isinstance(payload.get("fitted_at_utc"), datetime):
            payload["fitted_at_utc"] = payload["fitted_at_utc"].isoformat()
        return json.dumps(payload, sort_keys=True).encode("utf-8")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict calibrated positive-class probabilities.

        Feature order is enforced to match ``feature_names``. Missing features raise
        ``BundleFeatureMismatchError``.

        Args:
            X: Input feature DataFrame. May have columns in any order.

        Returns:
            1-D float64 array of calibrated probabilities, one per row.
        """
        missing = [f for f in self.feature_names if f not in X.columns]
        if missing:
            raise BundleFeatureMismatchError(
                f"MISSING_FEATURES: Input DataFrame is missing: {missing}"
            )

        # Enforce canonical order
        X_ordered = X[self.feature_names].to_numpy(dtype=np.float64)
        coefs = np.asarray(self.coefficients, dtype=np.float64)
        raw_scores = X_ordered @ coefs + self.intercept

        # Platt sigmoid: sigmoid(a * score + b)
        a = float(self.calibration["a"])
        b = float(self.calibration["b"])
        logits = np.clip(a * raw_scores + b, -50.0, 50.0)
        return 1.0 / (1.0 + np.exp(-logits))


# ---------------------------------------------------------------------------
# PortableBundleLoader — guarded deserialization
# ---------------------------------------------------------------------------


class PortableBundleLoader:
    """Loads and validates PortableBundle from JSON bytes.

    Guards:
    - Recomputes weights checksum and rejects mismatches (ML-04-AC1).
    - Verifies all required calibration fields are present (ML-04-AC2).
    """

    def load_from_bytes(self, data: bytes) -> PortableBundle:
        """Deserialize bytes into a verified PortableBundle.

        Args:
            data: UTF-8 JSON bytes as produced by ``PortableBundle.to_bytes()``.

        Returns:
            A validated ``PortableBundle`` ready for inference.

        Raises:
            MissingCalibrationMetadataError: If the ``calibration`` block is absent or
                missing any required field.
            BundleChecksumMismatchError: If the stored ``weights_checksum`` does not
                match the recomputed checksum from the weights in the payload.
        """
        payload: dict[str, Any] = json.loads(data.decode("utf-8"))

        # --- AC2: Validate calibration metadata first ---
        calibration = payload.get("calibration")
        if not calibration:
            raise MissingCalibrationMetadataError(
                "MISSING_CALIBRATION_METADATA: Bundle does not contain a 'calibration' block. "
                "Cannot reconstruct calibrated predictions without calibration parameters."
            )
        missing_cal_fields = _REQUIRED_CALIBRATION_FIELDS - set(calibration.keys())
        if missing_cal_fields:
            raise MissingCalibrationMetadataError(
                f"MISSING_CALIBRATION_FIELDS: Required calibration fields absent: {sorted(missing_cal_fields)}. "
                "Bundle integrity cannot be guaranteed without complete calibration metadata."
            )

        # --- AC1: Verify weights checksum ---
        stored_checksum: str = payload.get("weights_checksum", "")
        coefficients = payload.get("coefficients", [])
        intercept = payload.get("intercept", 0.0)

        weights_payload = json.dumps(
            {"coefficients": coefficients, "intercept": intercept},
            sort_keys=True,
        ).encode("utf-8")
        computed_checksum = hashlib.sha256(weights_payload).hexdigest()

        if stored_checksum != computed_checksum:
            raise BundleChecksumMismatchError(
                f"CHECKSUM_MISMATCH: Stored weights checksum '{stored_checksum[:16]}...' "
                f"does not match recomputed '{computed_checksum[:16]}...'. "
                "Bundle may have been corrupted or tampered with."
            )

        # --- Reconstruct PortableBundle ---
        # Parse fitted_at_utc if it's a string
        fitted_at_utc = payload.get("fitted_at_utc")
        if isinstance(fitted_at_utc, str):
            from datetime import timezone
            dt = datetime.fromisoformat(fitted_at_utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            payload["fitted_at_utc"] = dt

        return PortableBundle(**payload)
