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


class BackupVerificationError(RuntimeError):
    """Raised when a completed backup cannot be verified as a faithful copy.

    A backup is only successful if the produced artifact has been proven to carry
    the source schema, page count and structural integrity. Anything less turns a
    silent dataset loss into a reported success, so this fails closed and never
    publishes a target file.
    """


_SQLITE_HEADER_BYTES = 16


def _database_inventory(conn: sqlite3.Connection) -> tuple[tuple[str, str, str], ...]:
    """Return the user-defined schema objects of a database in a stable order."""
    return tuple(
        tuple(row)  # type: ignore[misc]
        for row in conn.execute(
            "SELECT type, name, tbl_name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name"
        ).fetchall()
    )


def _page_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA page_count").fetchone()[0])


def _remove_sqlite_sidecars(database_path: Path) -> None:
    """Delete the -wal/-shm sidecars SQLite may leave next to a staged copy."""
    for suffix in ("-wal", "-shm", "-journal"):
        Path(f"{database_path}{suffix}").unlink(missing_ok=True)


def _verify_sqlite_backup(
    temp_target: Path,
    expected_objects: tuple[tuple[str, str, str], ...],
    expected_pages: int,
    source: Path,
) -> None:
    """Prove the staged backup is a complete, faithful, uncorrupted copy."""
    verify_conn: sqlite3.Connection | None = None
    try:
        verify_conn = sqlite3.connect(
            f"{temp_target.resolve().as_uri()}?mode=ro", uri=True
        )
        integrity = [row[0] for row in verify_conn.execute("PRAGMA integrity_check")]
        actual_objects = _database_inventory(verify_conn)
        actual_pages = _page_count(verify_conn)
    except sqlite3.Error as exc:
        raise BackupVerificationError(f"BACKUP_UNREADABLE:{source}:{exc}") from exc
    finally:
        if verify_conn is not None:
            verify_conn.close()

    if integrity != ["ok"]:
        raise BackupVerificationError(
            f"BACKUP_INTEGRITY_CHECK_FAILED:{source}:{integrity}"
        )
    if actual_objects != expected_objects:
        # Catches a backup API that returned without copying the schema at all.
        raise BackupVerificationError(
            f"BACKUP_SCHEMA_MISMATCH:{source}:{actual_objects}!={expected_objects}"
        )
    if actual_pages != expected_pages:
        raise BackupVerificationError(
            f"BACKUP_PAGE_COUNT_MISMATCH:{source}:{actual_pages}!={expected_pages}"
        )


