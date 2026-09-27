from __future__ import annotations

import json
from pathlib import Path

import pytest

from indodax_lab.data.manifest import build_dataset_manifest, content_id_path_component
from scripts.research.measure_s09_pump_gap_ranges import _load_snapshot_manifest


def _write_manifest(root: Path) -> Path:
    manifest = build_dataset_manifest(
        [
            {
                "path": "bronze/example.parquet",
                "sha256": "a" * 64,
                "size_bytes": 10,
                "row_count": 1,
                "schema_identity": "sha256:schema",
            }
        ]
    )
    manifest_dir = root / "snapshots" / content_id_path_component(
        manifest["dataset_snapshot_id"]
    )
    manifest_dir.mkdir(parents=True)
    path = manifest_dir / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_snapshot_manifest_requires_canonical_content_id(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["dataset_snapshot_id"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="dataset_snapshot_id"):
        _load_snapshot_manifest(path)


def test_snapshot_manifest_directory_must_bind_content_id(tmp_path: Path) -> None:
    path = _write_manifest(tmp_path)
    wrong_dir = path.parent.parent / ("sha256_" + "0" * 64)
    wrong_dir.mkdir()
    moved = wrong_dir / path.name
    path.replace(moved)

    with pytest.raises(ValueError, match="SNAPSHOT_MANIFEST_DIRECTORY_ID_MISMATCH"):
        _load_snapshot_manifest(moved)
