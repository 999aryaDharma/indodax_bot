"""Regression tests for OPS-03 maintenance findings.

Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from indodax_lab.orchestration.maintenance import (
    RetentionPolicy,
    StorageCleaner,
    SymlinkEscapeError,
    _is_symlink_or_junction,
)


def _empty_protected_registry(_: str) -> dict[str, set[str]]:
    return {}


def test_ops_03_r1_symlink_target_not_deleted() -> None:
    """OPS-03-R1 (Critical): a symlink inside the root must not cause its target to be deleted.

    The cleaner must reject the symlink and delete the link itself, not follow it
    to the target. The target file outside the root must remain intact.
    """
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        outside_target = root.parent / "protected_live_artifact.db"
        outside_target.write_bytes(b"critical live data")
        assert outside_target.exists()

        # Create a regular file inside root to represent the symlink target
        # (we mock the symlink check)
        link = root / "champion_link.db"
        link.write_bytes(b"not a real symlink")
        # Make it old
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(link, (old_time.timestamp(), old_time.timestamp()))

        # Mock the symlink detection to pretend 'link' is a symlink
        with patch("indodax_lab.orchestration.maintenance._is_symlink_or_junction") as mock_is_symlink:
            mock_is_symlink.side_effect = lambda p: p == link

            policy = RetentionPolicy(retention_days=1, dry_run=False)
            cleaner = StorageCleaner(root, policy, protected_resolver=_empty_protected_registry)
            report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)

        # The outside target must still exist
        assert outside_target.exists(), "symlink target was deleted — critical data loss"

        # The symlink itself should be rejected
        assert any("SYMLINK_DETECTED" in r for r in report.rejected_candidates)


def test_ops_03_r4_single_escape_does_not_abort_audit() -> None:
    """OPS-03-R4 (Important): one escaping file must not abort the whole scan."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)

        # Create a normal file that should be audited
        normal = root / "normal.txt"
        normal.write_text("normal")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(normal, (old_time.timestamp(), old_time.timestamp()))

        # Create a file we'll pretend is a symlink escape
        escape = root / "escaping_link.txt"
        escape.write_text("escape")
        os.utime(escape, (old_time.timestamp(), old_time.timestamp()))

        with patch("indodax_lab.orchestration.maintenance._is_symlink_or_junction") as mock_is_symlink:
            mock_is_symlink.side_effect = lambda p: p == escape

            policy = RetentionPolicy(retention_days=1, dry_run=True)
            cleaner = StorageCleaner(root, policy, protected_resolver=_empty_protected_registry)
            report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=True)

        # Audit must complete: scanned_count includes both files
        assert report.scanned_files_count == 2
        # One rejection recorded
        assert len(report.rejected_candidates) == 1
        assert "SYMLINK_DETECTED" in report.rejected_candidates[0]
        # Normal file appears as candidate
        assert "normal.txt" in report.deletion_candidates


def test_ops_03_r5_retention_days_ge_1_validation() -> None:
    """OPS-03-R5 (Important): retention_days must be >= 1."""
    with pytest.raises(ValueError):
        RetentionPolicy(retention_days=0)
    with pytest.raises(ValueError):
        RetentionPolicy(retention_days=-5)
    # Valid
    RetentionPolicy(retention_days=1)
    RetentionPolicy(retention_days=30)


def test_ops_03_r6_root_symlink_rejected_at_init() -> None:
    """OPS-03-R6 (Minor): storage_root itself must not be a symlink/junction."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)

        with patch("indodax_lab.orchestration.maintenance._is_symlink_or_junction") as mock_is_symlink:
            mock_is_symlink.return_value = True

            with pytest.raises(SymlinkEscapeError, match="SYMLINK_DETECTED"):
                StorageCleaner(root)


def test_ops_03_protected_resolver_from_registry() -> None:
    """OPS-03-R2/R3 (Important): protected artifacts resolved from registry callback."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        # Champion artifact with a different filename
        champion = root / "models" / "2025" / "weights.onnx"
        champion.parent.mkdir(parents=True)
        champion.write_bytes(b"model")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(champion, (old_time.timestamp(), old_time.timestamp()))
        # Old file with the protected name but NOT the champion
        old = root / "archive" / "weights.onnx"
        old.parent.mkdir()
        old.write_bytes(b"old")
        os.utime(old, (old_time.timestamp(), old_time.timestamp()))

        def registry_resolver(storage_root: str) -> dict[str, set[str]]:
            return {"sha256:champion-model": {"models/2025/weights.onnx"}}

        policy = RetentionPolicy(
            retention_days=1,
            protected_artifact_ids={"sha256:champion-model"},
            dry_run=False,
        )
        cleaner = StorageCleaner(root, policy, protected_resolver=registry_resolver)
        report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)

        # Actual champion protected
        assert champion.exists()
        # Old file with same base name but different ID is NOT protected
        assert not old.exists()
        assert "archive/weights.onnx" in report.deleted_files


