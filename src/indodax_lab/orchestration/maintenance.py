"""Storage retention, integrity audits, and safe artifact cleanup (OPS-03).

Contract:
registry reachability + retention policy -> deletion candidates, approved apply report.
Champion dan sealed inputs tidak terhapus.
Symlink escape ditolak.
Interrupted cleanup dapat rerun tanpa menghapus live data.
"""

from __future__ import annotations

import os
import stat as stat_module
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def _is_symlink_or_junction(path: Path) -> bool:
    """Reject symlinks, junctions, all Windows reparse points, and unknown states."""
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        if os.name == "nt":
            attrs = path.lstat().st_file_attributes
            return bool(attrs & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        return False
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _assert_no_symlink_or_junction(path: Path) -> None:
    """Walk every existing path component to the filesystem root."""
    current = path
    while True:
        if _is_symlink_or_junction(current):
            raise SymlinkEscapeError(
                f"SYMLINK_DETECTED: path component '{current}' is a symlink or junction"
            )
        if current == current.parent:
            break
        current = current.parent


class SymlinkEscapeError(ValueError):
    """Raised when an artifact or target path escapes the allowed storage boundary or is a symlink/junction."""


class ProtectedArtifactRegistryError(RuntimeError):
    """Raised when authoritative protected-artifact reachability is unavailable or invalid."""


class RetentionPolicy(BaseModel):
    """Retention parameters and protection rules for artifact storage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retention_days: int = Field(default=30, ge=1)
    protected_artifact_ids: set[str] = Field(default_factory=set)
    dry_run: bool = True


class CleanupReport(BaseModel):
    """Structured report documenting audit findings and deletions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str
    storage_root: str
    scanned_files_count: int
    deletion_candidates: list[str]
    deleted_files: list[str]
    deleted_count: int
    freed_bytes: int
    rejected_candidates: list[str]
    dry_run: bool
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("executed_at", mode="after")
    @classmethod
    def validate_executed_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "executed_at")


