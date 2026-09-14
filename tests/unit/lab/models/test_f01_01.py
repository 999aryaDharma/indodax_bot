"""Unit tests for F01-01 Foundation provenance gate.

Guarantees:
1. F01-01-AC0: Loader memverifikasi asal, lisensi, checksum dan cutoff external model (test_f01_01_valid_contract).
2. F01-01-AC1: Unknown cutoff blocks promotion fail-closed (test_f01_01_contract_1).
3. F01-01-AC2: Unverified bytes tidak diload; mismatch checksum ditolak (test_f01_01_contract_2).
4. F01-01-AC3: CI memakai fake adapter tanpa unduh weights (test_f01_01_contract_3).
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import pytest

from indodax_lab.models.foundation.provenance import (
    ChecksumVerificationFailedError,
    FakeFoundationModelAdapter,
    FoundationArtifactStatus,
    FoundationModelProvenance,
    FoundationProvenanceGate,
    IncompatibleLicenseError,
    UnknownCutoffBlockedError,
)


def test_f01_01_valid_contract() -> None:
    """F01-01-AC0: Loader memverifikasi asal, lisensi, checksum dan cutoff external model."""
    dummy_weights = b"mock_foundation_weights_v1.0"
    computed_sha = hashlib.sha256(dummy_weights).hexdigest()

    provenance = FoundationModelProvenance(
        model_name="chronos-t5-small",
        revision="v1.0.0",
        expected_sha256=computed_sha,
        license_spdx="Apache-2.0",
        release_date=datetime(2024, 3, 1, 0, 0, tzinfo=UTC),
        training_cutoff_date=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
    )

    gate = FoundationProvenanceGate()
    result = gate.verify_provenance(provenance=provenance, weight_bytes=dummy_weights)

    assert result.status == FoundationArtifactStatus.VERIFIED
    assert result.checksum_verified is True
    assert result.license_approved is True
    assert result.cutoff_verified is True


def test_f01_01_contract_1() -> None:
    """F01-01-AC1: Unknown cutoff blocks promotion."""
    dummy_weights = b"mock_foundation_weights_exploratory"
    computed_sha = hashlib.sha256(dummy_weights).hexdigest()

    # Provenance with unknown training cutoff
    provenance_no_cutoff = FoundationModelProvenance(
        model_name="external-blackbox-model",
        revision="r12",
        expected_sha256=computed_sha,
        license_spdx="MIT",
        release_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
        training_cutoff_date=None,  # Unknown cutoff!
    )

    gate = FoundationProvenanceGate()
    result = gate.verify_provenance(provenance=provenance_no_cutoff, weight_bytes=dummy_weights)

    # Allowed only as EXPLORATORY
    assert result.status == FoundationArtifactStatus.EXPLORATORY

    # But promotion to benchmark or release candidate MUST be blocked fail-closed
    with pytest.raises(UnknownCutoffBlockedError, match="UNKNOWN_CUTOFF_BLOCKS_PROMOTION"):
        gate.attempt_promotion(
            provenance=provenance_no_cutoff,
            test_start_date=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        )


def test_f01_01_contract_2() -> None:
    """F01-01-AC2: Unverified bytes tidak diload; checksum mismatch ditolak fail-closed."""
    dummy_weights = b"corrupted_or_tampered_weights"
    expected_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    provenance = FoundationModelProvenance(
        model_name="time-gpt-small",
        revision="v0.1",
        expected_sha256=expected_sha,
        license_spdx="Apache-2.0",
        release_date=datetime(2024, 2, 1, 0, 0, tzinfo=UTC),
        training_cutoff_date=datetime(2023, 12, 31, 0, 0, tzinfo=UTC),
    )

    gate = FoundationProvenanceGate()

    with pytest.raises(ChecksumVerificationFailedError, match="CHECKSUM_VERIFICATION_FAILED"):
        gate.verify_provenance(provenance=provenance, weight_bytes=dummy_weights)


def test_f01_01_contract_3() -> None:
    """F01-01-AC3: CI memakai fake adapter tanpa unduh weights."""
    adapter = FakeFoundationModelAdapter(model_name="fake-t5-tabular")
    weights, provenance = adapter.get_test_weights_and_provenance()

    assert len(weights) > 0
    assert provenance.model_name == "fake-t5-tabular"
    assert provenance.license_spdx == "Apache-2.0"

    gate = FoundationProvenanceGate()
    result = gate.verify_provenance(provenance=provenance, weight_bytes=weights)
    assert result.status == FoundationArtifactStatus.VERIFIED
    assert result.checksum_verified is True
