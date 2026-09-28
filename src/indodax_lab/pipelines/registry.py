"""Draft store and service facade for the typed pipeline composer (RW2-03).

Local SQLite drafts with revision compare-and-swap and immutable, no-clobber
publication. Component references resolve only through the published RW2-01
strategy store and the verified RW2-02 model registry; no execution occurs.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path

from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.contracts.workbench import PipelineManifest
from indodax_lab.models.registry import ModelRegistry
from indodax_lab.pipelines.validation import (
    PipelineValidationError,
    ValidationReport,
    canonicalize,
    export_yaml,
    import_yaml,
    validate_manifest,
)
from indodax_lab.strategies.base import DraftRef
from indodax_lab.strategies.store import StrategyService


class PipelineDraftStore:
    """SQLite-backed pipeline drafts and immutable publications."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS pipeline_drafts (
                    draft_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    digest TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('DRAFT', 'PUBLISHED'))
                )"""
            )
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS pipeline_publications (
                    pipeline_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    PRIMARY KEY(pipeline_id, version)
                )"""
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _ref(manifest: PipelineManifest, digest: str) -> ArtifactRef:
        return ArtifactRef(
            kind="pipeline_manifest",
            id=manifest.pipeline_id,
            version=manifest.version,
            sha256=digest,
            schema_version=manifest.schema_version,
        )

    def create_draft(self, manifest: PipelineManifest) -> DraftRef:
        digest = manifest_digest(manifest)
        draft_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    """INSERT INTO pipeline_drafts
                       (draft_id, revision, digest, manifest_json, state)
                       VALUES (?, 1, ?, ?, 'DRAFT')""",
                    (draft_id, digest, manifest.model_dump_json()),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return DraftRef(id=draft_id, revision=1, digest=digest)

    def get_draft(self, draft_id: str) -> tuple[DraftRef, PipelineManifest]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pipeline_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            raise KeyError("PIPELINE_DRAFT_NOT_FOUND")
        manifest = PipelineManifest.model_validate_json(row["manifest_json"])
        if manifest_digest(manifest) != row["digest"]:
            raise ValueError("PIPELINE_DRAFT_DIGEST_MISMATCH")
        return DraftRef(id=draft_id, revision=row["revision"], digest=row["digest"]), manifest

    def update_draft(
        self, draft_id: str, expected_revision: int, manifest: PipelineManifest
    ) -> DraftRef:
        digest = manifest_digest(manifest)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT revision, state FROM pipeline_drafts WHERE draft_id = ?",
                    (draft_id,),
                ).fetchone()
                if row is None:
                    raise KeyError("PIPELINE_DRAFT_NOT_FOUND")
                if row["state"] != "DRAFT":
                    raise ValueError("PIPELINE_DRAFT_ALREADY_PUBLISHED")
                if row["revision"] != expected_revision:
                    raise ValueError("STALE_DRAFT_REVISION")
                revision = expected_revision + 1
                self._conn.execute(
                    """UPDATE pipeline_drafts
                       SET revision = ?, digest = ?, manifest_json = ?
                       WHERE draft_id = ? AND revision = ?""",
                    (revision, digest, manifest.model_dump_json(), draft_id, expected_revision),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return DraftRef(id=draft_id, revision=revision, digest=digest)

    def publish(self, draft_id: str, expected_revision: int) -> ArtifactRef:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT * FROM pipeline_drafts WHERE draft_id = ?", (draft_id,)
                ).fetchone()
                if row is None:
                    raise KeyError("PIPELINE_DRAFT_NOT_FOUND")
                if row["revision"] != expected_revision:
                    raise ValueError("STALE_DRAFT_REVISION")
                manifest = PipelineManifest.model_validate_json(row["manifest_json"])
                digest = manifest_digest(manifest)
                if digest != row["digest"]:
                    raise ValueError("PIPELINE_DRAFT_DIGEST_MISMATCH")
                existing = self._conn.execute(
                    "SELECT digest FROM pipeline_publications "
                    "WHERE pipeline_id = ? AND version = ?",
                    (manifest.pipeline_id, manifest.version),
                ).fetchone()
                if existing is not None and existing["digest"] != digest:
                    raise ValueError("IMMUTABLE_VERSION_CONFLICT")
                if existing is None:
                    self._conn.execute(
                        """INSERT INTO pipeline_publications
                           (pipeline_id, version, digest, manifest_json) VALUES (?, ?, ?, ?)""",
                        (manifest.pipeline_id, manifest.version, digest, row["manifest_json"]),
                    )
                self._conn.execute(
                    "UPDATE pipeline_drafts SET state = 'PUBLISHED' WHERE draft_id = ?",
                    (draft_id,),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._ref(manifest, digest)

    def get_published(self, ref: ArtifactRef) -> PipelineManifest:
        with self._lock:
            row = self._conn.execute(
                "SELECT manifest_json, digest FROM pipeline_publications "
                "WHERE pipeline_id = ? AND version = ?",
                (ref.id, ref.version),
            ).fetchone()
        if row is None:
            raise KeyError("PIPELINE_ARTIFACT_NOT_FOUND")
        if row["digest"] != ref.sha256:
            raise ValueError("PIPELINE_ARTIFACT_REF_MISMATCH")
        manifest = PipelineManifest.model_validate_json(row["manifest_json"])
        if manifest_digest(manifest) != ref.sha256:
            raise ValueError("PIPELINE_ARTIFACT_DIGEST_MISMATCH")
        return manifest.model_copy(deep=True)


class PipelineService:
    """Validated facade over pipeline drafts, publication and components."""

    def __init__(
        self,
        db_path: str | Path,
        strategies: StrategyService,
        models: ModelRegistry,
    ) -> None:
        self.store = PipelineDraftStore(db_path)
        self.strategies = strategies
        self.models = models

    def validate(self, manifest: PipelineManifest) -> ValidationReport:
        return validate_manifest(manifest, strategies=self.strategies, models=self.models)

    def create(self, manifest: PipelineManifest) -> DraftRef:
        report = self.validate(manifest)
        if not report.valid:
            raise PipelineValidationError(report)
        return self.store.create_draft(canonicalize(manifest))

    def update(
        self, draft_id: str, expected_revision: int, manifest: PipelineManifest
    ) -> DraftRef:
        report = self.validate(manifest)
        if not report.valid:
            raise PipelineValidationError(report)
        return self.store.update_draft(draft_id, expected_revision, canonicalize(manifest))

    def publish(self, draft_id: str, revision: int) -> ArtifactRef:
        _, manifest = self.store.get_draft(draft_id)
        report = self.validate(manifest)
        if not report.valid:
            raise PipelineValidationError(report)
        return self.store.publish(draft_id, revision)

    def clone(self, ref: DraftRef | ArtifactRef) -> DraftRef:
        if isinstance(ref, ArtifactRef):
            manifest = self.store.get_published(ref)
            manifest = manifest.model_copy(
                deep=True,
                update={"version": f"{manifest.version}-clone-{uuid.uuid4().hex[:8]}"},
            )
        else:
            current, manifest = self.store.get_draft(ref.id)
            if current.digest != ref.digest:
                raise ValueError("PIPELINE_DRAFT_REF_MISMATCH")
        return self.store.create_draft(manifest)

    def import_yaml(self, text: str) -> PipelineManifest:
        return import_yaml(text)

    def export_yaml(self, manifest: PipelineManifest) -> str:
        return export_yaml(manifest)
