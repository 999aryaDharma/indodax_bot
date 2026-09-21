"""Immutable release bundle governance with cryptographic digest verification."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleaseBundleIntegrityError(ValueError):
    """Raised when release bundle hashes do not match target environment or schemas."""


class ReleaseBundle(BaseModel):
    """Immutable release bundle certifying exact code, config, and schema hashes.

    NOTE: The bundle_digest is a content-integrity hash (SHA-256 over all constituent fields),
    designed for tamper detection and deterministic pipeline gating. It is not an asymmetric
    cryptographic signature.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str
    git_commit_sha: str
    config_hash: str
    schema_hash: str
    packaged_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    author: str
    bundle_digest: str


ContentIntegrityBundle = ReleaseBundle


def compute_sha256(data: str | bytes) -> str:
    """Deterministic SHA-256 hash helper."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def create_release_bundle(
    *,
    bundle_id: str,
    git_commit_sha: str,
    config_payload: str | bytes,
    schema_payload: str | bytes,
    author: str,
    packaged_at: datetime | None = None,
) -> ReleaseBundle:
    """Create a verified immutable release bundle."""
    cfg_hash = compute_sha256(config_payload)
    sch_hash = compute_sha256(schema_payload)
    pack_time = packaged_at or datetime.now(UTC)

    # Compute bundle digest combining all integrity fields
    combined = (
        f"{bundle_id}:{git_commit_sha}:{cfg_hash}:{sch_hash}:{pack_time.isoformat()}:{author}"
    )
    bundle_digest = compute_sha256(combined)

    return ReleaseBundle(
        bundle_id=bundle_id,
        git_commit_sha=git_commit_sha,
        config_hash=cfg_hash,
        schema_hash=sch_hash,
        packaged_at_utc=pack_time,
        author=author,
        bundle_digest=bundle_digest,
    )


def verify_release_bundle(
    bundle: ReleaseBundle,
    *,
    expected_git_sha: str,
    config_payload: str | bytes,
    schema_payload: str | bytes,
) -> bool:
    """Verify release bundle integrity against current runtime environment."""
    if bundle.git_commit_sha != expected_git_sha:
        raise ReleaseBundleIntegrityError(
            f"GIT_SHA_MISMATCH: bundle={bundle.git_commit_sha} expected={expected_git_sha}"
        )

    expected_cfg_hash = compute_sha256(config_payload)
    if bundle.config_hash != expected_cfg_hash:
        raise ReleaseBundleIntegrityError(
            f"CONFIG_HASH_MISMATCH: bundle={bundle.config_hash} expected={expected_cfg_hash}"
        )

    expected_sch_hash = compute_sha256(schema_payload)
    if bundle.schema_hash != expected_sch_hash:
        raise ReleaseBundleIntegrityError(
            f"SCHEMA_HASH_MISMATCH: bundle={bundle.schema_hash} expected={expected_sch_hash}"
        )

    # Re-verify internal bundle digest
    combined = (
        f"{bundle.bundle_id}:{bundle.git_commit_sha}:{bundle.config_hash}:"
        f"{bundle.schema_hash}:{bundle.packaged_at_utc.isoformat()}:{bundle.author}"
    )
    if bundle.bundle_digest != compute_sha256(combined):
        raise ReleaseBundleIntegrityError("BUNDLE_DIGEST_CORRUPTED")

    return True
