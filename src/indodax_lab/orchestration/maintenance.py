"""Storage retention, integrity audits, and safe artifact cleanup (OPS-03).

Contract:
registry reachability + retention policy -> deletion candidates, approved apply report.
Champion dan sealed inputs tidak terhapus.
Symlink escape ditolak.
Interrupted cleanup dapat rerun tanpa menghapus live data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import uuid
from typing import Callable
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def _is_symlink_or_junction(path: Path) -> bool:
    """Check if path is a symlink or junction, without raising on permission errors."""
    try:
        if path.is_symlink():
            return True
    except OSError:
        return False
    try:
        is_junction = path.is_junction()
    except (OSError, AttributeError):
        return False
    return bool(is_junction)


def _assert_no_symlink_or_junction(path: Path, root: Path) -> None:
    """Walk from path up to root (exclusive), rejecting any symlink or junction component."""
    # Check the path itself
    if _is_symlink_or_junction(path):
        raise SymlinkEscapeError(
            f"SYMLINK_DETECTED: path '{path}' is a symlink; delete the link, not its target"
        )
    # Check each parent up to root
    current = path.parent
    while current != root and current != current.parent:
        if _is_symlink_or_junction(current):
            raise SymlinkEscapeError(
                f"SYMLINK_DETECTED: path component '{current}' is a symlink"
            )
        current = current.parent


class SymlinkEscapeError(ValueError):
    """Raised when an artifact or target path escapes the allowed storage boundary or is a symlink/junction."""


def champion_registry_resolver(
    registry_root: Path | str, model_id: str, version: str
) -> Callable[[str], set[str]]:
    """Build a protected-resolver from the real model registry.

    Resolves the champion manifest plus every artifact object it references
    into absolute, resolved path strings. Any registry outage (missing row,
    corrupt manifest, unreadable DB) raises instead of returning an empty set,
    so the cleaner fails closed. Lazy import keeps the orchestration layer free
    of a hard models-layer dependency.
    """

    def _resolve(_storage_root: str) -> set[str]:
        from indodax_lab.models.registry import ModelRegistry

        registry = ModelRegistry(registry_root)
        with registry._connection() as conn:
            row = conn.execute(
                "SELECT manifest_json FROM model_registry "
                "WHERE model_id = ? AND version = ?",
                (model_id, version),
            ).fetchone()
        if row is None:
            raise ValueError(
                f"CHAMPION_NOT_REGISTERED: no published model for {model_id}:{version}"
            )
        from indodax_lab.contracts.workbench import ModelManifest

        manifest = ModelManifest.model_validate_json(row["manifest_json"])
        paths = {
            str(registry.object_path(manifest.to_artifact_ref()).resolve()),
            str((Path(registry_root) / "registry.sqlite").resolve()),
        }
        for ref in manifest.artifact_refs:
            paths.add(str(registry.object_path(ref).resolve()))
        return paths

    return _resolve


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
        protected_resolver: Callable[[str], set[str]] | None = None,
    ) -> None:
        # OPS-03-R6: reject symlink/junction at root
        root = Path(storage_root).resolve()
        _assert_no_symlink_or_junction(root, root.parent)
        self.storage_root = root
        self.policy = policy or RetentionPolicy()
        self._protected_resolver = protected_resolver

    def _get_protected_artifact_ids(self) -> set[str]:
        """Resolve protected artifact IDs from registry.

        Fail closed: a resolver outage aborts the whole scan (the caller lets
        the error propagate before any deletion) instead of silently
        downgrading to policy names.
        """
        if self._protected_resolver:
            return self._protected_resolver(str(self.storage_root))
        return set(self.policy.protected_artifact_ids)

    def validate_safe_path(self, target_path: str | Path) -> Path:
        """Verify that target_path resides safely within storage_root without escaping.

        Detects path traversal ('../') and symlink/junction escapes (OPS-03-AC2).
        Also rejects any symlink or junction component in the path (OPS-03-R1).
        Returns the *link* path (not resolved target) so deletion removes the link.
        """
        candidate = Path(target_path)
        if not candidate.is_absolute():
            candidate = self.storage_root / candidate

        # OPS-03-R1: check each component for symlink/junction before resolving
        _assert_no_symlink_or_junction(candidate, self.storage_root)

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

        protected_ids = self._get_protected_artifact_ids()
        protected_abs = {
            str(Path(p).resolve())
            for p in protected_ids
            if os.path.isabs(p)
        }
        scanned_count = 0
        candidates: list[Path] = []
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

                # Invariant 1: Check protected names/IDs (OPS-03-AC1, R2, R3).
                # Registry adapters contribute resolved absolute paths; match
                # those by identity, not by filename.
                if fname in protected_ids or rel_path in protected_ids:
                    continue
                if str(safe_path.resolve()) in protected_abs:
                    continue

                # Invariant 2: Check age vs retention cutoff
                try:
                    stat = safe_path.stat()
                except FileNotFoundError:
                    # File already gone (idempotent rerun)
                    continue
                if stat.st_mtime < cutoff_timestamp:
                    candidates.append(safe_path)
                    candidate_relpaths.append(rel_path)
                    candidate_bytes += stat.st_size

        deleted_paths: list[str] = []
        freed_bytes = 0

        if not is_dry:
            for file_path in candidates:
                try:
                    if file_path.exists():
                        fsize = file_path.stat().st_size
                        file_path.unlink()
                        freed_bytes += fsize
                        deleted_paths.append(file_path.relative_to(self.storage_root).as_posix())
                except FileNotFoundError:
                    # Gracefully handle already-deleted file from previous interrupted run (OPS-03-AC3)
                    continue

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
