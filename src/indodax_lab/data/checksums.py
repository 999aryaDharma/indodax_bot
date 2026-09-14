"""Checksum helpers for immutable research artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(value: bytes) -> str:
    """Return the lowercase SHA-256 digest for immutable content."""
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Stream a file into SHA-256 without loading a partition into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
