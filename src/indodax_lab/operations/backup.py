"""Consistent backup utilities for SQLite and datasets (OPS-02).

Contract:
- Backup SQLite memakai consistent API bukan copy WAL mentah.
- Generates verified bundles with SHA-256 manifest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Sequence
import uuid


def _ensure_utc(dt: datetime, field_name: str = "timestamp") -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"UTC_TIMEZONE_AWARE_REQUIRED:{field_name}")
    return dt


def compute_sha256(file_path: Path | str) -> str:
    """Compute sha256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def is_sqlite_database(path: Path) -> bool:
    """Check whether a file is a SQLite database by path extension or header."""
    if path.suffix.lower() in (".db", ".sqlite", ".sqlite3"):
        return True
    if path.is_file() and path.stat().st_size >= 16:
        try:
            with open(path, "rb") as f:
                header = f.read(16)
                return header.startswith(b"SQLite format 3\x00")
        except OSError:
            return False
    return False


def backup_sqlite_db(source_db_path: Path | str, target_backup_path: Path | str) -> Path:
    """Perform consistent online SQLite backup using sqlite3 backup API.

    Guarantees:
    - Does NOT copy raw uncheckpointed WAL or SHM lock files.
    - Captures committed transactions consistent with active readers/writers.
    - Atomically replaces target backup path.
    """
    src = Path(source_db_path)
    target = Path(target_backup_path)
    if not src.exists():
        raise FileNotFoundError(f"SOURCE_DATABASE_NOT_FOUND:{src}")

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.parent / f"{target.name}.tmp.{uuid.uuid4().hex}"

    source_conn = None
    backup_conn = None
    try:
        source_conn = sqlite3.connect(str(src), timeout=10.0)
        backup_conn = sqlite3.connect(str(temp_target), timeout=10.0)
        source_conn.backup(backup_conn)
    finally:
        if backup_conn is not None:
            backup_conn.close()
        if source_conn is not None:
            source_conn.close()

    os.replace(temp_target, target)
    return target


def create_backup_bundle(
    source_root: Path | str,
    relative_paths: Sequence[str | Path],
    bundle_output_dir: Path | str,
    source_host: str = "asus",
) -> Path:
    """Assemble a self-contained, verified transfer bundle from source root.

    Copies datasets and runs consistent SQLite backups for databases,
    generating a transfer_manifest.json with exact relative path checksums.
    """
    src_root = Path(source_root).resolve()
    bundle_dir = Path(bundle_output_dir).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)

    file_checksums: dict[str, str] = {}
    total_bytes = 0

    for rel in relative_paths:
        rel_path_str = str(rel).replace("\\", "/")
        source_path = src_root / rel_path_str

        if not source_path.exists():
            raise FileNotFoundError(f"PATH_NOT_FOUND_IN_SOURCE_ROOT:{rel_path_str}")

        if source_path.is_dir():
            # Copy all files recursively inside directory
            for root, _, files in os.walk(source_path):
                for fname in files:
                    file_src = Path(root) / fname
                    file_rel = file_src.relative_to(src_root).as_posix()
                    file_dest = bundle_dir / file_rel
                    file_dest.parent.mkdir(parents=True, exist_ok=True)

                    if is_sqlite_database(file_src):
                        backup_sqlite_db(file_src, file_dest)
                    else:
                        shutil.copy2(file_src, file_dest)

                    sha = compute_sha256(file_dest)
                    file_checksums[file_rel] = sha
                    total_bytes += file_dest.stat().st_size
        else:
            file_dest = bundle_dir / rel_path_str
            file_dest.parent.mkdir(parents=True, exist_ok=True)

            if is_sqlite_database(source_path):
                backup_sqlite_db(source_path, file_dest)
            else:
                shutil.copy2(source_path, file_dest)

            sha = compute_sha256(file_dest)
            file_checksums[rel_path_str] = sha
            total_bytes += file_dest.stat().st_size

    # Write transfer manifest
    now = datetime.now(UTC)
    bundle_id = f"bundle_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    manifest_data = {
        "bundle_id": bundle_id,
        "source_host": source_host,
        "created_at": now.isoformat(),
        "files": file_checksums,
        "total_bytes": total_bytes,
    }

    manifest_path = bundle_dir / "transfer_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    return bundle_dir
