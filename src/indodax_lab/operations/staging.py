"""Staging, checksum verification, and atomic publishing (OPS-02).

Contract:
- manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.
- Partial transfer tidak mengganti aktif snapshot.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from indodax_lab.operations.backup import compute_sha256


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class ChecksumMismatchError(ValueError):
    """Raised when transferred file checksum does not match manifest."""


class CorruptTransferError(ValueError):
    """Raised when transfer bundle is incomplete or corrupted."""


class TransferManifest(BaseModel):
    """Transfer bundle metadata and cryptographic file hashes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str
    source_host: str
    created_at: datetime
    files: dict[str, str] = Field(default_factory=dict)
    total_bytes: int = 0

    @field_validator("created_at", mode="after")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")

    @model_validator(mode="after")
    def validate_members_and_hashes(self) -> "TransferManifest":
        _normalized_manifest_members(self.files)
        if self.total_bytes < 0:
            raise ValueError("TRANSFER_TOTAL_BYTES_NEGATIVE")
        for member, digest in self.files.items():
            if len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
                raise ValueError(f"TRANSFER_CHECKSUM_INVALID:{member}")
        return self


class StagingResult(BaseModel):
    """Outcome of verifying and publishing a staged transfer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    verified_file_count: int
    manifest: TransferManifest
    manifest_hash: str
    published_root: Path
    active_reference: Path


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _manifest_hash(manifest: TransferManifest) -> str:
    import hashlib

    return hashlib.sha256(_canonical_json_bytes(manifest.model_dump(mode="json"))).hexdigest()


def _canonical_member(raw: str) -> str:
    normalized = raw.replace("\\", "/")
    member = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or member.is_absolute()
        or any(part in ("", ".", "..") for part in member.parts)
        or any(":" in part for part in member.parts)
    ):
        raise CorruptTransferError(f"UNSAFE_MANIFEST_MEMBER:{raw}")
    return member.as_posix()


def _normalized_manifest_members(files: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw, digest in files.items():
        member = _canonical_member(raw)
        if member in normalized:
            raise CorruptTransferError(f"DUPLICATE_NORMALIZED_TARGET:{member}")
        normalized[member] = digest
    return normalized


def _reject_symlink_ancestors(path: Path, label: str) -> None:
    absolute = path.absolute()
    candidates = list(reversed(absolute.parents)) + [absolute]
    for candidate in candidates:
        if candidate.is_symlink() or (
            hasattr(candidate, "is_junction") and candidate.is_junction()
        ):
            raise CorruptTransferError(f"SYMLINK_{label}_FORBIDDEN:{candidate}")


def _safe_bundle_file(bundle_root: Path, member: str) -> Path:
    current = bundle_root
    for part in PurePosixPath(member).parts:
        current = current / part
        if current.is_symlink() or (
            hasattr(current, "is_junction") and current.is_junction()
        ):
            raise CorruptTransferError(f"SYMLINK_MEMBER_FORBIDDEN:{member}")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(bundle_root)
    except (FileNotFoundError, ValueError) as exc:
        raise CorruptTransferError(f"FILE_MISSING_OR_ESCAPE_FROM_BUNDLE:{member}") from exc
    if not resolved.is_file():
        raise CorruptTransferError(f"FILE_MISSING_FROM_BUNDLE:{member}")
    return resolved


def _copy_file_durable(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as source_stream, destination.open("xb") as destination_stream:
        shutil.copyfileobj(source_stream, destination_stream)
        destination_stream.flush()
        os.fsync(destination_stream.fileno())


def _fsync_directory(path: Path) -> None:
    """Persist directory entries where the platform exposes directory fsync."""
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_tree(root: Path) -> None:
    if os.name == "nt":
        return
    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        _fsync_directory(directory)
    _fsync_directory(root)


def load_transfer_manifest(bundle_dir: Path | str) -> TransferManifest:
    """Read and validate the transfer manifest from a bundle directory."""
    raw_bundle_dir = Path(bundle_dir)
    _reject_symlink_ancestors(raw_bundle_dir, "BUNDLE_ROOT")
    b_dir = raw_bundle_dir.resolve()
    manifest_file = b_dir / "transfer_manifest.json"
    if manifest_file.is_symlink() or (
        hasattr(manifest_file, "is_junction") and manifest_file.is_junction()
    ):
        raise CorruptTransferError(f"SYMLINK_MANIFEST_FORBIDDEN:{manifest_file}")
    if not manifest_file.is_file():
        raise CorruptTransferError(f"TRANSFER_MANIFEST_MISSING:{manifest_file}")

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        return TransferManifest.model_validate(data)
    except CorruptTransferError:
        raise
    except Exception as exc:
        raise CorruptTransferError(f"TRANSFER_MANIFEST_INVALID:{exc}") from exc


def verify_bundle(bundle_dir: Path | str) -> TransferManifest:
    """Verify cryptographic integrity of all files listed in manifest."""
    raw_bundle_dir = Path(bundle_dir)
    manifest = load_transfer_manifest(raw_bundle_dir)
    b_dir = raw_bundle_dir.resolve()
    members = _normalized_manifest_members(manifest.files)
    observed_total = 0

    for rel_path, expected_hash in members.items():
        file_path = _safe_bundle_file(b_dir, rel_path)

        actual_hash = compute_sha256(file_path)
        if actual_hash != expected_hash:
            raise ChecksumMismatchError(
                f"CHECKSUM_MISMATCH:{rel_path}: expected {expected_hash}, got {actual_hash}"
            )
        observed_total += file_path.stat().st_size

    if observed_total != manifest.total_bytes:
        raise CorruptTransferError(
            f"TOTAL_BYTES_MISMATCH: expected {manifest.total_bytes}, got {observed_total}"
        )

    return manifest


def stage_and_publish_transfer(
    bundle_dir: Path | str,
    destination_root: Path | str,
) -> StagingResult:
    """Verify bundle in staging and atomically publish files to destination.

    Crucial Invariant (OPS-02-AC1):
    If verification fails, destination_root is never modified or partially overwritten.
    """
    b_dir = Path(bundle_dir)
    raw_dest_root = Path(destination_root)

    # Step 1: Pre-flight integrity verification
    manifest = verify_bundle(b_dir)
    b_dir = b_dir.resolve()
    members = _normalized_manifest_members(manifest.files)
    manifest_hash = _manifest_hash(manifest)

    # Step 2: Build one immutable version, then atomically switch one active
    # reference. Readers never observe a mixture of old and new files.
    _reject_symlink_ancestors(raw_dest_root, "DESTINATION_ROOT")
    dest_root = raw_dest_root.resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    versions_root = dest_root / "versions"
    if versions_root.is_symlink() or (
        hasattr(versions_root, "is_junction") and versions_root.is_junction()
    ):
        raise CorruptTransferError(f"SYMLINK_VERSIONS_ROOT_FORBIDDEN:{versions_root}")
    versions_root.mkdir(exist_ok=True)
    final_version = versions_root / manifest_hash
    if final_version.is_symlink() or (
        hasattr(final_version, "is_junction") and final_version.is_junction()
    ):
        raise CorruptTransferError(f"IMMUTABLE_VERSION_TARGET_INVALID:{final_version}")
    if final_version.exists():
        if not final_version.is_dir():
            raise CorruptTransferError(f"IMMUTABLE_VERSION_TARGET_INVALID:{final_version}")
    else:
        temp_publish_dir = versions_root / f".staging-{manifest_hash}-{uuid.uuid4().hex}"
        temp_publish_dir.mkdir(parents=True, exist_ok=False)
        # Copy the complete verified snapshot and its manifest into one staging
        # directory. On failure it remains non-active as recovery evidence.
        for rel_path in members:
            source_file = _safe_bundle_file(b_dir, rel_path)
            staged_file = temp_publish_dir / rel_path
            _copy_file_durable(source_file, staged_file)
        _copy_file_durable(b_dir / "transfer_manifest.json", temp_publish_dir / "transfer_manifest.json")
        verify_bundle(temp_publish_dir)
        _fsync_tree(temp_publish_dir)
        try:
            os.replace(temp_publish_dir, final_version)
        except OSError:
            # A racing publisher may have installed the same immutable version.
            # Any other replace failure remains visible and non-active.
            if not final_version.is_dir():
                raise

    # Never trust a pre-existing/racing immutable target solely by its name.
    verify_bundle(final_version)
    _fsync_directory(versions_root)

    active_reference = dest_root / "active.json"
    if active_reference.is_symlink() or (
        hasattr(active_reference, "is_junction") and active_reference.is_junction()
    ):
        raise CorruptTransferError(f"SYMLINK_ACTIVE_REFERENCE_FORBIDDEN:{active_reference}")
    active_payload = {
        "bundle_id": manifest.bundle_id,
        "manifest_hash": manifest_hash,
        "relative_path": f"versions/{manifest_hash}",
    }
    temp_active = dest_root / f".active-{uuid.uuid4().hex}.tmp"
    with temp_active.open("xb") as active_stream:
        active_stream.write(_canonical_json_bytes(active_payload))
        active_stream.flush()
        os.fsync(active_stream.fileno())
    os.replace(temp_active, active_reference)
    _fsync_directory(dest_root)

    return StagingResult(
        status="SUCCESS",
        verified_file_count=len(manifest.files),
        manifest=manifest,
        manifest_hash=manifest_hash,
        published_root=final_version,
        active_reference=active_reference,
    )