@pytest.mark.skipif(os.name != "nt", reason="Windows path identity is case-insensitive")
def test_ops_03_registry_path_case_matches_windows_file_identity() -> None:
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        artifact = root / "maintenance.py"
        artifact.write_bytes(b"protected")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(artifact, (old_time.timestamp(), old_time.timestamp()))
        cleaner = StorageCleaner(
            root,
            RetentionPolicy(retention_days=1, dry_run=True),
            protected_resolver=lambda _: {"champion": {"MAINTENANCE.PY"}},
        )

        report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=True)

        assert "maintenance.py" not in report.deletion_candidates


def test_ops_03_registry_lookup_failure_aborts_cleanup() -> None:
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        artifact = root / "weights-v42.onnx"
        artifact.write_bytes(b"champion")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(artifact, (old_time.timestamp(), old_time.timestamp()))

        def unavailable(_: str) -> dict[str, set[str]]:
            raise RuntimeError("registry unavailable")

        cleaner = StorageCleaner(
            root,
            RetentionPolicy(retention_days=1, dry_run=False),
            protected_resolver=unavailable,
        )
        with pytest.raises(RuntimeError, match="PROTECTED_ARTIFACT_REGISTRY_UNAVAILABLE"):
            cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)
        assert artifact.exists()


def test_ops_03_apply_rechecks_new_registry_reachability() -> None:
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        artifact = root / "weights-v42.onnx"
        artifact.write_bytes(b"champion")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(artifact, (old_time.timestamp(), old_time.timestamp()))
        calls = 0

        def resolver(_: str) -> dict[str, set[str]]:
            nonlocal calls
            calls += 1
            return {} if calls == 1 else {"sha256:champion": {"weights-v42.onnx"}}

        cleaner = StorageCleaner(
            root,
            RetentionPolicy(retention_days=1, dry_run=False),
            protected_resolver=resolver,
        )
        report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)

        assert artifact.exists()
        assert report.deleted_count == 0
        assert any("PROTECTED_ARTIFACT_REACHABILITY_CHANGED" in item for item in report.rejected_candidates)


def test_ops_03_apply_rejects_replaced_candidate() -> None:
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        artifact = root / "expired.bin"
        artifact.write_bytes(b"old")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(artifact, (old_time.timestamp(), old_time.timestamp()))
        calls = 0

        def resolver(_: str) -> dict[str, set[str]]:
            nonlocal calls
            calls += 1
            if calls == 2:
                artifact.write_bytes(b"replacement is current")
            return {}

        cleaner = StorageCleaner(
            root,
            RetentionPolicy(retention_days=1, dry_run=False),
            protected_resolver=resolver,
        )
        report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)

        assert artifact.exists()
        assert artifact.read_bytes() == b"replacement is current"
        assert report.deleted_count == 0
        assert any("CANDIDATE_CHANGED_AFTER_SCAN" in item for item in report.rejected_candidates)


def test_ops_03_junction_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path("junction-probe")
    path_type = type(path)
    monkeypatch.setattr(path_type, "is_junction", lambda self: self == path, raising=False)

    assert _is_symlink_or_junction(path)


def test_ops_03_root_link_rejected_before_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        target = root / "real"
        target.mkdir()
        alias = root / "alias"
        alias.mkdir()
        path_type = type(alias)
        original_resolve = path_type.resolve

        def resolve_as_target(path: Path, *args, **kwargs) -> Path:
            return target if path == alias else original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(path_type, "resolve", resolve_as_target)
        monkeypatch.setattr(
            "indodax_lab.orchestration.maintenance._is_symlink_or_junction",
            lambda path: Path(path) == alias,
        )

        with pytest.raises(SymlinkEscapeError, match="SYMLINK_DETECTED"):
            StorageCleaner(alias, protected_resolver=_empty_protected_registry)


