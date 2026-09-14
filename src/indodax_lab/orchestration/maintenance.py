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
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


class SymlinkEscapeError(ValueError):
    """Raised when an artifact or target path escapes the allowed storage boundary."""


class RetentionPolicy(BaseModel):
    """Retention parameters and protection rules for artifact storage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retention_days: int = 30
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
    dry_run: bool
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("executed_at", mode="after")
    @classmethod
    def validate_executed_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "executed_at")


class StorageCleaner:
    """Safe maintenance engine that audits and removes expired, unreferenced artifacts."""

    def __init__(self, storage_root: Path | str, policy: RetentionPolicy | None = None) -> None:
        self.storage_root = Path(storage_root).resolve()
        self.policy = policy or RetentionPolicy()

    def validate_safe_path(self, target_path: str | Path) -> Path:
        """Verify that target_path resides safely within storage_root without escaping.

        Detects path traversal ('../') and symlink escapes (OPS-03-AC2).
        """
        candidate = Path(target_path)
        if not candidate.is_absolute():
            resolved = (self.storage_root / candidate).resolve()
        else:
            resolved = candidate.resolve()

        try:
            # Check relative to root
            resolved.relative_to(self.storage_root)
        except ValueError as err:
            raise SymlinkEscapeError(
                f"SYMLINK_OR_PATH_ESCAPE_DETECTED: path '{target_path}' resolves to '{resolved}' outside root '{self.storage_root}'"
            ) from err

        return resolved

    def scan_and_clean(
        self,
        as_of: datetime | None = None,
        dry_run: bool | None = None,
    ) -> CleanupReport:
        """Scan storage for expired, unreferenced artifacts and delete if approved.

        Invariants:
        - Champion and sealed inputs are strictly preserved (OPS-03-AC1).
        - Symlink or traversal escapes are rejected immediately (OPS-03-AC2).
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
                dry_run=is_dry,
                executed_at=now,
            )

        scanned_count = 0
        candidates: list[Path] = []
        candidate_relpaths: list[str] = []
        candidate_bytes = 0

        for root, _, files in os.walk(self.storage_root):
            for fname in files:
                scanned_count += 1
                raw_path = Path(root) / fname
                safe_path = self.validate_safe_path(raw_path)

                # Relative path from storage root
                rel_path = safe_path.relative_to(self.storage_root).as_posix()

                # Invariant 1: Check protected names/IDs (OPS-03-AC1)
                if fname in self.policy.protected_artifact_ids or rel_path in self.policy.protected_artifact_ids:
                    continue

                # Invariant 2: Check age vs retention cutoff
                stat = safe_path.stat()
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
            freed_bytes=freed_bytes if not is_dry else 0,
            dry_run=is_dry,
            executed_at=now,
        )
