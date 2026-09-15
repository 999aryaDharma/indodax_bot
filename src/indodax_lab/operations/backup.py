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
from pathlib import Path, PurePosixPath
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


def _safe_relative_member(raw_path: str | Path) -> str:
    """Return a canonical POSIX relative path or reject the member fail-closed."""
    raw = str(raw_path).replace("\\", "/")
    member = PurePosixPath(raw)
    if (
        not raw
        or raw.startswith("/")
        or member.is_absolute()
        or any(part in ("", ".", "..") for part in member.parts)
        or any(":" in part for part in member.parts)
    ):
        raise ValueError(f"UNSAFE_RELATIVE_PATH:{raw_path}")
    return member.as_posix()


def _assert_no_symlink_ancestors(path: Path, label: str) -> None:
    absolute = path.absolute()
    for candidate in list(reversed(absolute.parents)) + [absolute]:
        if candidate.is_symlink() or (
            hasattr(candidate, "is_junction") and candidate.is_junction()
        ):
            raise ValueError(f"UNSAFE_SYMLINK_{label}:{candidate}")


def _assert_no_symlink_path(root: Path, relative_path: str) -> Path:
    current = root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        if current.is_symlink() or (
            hasattr(current, "is_junction") and current.is_junction()
        ):
            raise ValueError(f"UNSAFE_SYMLINK_SOURCE:{relative_path}")
    try:
        resolved = current.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"PATH_NOT_FOUND_IN_SOURCE_ROOT:{relative_path}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"UNSAFE_SOURCE_ESCAPE:{relative_path}") from exc
    return current


def _copy_file_durable(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as source_stream, destination.open("xb") as destination_stream:
        shutil.copyfileobj(source_stream, destination_stream)
        destination_stream.flush()
        os.fsync(destination_stream.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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

    # Windows rejects fsync on a read-only CRT descriptor. Opening the completed
    # backup read/write does not mutate it and gives fsync the required handle.
    with temp_target.open("r+b") as backup_stream:
        os.fsync(backup_stream.fileno())
    os.replace(temp_target, target)
    _fsync_directory(target.parent)
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
    raw_source_root = Path(source_root)
    _assert_no_symlink_ancestors(raw_source_root, "SOURCE_ROOT")
    src_root = raw_source_root.resolve(strict=True)
    if not src_root.is_dir():
        raise NotADirectoryError(f"SOURCE_ROOT_NOT_DIRECTORY:{src_root}")
    raw_bundle_dir = Path(bundle_output_dir)
    _assert_no_symlink_ancestors(raw_bundle_dir, "BUNDLE_OUTPUT")
    bundle_dir = raw_bundle_dir.resolve()
    if bundle_dir == src_root or bundle_dir.is_relative_to(src_root):
        raise ValueError("UNSAFE_BUNDLE_OUTPUT_INSIDE_SOURCE_ROOT")

    # Validate the complete request before creating or modifying the bundle.
    canonical_members: list[str] = []
    seen: set[str] = set()
    for requested in relative_paths:
        member = _safe_relative_member(requested)
        if member in seen:
            raise ValueError(f"DUPLICATE_NORMALIZED_PATH:{member}")
        seen.add(member)
        _assert_no_symlink_path(src_root, member)
        canonical_members.append(member)

    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        raise ValueError(f"BUNDLE_OUTPUT_NOT_EMPTY:{bundle_dir}")

    files_to_copy: dict[str, Path] = {}
    for rel_path_str in canonical_members:
        source_path = _assert_no_symlink_path(src_root, rel_path_str)
        if source_path.is_dir():
            for root, dirs, files in os.walk(source_path, followlinks=False):
                root_path = Path(root)
                for directory in dirs:
                    directory_path = root_path / directory
                    if directory_path.is_symlink():
                        relative = directory_path.relative_to(src_root).as_posix()
                        raise ValueError(f"UNSAFE_SYMLINK_SOURCE:{relative}")
                for fname in files:
                    file_src = root_path / fname
                    file_rel = file_src.relative_to(src_root).as_posix()
                    safe_source = _assert_no_symlink_path(src_root, file_rel)
                    if file_rel in files_to_copy:
                        raise ValueError(f"DUPLICATE_NORMALIZED_PATH:{file_rel}")
                    files_to_copy[file_rel] = safe_source
        elif source_path.is_file():
            if rel_path_str in files_to_copy:
                raise ValueError(f"DUPLICATE_NORMALIZED_PATH:{rel_path_str}")
            files_to_copy[rel_path_str] = source_path
        else:
            raise ValueError(f"UNSAFE_SOURCE_TYPE:{rel_path_str}")

    # Only now, after every source member and output path is validated, create
    # the output and begin durable copies.
    bundle_dir.mkdir(parents=True, exist_ok=True)

    file_checksums: dict[str, str] = {}
    total_bytes = 0

    for file_rel, source_path in sorted(files_to_copy.items()):
        file_dest = bundle_dir / file_rel
        if is_sqlite_database(source_path):
            backup_sqlite_db(source_path, file_dest)
        else:
            _copy_file_durable(source_path, file_dest)

        sha = compute_sha256(file_dest)
        file_checksums[file_rel] = sha
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
    temp_manifest = bundle_dir / f".transfer_manifest.{uuid.uuid4().hex}.tmp"
    with temp_manifest.open("x", encoding="utf-8", newline="\n") as manifest_stream:
        json.dump(manifest_data, manifest_stream, sort_keys=True, separators=(",", ":"))
        manifest_stream.flush()
        os.fsync(manifest_stream.fileno())
    os.replace(temp_manifest, manifest_path)
    _fsync_directory(bundle_dir)

    return bundle_dir
