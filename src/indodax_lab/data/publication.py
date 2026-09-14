"""Shared durable no-clobber publication primitives for immutable lab artifacts."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path

from .manifest import ImmutableContentConflictError


class IndeterminatePublicationError(RuntimeError):
    """A rollback failed, so the caller cannot safely infer publication state."""


def fsync_directory(path: Path) -> None:
    """Durably record the current namespace state of one directory."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_directory_tree(
    directory: Path, *, fsync_directory_fn: Callable[[Path], None] = fsync_directory
) -> None:
    """Create missing namespace levels and fsync every new parent entry."""
    missing: list[Path] = []
    candidate = directory
    while not candidate.exists():
        missing.append(candidate)
        candidate = candidate.parent
    directory.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):
        fsync_directory_fn(created.parent)


def remove_entry(
    path: Path, *, fsync_directory_fn: Callable[[Path], None] = fsync_directory
) -> None:
    """Unlink one entry and durably record its removal."""
    path.unlink()
    fsync_directory_fn(path.parent)


def best_effort_remove_entry(
    path: Path, *, fsync_directory_fn: Callable[[Path], None] = fsync_directory
) -> None:
    """Attempt cleanup without replacing the operation's original exception."""
    try:
        remove_entry(path, fsync_directory_fn=fsync_directory_fn)
    except FileNotFoundError:
        return
    except OSError:
        pass


def rollback_or_raise_indeterminate(
    path: Path,
    operation: str,
    *,
    fsync_directory_fn: Callable[[Path], None] = fsync_directory,
) -> None:
    """Durably remove a new final or report that publication state is unknown."""
    try:
        remove_entry(path, fsync_directory_fn=fsync_directory_fn)
    except OSError as error:
        raise IndeterminatePublicationError(
            f"cannot establish storage state after {operation} failed: {path}"
        ) from error


def publish_existing_partial(
    partial_path: Path,
    final_path: Path,
    *,
    same_content: Callable[[Path], bool],
    conflict_message: str,
    fsync_directory_fn: Callable[[Path], None] = fsync_directory,
    rollback_fn: Callable[[Path, str], None] | None = None,
) -> bool:
    """Link a flushed partial without replacement and fsync new or reused namespace state."""
    published_new = False
    try:
        os.link(partial_path, final_path)
        published_new = True
    except FileExistsError as error:
        if not same_content(final_path):
            raise ImmutableContentConflictError(conflict_message) from error
    try:
        fsync_directory_fn(final_path.parent)
    except OSError:
        if published_new:
            if rollback_fn is None:
                rollback_or_raise_indeterminate(
                    final_path,
                    "immutable namespace fsync",
                    fsync_directory_fn=fsync_directory_fn,
                )
            else:
                rollback_fn(final_path, "immutable namespace fsync")
        raise
    return published_new


def publish_immutable_bytes(
    path: Path,
    content: bytes,
    *,
    fsync_directory_fn: Callable[[Path], None] = fsync_directory,
) -> bool:
    """Flush, no-clobber publish, durably clean partial, and roll back failures."""
    ensure_directory_tree(path.parent, fsync_directory_fn=fsync_directory_fn)
    partial_path = path.parent / f".{uuid.uuid4().hex}.partial"
    published_new = False
    try:
        with partial_path.open("xb") as sink:
            sink.write(content)
            sink.flush()
            os.fsync(sink.fileno())
        published_new = publish_existing_partial(
            partial_path,
            path,
            same_content=lambda existing: existing.read_bytes() == content,
            conflict_message=f"immutable path already contains different content: {path}",
            fsync_directory_fn=fsync_directory_fn,
        )
        try:
            remove_entry(partial_path, fsync_directory_fn=fsync_directory_fn)
        except OSError:
            if published_new:
                rollback_or_raise_indeterminate(
                    path,
                    "immutable partial cleanup",
                    fsync_directory_fn=fsync_directory_fn,
                )
            raise
    except Exception:
        best_effort_remove_entry(partial_path, fsync_directory_fn=fsync_directory_fn)
        raise
    return published_new