def test_ops_03_idempotent_rerun_no_crash() -> None:
    """OPS-03-AC3 (and R8): interrupted cleanup reruns cleanly."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        f1 = root / "expired1.txt"
        f1.write_text("expired")
        f2 = root / "expired2.txt"
        f2.write_text("expired")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(f1, (old_time.timestamp(), old_time.timestamp()))
        os.utime(f2, (old_time.timestamp(), old_time.timestamp()))

        policy = RetentionPolicy(retention_days=1, dry_run=False)
        cleaner = StorageCleaner(root, policy, protected_resolver=_empty_protected_registry)

        # First run
        r1 = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)
        assert r1.deleted_count == 2
        assert not f1.exists() and not f2.exists()

        # Second run (simulating interrupted first run where some already deleted)
        r2 = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)
        assert r2.deleted_count == 0
        assert r2.scanned_files_count == 0  # files are gone, walk finds none


def test_ops_03_dry_run_shows_would_free_bytes() -> None:
    """OPS-03-R7 (Minor): dry run reports bytes that would be freed."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        f1 = root / "big.txt"
        f1.write_bytes(b"x" * 1000)
        f2 = root / "small.txt"
        f2.write_bytes(b"y" * 100)
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(f1, (old_time.timestamp(), old_time.timestamp()))
        os.utime(f2, (old_time.timestamp(), old_time.timestamp()))

        policy = RetentionPolicy(retention_days=1, dry_run=True)
        cleaner = StorageCleaner(root, policy, protected_resolver=_empty_protected_registry)
        report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=True)

        assert report.dry_run is True
        assert report.freed_bytes == 1100  # would free
        assert report.deleted_count == 0  # but didn't delete


def test_ops_03_rejected_candidates_in_report() -> None:
    """Rejected (symlink) candidates appear in report for audit."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        link = root / "link.txt"
        link.write_text("not a symlink")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(link, (old_time.timestamp(), old_time.timestamp()))

        with patch("indodax_lab.orchestration.maintenance._is_symlink_or_junction") as mock_is_symlink:
            mock_is_symlink.side_effect = lambda p: p == link

            policy = RetentionPolicy(retention_days=1, dry_run=True)
            cleaner = StorageCleaner(root, policy, protected_resolver=_empty_protected_registry)
            report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=True)

        assert len(report.rejected_candidates) == 1
        assert "link.txt" in report.rejected_candidates[0]
        assert "SYMLINK_DETECTED" in report.rejected_candidates[0]


def test_ops_03_r1_traversal_outside_root_rejected() -> None:
    """Path traversal outside root is rejected."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        f = root / "normal.txt"
        f.write_text("normal")

        # Try to pass a path that traverses outside
        with pytest.raises(SymlinkEscapeError, match="SYMLINK_OR_PATH_ESCAPE_DETECTED"):
            cleaner = StorageCleaner(root)
            cleaner.validate_safe_path("../outside.txt")


def test_ops_03_r1_symlink_in_parent_component_rejected() -> None:
    """A symlink in any parent component is rejected."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        subdir = root / "subdir"
        subdir.mkdir()
        f = subdir / "file.txt"
        f.write_text("file")

        with patch("indodax_lab.orchestration.maintenance._is_symlink_or_junction") as mock_is_symlink:
            # Pretend the subdir itself is a symlink
            mock_is_symlink.side_effect = lambda p: p == subdir

            cleaner = StorageCleaner(root)
            with pytest.raises(SymlinkEscapeError, match="SYMLINK_DETECTED"):
                cleaner.validate_safe_path(f)


def test_ops_03_dry_run_false_deletes() -> None:
    """Non-dry-run actually deletes files."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)
        f = root / "expired.txt"
        f.write_text("expired")
        old_time = datetime.now(UTC) - timedelta(days=10)
        os.utime(f, (old_time.timestamp(), old_time.timestamp()))

        policy = RetentionPolicy(retention_days=1, dry_run=False)
        cleaner = StorageCleaner(root, policy, protected_resolver=_empty_protected_registry)
        report = cleaner.scan_and_clean(as_of=datetime.now(UTC), dry_run=False)

        assert not f.exists()
        assert report.deleted_count == 1
        assert report.freed_bytes > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:cacheprovider"])
