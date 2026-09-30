"""Immutable release bundle governance with cryptographic digest verification."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReleaseBundleIntegrityError(ValueError):
    """Raised when release bundle hashes do not match target environment or schemas."""


class ReleaseProvenanceError(ValueError):
    """Raised when candidate-bound release provenance is missing, mismatched, or inauthentic."""


_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


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


def digest_provenance_bytes(data: str | bytes) -> str:
    """SHA-256 content-integrity digest (tamper detection only, not a signature)."""
    return compute_sha256(data)


def _require_identity_payload(name: str, code: str, payload: str | bytes | None) -> bytes:
    """Reject blank/missing identity payloads fail-closed (PM-05-AC0)."""
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        raise ReleaseProvenanceError(
            f"{code}: required release identity {name!r} is missing or blank; "
            "refused instead of packaging an unverifiable release (PM-05-AC0)."
        )
    if isinstance(payload, bytes) and not payload:
        raise ReleaseProvenanceError(
            f"{code}: required release identity {name!r} is missing or blank; "
            "refused instead of packaging an unverifiable release (PM-05-AC0)."
        )
    return payload.encode("utf-8") if isinstance(payload, str) else payload


def _require_digest(name: str, code: str, value: str) -> str:
    """Reject blank/malformed digests fail-closed (PM-05-AC0)."""
    if not isinstance(value, str) or not _HEX64_RE.match(value):
        raise ReleaseProvenanceError(
            f"{code}: release identity {name!r} must be lowercase 64-hex SHA-256; "
            f"got {value!r} (PM-05-AC0)."
        )
    return value


class ProductionReleaseManifest(BaseModel):
    """Candidate-bound immutable production release manifest (PM-05).

    NOTE: ``manifest_digest`` is a content-integrity hash (SHA-256 over the
    canonical identity fields) for tamper detection and deterministic gating.
    It is not an asymmetric cryptographic signature. Authenticity claims
    require a detached signature verified against offline trust roots in
    ``indodax_lab.verification.release.verify_release``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    release_id: str
    candidate_ids: list[str]
    candidate_digests: dict[str, str]
    model_digest: str
    features_digest: str
    pipeline_digest: str
    risk_digest: str
    cost_digest: str
    execution_digest: str
    git_sha: str
    git_digest: str
    dependency_digest: str
    environment_digest: str
    allocation_policy_digest: str
    aggregate_evidence_digest: str
    qualification_refs: dict[str, str]
    pair_owner_map: dict[str, str]
    artifact_manifest: dict[str, str] = Field(default_factory=dict)
    packaged_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    author: str
    manifest_digest: str


def _production_digest_input(
    *,
    release_id: str,
    candidate_ids: list[str],
    candidate_digests: dict[str, str],
    model_digest: str,
    features_digest: str,
    pipeline_digest: str,
    risk_digest: str,
    cost_digest: str,
    execution_digest: str,
    git_sha: str,
    git_digest: str,
    dependency_digest: str,
    environment_digest: str,
    allocation_policy_digest: str,
    aggregate_evidence_digest: str,
    qualification_refs: dict[str, str],
    pair_owner_map: dict[str, str],
    artifact_manifest: dict[str, str],
    packaged_at_utc: datetime,
    author: str,
) -> str:
    parts = [
        release_id,
        ",".join(candidate_ids),
        ",".join(f"{cid}={candidate_digests[cid]}" for cid in candidate_ids),
        model_digest,
        features_digest,
        pipeline_digest,
        risk_digest,
        cost_digest,
        execution_digest,
        git_sha,
        git_digest,
        dependency_digest,
        environment_digest,
        allocation_policy_digest,
        aggregate_evidence_digest,
        ",".join(f"{cid}={qualification_refs[cid]}" for cid in candidate_ids),
        ",".join(f"{pair}={pair_owner_map[pair]}" for pair in sorted(pair_owner_map)),
        ",".join(f"{name}={artifact_manifest[name]}" for name in sorted(artifact_manifest)),
        packaged_at_utc.isoformat(),
        author,
    ]
    return ":".join(parts)


