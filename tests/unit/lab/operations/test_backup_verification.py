"""Regression tests for the OPS-02 backup/restore review findings.

Spec: ``docs/specs/17-operations-security-and-recovery.md`` -> OPS-02,
"manifest + checksums + SQLite consistent backup -> staged copy -> verify ->
atomic publish". The declared pipeline contains a *verify* step and an *atomic
publish* step; both were missing.

Findings covered:

- **OPS-02-F1 (Important)**: ``backup_sqlite_db`` performs no post-backup
  verification. It copies with the SQLite backup API, fsyncs and renames into
  place, then returns success. A zero-byte or otherwise empty source database --
  a path pre-created by a supervisor, or truncated to zero by a failed
  checkpoint restore -- yields a "successful" 4096-byte backup containing no
  tables at all, and restoring it silently empties the dataset. If the backup
  API returns without copying anything, the same false success is reported. On
  any failure the ``<target>.tmp.<uuid>`` staging file is also leaked next to
  the target, and the raised error is a bare ``sqlite3.DatabaseError`` that
  names neither the source nor the nature of the failure.
- **OPS-02-F2 (Important)**: ``create_backup_bundle`` copies directly into the
  final output directory. An interruption part-way through the copy loop leaves
  a populated directory that contains no ``transfer_manifest.json``, and because
  reruns are guarded by ``BUNDLE_OUTPUT_NOT_EMPTY`` the operator can no longer
  re-run the backup at all without hand-deleting the directory. A partial bundle
  is also indistinguishable from a complete one by a non-empty check alone.

Isolation: every test writes only under ``tmp_path`` and uses throwaway SQLite
files created in-process. No real data directory, no live service, no network,
no production database, no ledger and no orders are touched.
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest

import indodax_lab.operations.backup as backup_mod
from indodax_lab.operations.backup import backup_sqlite_db, create_backup_bundle


# Resolved lazily so the suite still collects (and fails on behaviour) against a
# module that does not yet export the typed fail-closed error.
_BACKUP_ERRORS: tuple[type[BaseException], ...] = tuple(
    error
    for error in (
        getattr(backup_mod, "BackupVerificationError", None),
        sqlite3.DatabaseError,
        RuntimeError,
    )
    if isinstance(error, type) and issubclass(error, BaseException)
)


def _call_expecting_failure(func, *args, **kwargs) -> BaseException | None:
    """Call ``func`` and return the exception it raised, or ``None`` if it succeeded."""
    try:
        func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - the failure mode is the assertion
        return exc
    return None


def _make_wal_db(path: Path, rows: int = 5) -> Path:
    """Create a real WAL-mode SQLite database with committed content."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL);")
    conn.executemany(
        "INSERT INTO jobs VALUES (?, ?)",
        [(f"job_{index:04d}", f"payload-{index}" * 32) for index in range(rows)],
    )
    conn.commit()
    conn.close()
    return path


def _strays(directory: Path, ignore: set[str]) -> list[str]:
    return sorted(entry.name for entry in directory.iterdir() if entry.name not in ignore)


# ---------------------------------------------------------------------------
# OPS-02-F1: a backup is only "successful" if it is verified
# ---------------------------------------------------------------------------


def test_backup_refuses_to_report_success_for_empty_source_database(tmp_path: Path) -> None:
    """OPS-02-F1: a zero-byte source must not yield a 'successful' empty backup."""
    empty_source = tmp_path / "queue.db"
    empty_source.write_bytes(b"")
    target = tmp_path / "out" / "queue.db"

    failure = _call_expecting_failure(backup_sqlite_db, empty_source, target)

    assert failure is not None, (
        "backup_sqlite_db reported success for a zero-byte source database; the "
        "resulting backup is a 4096-byte database with no tables, so restoring it "
        "silently empties the dataset"
    )
    assert not target.exists(), (
        "a refused backup still published a target file: "
        f"{target.exists() and target.stat().st_size} bytes"
    )


def test_backup_detects_empty_result_from_backup_api(tmp_path: Path) -> None:
    """OPS-02-F1: a backup API that copies nothing must not be reported as success."""
    source = _make_wal_db(tmp_path / "queue.db")
    target = tmp_path / "out" / "queue.db"

    real_connect = sqlite3.connect

    class _NoOpBackupConnection:
        """A genuine SQLite connection whose ``backup()`` silently copies nothing."""

        def __init__(self, real: sqlite3.Connection) -> None:
            self._real = real

        def backup(self, *args, **kwargs):  # noqa: ANN002, ANN003, ARG002
            return None

        def __getattr__(self, name):  # noqa: ANN002
            return getattr(self._real, name)

        def close(self) -> None:
            self._real.close()

    def fake_connect(path, **kwargs):  # noqa: ANN001, ANN003, ARG001
        return _NoOpBackupConnection(real_connect(path, **kwargs))

    with patch.object(backup_mod.sqlite3, "connect", side_effect=fake_connect):
        failure = _call_expecting_failure(backup_sqlite_db, source, target)

    assert failure is not None, (
        "backup_sqlite_db reported success even though the backup API produced an "
        "empty database with none of the source schema"
    )
    assert not target.exists(), "an unverified backup was still published to the target"


