"""Foundation model provenance gate, license verification, and cutoff integrity (F01-01).

Guarantees:
1. F01-01-AC0: Verifies revision, license, checksum, release date, and cutoff before artifact usage.
2. F01-01-AC1: Unknown or lookahead training cutoff strictly blocks promotion beyond EXPLORATORY fail-closed.
3. F01-01-AC2: Raw bytes without matching SHA-256 checksum are rejected and never loaded into memory.
4. F01-01-AC3: Fake adapter provides reproducible offline weights for CI without external downloads.

`docs/specs/15-deep-learning-and-provenance.md` is authoritative: "Missing revision/hash/license
rejects load. Unknown cutoff can permit explicitly exploratory analysis but blocks promotion."
Every rejection therefore raises a typed error; the `REJECTED_*` members of
`FoundationArtifactStatus` are retained for report rendering and are never returned by
`verify_provenance`, which either returns VERIFIED/EXPLORATORY or raises.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


# ---------------------------------------------------------------------------
# Enums and Errors
# ---------------------------------------------------------------------------


class FoundationArtifactStatus(StrEnum):
    """Integrity and provenance status of an external foundation artifact."""

    VERIFIED = "verified"
    EXPLORATORY = "exploratory"
    REJECTED_CHECKSUM = "rejected_checksum"
    REJECTED_LICENSE = "rejected_license"


class ChecksumVerificationFailedError(ValueError):
    """Raised when the calculated sha256 checksum does not match expected provenance."""


class IncompatibleLicenseError(ValueError):
    """Raised when an external model has an unapproved, viral, or restrictive license."""


class UnknownCutoffBlockedError(ValueError):
    """Raised when attempting to promote a model whose training cutoff is unknown or violates causality."""


# ---------------------------------------------------------------------------
# Provenance Model
# ---------------------------------------------------------------------------


APPROVED_OPEN_LICENSES: frozenset[str] = frozenset(
    {
        "Apache-2.0",
        "MIT",
        "BSD-3-Clause",
        "BSD-2-Clause",
        "CC0-1.0",
        "ISC",
    }
)


class FoundationModelProvenance(BaseModel):
    """Immutable specification of origin and legal/causal bounds of an external model.

    Spec 15 requires that a missing revision, hash, or license rejects the load. These
    are therefore structural constraints of the model itself, so an un-loadable artifact
    cannot be represented at all rather than being discovered later at a call site.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model_name: str
    revision: str
    expected_sha256: str
    license_spdx: str
    release_date: datetime
    training_cutoff_date: datetime | None = None
    source_url: str | None = None

    @field_validator("release_date", "training_cutoff_date", mode="after")
    @classmethod
    def validate_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.utcoffset() != timedelta(0):
            raise ValueError("UTC_AWARE_DATETIME_REQUIRED")
        return v

    @field_validator("model_name", "revision", mode="after")
    @classmethod
    def validate_known_identity(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "IDENTITY_FIELD_REQUIRED: model_name and revision must be known, non-blank values"
            )
        return v

    @field_validator("expected_sha256", mode="after")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if len(v) != 64 or not set(v) <= _HEX_DIGITS:
            raise ValueError(
                "SHA256_DIGEST_REQUIRED: expected_sha256 must be a 64-character hexadecimal digest"
            )
        return v.lower()

    @model_validator(mode="after")
    def validate_release_and_cutoff_order(self) -> FoundationModelProvenance:
        if self.release_date > datetime.now(UTC):
            raise ValueError(
                "FUTURE_RELEASE_DATE_FORBIDDEN: release_date cannot be in the "
                "future for a loadable artifact"
            )
        if self.training_cutoff_date is not None and self.training_cutoff_date > self.release_date:
            raise ValueError(
                "CUTOFF_AFTER_RELEASE_FORBIDDEN: declared training cutoff cannot "
                "follow the release date"
            )
        return self