def create_production_release_manifest(
    *,
    release_id: str,
    candidate_digests: dict[str, str],
    model_payload: str | bytes | None,
    features_payload: str | bytes | None,
    pipeline_payload: str | bytes | None,
    risk_payload: str | bytes | None,
    cost_payload: str | bytes | None,
    execution_payload: str | bytes | None,
    git_sha: str,
    dependency_payload: str | bytes | None,
    environment_payload: str | bytes | None,
    allocation_policy_payload: str | bytes | None,
    aggregate_evidence_payload: str | bytes | None,
    qualification_refs: dict[str, str],
    pair_owner_map: dict[str, str],
    artifact_payloads: dict[str, str | bytes] | None = None,
    author: str,
    packaged_at: datetime | None = None,
) -> ProductionReleaseManifest:
    """Package an immutable candidate-bound production release manifest (PM-05).

    Every production identity field is required; legacy content-integrity
    bundles remain available through ``create_release_bundle`` unchanged.
    """
    if not isinstance(release_id, str) or not release_id.strip():
        raise ReleaseProvenanceError(
            "RELEASE_ID_MISSING: production release requires a nonempty release_id (PM-05-AC0)."
        )
    if not candidate_digests:
        raise ReleaseProvenanceError(
            "CANDIDATE_IDENTITY_MISSING: production release requires at least one "
            "candidate digest (PM-05-AC0)."
        )
    candidate_ids = sorted(candidate_digests)
    for cid in candidate_ids:
        if not isinstance(cid, str) or not cid.strip():
            raise ReleaseProvenanceError(
                f"CANDIDATE_IDENTITY_INVALID: candidate id {cid!r} must be nonempty (PM-05-AC0)."
            )
        _require_digest(f"candidate {cid}", "CANDIDATE_IDENTITY_INVALID", candidate_digests[cid])

    if set(qualification_refs) != set(candidate_ids) or any(
        not isinstance(ref, str) or not ref.strip() for ref in qualification_refs.values()
    ):
        raise ReleaseProvenanceError(
            "CANDIDATE_IDENTITY_MISMATCH: qualification_refs must cover every candidate id "
            f"{candidate_ids} with a nonempty ref; got {qualification_refs!r} (PM-05-AC0)."
        )

    model_digest = digest_provenance_bytes(
        _require_identity_payload("model artifact bytes", "MODEL_IDENTITY_MISSING", model_payload)
    )
    features_digest = digest_provenance_bytes(
        _require_identity_payload(
            "feature schema bytes", "SCHEMA_IDENTITY_MISSING", features_payload
        )
    )
    pipeline_digest = digest_provenance_bytes(
        _require_identity_payload(
            "pipeline graph bytes", "PIPELINE_IDENTITY_MISSING", pipeline_payload
        )
    )
    risk_digest = digest_provenance_bytes(
        _require_identity_payload("risk policy bytes", "POLICY_IDENTITY_MISSING", risk_payload)
    )
    cost_digest = digest_provenance_bytes(
        _require_identity_payload("cost policy bytes", "COST_IDENTITY_MISSING", cost_payload)
    )
    execution_digest = digest_provenance_bytes(
        _require_identity_payload(
            "execution policy bytes", "EXECUTION_IDENTITY_MISSING", execution_payload
        )
    )
    if not isinstance(git_sha, str) or not git_sha.strip():
        raise ReleaseProvenanceError(
            "GIT_IDENTITY_MISSING: production release requires a nonempty git_sha (PM-05-AC0)."
        )
    git_digest = digest_provenance_bytes(git_sha.strip())
    dependency_digest = digest_provenance_bytes(
        _require_identity_payload(
            "dependency lock bytes", "DEPENDENCY_IDENTITY_MISSING", dependency_payload
        )
    )
    environment_digest = digest_provenance_bytes(
        _require_identity_payload(
            "environment fingerprint bytes", "ENVIRONMENT_IDENTITY_MISSING", environment_payload
        )
    )
    allocation_policy_digest = digest_provenance_bytes(
        _require_identity_payload(
            "allocation policy bytes", "ALLOCATION_IDENTITY_MISSING", allocation_policy_payload
        )
    )
    aggregate_evidence_digest = digest_provenance_bytes(
        _require_identity_payload(
            "aggregate shared-capital evidence bytes",
            "AGGREGATE_EVIDENCE_MISSING",
            aggregate_evidence_payload,
        )
    )

    if not pair_owner_map:
        raise ReleaseProvenanceError(
            "PAIR_OWNER_MISSING: production release requires a nonempty pair_owner_map (PM-05-AC5)."
        )
    for pair, owner in pair_owner_map.items():
        if owner not in candidate_digests:
            raise ReleaseProvenanceError(
                f"PAIR_OWNER_UNKNOWN: pair {pair!r} is owned by unknown candidate {owner!r}; "
                "overlapping or unowned assignments reject the entire release (PM-05-AC5)."
            )
    owned = set(pair_owner_map.values())
    missing_owners = set(candidate_ids) - owned
    if missing_owners:
        raise ReleaseProvenanceError(
            f"PAIR_OWNER_MISSING: candidates {sorted(missing_owners)} own no pair; every "
            "release candidate must exclusively own at least one pair (PM-05-AC5)."
        )

    artifact_manifest: dict[str, str] = {}
    for name, payload in (artifact_payloads or {}).items():
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        artifact_manifest[name] = hashlib.sha256(raw).hexdigest()

    if not isinstance(author, str) or not author.strip():
        raise ReleaseProvenanceError("AUTHOR_MISSING: production release requires an author.")
    pack_time = packaged_at or datetime.now(UTC)

    manifest_digest = digest_provenance_bytes(
        _production_digest_input(
            release_id=release_id.strip(),
            candidate_ids=candidate_ids,
            candidate_digests={cid: candidate_digests[cid] for cid in candidate_ids},
            model_digest=model_digest,
            features_digest=features_digest,
            pipeline_digest=pipeline_digest,
            risk_digest=risk_digest,
            cost_digest=cost_digest,
            execution_digest=execution_digest,
            git_sha=git_sha.strip(),
            git_digest=git_digest,
            dependency_digest=dependency_digest,
            environment_digest=environment_digest,
            allocation_policy_digest=allocation_policy_digest,
            aggregate_evidence_digest=aggregate_evidence_digest,
            qualification_refs={cid: qualification_refs[cid] for cid in candidate_ids},
            pair_owner_map=dict(pair_owner_map),
            artifact_manifest=artifact_manifest,
            packaged_at_utc=pack_time,
            author=author.strip(),
        )
    )

    return ProductionReleaseManifest(
        release_id=release_id.strip(),
        candidate_ids=candidate_ids,
        candidate_digests={cid: candidate_digests[cid] for cid in candidate_ids},
        model_digest=model_digest,
        features_digest=features_digest,
        pipeline_digest=pipeline_digest,
        risk_digest=risk_digest,
        cost_digest=cost_digest,
        execution_digest=execution_digest,
        git_sha=git_sha.strip(),
        git_digest=git_digest,
        dependency_digest=dependency_digest,
        environment_digest=environment_digest,
        allocation_policy_digest=allocation_policy_digest,
        aggregate_evidence_digest=aggregate_evidence_digest,
        qualification_refs={cid: qualification_refs[cid] for cid in candidate_ids},
        pair_owner_map=dict(pair_owner_map),
        artifact_manifest=artifact_manifest,
        packaged_at_utc=pack_time,
        author=author.strip(),
        manifest_digest=manifest_digest,
    )


