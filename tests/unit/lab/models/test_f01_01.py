"""Unit tests for F01-01 Foundation provenance gate.

Guarantees:
1. F01-01-AC0: Loader memverifikasi asal, lisensi, checksum dan cutoff external model (test_f01_01_valid_contract).
2. F01-01-AC1: Unknown cutoff blocks promotion fail-closed (test_f01_01_contract_1).
3. F01-01-AC2: Unverified bytes tidak diload; mismatch checksum ditolak (test_f01_01_contract_2).
4. F01-01-AC3: CI memakai fake adapter tanpa unduh weights (test_f01_01_contract_3).

Independent-review regression coverage (2026-09 sprint review, see handoff evidence section):
5. Missing revision / non-digest hash rejects load
   (spec 15 "Missing revision/hash/license rejects load").
6. `attempt_promotion` re-derives license and byte verification instead of trusting the caller.
7. Release date must be historical and must not precede the declared training cutoff.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from indodax_lab.models.foundation.provenance import (
    ChecksumVerificationFailedError,
    FakeFoundationModelAdapter,
    FoundationArtifactStatus,
    FoundationModelProvenance,
    FoundationProvenanceGate,
    IncompatibleLicenseError,
    UnknownCutoffBlockedError,
    VerificationResult,
)


def _provenance(**overrides: object) -> FoundationModelProvenance:
    """Build a structurally valid provenance record; override fields per test."""
    weights = overrides.pop("weights", b"mock_foundation_weights_v1.0")
    fields: dict[str, object] = {
        "model_name": "chronos-t5-small",
        "revision": "v1.0.0",
        "expected_sha256": hashlib.sha256(weights).hexdigest(),
        "license_spdx": "Apache-2.0",
        "release_date": datetime(2024, 3, 1, 0, 0, tzinfo=UTC),
        "training_cutoff_date": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return FoundationModelProvenance(**fields)  # type: ignore[arg-type]


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


# ---------------------------------------------------------------------------
# Independent-review regression coverage
# ---------------------------------------------------------------------------


def test_f01_01_missing_revision_rejects_load() -> None:
    """Spec 15: a missing (blank) origin revision must reject the load, not return VERIFIED."""
    gate = FoundationProvenanceGate()
    weights = b"mock_foundation_weights_v1.0"

    with pytest.raises(ValidationError, match="IDENTITY_FIELD_REQUIRED"):
        _provenance(revision="   ", weights=weights)

    # And the gate must not be reachable with such a record at all.
    with pytest.raises(ValidationError, match="IDENTITY_FIELD_REQUIRED"):
        FoundationModelProvenance(
            model_name="chronos-t5-small",
            revision="",
            expected_sha256=hashlib.sha256(weights).hexdigest(),
            license_spdx="Apache-2.0",
            release_date=datetime(2024, 3, 1, 0, 0, tzinfo=UTC),
            training_cutoff_date=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        )
    assert gate.approved_licenses  # gate still constructed; no unverified record exists to verify


def test_f01_01_malformed_sha256_rejects_load() -> None:
    """Spec 15: a non-digest hash must reject the load instead of reaching a byte comparison."""
    with pytest.raises(ValidationError, match="SHA256_DIGEST_REQUIRED"):
        _provenance(expected_sha256="not-a-digest")

    with pytest.raises(ValidationError, match="SHA256_DIGEST_REQUIRED"):
        _provenance(expected_sha256="e3b0c44298fc1c14")


def test_f01_01_release_must_precede_cutoff_and_not_be_future() -> None:
    """A cutoff after release, or a future release date, must not be loadable as verified."""
    with pytest.raises(ValidationError, match="CUTOFF_AFTER_RELEASE_FORBIDDEN"):
        _provenance(training_cutoff_date=datetime(2025, 1, 1, 0, 0, tzinfo=UTC))

    with pytest.raises(ValidationError, match="FUTURE_RELEASE_DATE_FORBIDDEN"):
        _provenance(release_date=datetime.now(UTC) + timedelta(days=365))


def test_f01_01_promotion_rejects_unapproved_license() -> None:
    """Critical: promotion must re-derive the license gate, not trust the caller's result."""
    gate = FoundationProvenanceGate()
    weights = b"mock_foundation_weights_v1.0"
    proprietary = _provenance(
        license_spdx="LicenseRef-Proprietary-All-Rights-Reserved",
        weights=weights,
    )
    # Baseline behavior: the license gate lives only in verify_provenance, so an artifact that
    # was never verified (and could never be verified) still promotes here.
    with pytest.raises(IncompatibleLicenseError, match="INCOMPATIBLE_LICENSE"):
        gate.attempt_promotion(
            provenance=proprietary,
            test_start_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
        )

    # A caller-supplied result that claims everything is verified must still be refused.
    caller_supplied = VerificationResult(
        status=FoundationArtifactStatus.VERIFIED,
        checksum_verified=True,
        license_approved=True,
        cutoff_verified=True,
        computed_sha256=proprietary.expected_sha256,
        verified_at_utc=datetime(2024, 7, 1, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(IncompatibleLicenseError, match="INCOMPATIBLE_LICENSE"):
        gate.attempt_promotion(
            provenance=proprietary,
            test_start_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
            verification=caller_supplied,
        )


def test_f01_01_promotion_requires_verified_bytes() -> None:
    """Critical: promotion must require a VERIFIED result for the declared bytes."""
    gate = FoundationProvenanceGate()
    weights = b"mock_foundation_weights_v1.0"
    provenance = _provenance(weights=weights)

    # No verification evidence at all -> cannot promote (baseline promotes silently).
    with pytest.raises(UnknownCutoffBlockedError, match="UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION"):
        gate.attempt_promotion(
            provenance=provenance,
            test_start_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
        )

    exploratory = VerificationResult(
        status=FoundationArtifactStatus.EXPLORATORY,
        checksum_verified=True,
        license_approved=True,
        cutoff_verified=False,
        computed_sha256=provenance.expected_sha256,
        verified_at_utc=datetime(2024, 7, 1, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(UnknownCutoffBlockedError, match="UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION"):
        gate.attempt_promotion(
            provenance=provenance,
            test_start_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
            verification=exploratory,
        )

    other_digest = VerificationResult(
        status=FoundationArtifactStatus.VERIFIED,
        checksum_verified=True,
        license_approved=True,
        cutoff_verified=True,
        computed_sha256=hashlib.sha256(b"some other bytes").hexdigest(),
        verified_at_utc=datetime(2024, 7, 1, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(UnknownCutoffBlockedError, match="UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION"):
        gate.attempt_promotion(
            provenance=provenance,
            test_start_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
            verification=other_digest,
        )

    unverified_flags = VerificationResult(
        status=FoundationArtifactStatus.VERIFIED,
        checksum_verified=False,
        license_approved=True,
        cutoff_verified=True,
        computed_sha256=provenance.expected_sha256,
        verified_at_utc=datetime(2024, 7, 1, 0, 0, tzinfo=UTC),
    )
    with pytest.raises(UnknownCutoffBlockedError, match="UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION"):
        gate.attempt_promotion(
            provenance=provenance,
            test_start_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
            verification=unverified_flags,
        )


def test_f01_01_verified_artifact_promotes() -> None:
    """Positive path: a fully verified artifact still promotes (guard is not blanket-blocked)."""
    gate = FoundationProvenanceGate()
    weights = b"mock_foundation_weights_v1.0"
    provenance = _provenance(weights=weights)
    result = gate.verify_provenance(provenance=provenance, weight_bytes=weights)

    assert result.status is FoundationArtifactStatus.VERIFIED
    assert (
        gate.attempt_promotion(
            provenance=provenance,
            test_start_date=datetime(2024, 6, 1, 0, 0, tzinfo=UTC),
            verification=result,
        )
        is None
    )
