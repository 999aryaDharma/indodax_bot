"""Durable draft and immutable publication service for allowlisted strategies."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from indodax_lab.contracts.identity import ArtifactRef, canonical_bytes, manifest_digest
from indodax_lab.contracts.workbench import StrategyManifest
from indodax_lab.strategies.base import (
    DraftRef,
    StrategyComponentMetadata,
)
from indodax_lab.strategies.registry import (
    builtin_strategy_implementation,
    component_id_for_strategy,
)


class _RiskProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_position_pct: Decimal = Field(default=Decimal("0.25"), gt=0, le=1)
    stop_loss_pct: Decimal = Field(default=Decimal("0.02"), gt=0, le=1)


class _PairParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pair: str | None = Field(default=None, pattern=r"^[a-z0-9]+_[a-z0-9]+$")
    risk_profile: _RiskProfile = Field(default_factory=_RiskProfile)


class _C02Parameters(_PairParameters):
    ema_fast_period: int = Field(default=20, gt=0)
    ema_slow_period: int = Field(default=50, gt=0)
    atr_multiplier: float = Field(default=1.5, gt=0)
    desired_qty: Decimal = Field(default=Decimal("0.1"), gt=0)


class _C07Parameters(_PairParameters):
    bb_std: float = Field(default=2.0, gt=0)
    rsi_oversold: float = Field(default=30.0, gt=0, le=100)
    adx_trend_threshold: float = Field(default=0.25, ge=0)
    atr_multiplier: float = Field(default=1.5, gt=0)
    desired_qty: Decimal = Field(default=Decimal("0.1"), gt=0)
    di_spread_threshold: float = -0.15
    sideways_regimes: list[str] = Field(default_factory=lambda: ["sideways", "ranging", "neutral"])
    downtrend_regimes: list[str] = Field(default_factory=lambda: ["downtrend", "strong_downtrend"])


_PARAMETER_MODELS: dict[str, type[BaseModel]] = {"C02": _C02Parameters, "C07": _C07Parameters}
_COMPONENTS: dict[str, tuple[str, tuple[str, ...], dict[str, Any]]] = {
    "C02": (
        "trend_pullback",
        ("close", "ema_fast", "ema_slow", "low", "atr_14"),
        {"kind": "atr_stop", "version": "v1", "atr_parameter": "atr_multiplier"},
    ),
    "C07": (
        "mean_reversion",
        ("close", "bb_width", "bb_z", "rsi_14", "adx_14", "di_spread_14", "regime", "atr_14"),
        {
            "kind": "atr_stop_and_target",
            "version": "v1",
            "atr_parameter": "atr_multiplier",
        },
    ),
}
_SEED_FILE = Path(__file__).resolve().parents[3] / "configs" / "strategies" / "seeds.yaml"
_CONFIG_DIR = _SEED_FILE.parent
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _parameter_schema_hash(component_id: str) -> str:
    schema = _PARAMETER_MODELS[component_id].model_json_schema()
    return hashlib.sha256(canonical_bytes({"version": "v1", "schema": schema})).hexdigest()


def _exit_contract_version(contract: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_bytes(contract)).hexdigest()[:16]
    return f"{contract['version']}-{digest}"


def _json(model: BaseModel) -> str:
    return canonical_bytes(model).decode("utf-8")


def _component(manifest: StrategyManifest) -> str:
    return component_id_for_strategy(manifest.strategy_id)


class StrategyStore:
    """SQLite-backed drafts, source bytes, and immutable strategy publications."""

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
                """CREATE TABLE IF NOT EXISTS strategy_blobs (
                    sha256 TEXT PRIMARY KEY, content BLOB NOT NULL
                )"""
            )
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS strategy_drafts (
                    draft_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    digest TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    parent_ref_json TEXT,
                    state TEXT NOT NULL CHECK(state IN ('DRAFT', 'PUBLISHED'))
                )"""
            )
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS strategy_publications (
                    strategy_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    PRIMARY KEY(strategy_id, version)
                )"""
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create_draft(
        self,
        manifest: StrategyManifest,
        source_bytes: bytes,
        parent_ref: ArtifactRef | None = None,
    ) -> DraftRef:
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        if source_digest != manifest.implementation_artifact_ref.sha256:
            raise ValueError("STRATEGY_SOURCE_HASH_MISMATCH")
        draft_id = uuid.uuid4().hex
        digest = manifest_digest(manifest)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                blob = self._conn.execute(
                    "SELECT content FROM strategy_blobs WHERE sha256 = ?", (source_digest,)
                ).fetchone()
                if blob is None:
                    self._conn.execute(
                        "INSERT INTO strategy_blobs(sha256, content) VALUES (?, ?)",
                        (source_digest, source_bytes),
                    )
                elif bytes(blob["content"]) != source_bytes:
                    raise ValueError("STRATEGY_SOURCE_HASH_COLLISION")
                self._conn.execute(
                    """INSERT INTO strategy_drafts
                       (draft_id, revision, digest, manifest_json, parent_ref_json, state)
                       VALUES (?, 1, ?, ?, ?, 'DRAFT')""",
                    (
                        draft_id,
                        digest,
                        _json(manifest),
                        _json(parent_ref) if parent_ref is not None else None,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return DraftRef(id=draft_id, revision=1, digest=digest)

    def get_draft(self, draft_id: str) -> tuple[DraftRef, StrategyManifest]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM strategy_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            raise KeyError("STRATEGY_DRAFT_NOT_FOUND")
        manifest = StrategyManifest.model_validate_json(row["manifest_json"])
        if manifest_digest(manifest) != row["digest"]:
            raise ValueError("STRATEGY_DRAFT_DIGEST_MISMATCH")
        return DraftRef(id=draft_id, revision=row["revision"], digest=row["digest"]), manifest

    def get_draft_parent(self, draft_id: str) -> ArtifactRef | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT parent_ref_json FROM strategy_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            raise KeyError("STRATEGY_DRAFT_NOT_FOUND")
        return (
            ArtifactRef.model_validate_json(row["parent_ref_json"])
            if row["parent_ref_json"]
            else None
        )

    def update_draft(
        self,
        draft_id: str,
        expected_revision: int,
        manifest: StrategyManifest,
        source_bytes: bytes,
    ) -> DraftRef:
        digest = manifest_digest(manifest)
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        if source_digest != manifest.implementation_artifact_ref.sha256:
            raise ValueError("STRATEGY_SOURCE_HASH_MISMATCH")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT revision, state FROM strategy_drafts WHERE draft_id = ?", (draft_id,)
                ).fetchone()
                if row is None:
                    raise KeyError("STRATEGY_DRAFT_NOT_FOUND")
                if row["state"] != "DRAFT":
                    raise ValueError("STRATEGY_DRAFT_ALREADY_PUBLISHED")
                if row["revision"] != expected_revision:
                    raise ValueError("STALE_DRAFT_REVISION")
                blob = self._conn.execute(
                    "SELECT content FROM strategy_blobs WHERE sha256 = ?", (source_digest,)
                ).fetchone()
                if blob is None:
                    self._conn.execute(
                        "INSERT INTO strategy_blobs(sha256, content) VALUES (?, ?)",
                        (source_digest, source_bytes),
                    )
                elif bytes(blob["content"]) != source_bytes:
                    raise ValueError("STRATEGY_SOURCE_HASH_COLLISION")
                revision = expected_revision + 1
                self._conn.execute(
                    """UPDATE strategy_drafts SET revision = ?, digest = ?, manifest_json = ?
                       WHERE draft_id = ? AND revision = ?""",
                    (revision, digest, _json(manifest), draft_id, expected_revision),
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
                    "SELECT * FROM strategy_drafts WHERE draft_id = ?", (draft_id,)
                ).fetchone()
                if row is None:
                    raise KeyError("STRATEGY_DRAFT_NOT_FOUND")
                if row["revision"] != expected_revision:
                    raise ValueError("STALE_DRAFT_REVISION")
                manifest = StrategyManifest.model_validate_json(row["manifest_json"])
                digest = manifest_digest(manifest)
                if digest != row["digest"]:
                    raise ValueError("STRATEGY_DRAFT_DIGEST_MISMATCH")
                source_hash = manifest.implementation_artifact_ref.sha256
                blob = self._conn.execute(
                    "SELECT content FROM strategy_blobs WHERE sha256 = ?", (source_hash,)
                ).fetchone()
                if (
                    blob is None
                    or hashlib.sha256(bytes(blob["content"])).hexdigest() != source_hash
                ):
                    raise ValueError("STRATEGY_SOURCE_ARTIFACT_UNAVAILABLE")
                existing = self._conn.execute(
                    "SELECT digest FROM strategy_publications "
                    "WHERE strategy_id = ? AND version = ?",
                    (manifest.strategy_id, manifest.version),
                ).fetchone()
                if existing is not None and existing["digest"] != digest:
                    raise ValueError("IMMUTABLE_VERSION_CONFLICT")
                if existing is None:
                    self._conn.execute(
                        """INSERT INTO strategy_publications
                           (strategy_id, version, digest, manifest_json) VALUES (?, ?, ?, ?)""",
                        (manifest.strategy_id, manifest.version, digest, row["manifest_json"]),
                    )
                self._conn.execute(
                    "UPDATE strategy_drafts SET state = 'PUBLISHED' WHERE draft_id = ?",
                    (draft_id,),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self._manifest_ref(manifest, digest)

    def get(self, ref: ArtifactRef) -> StrategyManifest:
        with self._lock:
            row = self._conn.execute(
                """SELECT manifest_json, digest FROM strategy_publications
                   WHERE strategy_id = ? AND version = ?""",
                (ref.id, ref.version),
            ).fetchone()
            if row is None:
                raise KeyError("STRATEGY_ARTIFACT_NOT_FOUND")
            if row["digest"] != ref.sha256:
                raise ValueError("STRATEGY_ARTIFACT_REF_MISMATCH")
            manifest = StrategyManifest.model_validate_json(row["manifest_json"])
            blob = self._conn.execute(
                "SELECT content FROM strategy_blobs WHERE sha256 = ?",
                (manifest.implementation_artifact_ref.sha256,),
            ).fetchone()
        if manifest_digest(manifest) != ref.sha256:
            raise ValueError("STRATEGY_ARTIFACT_DIGEST_MISMATCH")
        if blob is None:
            raise ValueError("STRATEGY_SOURCE_ARTIFACT_UNAVAILABLE")
        if (
            hashlib.sha256(bytes(blob["content"])).hexdigest()
            != manifest.implementation_artifact_ref.sha256
        ):
            raise ValueError("STRATEGY_SOURCE_HASH_MISMATCH")
        return manifest.model_copy(deep=True)

    def get_source_bytes(self, source_hash: str) -> bytes:
        if not _SHA256.fullmatch(source_hash):
            raise ValueError("INVALID_STRATEGY_SOURCE_HASH")
        with self._lock:
            row = self._conn.execute(
                "SELECT content FROM strategy_blobs WHERE sha256 = ?", (source_hash,)
            ).fetchone()
        if row is None:
            raise KeyError("STRATEGY_SOURCE_ARTIFACT_NOT_FOUND")
        content = bytes(row["content"])
        if hashlib.sha256(content).hexdigest() != source_hash:
            raise ValueError("STRATEGY_SOURCE_HASH_MISMATCH")
        return content

    @staticmethod
    def _manifest_ref(manifest: StrategyManifest, digest: str) -> ArtifactRef:
        return ArtifactRef(
            kind="strategy_manifest",
            id=manifest.strategy_id,
            version=manifest.version,
            sha256=digest,
            schema_version=manifest.schema_version,
        )


class StrategyService:
    """Validated facade over the existing allowlisted strategy registry and store."""

    def __init__(self, store: StrategyStore) -> None:
        self.store = store

    @staticmethod
    def _source(component_id: str) -> tuple[ArtifactRef, bytes]:
        implementation = builtin_strategy_implementation(component_id)
        source = implementation.source_path.read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        return (
            ArtifactRef(
                kind="strategy_source",
                id=component_id,
                version=digest[:16],
                sha256=digest,
                schema_version="v1",
            ),
            source,
        )

    @classmethod
    def builtin_manifest(
        cls,
        strategy_id: str,
        *,
        version: str = "1.0.0",
        pair: str | None = None,
    ) -> StrategyManifest:
        component_id = component_id_for_strategy(strategy_id)
        model = _PARAMETER_MODELS[component_id]
        from indodax_lab.strategies.registry import StrategyRegistry

        base_spec = StrategyRegistry().load_specification_from_yaml(
            _CONFIG_DIR / f"{component_id}_v1.yaml"
        )
        if base_spec.strategy_id != component_id:
            raise ValueError("BUILTIN_CONFIG_COMPONENT_MISMATCH")
        values = {**base_spec.parameters, "risk_profile": base_spec.risk_profile}
        if pair is not None:
            values["pair"] = pair
        parameter_model = model.model_validate(values)
        family, required_features, exit_contract = _COMPONENTS[component_id]
        source_ref, _ = cls._source(component_id)
        feature_schema = {"version": "v1", "features": required_features}
        return StrategyManifest(
            strategy_id=strategy_id,
            family=family,
            version=version,
            implementation_artifact_ref=source_ref,
            parameter_schema_hash=_parameter_schema_hash(component_id),
            parameters=parameter_model.model_dump(mode="json", exclude_none=True),
            required_feature_schema_hash=hashlib.sha256(
                canonical_bytes(feature_schema)
            ).hexdigest(),
            timeframe_constraints=("1h",),
            decision_contract_version="v1",
            exit_contract_version=_exit_contract_version(exit_contract),
            schema_version="v1",
        )

    def component_metadata(self) -> tuple[StrategyComponentMetadata, ...]:
        result = []
        for component_id, parameter_model in _PARAMETER_MODELS.items():
            _, features, exit_contract = _COMPONENTS[component_id]
            result.append(
                StrategyComponentMetadata(
                    component_id=component_id,
                    family=_COMPONENTS[component_id][0],
                    metadata_version="v1",
                    parameter_schema_version="v1",
                    parameter_schema=parameter_model.model_json_schema(),
                    required_features=features,
                    required_feature_schema_version="v1",
                    decision_contract_version="v1",
                    exit_contract_version=_exit_contract_version(exit_contract),
                    exit_contract=dict(exit_contract),
                )
            )
        return tuple(result)

    def _validate_manifest(
        self, manifest: StrategyManifest, source_bytes: bytes | None = None
    ) -> tuple[str, bytes]:
        component_id = _component(manifest)
        source_ref = manifest.implementation_artifact_ref
        if source_bytes is None:
            expected_ref, source_bytes = self._source(component_id)
            if source_ref != expected_ref:
                raise ValueError("UNAPPROVED_STRATEGY_SOURCE")
        elif (
            source_ref.kind != "strategy_source"
            or source_ref.id != component_id
            or source_ref.version != source_ref.sha256[:16]
            or source_ref.schema_version != "v1"
            or hashlib.sha256(source_bytes).hexdigest() != source_ref.sha256
        ):
            raise ValueError("UNAPPROVED_STRATEGY_SOURCE")
        family, features, exit_contract = _COMPONENTS[component_id]
        if manifest.family != family:
            raise ValueError("STRATEGY_FAMILY_MISMATCH")
        if manifest.parameter_schema_hash != _parameter_schema_hash(component_id):
            raise ValueError("STRATEGY_PARAMETER_SCHEMA_MISMATCH")
        feature_schema = {"version": "v1", "features": features}
        if (
            manifest.required_feature_schema_hash
            != hashlib.sha256(canonical_bytes(feature_schema)).hexdigest()
        ):
            raise ValueError("STRATEGY_FEATURE_SCHEMA_MISMATCH")
        if manifest.timeframe_constraints != ("1h",):
            raise ValueError("UNSUPPORTED_STRATEGY_TIMEFRAME")
        if manifest.decision_contract_version != "v1" or manifest.schema_version != "v1":
            raise ValueError("STRATEGY_CONTRACT_VERSION_UNSUPPORTED")
        if manifest.exit_contract_version != _exit_contract_version(exit_contract):
            raise ValueError("STRATEGY_EXIT_CONTRACT_MISMATCH")
        try:
            _PARAMETER_MODELS[component_id].model_validate(manifest.parameters)
        except ValidationError as exc:
            raise ValueError(f"INVALID_STRATEGY_PARAMETERS: {exc}") from exc
        return component_id, source_bytes

    def create_draft(self, manifest: StrategyManifest) -> DraftRef:
        _, source_bytes = self._validate_manifest(manifest)
        return self.store.create_draft(manifest.model_copy(deep=True), source_bytes)

    def get_draft(self, draft_id: str) -> StrategyManifest:
        _, manifest = self.store.get_draft(draft_id)
        return manifest.model_copy(deep=True)

    def get_draft_parent(self, draft_id: str) -> ArtifactRef | None:
        return self.store.get_draft_parent(draft_id)

    def update_draft(
        self,
        draft_id: str,
        expected_revision: int,
        parameters: dict[str, Any],
    ) -> DraftRef:
        current_ref, current = self.store.get_draft(draft_id)
        if current_ref.revision != expected_revision:
            raise ValueError("STALE_DRAFT_REVISION")
        component_id = _component(current)
        try:
            validated = _PARAMETER_MODELS[component_id].model_validate(parameters)
        except ValidationError as exc:
            raise ValueError(f"INVALID_STRATEGY_PARAMETERS: {exc}") from exc
        updated = current.model_copy(
            deep=True,
            update={"parameters": validated.model_dump(mode="json", exclude_none=True)},
        )
        source_bytes = self.store.get_source_bytes(updated.implementation_artifact_ref.sha256)
        self._validate_manifest(updated, source_bytes)
        return self.store.update_draft(draft_id, expected_revision, updated, source_bytes)

    def publish(self, draft_id: str, expected_revision: int) -> ArtifactRef:
        current_ref, manifest = self.store.get_draft(draft_id)
        if current_ref.revision != expected_revision:
            raise ValueError("STALE_DRAFT_REVISION")
        source_bytes = self.store.get_source_bytes(manifest.implementation_artifact_ref.sha256)
        self._validate_manifest(manifest, source_bytes)
        return self.store.publish(draft_id, expected_revision)

    def clone(self, ref: ArtifactRef) -> DraftRef:
        manifest = self.get(ref)
        source_bytes = self.store.get_source_bytes(manifest.implementation_artifact_ref.sha256)
        clone_manifest = manifest.model_copy(
            deep=True,
            update={"version": f"{manifest.version}-clone-{uuid.uuid4().hex[:8]}"},
        )
        return self.store.create_draft(clone_manifest, source_bytes, parent_ref=ref)

    def get(self, ref: ArtifactRef) -> StrategyManifest:
        if ref.kind != "strategy_manifest":
            raise ValueError("STRATEGY_ARTIFACT_KIND_MISMATCH")
        manifest = self.store.get(ref)
        source_bytes = self.store.get_source_bytes(manifest.implementation_artifact_ref.sha256)
        self._validate_manifest(manifest, source_bytes)
        return manifest

    def load_manifest_yaml(self, text: str) -> StrategyManifest:
        try:
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                raise ValueError("STRATEGY_MANIFEST_YAML_ROOT_MUST_BE_MAPPING")
            return StrategyManifest.model_validate(data)
        except (ValidationError, yaml.YAMLError) as exc:
            raise ValueError(f"UNKNOWN_CONFIG_FIELDS_OR_INVALID_MANIFEST: {exc}") from exc

    @staticmethod
    def export_manifest_yaml(manifest: StrategyManifest) -> str:
        data = json.loads(canonical_bytes(manifest))
        return yaml.safe_dump(data, sort_keys=True, allow_unicode=True)

    def seed_manifests(self) -> tuple[ArtifactRef, ...]:
        """Idempotently publish the declarative C07/C02 seed manifests."""
        try:
            data = yaml.safe_load(_SEED_FILE.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"INVALID_STRATEGY_SEED_FILE: {exc}") from exc
        if not isinstance(data, dict) or set(data) != {"schema_version", "seeds"}:
            raise ValueError("INVALID_STRATEGY_SEED_FILE")
        if data["schema_version"] != "v1" or not isinstance(data["seeds"], list):
            raise ValueError("INVALID_STRATEGY_SEED_SCHEMA")
        refs = []
        for row in data["seeds"]:
            if not isinstance(row, dict) or set(row) != {
                "strategy_id",
                "version",
                "component_id",
                "pair",
            }:
                raise ValueError("INVALID_STRATEGY_SEED_ENTRY")
            component_id = row["component_id"]
            if component_id not in _PARAMETER_MODELS:
                raise ValueError("UNAPPROVED_STRATEGY_COMPONENT")
            if component_id_for_strategy(row["strategy_id"]) != component_id:
                raise ValueError("STRATEGY_SEED_COMPONENT_MISMATCH")
            base = self.builtin_manifest(
                row["strategy_id"], version=row["version"], pair=row["pair"]
            )
            draft = self.create_draft(base)
            refs.append(self.publish(draft.id, draft.revision))
        return tuple(refs)
