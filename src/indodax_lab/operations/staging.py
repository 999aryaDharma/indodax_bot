"""Staging, checksum verification, and atomic publishing (OPS-02).

Contract:
- manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.
- Partial transfer tidak mengganti aktif snapshot.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class StagingResult(BaseModel):
    """Outcome of verifying and publishing a staged transfer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    verified_file_count: int
    manifest: TransferManifest


def load_transfer_manifest(bundle_dir: Path | str) -> TransferManifest:
    """Read and validate the transfer manifest from a bundle directory."""
    b_dir = Path(bundle_dir)
    manifest_file = b_dir / "transfer_manifest.json"
    if not manifest_file.exists():
        raise CorruptTransferError(f"TRANSFER_MANIFEST_MISSING:{manifest_file}")

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        return TransferManifest(
            bundle_id=data["bundle_id"],
            source_host=data["source_host"],
            created_at=datetime.fromisoformat(data["created_at"]),
            files=data["files"],
            total_bytes=data["total_bytes"],
        )
    except Exception as exc:
        raise CorruptTransferError(f"TRANSFER_MANIFEST_INVALID:{exc}") from exc


def verify_bundle(bundle_dir: Path | str) -> TransferManifest:
    """Verify cryptographic integrity of all files listed in manifest."""
    b_dir = Path(bundle_dir)
    manifest = load_transfer_manifest(b_dir)

    for rel_path, expected_hash in manifest.files.items():
        file_path = b_dir / rel_path
        if not file_path.exists():
            raise CorruptTransferError(f"FILE_MISSING_FROM_BUNDLE:{rel_path}")

        actual_hash = compute_sha256(file_path)
        if actual_hash != expected_hash:
            raise ChecksumMismatchError(
                f"CHECKSUM_MISMATCH:{rel_path}: expected {expected_hash}, got {actual_hash}"
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
    dest_root = Path(destination_root)

    # Step 1: Pre-flight integrity verification
    manifest = verify_bundle(b_dir)

    # Step 2: Atomic publishing into destination_root
    dest_root.mkdir(parents=True, exist_ok=True)
    temp_publish_dir = dest_root / f".staging_tmp_{uuid.uuid4().hex}"
    temp_publish_dir.mkdir(parents=True, exist_ok=True)

    try:
        # First copy all verified files into temp staging under destination root
        for rel_path in manifest.files:
            source_file = b_dir / rel_path
            staged_file = temp_publish_dir / rel_path
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, staged_file)

        # Atomically move each staged file to its final destination path
        for rel_path in manifest.files:
            staged_file = temp_publish_dir / rel_path
            final_target = dest_root / rel_path
            final_target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_file, final_target)

    finally:
        if temp_publish_dir.exists():
            shutil.rmtree(temp_publish_dir, ignore_errors=True)

    return StagingResult(
        status="SUCCESS",
        verified_file_count=len(manifest.files),
        manifest=manifest,
    )
