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

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    bundle_id: str
    git_commit_sha: str
    config_hash: str
    schema_hash: str
    candidate_id: str | None = None
    model_artifact_hash: str | None = None
    feature_schema_hash: str | None = None
    risk_policy_hash: str | None = None
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
    candidate_id: str | None = None,
    model_artifact_payload: str | bytes | None = None,
    feature_schema_payload: str | bytes | None = None,
    risk_policy_payload: str | bytes | None = None,
    packaged_at: datetime | None = None,
) -> ReleaseBundle:
    """Create a verified immutable release bundle."""
    cfg_hash = compute_sha256(config_payload)
    sch_hash = compute_sha256(schema_payload)
    model_hash = (
        compute_sha256(model_artifact_payload) if model_artifact_payload is not None else None
    )
    feat_hash = (
        compute_sha256(feature_schema_payload) if feature_schema_payload is not None else None
    )
    risk_hash = (
        compute_sha256(risk_policy_payload) if risk_policy_payload is not None else None
    )
    pack_time = packaged_at or datetime.now(UTC)

    # Compute bundle digest combining all integrity fields
    combined = (
        f"{bundle_id}:{git_commit_sha}:{cfg_hash}:{sch_hash}:"
        f"{candidate_id or ''}:{model_hash or ''}:{feat_hash or ''}:{risk_hash or ''}:"
        f"{pack_time.isoformat()}:{author}"
    )
    bundle_digest = compute_sha256(combined)

    return ReleaseBundle(
        bundle_id=bundle_id,
        git_commit_sha=git_commit_sha,
        config_hash=cfg_hash,
        schema_hash=sch_hash,
        candidate_id=candidate_id,
        model_artifact_hash=model_hash,
        feature_schema_hash=feat_hash,
        risk_policy_hash=risk_hash,
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
    expected_candidate_id: str | None = None,
    model_artifact_payload: str | bytes | None = None,
    feature_schema_payload: str | bytes | None = None,
    risk_policy_payload: str | bytes | None = None,
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

    if expected_candidate_id is not None and bundle.candidate_id != expected_candidate_id:
        raise ReleaseBundleIntegrityError(
            f"CANDIDATE_ID_MISMATCH: bundle={bundle.candidate_id} expected={expected_candidate_id}"
        )

    if model_artifact_payload is not None:
        expected_model_hash = compute_sha256(model_artifact_payload)
        if bundle.model_artifact_hash != expected_model_hash:
            raise ReleaseBundleIntegrityError(
                f"MODEL_ARTIFACT_HASH_MISMATCH: bundle={bundle.model_artifact_hash} "
                f"expected={expected_model_hash}"
            )

    if feature_schema_payload is not None:
        expected_feat_hash = compute_sha256(feature_schema_payload)
        if bundle.feature_schema_hash != expected_feat_hash:
            raise ReleaseBundleIntegrityError(
                f"FEATURE_SCHEMA_HASH_MISMATCH: bundle={bundle.feature_schema_hash} "
                f"expected={expected_feat_hash}"
            )

    if risk_policy_payload is not None:
        expected_risk_hash = compute_sha256(risk_policy_payload)
        if bundle.risk_policy_hash != expected_risk_hash:
            raise ReleaseBundleIntegrityError(
                f"RISK_POLICY_HASH_MISMATCH: bundle={bundle.risk_policy_hash} "
                f"expected={expected_risk_hash}"
            )

    # Re-verify internal bundle digest
    combined = (
        f"{bundle.bundle_id}:{bundle.git_commit_sha}:{bundle.config_hash}:{bundle.schema_hash}:"
        f"{bundle.candidate_id or ''}:{bundle.model_artifact_hash or ''}:"
        f"{bundle.feature_schema_hash or ''}:{bundle.risk_policy_hash or ''}:"
        f"{bundle.packaged_at_utc.isoformat()}:{bundle.author}"
    )
    if bundle.bundle_digest != compute_sha256(combined):
        raise ReleaseBundleIntegrityError("BUNDLE_DIGEST_CORRUPTED: Internal digest mismatch")

    return True
