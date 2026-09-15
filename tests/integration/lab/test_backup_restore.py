"""Integration tests for OPS-02 Snapshot transfer and restore.

Acceptance Criteria:
- OPS-02-AC0 (test_ops_02_valid_contract): Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.
- OPS-02-AC1 (test_ops_02_contract_1): Partial transfer tidak mengganti aktif snapshot.
- OPS-02-AC2 (test_ops_02_contract_2): Backup SQLite memakai consistent API bukan copy WAL mentah.
- OPS-02-AC3 (test_ops_02_contract_3): Restore run di root baru mempertahankan IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from unittest.mock import patch
import pytest

from indodax_lab.operations.backup import backup_sqlite_db, create_backup_bundle
from indodax_lab.operations.restore import restore_snapshot_bundle
from indodax_lab.operations.staging import (
    ChecksumMismatchError,
    CorruptTransferError,
    TransferManifest,
    verify_bundle,
    stage_and_publish_transfer,
)


def _setup_source_environment(source_root: Path) -> tuple[Path, Path]:
    """Create sample dataset snapshot and WAL SQLite DB in source root."""
    # 1. Dataset snapshot
    dataset_dir = source_root / "datasets" / "btc_idr_snapshot_v1"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    data_file = dataset_dir / "bars.parquet"
    data_content = b"PARQUET_FORMAT_SIMULATED_CONTENT_BYTES_12345"
    data_file.write_bytes(data_content)

    manifest_file = dataset_dir / "manifest.json"
    manifest_data = {
        "snapshot_id": "btc_idr_snapshot_v1",
        "pair": "btc_idr",
        "created_at": "2025-06-01T12:00:00+00:00",
        "file_sha256": hashlib.sha256(data_content).hexdigest(),
    }
    manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # 2. SQLite Database with WAL mode
    db_path = source_root / "queue" / "jobs.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, recipe_hash TEXT NOT NULL);")
    conn.execute("INSERT INTO jobs VALUES ('job_001', 'recipe_hash_alpha');")
    conn.commit()
    conn.close()

    return dataset_dir, db_path


def test_ops_02_valid_contract(tmp_path: Path) -> None:
    """OPS-02-AC0: Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi."""
    source_root = tmp_path / "asus_source"
    dest_root = tmp_path / "lenovo_dest"
    bundle_staging = tmp_path / "staging_transfer"

    _setup_source_environment(source_root)

    # 1. Create backup bundle on source host
    bundle_dir = create_backup_bundle(
        source_root=source_root,
        relative_paths=["datasets/btc_idr_snapshot_v1", "queue/jobs.db"],
        bundle_output_dir=bundle_staging,
        source_host="asus",
    )

    manifest_path = bundle_dir / "transfer_manifest.json"
    assert manifest_path.exists()

    # 2. Stage, verify checksums, and publish atomically to target host
    result = stage_and_publish_transfer(
        bundle_dir=bundle_dir,
        destination_root=dest_root,
    )

    assert result.status == "SUCCESS"
    assert result.verified_file_count >= 3

    # 3. Verify destination integrity
    dest_data_file = result.published_root / "datasets" / "btc_idr_snapshot_v1" / "bars.parquet"
    assert dest_data_file.exists()
    assert dest_data_file.read_bytes() == b"PARQUET_FORMAT_SIMULATED_CONTENT_BYTES_12345"

    dest_db = result.published_root / "queue" / "jobs.db"
    assert dest_db.exists()
    conn = sqlite3.connect(str(dest_db))
    cur = conn.cursor()
    cur.execute("SELECT job_id, recipe_hash FROM jobs WHERE job_id = 'job_001';")
    row = cur.fetchone()
    assert row == ("job_001", "recipe_hash_alpha")
    conn.close()


def test_ops_02_contract_1(tmp_path: Path) -> None:
    """OPS-02-AC1: Partial transfer tidak mengganti aktif snapshot."""
    source_root = tmp_path / "asus_source"
    dest_root = tmp_path / "lenovo_dest"
    bundle_staging = tmp_path / "staging_transfer"

    _setup_source_environment(source_root)

    # Pre-existing active snapshot in destination
    active_snapshot_dir = dest_root / "datasets" / "btc_idr_snapshot_v1"
    active_snapshot_dir.mkdir(parents=True, exist_ok=True)
    active_file = active_snapshot_dir / "bars.parquet"
    original_active_content = b"ACTIVE_ORIGINAL_CORRECT_VERSION_DO_NOT_OVERWRITE"
    active_file.write_bytes(original_active_content)

    # Create transfer bundle
    bundle_dir = create_backup_bundle(
        source_root=source_root,
        relative_paths=["datasets/btc_idr_snapshot_v1"],
        bundle_output_dir=bundle_staging,
        source_host="asus",
    )

    # Corrupt/truncate a file in bundle to simulate partial/interrupted transfer
    corrupted_target = bundle_dir / "datasets" / "btc_idr_snapshot_v1" / "bars.parquet"
    corrupted_target.write_bytes(b"PARTIAL_TRUNCATED_BYTES")

    # Publishing must fail closed with ChecksumMismatchError
    with pytest.raises((ChecksumMismatchError, CorruptTransferError)):
        stage_and_publish_transfer(
            bundle_dir=bundle_dir,
            destination_root=dest_root,
        )

    # Assert active snapshot remains 100% UNCHANGED and NOT replaced
    assert active_file.exists()
    assert active_file.read_bytes() == original_active_content


def test_ops_02_contract_2(tmp_path: Path) -> None:
    """OPS-02-AC2: Backup SQLite memakai consistent API bukan copy WAL mentah."""
    source_db = tmp_path / "live.db"
    backup_db = tmp_path / "consistent_backup.db"

    conn = sqlite3.connect(str(source_db))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL);")
    conn.execute("INSERT INTO records (value) VALUES ('val_committed_in_wal');")
    conn.commit()

    # Active WAL file exists with dirty pages
    wal_file = tmp_path / "live.db-wal"
    assert wal_file.exists()

    # Perform consistent backup
    backup_path = backup_sqlite_db(source_db, backup_db)
    assert backup_path == backup_db
    assert backup_db.exists()

    # Verify backup contains committed transaction without requiring raw WAL copying
    backup_conn = sqlite3.connect(str(backup_db))
    cur = backup_conn.cursor()
    cur.execute("SELECT value FROM records WHERE id = 1;")
    res = cur.fetchone()
    assert res == ("val_committed_in_wal",)
    backup_conn.close()
    conn.close()


def test_ops_02_contract_3(tmp_path: Path) -> None:
    """OPS-02-AC3: Restore run di root baru mempertahankan IDs."""
    source_root = tmp_path / "original_host"
    restore_root = tmp_path / "new_dr_host"
    bundle_dir = tmp_path / "bundle"

    _setup_source_environment(source_root)

    create_backup_bundle(
        source_root=source_root,
        relative_paths=["datasets/btc_idr_snapshot_v1", "queue/jobs.db"],
        bundle_output_dir=bundle_dir,
        source_host="asus",
    )

    # Restore into completely new root directory
    restore_result = restore_snapshot_bundle(
        bundle_dir=bundle_dir,
        target_root=restore_root,
    )

    assert restore_result.status == "SUCCESS"

    # Verify IDs are preserved exactly
    manifest_file = restore_result.target_root / "datasets" / "btc_idr_snapshot_v1" / "manifest.json"
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest_data["snapshot_id"] == "btc_idr_snapshot_v1"
    assert manifest_data["pair"] == "btc_idr"

    db_path = restore_result.target_root / "queue" / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT job_id, recipe_hash FROM jobs;")
    row = cur.fetchone()
    assert row == ("job_001", "recipe_hash_alpha")
    conn.close()


def _write_manifest(bundle_dir: Path, files: dict[str, str], total_bytes: int = 0) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "transfer_manifest.json").write_text(
        json.dumps({
            "bundle_id": "attack-fixture",
            "source_host": "fixture",
            "created_at": "2025-06-01T12:00:00+00:00",
            "files": files,
            "total_bytes": total_bytes,
        }),
        encoding="utf-8",
    )


@pytest.mark.parametrize("member", ["../outside.bin", "/absolute.bin", "C:/drive.bin"])
def test_transfer_rejects_unsafe_manifest_member_before_writing(
    tmp_path: Path,
    member: str,
) -> None:
    bundle = tmp_path / "bundle"
    destination = tmp_path / "destination"
    outside = tmp_path / "outside.bin"
    _write_manifest(bundle, {member: hashlib.sha256(b"attack").hexdigest()})

    with pytest.raises(CorruptTransferError, match="UNSAFE"):
        stage_and_publish_transfer(bundle, destination)

    assert not outside.exists()
    assert not destination.exists()


def test_transfer_rejects_duplicate_normalized_targets(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_manifest(bundle, {
        "data/file.bin": hashlib.sha256(b"one").hexdigest(),
        "data\\file.bin": hashlib.sha256(b"two").hexdigest(),
    })

    with pytest.raises(CorruptTransferError, match="DUPLICATE"):
        verify_bundle(bundle)


def test_transfer_rejects_symlink_escape(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside = outside_dir / "outside.bin"
    outside.write_bytes(b"outside")
    bundle.mkdir()
    link = bundle / "linked"
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside_dir)],
            check=False,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
    else:
        link.symlink_to(outside_dir, target_is_directory=True)
    _write_manifest(
        bundle,
        {"linked/outside.bin": hashlib.sha256(b"outside").hexdigest()},
        len(b"outside"),
    )

    with pytest.raises(CorruptTransferError, match="SYMLINK|ESCAPE"):
        verify_bundle(bundle)


def test_backup_rejects_source_traversal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    bundle = tmp_path / "bundle"

    with pytest.raises(ValueError, match="UNSAFE"):
        create_backup_bundle(source, ["../outside.bin"], bundle)

    assert not (bundle / "outside.bin").exists()


def _simple_bundle(tmp_path: Path, name: str, values: tuple[bytes, bytes]) -> Path:
    source = tmp_path / f"source-{name}"
    source.mkdir()
    (source / "a.bin").write_bytes(values[0])
    (source / "b.bin").write_bytes(values[1])
    return create_backup_bundle(source, ["a.bin", "b.bin"], tmp_path / f"bundle-{name}")


def test_second_publish_failure_keeps_entire_old_active_view(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    old_result = stage_and_publish_transfer(
        _simple_bundle(tmp_path, "old", (b"old-a", b"old-b")),
        destination,
    )
    old_active_bytes = old_result.active_reference.read_bytes()
    new_bundle = _simple_bundle(tmp_path, "new", (b"new-a", b"new-b"))

    from indodax_lab.operations import staging

    real_replace = staging.os.replace
    calls = 0

    def fail_second_replace(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected active-switch failure")
        return real_replace(source, target)

    with patch("indodax_lab.operations.staging.os.replace", side_effect=fail_second_replace):
        with pytest.raises(OSError, match="active-switch"):
            stage_and_publish_transfer(new_bundle, destination)

    assert old_result.active_reference.read_bytes() == old_active_bytes
    assert (old_result.published_root / "a.bin").read_bytes() == b"old-a"
    assert (old_result.published_root / "b.bin").read_bytes() == b"old-b"


def test_successful_transfer_retry_is_idempotent(tmp_path: Path) -> None:
    bundle = _simple_bundle(tmp_path, "retry", (b"same-a", b"same-b"))
    destination = tmp_path / "destination"

    first = stage_and_publish_transfer(bundle, destination)
    retry = stage_and_publish_transfer(bundle, destination)

    assert retry.manifest_hash == first.manifest_hash
    assert retry.published_root == first.published_root
    assert retry.active_reference.read_bytes() == first.active_reference.read_bytes()