class StorageCleaner:
    """Safe maintenance engine that audits and removes expired, unreferenced artifacts."""

    def __init__(
        self,
        storage_root: Path | str,
        policy: RetentionPolicy | None = None,
        protected_resolver: Callable[[str], Mapping[str, set[str]]] | None = None,
    ) -> None:
        # Inspect the supplied root before resolve can hide a link or junction.
        root = Path(os.path.abspath(storage_root))
        _assert_no_symlink_or_junction(root)
        self.storage_root = root.resolve()
        self.policy = policy or RetentionPolicy()
        self._protected_resolver = protected_resolver

    def _get_protected_artifact_paths(self) -> set[str]:
        """Resolve opaque registry IDs to exact root-relative paths, failing closed."""
        if self._protected_resolver is None:
            raise ProtectedArtifactRegistryError("PROTECTED_ARTIFACT_REGISTRY_UNAVAILABLE")
        try:
            references = self._protected_resolver(str(self.storage_root))
            if not isinstance(references, Mapping):
                raise ValueError("registry resolver must return artifact_id -> paths")
            if not self.policy.protected_artifact_ids.issubset(references):
                raise ValueError("required protected artifact ID is missing from registry")
            protected_paths: set[str] = set()
            for artifact_id, paths in references.items():
                if not isinstance(artifact_id, str) or not artifact_id.strip():
                    raise ValueError("registry returned a blank artifact ID")
                if not isinstance(paths, (set, frozenset)) or not paths:
                    raise ValueError(f"registry returned invalid paths for artifact ID {artifact_id!r}")
                for raw_path in paths:
                    safe_path = self.validate_safe_path(raw_path)
                    if not safe_path.is_file():
                        raise ValueError(f"registered artifact path is missing: {raw_path!r}")
                    rel_path = safe_path.relative_to(self.storage_root).as_posix()
                    protected_paths.add(os.path.normcase(rel_path))
            return protected_paths
        except ProtectedArtifactRegistryError:
            raise
        except Exception as err:
            raise ProtectedArtifactRegistryError("PROTECTED_ARTIFACT_REGISTRY_UNAVAILABLE") from err

    def validate_safe_path(self, target_path: str | Path) -> Path:
        """Verify that target_path resides safely within storage_root without escaping.

        Detects path traversal ('../') and symlink/junction escapes (OPS-03-AC2).
        Also rejects any symlink or junction component in the path (OPS-03-R1).
        Returns the *link* path (not resolved target) so deletion removes the link.
        """
        candidate = Path(target_path)
        if not candidate.is_absolute():
            candidate = self.storage_root / candidate
        candidate = Path(os.path.abspath(candidate))

        _assert_no_symlink_or_junction(candidate)

        # Now resolve and verify containment
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.storage_root)
        except ValueError as err:
            raise SymlinkEscapeError(
                f"SYMLINK_OR_PATH_ESCAPE_DETECTED: path '{target_path}' resolves to '{resolved}' outside root '{self.storage_root}'"
            ) from err

        # Return the unresolved link path so unlink() deletes the link, not the target
        return candidate

    def scan_and_clean(
        self,
        as_of: datetime | None = None,
        dry_run: bool | None = None,
    ) -> CleanupReport:
        """Scan storage for expired, unreferenced artifacts and delete if approved.

        Invariants:
        - Champion and sealed inputs are strictly preserved (OPS-03-AC1).
        - Symlink or traversal escapes are rejected per-file (OPS-03-AC2, OPS-03-R4).
        - Idempotent: can rerun cleanly if interrupted (OPS-03-AC3).
        """
        now = as_of or datetime.now(UTC)
        is_dry = self.policy.dry_run if dry_run is None else dry_run
        cutoff_timestamp = (now - timedelta(days=self.policy.retention_days)).timestamp()

        if not self.storage_root.exists():
            return CleanupReport(
                report_id=f"clean_{uuid.uuid4().hex[:8]}",
                storage_root=str(self.storage_root),
                scanned_files_count=0,
                deletion_candidates=[],
                deleted_files=[],
                deleted_count=0,
                freed_bytes=0,
                rejected_candidates=[],
                dry_run=is_dry,
                executed_at=now,
            )

        protected_paths = self._get_protected_artifact_paths()
        scanned_count = 0
        candidates: list[tuple[Path, os.stat_result]] = []
        candidate_relpaths: list[str] = []
        candidate_bytes = 0
        rejected: list[str] = []

        for root, _, files in os.walk(self.storage_root, followlinks=False):
            for fname in files:
                scanned_count += 1
                raw_path = Path(root) / fname

                try:
                    safe_path = self.validate_safe_path(raw_path)
                except SymlinkEscapeError as err:
                    # OPS-03-R4: record rejection and continue audit
                    rejected.append(f"{raw_path.relative_to(self.storage_root).as_posix()}: {err}")
                    continue

                # Relative path from storage root
                rel_path = safe_path.relative_to(self.storage_root).as_posix()

                # Invariant 1: resolve identity to concrete paths; never compare basenames.
                if os.path.normcase(rel_path) in protected_paths:
                    continue

                # Invariant 2: Check age vs retention cutoff
                try:
                    file_stat = safe_path.lstat()
                except FileNotFoundError:
                    # File already gone (idempotent rerun)
                    continue
                if stat_module.S_ISREG(file_stat.st_mode) and file_stat.st_mtime < cutoff_timestamp:
                    candidates.append((safe_path, file_stat))
                    candidate_relpaths.append(rel_path)
                    candidate_bytes += file_stat.st_size

        deleted_paths: list[str] = []
        freed_bytes = 0

        if not is_dry:
            for file_path, scanned_stat in candidates:
                try:
                    file_path = self.validate_safe_path(file_path)
                    rel_path = file_path.relative_to(self.storage_root).as_posix()
                    if os.path.normcase(rel_path) in self._get_protected_artifact_paths():
                        rejected.append(f"{rel_path}: PROTECTED_ARTIFACT_REACHABILITY_CHANGED")
                        continue
                    current_stat = file_path.lstat()
                except FileNotFoundError:
                    # Gracefully handle already-deleted file from previous interrupted run (OPS-03-AC3)
                    continue
                except ProtectedArtifactRegistryError:
                    rejected.append("PROTECTED_ARTIFACT_REGISTRY_UNAVAILABLE_DURING_APPLY")
                    break
                except SymlinkEscapeError as err:
                    rejected.append(f"{file_path}: {err}")
                    continue

                identity = lambda value: (
                    value.st_dev,
                    value.st_ino,
                    value.st_size,
                    value.st_mtime_ns,
                    value.st_ctime_ns,
                )
                if (
                    not stat_module.S_ISREG(current_stat.st_mode)
                    or identity(current_stat) != identity(scanned_stat)
                    or current_stat.st_mtime >= cutoff_timestamp
                ):
                    rejected.append(f"{rel_path}: CANDIDATE_CHANGED_AFTER_SCAN")
                    continue
                file_path.unlink()
                freed_bytes += current_stat.st_size
                deleted_paths.append(rel_path)

        return CleanupReport(
            report_id=f"clean_{uuid.uuid4().hex[:8]}",
            storage_root=str(self.storage_root),
            scanned_files_count=scanned_count,
            deletion_candidates=candidate_relpaths,
            deleted_files=deleted_paths,
            deleted_count=len(deleted_paths) if not is_dry else 0,
            freed_bytes=freed_bytes if not is_dry else candidate_bytes,
            rejected_candidates=rejected,
            dry_run=is_dry,
            executed_at=now,
        )