def backup_sqlite_db(source_db_path: Path | str, target_backup_path: Path | str) -> Path:
    """Perform consistent, verified online SQLite backup using the sqlite3 API.

    Guarantees:
    - Does NOT copy raw uncheckpointed WAL or SHM lock files.
    - Captures committed transactions consistent with active readers/writers.
    - Verifies schema, page count and ``PRAGMA integrity_check`` of the result
      before publishing it; an unverifiable backup raises and leaves no artifact.
    - Atomically replaces target backup path, cleaning up on any failure.
    """
    src = Path(source_db_path)
    target = Path(target_backup_path)
    if not src.exists():
        raise FileNotFoundError(f"SOURCE_DATABASE_NOT_FOUND:{src}")

    # A file smaller than a SQLite header is not a usable database. Backing it up
    # would yield a valid-looking but table-less database, so refuse up front
    # rather than report a success that would silently empty the dataset.
    if src.stat().st_size < _SQLITE_HEADER_BYTES:
        raise BackupVerificationError(
            f"SOURCE_DATABASE_TOO_SMALL_TO_BACKUP:{src}:{src.stat().st_size}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.parent / f"{target.name}.tmp.{uuid.uuid4().hex}"

    source_conn = None
    backup_conn = None
    try:
        try:
            source_conn = sqlite3.connect(str(src), timeout=10.0)
            backup_conn = sqlite3.connect(str(temp_target), timeout=10.0)
            source_conn.execute("BEGIN")
            expected_objects = _database_inventory(source_conn)
            expected_pages = _page_count(source_conn)
            source_conn.backup(backup_conn)
            # A WAL source stamps WAL mode into the copied header. Fold the
            # staged copy back to a rollback journal so the published target is a
            # single self-contained file with no -wal/-shm sidecars, which is
            # exactly the raw-WAL artifact this API exists to avoid.
            backup_conn.execute("PRAGMA journal_mode=DELETE;")
        except sqlite3.Error as exc:
            raise BackupVerificationError(f"SQLITE_BACKUP_FAILED:{src}:{exc}") from exc
        finally:
            if backup_conn is not None:
                backup_conn.close()
            if source_conn is not None:
                source_conn.close()

        _remove_sqlite_sidecars(temp_target)
        _verify_sqlite_backup(temp_target, expected_objects, expected_pages, src)
    except BaseException:
        # Never leave a half-written staging file beside the target: a retry must
        # see a clean destination directory.
        _remove_sqlite_sidecars(temp_target)
        temp_target.unlink(missing_ok=True)
        _fsync_directory(target.parent)
        raise

    try:
        # Windows rejects fsync on a read-only CRT descriptor. Opening the completed
        # backup read/write does not mutate it and gives fsync the required handle.
        with temp_target.open("r+b") as backup_stream:
            os.fsync(backup_stream.fileno())
        os.replace(temp_target, target)
        _fsync_directory(target.parent)
    except BaseException:
        _remove_sqlite_sidecars(temp_target)
        temp_target.unlink(missing_ok=True)
        _fsync_directory(target.parent)
        raise
    return target


def _publish_bundle_dir(staging_dir: Path, bundle_dir: Path) -> None:
    """Atomically make a fully built staging directory the published bundle."""
    if bundle_dir.exists():
        if any(bundle_dir.iterdir()):
            raise ValueError(f"BUNDLE_OUTPUT_NOT_EMPTY:{bundle_dir}")
        # os.replace cannot overwrite an existing directory on Windows, and the
        # only directory allowed here is one we already proved empty.
        bundle_dir.rmdir()
    os.replace(staging_dir, bundle_dir)
    _fsync_directory(bundle_dir.parent)


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
                    if fname.endswith(("-wal", "-shm", "-journal")):
                        continue
                    file_src = root_path / fname
                    file_rel = file_src.relative_to(src_root).as_posix()
                    safe_source = _assert_no_symlink_path(src_root, file_rel)
                    if file_rel in files_to_copy:
                        raise ValueError(f"DUPLICATE_NORMALIZED_PATH:{file_rel}")
                    files_to_copy[file_rel] = safe_source
        elif source_path.is_file():
            if source_path.name.endswith(("-wal", "-shm", "-journal")):
                continue
            if rel_path_str in files_to_copy:
                raise ValueError(f"DUPLICATE_NORMALIZED_PATH:{rel_path_str}")
            files_to_copy[rel_path_str] = source_path
        else:
            raise ValueError(f"UNSAFE_SOURCE_TYPE:{rel_path_str}")

    # Only now, after every source member and output path is validated, build the
    # bundle. Members are staged in a unique sibling directory and published with
    # a single atomic rename, so an interrupted run never leaves a populated
    # output directory and the backup can simply be re-run.
    bundle_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = bundle_dir.parent / f".{bundle_dir.name}.staging.{uuid.uuid4().hex}"
    staging_dir.mkdir()
    try:
        file_checksums: dict[str, str] = {}
        total_bytes = 0

        for file_rel, source_path in sorted(files_to_copy.items()):
            file_dest = staging_dir / file_rel
            if is_sqlite_database(source_path):
                backup_sqlite_db(source_path, file_dest)
            else:
                _copy_file_durable(source_path, file_dest)

            sha = compute_sha256(file_dest)
            file_checksums[file_rel] = sha
            total_bytes += file_dest.stat().st_size

        # Write transfer manifest last, so a member is never visible at the
        # published path before the manifest that makes it verifiable.
        now = datetime.now(UTC)
        bundle_id = f"bundle_{now.strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        manifest_data = {
            "bundle_id": bundle_id,
            "source_host": source_host,
            "created_at": now.isoformat(),
            "files": file_checksums,
            "total_bytes": total_bytes,
        }

        manifest_path = staging_dir / "transfer_manifest.json"
        temp_manifest = staging_dir / f".transfer_manifest.{uuid.uuid4().hex}.tmp"
        with temp_manifest.open("x", encoding="utf-8", newline="\n") as manifest_stream:
            json.dump(
                manifest_data, manifest_stream, sort_keys=True, separators=(",", ":")
            )
            manifest_stream.flush()
            os.fsync(manifest_stream.fileno())
        os.replace(temp_manifest, manifest_path)
        _fsync_directory(staging_dir)

        _publish_bundle_dir(staging_dir, bundle_dir)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        _fsync_directory(bundle_dir.parent)
        raise

    return bundle_dir