def verify_production_artifact_bytes(
    manifest: ProductionReleaseManifest,
    artifacts: dict[str, str | bytes],
) -> bool:
    """Verify referenced artifact bytes against the manifest (PM-05-AC1)."""
    expected_digest = digest_provenance_bytes(
        _production_digest_input(
            release_id=manifest.release_id,
            candidate_ids=list(manifest.candidate_ids),
            candidate_digests=dict(manifest.candidate_digests),
            model_digest=manifest.model_digest,
            features_digest=manifest.features_digest,
            pipeline_digest=manifest.pipeline_digest,
            risk_digest=manifest.risk_digest,
            cost_digest=manifest.cost_digest,
            execution_digest=manifest.execution_digest,
            git_sha=manifest.git_sha,
            git_digest=manifest.git_digest,
            dependency_digest=manifest.dependency_digest,
            environment_digest=manifest.environment_digest,
            allocation_policy_digest=manifest.allocation_policy_digest,
            aggregate_evidence_digest=manifest.aggregate_evidence_digest,
            qualification_refs=dict(manifest.qualification_refs),
            pair_owner_map=dict(manifest.pair_owner_map),
            artifact_manifest=dict(manifest.artifact_manifest),
            packaged_at_utc=manifest.packaged_at_utc,
            author=manifest.author,
        )
    )
    if manifest.manifest_digest != expected_digest:
        raise ReleaseProvenanceError(
            "MANIFEST_DIGEST_MISMATCH: manifest fields do not match the packaged "
            "manifest_digest; conflicting bytes under the same release identity "
            "reject fail-closed (PM-05-AC6)."
        )
    for filename, expected_checksum in manifest.artifact_manifest.items():
        if filename not in artifacts:
            raise ReleaseProvenanceError(
                f"ARTIFACT_MISSING: artifact {filename!r} referenced by release "
                f"{manifest.release_id!r} was not supplied (PM-05-AC1)."
            )
        payload = artifacts[filename]
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected_checksum:
            raise ReleaseProvenanceError(
                f"ARTIFACT_BYTES_MISMATCH: artifact {filename!r} bytes changed under the same "
                f"name (actual {actual}, expected {expected_checksum}); refused (PM-05-AC1)."
            )
    return True
