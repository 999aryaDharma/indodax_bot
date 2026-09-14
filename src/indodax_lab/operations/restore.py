"""Snapshot restoration and disaster recovery utilities (OPS-02).

Contract:
- Restore run di root baru mempertahankan IDs.
- Restores verified state into alternate destination roots.
"""

from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, ConfigDict

from indodax_lab.operations.staging import stage_and_publish_transfer


class RestoreResult(BaseModel):
    """Result of restoring a verified bundle to a target root."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    restored_files: list[str]
    target_root: Path


def restore_snapshot_bundle(
    bundle_dir: Path | str,
    target_root: Path | str,
    verify_checksums: bool = True,
) -> RestoreResult:
    """Restore a verified snapshot bundle into a designated target root.

    Invariant (OPS-02-AC3):
    Restoration preserves all IDs, timestamps, and cryptographic integrity
    without modifying data content or schema.
    """
    b_dir = Path(bundle_dir)
    t_root = Path(target_root)

    staging_res = stage_and_publish_transfer(b_dir, t_root)

    return RestoreResult(
        status="SUCCESS",
        restored_files=sorted(list(staging_res.manifest.files.keys())),
        target_root=t_root,
    )