class VerificationResult(BaseModel):
    """Outcome of foundation model provenance and byte integrity check."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    status: FoundationArtifactStatus
    checksum_verified: bool
    license_approved: bool
    cutoff_verified: bool
    computed_sha256: str
    notes: str | None = None
    verified_at_utc: datetime


# ---------------------------------------------------------------------------
# Provenance Gate
# ---------------------------------------------------------------------------


class FoundationProvenanceGate:
    """Enforces provenance, license whitelist, checksum, and training cutoff checks."""

    def __init__(self, approved_licenses: frozenset[str] = APPROVED_OPEN_LICENSES) -> None:
        self.approved_licenses = approved_licenses

    def _require_approved_license(self, provenance: FoundationModelProvenance) -> None:
        """Fail closed unless the artifact license is on the approved open whitelist."""
        if provenance.license_spdx not in self.approved_licenses:
            raise IncompatibleLicenseError(
                f"INCOMPATIBLE_LICENSE: '{provenance.license_spdx}' is not in "
                f"approved open licenses "
                f"{sorted(self.approved_licenses)}"
            )

    def verify_provenance(
        self,
        provenance: FoundationModelProvenance,
        weight_bytes: bytes | None = None,
        weight_path: Path | None = None,
    ) -> VerificationResult:
        """Verify provenance metadata and raw byte checksum."""
        # 1. License check
        self._require_approved_license(provenance)

        # 2. Byte checksum check
        computed_sha = ""
        if weight_bytes is not None:
            computed_sha = hashlib.sha256(weight_bytes).hexdigest()
        elif weight_path is not None:
            h = hashlib.sha256()
            with open(weight_path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            computed_sha = h.hexdigest()
        else:
            raise ValueError("NO_WEIGHT_INPUT: Either weight_bytes or weight_path must be provided")

        if computed_sha.lower() != provenance.expected_sha256.lower():
            raise ChecksumVerificationFailedError(
                f"CHECKSUM_VERIFICATION_FAILED: Expected {provenance.expected_sha256}, calculated {computed_sha}"
            )

        # 3. Cutoff status evaluation
        if provenance.training_cutoff_date is None:
            # Artifact is allowed for offline exploratory research ONLY, cannot be marked VERIFIED
            return VerificationResult(
                status=FoundationArtifactStatus.EXPLORATORY,
                checksum_verified=True,
                license_approved=True,
                cutoff_verified=False,
                computed_sha256=computed_sha,
                notes="Unknown training cutoff; restricted to EXPLORATORY status",
                verified_at_utc=datetime.now(UTC),
            )

        return VerificationResult(
            status=FoundationArtifactStatus.VERIFIED,
            checksum_verified=True,
            license_approved=True,
            cutoff_verified=True,
            computed_sha256=computed_sha,
            notes="Provenance, license, checksum, and cutoff successfully verified",
            verified_at_utc=datetime.now(UTC),
        )

    def attempt_promotion(
        self,
        provenance: FoundationModelProvenance,
        test_start_date: datetime,
        verification: VerificationResult | None = None,
    ) -> None:
        """Attempt to promote external foundation model to benchmark or release qualification.

        Promotion is the only path past EXPLORATORY, so it re-derives every term of the
        F01-01 contract (`revision checksum license release and cutoff -> verified external
        artifact or EXPLORATORY`) instead of trusting the caller: the cutoff must be known
        and pre-test, the license must be on the whitelist, and the caller must present the
        `VerificationResult` produced by `verify_provenance` for these exact bytes. A
        caller-supplied, non-VERIFIED, absent or mismatched result cannot promote, and the
        promoted digest must match the declared `expected_sha256`.
        """
        if provenance.training_cutoff_date is None:
            raise UnknownCutoffBlockedError(
                "UNKNOWN_CUTOFF_BLOCKS_PROMOTION: Model has unknown training cutoff date; "
                "promotion beyond EXPLORATORY is strictly forbidden."
            )

        if provenance.training_cutoff_date >= test_start_date:
            raise UnknownCutoffBlockedError(
                f"CUTOFF_LOOKAHEAD_PROMOTION_BLOCKED: Model cutoff {provenance.training_cutoff_date.isoformat()} "
                f"reaches or exceeds test evaluation start {test_start_date.isoformat()}."
            )

        self._require_approved_license(provenance)

        if verification is None:
            raise UnknownCutoffBlockedError(
                "UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION: promotion requires the VerificationResult "
                "produced by verify_provenance for these exact bytes; none was supplied."
            )
        if verification.status is not FoundationArtifactStatus.VERIFIED:
            raise UnknownCutoffBlockedError(
                "UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION: promotion requires a "
                "VerificationResult with "
                f"status=verified, got status={verification.status.value!r}."
            )
        if not (
            verification.checksum_verified
            and verification.license_approved
            and verification.cutoff_verified
        ):
            raise UnknownCutoffBlockedError(
                "UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION: promotion requires checksum_verified, "
                "license_approved and cutoff_verified all true, got "
                f"checksum_verified={verification.checksum_verified}, "
                f"license_approved={verification.license_approved}, "
                f"cutoff_verified={verification.cutoff_verified}."
            )
        if verification.computed_sha256.lower() != provenance.expected_sha256.lower():
            raise UnknownCutoffBlockedError(
                "UNVERIFIED_ARTIFACT_BLOCKS_PROMOTION: supplied verification covers bytes "
                f"with digest {verification.computed_sha256}, but provenance declares "
                f"{provenance.expected_sha256}."
            )


# ---------------------------------------------------------------------------
# Fake Adapter for CI (F01-01-AC3)
# ---------------------------------------------------------------------------


class FakeFoundationModelAdapter:
    """Offline synthetic adapter supplying deterministic weights and provenance without HTTP."""

    def __init__(self, model_name: str = "fake-chronos-tabular") -> None:
        self.model_name = model_name

    def get_test_weights_and_provenance(self) -> tuple[bytes, FoundationModelProvenance]:
        """Produce synthetic reproducible weights and matching provenance metadata."""
        weights = f"OFFLINE_CI_WEIGHTS_{self.model_name}_STABLE_BYTES".encode()
        sha256_hash = hashlib.sha256(weights).hexdigest()

        provenance = FoundationModelProvenance(
            model_name=self.model_name,
            revision="v1.0.0-mock",
            expected_sha256=sha256_hash,
            license_spdx="Apache-2.0",
            release_date=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            training_cutoff_date=datetime(2023, 12, 1, 0, 0, tzinfo=UTC),
            source_url="internal://ci/fake_model_adapter",
        )
        return weights, provenance