def test_failed_backup_leaves_no_staging_or_target_artifact(tmp_path: Path) -> None:
    """OPS-02-F1: a failed backup must clean up its temp file next to the target."""
    corrupt_source = tmp_path / "queue.db"
    corrupt_source.write_bytes(b"NOT A SQLITE DATABASE" * 64)
    out_dir = tmp_path / "out"
    target = out_dir / "queue.db"

    failure = _call_expecting_failure(backup_sqlite_db, corrupt_source, target)

    assert failure is not None, "a corrupt source database was backed up as success"
    assert not target.exists(), "a corrupt source still produced a published target"
    strays = _strays(out_dir, ignore=set())
    assert not strays, (
        "a failed backup leaked staging artifacts into the target directory, so a "
        f"retry directory is polluted: {strays}"
    )


def test_verified_backup_publishes_a_faithful_copy(tmp_path: Path) -> None:
    """OPS-02-F1 positive control: a healthy source still backs up correctly."""
    source = _make_wal_db(tmp_path / "queue.db", rows=8)
    target = tmp_path / "out" / "queue.db"

    result = backup_sqlite_db(source, target)

    assert result == target
    assert not _strays(target.parent, ignore={target.name})

    verified = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        assert verified.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        objects = verified.execute(
            "SELECT type, name FROM sqlite_master ORDER BY name"
        ).fetchall()
        rows = verified.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    finally:
        verified.close()

    assert ("table", "jobs") in objects, "the verified backup lost the source schema"
    assert rows == 8, "the verified backup did not carry every committed row"


# ---------------------------------------------------------------------------
# OPS-02-F2: bundle publication is atomic, so an interruption is recoverable
# ---------------------------------------------------------------------------


def _flaky_bundle_source(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.bin").write_bytes(b"a" * 64)
    (source / "b.bin").write_bytes(b"b" * 64)
    (source / "c.bin").write_bytes(b"c" * 64)
    return source, tmp_path / "bundle", source


def _inject_copy_failure(fail_on_call: int = 2):
    """Patch the durable copy helper so the Nth file copy aborts the bundle."""
    real_copy = backup_mod._copy_file_durable
    calls = {"n": 0}

    def flaky_copy(source: Path, destination: Path) -> None:
        calls["n"] += 1
        if calls["n"] == fail_on_call:
            raise OSError("injected mid-bundle copy failure")
        real_copy(source, destination)

    return patch.object(backup_mod, "_copy_file_durable", side_effect=flaky_copy)


def test_interrupted_bundle_publishes_no_partial_output(tmp_path: Path) -> None:
    """OPS-02-F2: an interrupted bundle must not leave a populated output dir."""
    source, bundle_dir, _ = _flaky_bundle_source(tmp_path)

    with _inject_copy_failure():
        _call_expecting_failure(
            create_backup_bundle, source, ["a.bin", "b.bin", "c.bin"], bundle_dir
        )

    if bundle_dir.exists():
        assert not any(bundle_dir.iterdir()), (
            "create_backup_bundle left a populated directory after an interruption; "
            f"contents: {sorted(p.name for p in bundle_dir.iterdir())}"
        )
    strays = _strays(tmp_path, ignore={"source"})
    assert not strays, (
        "create_backup_bundle left staging debris beside the output directory: "
        f"{strays}"
    )


def test_bundle_can_be_rerun_after_an_interruption(tmp_path: Path) -> None:
    """OPS-02-F2: an interrupted bundle must not permanently block the retry."""
    source, bundle_dir, _ = _flaky_bundle_source(tmp_path)
    members = ["a.bin", "b.bin", "c.bin"]

    with _inject_copy_failure():
        _call_expecting_failure(
            create_backup_bundle, source, members, bundle_dir
        )

    rerun_failure = _call_expecting_failure(
        create_backup_bundle, source, members, bundle_dir
    )

    assert rerun_failure is None, (
        "a bundle could not be re-run after an interruption, so a single transient "
        f"copy error permanently blocks backups: {rerun_failure!r}"
    )

    manifest = bundle_dir / "transfer_manifest.json"
    assert manifest.exists(), "the re-run bundle has no manifest and is not verifiable"
    for member in members:
        assert (bundle_dir / member).read_bytes() == (source / member).read_bytes()


def test_bundle_output_directory_is_published_atomically(tmp_path: Path) -> None:
    """OPS-02-F2: every bundle file is durable before the output dir becomes visible."""
    source, bundle_dir, _ = _flaky_bundle_source(tmp_path)
    observed: list[tuple[str, bool]] = []

    real_copy = backup_mod._copy_file_durable

    def observing_copy(src: Path, destination: Path) -> None:
        real_copy(src, destination)
        observed.append(
            (str(destination), (bundle_dir / "transfer_manifest.json").exists())
        )

    with patch.object(backup_mod, "_copy_file_durable", side_effect=observing_copy):
        create_backup_bundle(source, ["a.bin", "b.bin", "c.bin"], bundle_dir)

    assert observed, "the bundle copied nothing"
    early_manifest = [path for path, manifest_seen in observed if manifest_seen]
    assert not early_manifest, (
        "bundle members became visible at the final output path before the manifest "
        f"was written: {early_manifest}"
    )
    assert (bundle_dir / "transfer_manifest.json").exists()


def test_existing_non_empty_bundle_output_is_still_rejected(tmp_path: Path) -> None:
    """Guard: the atomic-publish change must not weaken the pre-existing guard."""
    source, bundle_dir, _ = _flaky_bundle_source(tmp_path)
    bundle_dir.mkdir()
    (bundle_dir / "leftover.bin").write_bytes(b"stale")

    failure = _call_expecting_failure(
        create_backup_bundle, source, ["a.bin"], bundle_dir
    )

    assert failure is not None, (
        "create_backup_bundle overwrote a pre-existing non-empty output directory"
    )
    assert (bundle_dir / "leftover.bin").read_bytes() == b"stale"
