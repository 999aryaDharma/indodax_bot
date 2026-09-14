"""Integration tests for OPS-03 Storage retention and integrity maintenance.

Acceptance Criteria:
- OPS-03-AC0 (test_ops_03_valid_contract): Cleanup hanya menghapus artifact tidak direferensikan setelah retention dan dry-run audit.
- OPS-03-AC1 (test_ops_03_contract_1): Champion dan sealed inputs tidak terhapus.
- OPS-03-AC2 (test_ops_03_contract_2): Symlink escape ditolak.
- OPS-03-AC3 (test_ops_03_contract_3): Interrupted cleanup dapat rerun tanpa menghapus live data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import pytest

from indodax_lab.orchestration.maintenance import (
    CleanupReport,
    RetentionPolicy,
    StorageCleaner,
    SymlinkEscapeError,
)


def _setup_storage_environment(root: Path) -> tuple[Path, Path, Path]:
    """Create test artifacts with different age and reference status."""
    storage_dir = root / "artifacts"
    storage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Old referenced artifact (100 days old)
    old_referenced = storage_dir / "art_old_referenced.bin"
    old_referenced.write_bytes(b"OLD_REFERENCED_ARTIFACT_CONTENT")

    # 2. Recent unreferenced artifact (5 days old)
    recent_unreferenced = storage_dir / "art_recent_unref.bin"
    recent_unreferenced.write_bytes(b"RECENT_UNREFERENCED_CONTENT")

    # 3. Old unreferenced artifact (45 days old)
    old_unreferenced = storage_dir / "art_old_unref.bin"
    old_unreferenced.write_bytes(b"OLD_UNREFERENCED_CONTENT")

    return old_referenced, recent_unreferenced, old_unreferenced


def test_ops_03_valid_contract(tmp_path: Path) -> None:
    """OPS-03-AC0: Cleanup hanya menghapus artifact tidak direferensikan setelah retention dan dry-run audit."""
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    old_ref, recent_unref, old_unref = _setup_storage_environment(storage_root)

    # Simulated timestamps
    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    old_mtime = (now - timedelta(days=45)).timestamp()
    recent_mtime = (now - timedelta(days=5)).timestamp()

    os.utime(old_ref, (old_mtime, old_mtime))
    os.utime(recent_unref, (recent_mtime, recent_mtime))
    os.utime(old_unref, (old_mtime, old_mtime))

    policy = RetentionPolicy(
        retention_days=30,
        protected_artifact_ids={"art_old_referenced.bin"},
    )
    cleaner = StorageCleaner(storage_root, policy)

    # 1. Dry run audit: identifies candidate without deletion
    dry_report = cleaner.scan_and_clean(as_of=now, dry_run=True)
    assert dry_report.dry_run is True
    assert "artifacts/art_old_unref.bin" in [p.replace("\\", "/") for p in dry_report.deletion_candidates]
    assert "artifacts/art_old_referenced.bin" not in [p.replace("\\", "/") for p in dry_report.deletion_candidates]
    assert "artifacts/art_recent_unref.bin" not in [p.replace("\\", "/") for p in dry_report.deletion_candidates]

    # Confirm files still exist after dry run
    assert old_ref.exists()
    assert recent_unref.exists()
    assert old_unref.exists()

    # 2. Approved apply run: actually deletes unreferenced expired artifact
    apply_report = cleaner.scan_and_clean(as_of=now, dry_run=False)
    assert apply_report.dry_run is False
    assert apply_report.deleted_count == 1
    assert not old_unref.exists()

    # Protected and recent files still exist
    assert old_ref.exists()
    assert recent_unref.exists()


def test_ops_03_contract_1(tmp_path: Path) -> None:
    """OPS-03-AC1: Champion dan sealed inputs tidak terhapus."""
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)

    champion_artifact = storage_root / "champion_weights.pt"
    champion_artifact.write_bytes(b"CHAMPION_MODEL_WEIGHTS")

    sealed_input = storage_root / "sealed_test_fold.parquet"
    sealed_input.write_bytes(b"SEALED_TEST_FOLD_DATA")

    # Both are very old (200 days old)
    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    ancient_mtime = (now - timedelta(days=200)).timestamp()
    os.utime(champion_artifact, (ancient_mtime, ancient_mtime))
    os.utime(sealed_input, (ancient_mtime, ancient_mtime))

    policy = RetentionPolicy(
        retention_days=30,
        protected_artifact_ids={"champion_weights.pt", "sealed_test_fold.parquet"},
    )
    cleaner = StorageCleaner(storage_root, policy)

    report = cleaner.scan_and_clean(as_of=now, dry_run=False)

    # Neither champion nor sealed input can be deleted
    assert champion_artifact.name not in report.deleted_files
    assert sealed_input.name not in report.deleted_files
    assert champion_artifact.exists()
    assert sealed_input.exists()


def test_ops_03_contract_2(tmp_path: Path) -> None:
    """OPS-03-AC2: Symlink escape ditolak."""
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)

    outside_dir = tmp_path / "outside_sensitive"
    outside_dir.mkdir(parents=True, exist_ok=True)
    secret_file = outside_dir / "secret.env"
    secret_file.write_bytes(b"API_SECRET_KEY=confidential")

    policy = RetentionPolicy(retention_days=30)
    cleaner = StorageCleaner(storage_root, policy)

    # Test path escaping storage root
    escaping_path = "../outside_sensitive/secret.env"

    with pytest.raises(SymlinkEscapeError) as exc_info:
        cleaner.validate_safe_path(escaping_path)
    assert "SYMLINK_OR_PATH_ESCAPE_DETECTED" in str(exc_info.value)


def test_ops_03_contract_3(tmp_path: Path) -> None:
    """OPS-03-AC3: Interrupted cleanup dapat rerun tanpa menghapus live data."""
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)

    live_artifact = storage_root / "live_data.parquet"
    live_artifact.write_bytes(b"LIVE_DATA")

    dead_artifact_1 = storage_root / "dead_1.bin"
    dead_artifact_1.write_bytes(b"DEAD_1")
    dead_artifact_2 = storage_root / "dead_2.bin"
    dead_artifact_2.write_bytes(b"DEAD_2")

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    old_mtime = (now - timedelta(days=60)).timestamp()
    os.utime(dead_artifact_1, (old_mtime, old_mtime))
    os.utime(dead_artifact_2, (old_mtime, old_mtime))
    os.utime(live_artifact, (old_mtime, old_mtime))  # Also old, but protected

    policy = RetentionPolicy(
        retention_days=30,
        protected_artifact_ids={"live_data.parquet"},
    )
    cleaner = StorageCleaner(storage_root, policy)

    # Simulate interrupted cleanup where dead_artifact_1 was manually deleted or interrupted halfway
    dead_artifact_1.unlink()

    # Rerun cleanup
    rerun_report = cleaner.scan_and_clean(as_of=now, dry_run=False)

    assert dead_artifact_2.name in [Path(f).name for f in rerun_report.deleted_files]
    assert not dead_artifact_2.exists()

    # Live protected data is never touched or deleted across reruns
    assert live_artifact.exists()
    assert live_artifact.read_bytes() == b"LIVE_DATA"
