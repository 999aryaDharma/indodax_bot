"""Content-addressed model registry with verified, fail-closed loading (RW2-02).

Guarantees:
1. RW2-02-FR0: artifact hash mismatch is rejected before any loader invocation.
2. RW2-02-FR1: only pinned, allowlisted loaders deserialize model bytes;
   pickle/remote/eval loader ids reject at registration and load time.
3. RW2-02-FR2: prediction refuses a feature order/schema that differs from the
   manifest instead of silently reordering or dropping columns.
4. RW2-02-FR4: unmet runtime requirements surface as ``BLOCKED_RESOURCE``.
5. Registered model versions are immutable: conflicting semantics under an
   existing (model_id, version) identity are refused, never merged.
6. ``load_verified`` refuses manifests whose ``artifact_refs`` count is not
   exactly one: extra or missing refs are never silently dropped by the
   single-bytes loader.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar

import pandas as pd

from indodax_lab.contracts.identity import ArtifactRef, canonical_bytes
from indodax_lab.contracts.workbench import ModelManifest
from indodax_lab.models.artifacts import PortableBundle, PortableBundleLoader
from indodax_lab.models.dl.checkpoint import check_torch_availability
from indodax_lab.orchestration.resources import ResourceProbe

# ---------------------------------------------------------------------------
# Errors — fail-closed, ``<CODE>: <detail>`` messages
# ---------------------------------------------------------------------------


class ModelRegistryError(Exception):
    """Base error for model registry operations."""

    code: ClassVar[str] = "MODEL_REGISTRY_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(f"{self.code}: {detail}")


class ArtifactHashMismatchError(ModelRegistryError):
    code: ClassVar[str] = "ARTIFACT_HASH_MISMATCH"


class ArtifactMissingError(ModelRegistryError):
    code: ClassVar[str] = "ARTIFACT_MISSING"


class ModelNotRegisteredError(ModelRegistryError):
    code: ClassVar[str] = "MODEL_NOT_REGISTERED"


class ModelRefMismatchError(ModelRegistryError):
    code: ClassVar[str] = "MODEL_REF_MISMATCH"


class ImmutableVersionConflictError(ModelRegistryError):
    code: ClassVar[str] = "IMMUTABLE_VERSION_CONFLICT"


class LoaderNotAllowedError(ModelRegistryError):
    code: ClassVar[str] = "LOADER_NOT_ALLOWED"


class ModelManifestInvalidError(ModelRegistryError):
    code: ClassVar[str] = "MODEL_MANIFEST_INVALID"


class FeatureSchemaMismatchError(ModelRegistryError):
    code: ClassVar[str] = "FEATURE_SCHEMA_MISMATCH"


class RuntimeBlockedError(ModelRegistryError):
    code: ClassVar[str] = "BLOCKED_RESOURCE"


# ---------------------------------------------------------------------------
# Loader allowlist (RW2-02 Step 1) — pinned formats only, never pickle/remote
# ---------------------------------------------------------------------------

_LOADER_FUNCTIONS: dict[str, Callable[[bytes], Any]] = {
    "portable_bundle_json_v2": PortableBundleLoader().load_from_bytes,
}
LOADER_ALLOWLIST: Mapping[str, Callable[[bytes], Any]] = MappingProxyType(_LOADER_FUNCTIONS)
ARCHITECTURE_LOADERS: Mapping[str, str] = MappingProxyType(
    {"m01_logistic": "portable_bundle_json_v2"}
)


def resolve_loader(loader_id: str) -> Callable[[bytes], Any]:
    """Resolve a loader id against the pinned allowlist (fail-closed)."""
    loader = LOADER_ALLOWLIST.get(loader_id)
    if loader is None:
        raise LoaderNotAllowedError(
            f"loader {loader_id!r} is not in the pinned allowlist; "
            f"allowed: {sorted(LOADER_ALLOWLIST)}"
        )
    return loader


def unmet_runtime_requirements(
    requirements: Mapping[str, str],
    *,
    probe: ResourceProbe | None,
) -> tuple[str, ...]:
    """Return fail-closed reasons why declared runtime requirements are unmet.

    Unknown requirement keys are unmet by design: a requirement the registry
    cannot evaluate is never silently treated as satisfied.
    """
    reasons: list[str] = []
    for key in sorted(requirements):
        normalized_key = key.strip().lower()
        value = str(requirements[key]).strip().lower()
        if normalized_key in ("accelerator", "device"):
            if value in ("cuda", "gpu"):
                available: bool | None = None
                if probe is not None:
                    try:
                        available = probe.read().gpu_available
                    except Exception:  # a failed sensor read blocks, never passes
                        available = None
                if available is None:
                    reasons.append("SENSOR_UNKNOWN:gpu_available")
                elif not available:
                    reasons.append("GPU_UNAVAILABLE")
        elif normalized_key in ("torch", "pytorch"):
            if not check_torch_availability():
                reasons.append("TORCH_UNAVAILABLE")
        else:
            reasons.append(f"RUNTIME_REQUIREMENT_UNSUPPORTED:{key}")
    return tuple(reasons)


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureFrame:
    """Ordered feature matrix accepted by ``ModelPredictor.predict_proba``."""

    feature_names: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        names = tuple(self.feature_names)
        if not names or any(not isinstance(name, str) or not name for name in names):
            raise ValueError(f"FEATURE_FRAME_FEATURE_NAMES_INVALID: {names!r}")
        if len(set(names)) != len(names):
            raise ValueError(f"FEATURE_FRAME_FEATURE_NAMES_DUPLICATE: {names!r}")
        if not self.rows:
            raise ValueError("FEATURE_FRAME_ROWS_REQUIRED: at least one row is required")
        coerced: list[tuple[float, ...]] = []
        for row in self.rows:
            if len(row) != len(names):
                raise ValueError(
                    f"FEATURE_FRAME_ROW_WIDTH_MISMATCH: expected {len(names)} values, "
                    f"got {len(row)}"
                )
            values: list[float] = []
            for value in row:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"FEATURE_FRAME_VALUE_INVALID: {value!r}")
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f"NON_FINITE_VALUE_REQUIRED: {value!r}")
                values.append(number)
            coerced.append(tuple(values))
        object.__setattr__(self, "feature_names", names)
        object.__setattr__(self, "rows", tuple(coerced))


@dataclass(frozen=True)
class ProbabilityVector:
    """Positive-class probabilities produced by one prediction call."""

    model_id: str
    probabilities: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.model_id, str) or not self.model_id:
            raise ValueError(f"PROBABILITY_VECTOR_MODEL_ID_INVALID: {self.model_id!r}")
        if not self.probabilities:
            raise ValueError("PROBABILITY_VECTOR_EMPTY: at least one probability is required")
        coerced: list[float] = []
        for value in self.probabilities:
            number = float(value)
            if not math.isfinite(number) or not 0.0 <= number <= 1.0:
                raise ValueError(f"PROBABILITY_OUT_OF_RANGE: {value!r}")
            coerced.append(number)
        object.__setattr__(self, "probabilities", tuple(coerced))


@dataclass(frozen=True)
class ModelEntry:
    """Listing row distinguishing registered/verified/compatible/runtime states."""

    model_id: str
    version: str
    manifest_ref: ArtifactRef | None
    object_sha256: str
    registered: bool
    verified: bool
    compatible: bool
    runtime_eligible: bool
    reason: str | None


class ModelPredictor:
    """Verified model handle: manifest-scoped, schema-strict prediction."""

    def __init__(
        self,
        *,
        manifest: ModelManifest,
        model_ref: ArtifactRef,
        bundle: PortableBundle,
        loader_id: str,
    ) -> None:
        self._manifest = manifest
        self._model_ref = model_ref
        self._bundle = bundle
        self._loader_id = loader_id

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    @property
    def model_ref(self) -> ArtifactRef:
        return self._model_ref

    @property
    def model_id(self) -> str:
        return self._manifest.model_id

    @property
    def loader_id(self) -> str:
        return self._loader_id

    def predict_proba(self, frame: FeatureFrame) -> ProbabilityVector:
        """Predict calibrated positive-class probabilities for one frame.

        The frame must match the manifest's ordered feature schema exactly:
        no silent reordering, no column drop, no extra columns tolerated.
        """
        expected = tuple(self._manifest.ordered_feature_schema)
        actual = tuple(frame.feature_names)
        if actual != expected:
            raise FeatureSchemaMismatchError(
                f"frame feature order/schema {actual} does not match manifest schema {expected}"
            )
        columns: dict[str, list[float]] = {}
        for index, name in enumerate(frame.feature_names):
            columns[name] = [row[index] for row in frame.rows]
        features = pd.DataFrame(columns, columns=list(frame.feature_names))
        raw = self._bundle.predict_proba(features)
        return ProbabilityVector(
            model_id=self._manifest.model_id,
            probabilities=tuple(float(value) for value in raw),
        )


# ---------------------------------------------------------------------------
# ModelRegistry
# ---------------------------------------------------------------------------


class ModelRegistry:
    """Immutable, content-addressed model store with SQLite identity rows.

    Objects live at ``<root>/objects/<kind>/<artifact_id>/<version>/<sha256>``
    and published identities live in ``<root>/registry.sqlite``. Path safety
    comes from ``ArtifactRef`` validators (no path separators, no traversal).
    """

    def __init__(self, root: Path | str, probe: ResourceProbe | None = None) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._probe = probe
        self._db_path = self._root / "registry.sqlite"
        self._init_db()

    # -- properties --------------------------------------------------------

    @property
    def root(self) -> Path:
        return self._root

    @property
    def probe(self) -> ResourceProbe | None:
        return self._probe

    # -- storage -----------------------------------------------------------

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 5000;")
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_registry (
                    model_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    loader_id TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (model_id, version)
                );
                """
            )

    def object_path(self, ref: ArtifactRef) -> Path:
        """Return the content-addressed object path for a verified reference."""
        return self._root / "objects" / ref.kind / ref.id / ref.version / ref.sha256

    def put_bytes(
        self,
        data: bytes,
        *,
        kind: str,
        artifact_id: str,
        version: str = "1",
    ) -> ArtifactRef:
        """Store bytes in the content-addressed object store."""
        payload = bytes(data)
        ref = ArtifactRef(
            kind=kind,
            id=artifact_id,
            version=version,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        path = self.object_path(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return ref

    def read_object(self, ref: ArtifactRef) -> bytes:
        """Read object bytes after re-hashing them against the reference (fail-closed)."""
        path = self.object_path(ref)
        if not path.is_file():
            raise ArtifactMissingError(
                f"no bytes stored for {ref.kind}:{ref.id}:{ref.version}:{ref.sha256}"
            )
        data = path.read_bytes()
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != ref.sha256:
            raise ArtifactHashMismatchError(
                f"stored bytes for {ref.kind}:{ref.id}:{ref.version} hash to {actual_sha}, "
                f"reference requires {ref.sha256}"
            )
        return data

    # -- registration ------------------------------------------------------

    def register(self, manifest: ModelManifest) -> ArtifactRef:
        """Publish a model identity as an immutable (model_id, version) row."""
        loader_id = ARCHITECTURE_LOADERS.get(manifest.architecture)
        if loader_id is None or loader_id not in LOADER_ALLOWLIST:
            raise LoaderNotAllowedError(
                f"architecture {manifest.architecture!r} has no allowlisted loader; "
                f"allowed architectures: {sorted(ARCHITECTURE_LOADERS)}"
            )
        if not manifest.artifact_refs:
            raise ModelManifestInvalidError(
                "ARTIFACT_REFS_REQUIRED: manifest declares no loader artifact"
            )
        manifest_bytes = canonical_bytes(manifest)
        manifest_ref = manifest.to_artifact_ref()
        content_sha = hashlib.sha256(manifest_bytes).hexdigest()
        if manifest_ref.sha256 != content_sha:
            raise ModelManifestInvalidError(
                f"MANIFEST_DIGEST_MISMATCH: semantic digest {manifest_ref.sha256} does not "
                f"match manifest bytes sha {content_sha}"
            )
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT manifest_sha256 FROM model_registry "
                "WHERE model_id = ? AND version = ?",
                (manifest.model_id, manifest.version),
            ).fetchone()
        if existing is not None:
            if existing["manifest_sha256"] == manifest_ref.sha256:
                return manifest_ref
            raise ImmutableVersionConflictError(
                f"model {manifest.model_id}:{manifest.version} is already registered with sha "
                f"{existing['manifest_sha256']}; refusing conflicting sha {manifest_ref.sha256}"
            )
        for artifact in manifest.artifact_refs:
            self.read_object(artifact)
        path = self.object_path(manifest_ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(manifest_bytes)
        with self._connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO model_registry (
                        model_id, version, manifest_sha256, manifest_json, loader_id,
                        created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.model_id,
                        manifest.version,
                        manifest_ref.sha256,
                        manifest_bytes.decode("utf-8"),
                        loader_id,
                        datetime.now(UTC).isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ImmutableVersionConflictError(
                    f"model {manifest.model_id}:{manifest.version} was registered concurrently"
                ) from exc
        return manifest_ref

    # -- verified loading --------------------------------------------------

    def _read_manifest(self, ref: ArtifactRef) -> ModelManifest:
        data = self.read_object(ref)
        try:
            return ModelManifest.model_validate(json.loads(data))
        except ValueError as exc:
            raise ModelManifestInvalidError(f"cannot parse manifest bytes: {exc}") from exc

    def load_verified(self, ref: ArtifactRef) -> ModelPredictor:
        """Load a registered model after integrity, loader and runtime checks."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT model_id, version, manifest_sha256, loader_id FROM model_registry "
                "WHERE model_id = ? AND version = ?",
                (ref.id, ref.version),
            ).fetchone()
        if row is None:
            raise ModelNotRegisteredError(f"no published model for {ref.id}:{ref.version}")
        if row["manifest_sha256"] != ref.sha256:
            raise ModelRefMismatchError(
                f"requested sha {ref.sha256} does not match registered sha "
                f"{row['manifest_sha256']} for {ref.id}:{ref.version}"
            )
        manifest_ref = ArtifactRef(
            kind="model",
            id=row["model_id"],
            version=row["version"],
            sha256=row["manifest_sha256"],
        )
        manifest = self._read_manifest(manifest_ref)
        if len(manifest.artifact_refs) != 1:
            raise ModelManifestInvalidError(
                f"ARTIFACT_REFS_SINGLE_REQUIRED: manifest declares "
                f"{len(manifest.artifact_refs)} loader artifact(s); the pinned loader "
                "consumes exactly one, so a missing or extra ref is refused instead of "
                "silently dropping everything but the first"
            )
        artifact_bytes = [self.read_object(artifact) for artifact in manifest.artifact_refs]
        loader_id = ARCHITECTURE_LOADERS.get(manifest.architecture)
        if loader_id is None or loader_id != row["loader_id"]:
            raise LoaderNotAllowedError(
                f"architecture {manifest.architecture!r} resolves to loader {loader_id!r}, "
                f"registered loader is {row['loader_id']!r}"
            )
        unmet = unmet_runtime_requirements(manifest.runtime_requirements, probe=self._probe)
        if unmet:
            raise RuntimeBlockedError(
                f"{'; '.join(unmet)}: model {manifest.model_id}:{manifest.version} has unmet "
                "runtime requirements"
            )
        # Exactly one verified artifact, enforced above — no first-ref convention.
        bundle = resolve_loader(loader_id)(artifact_bytes[0])
        if not isinstance(bundle, PortableBundle):
            raise ModelManifestInvalidError(
                f"loader {loader_id!r} did not produce a PortableBundle"
            )
        if tuple(bundle.feature_names) != tuple(manifest.ordered_feature_schema):
            raise FeatureSchemaMismatchError(
                f"bundle features {tuple(bundle.feature_names)} do not match manifest schema "
                f"{tuple(manifest.ordered_feature_schema)}"
            )
        if bundle.model_id != manifest.model_id or bundle.version != manifest.version:
            raise ModelManifestInvalidError(
                f"bundle identity {bundle.model_id}:{bundle.version} does not match manifest "
                f"{manifest.model_id}:{manifest.version}"
            )
        return ModelPredictor(
            manifest=manifest,
            model_ref=manifest_ref,
            bundle=bundle,
            loader_id=loader_id,
        )

    # -- listing -----------------------------------------------------------

    def list_models(self) -> tuple[ModelEntry, ...]:
        """List registered versions plus unregistered model objects, with flags.

        The four flags are independent dimensions — ``registered`` (published
        identity), ``verified`` (bytes re-hash against the manifest),
        ``compatible`` (static schema/loader contract) and ``runtime_eligible``
        (probe-based runtime requirements). No dimension is substituted for
        another, and model objects without a published identity are listed as
        unregistered instead of being silently attached to a look-alike model.
        """
        entries: list[ModelEntry] = []
        referenced: set[tuple[str, str, str]] = set()
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT model_id, version, manifest_sha256, loader_id FROM model_registry "
                "ORDER BY model_id, version"
            ).fetchall()
        for row in rows:
            manifest_ref = ArtifactRef(
                kind="model",
                id=row["model_id"],
                version=row["version"],
                sha256=row["manifest_sha256"],
            )
            referenced.add((manifest_ref.id, manifest_ref.version, manifest_ref.sha256))
            entries.append(self._entry_for_row(row, manifest_ref, referenced))
        entries.extend(self._unregistered_entries(referenced))
        entries.sort(key=lambda entry: (entry.model_id, entry.version))
        return tuple(entries)

    def _entry_for_row(
        self,
        row: sqlite3.Row,
        manifest_ref: ArtifactRef,
        referenced: set[tuple[str, str, str]],
    ) -> ModelEntry:
        """Evaluate registered/verified/compatible/runtime flags for one row."""
        manifest: ModelManifest | None = None
        verify_reason: str | None = None
        verified = False
        try:
            manifest = self._read_manifest(manifest_ref)
            for artifact in manifest.artifact_refs:
                referenced.add((artifact.id, artifact.version, artifact.sha256))
                self.read_object(artifact)
            verified = True
        except ModelRegistryError as exc:
            verify_reason = str(exc)

        compatibility_reasons: list[str] = []
        runtime_reasons: tuple[str, ...] = ()
        compatible = False
        runtime_eligible = False
        if manifest is not None:
            compatibility_reasons = self._compatibility_reasons(row, manifest)
            compatible = not compatibility_reasons
            runtime_reasons = unmet_runtime_requirements(
                manifest.runtime_requirements, probe=self._probe
            )
            runtime_eligible = not runtime_reasons

        reason = verify_reason
        if reason is None and compatibility_reasons:
            reason = "; ".join(compatibility_reasons)
        if reason is None and runtime_reasons:
            reason = f"BLOCKED_RESOURCE: {'; '.join(runtime_reasons)}"
        return ModelEntry(
            model_id=row["model_id"],
            version=row["version"],
            manifest_ref=manifest_ref,
            object_sha256=row["manifest_sha256"],
            registered=True,
            verified=verified,
            compatible=compatible,
            runtime_eligible=runtime_eligible,
            reason=reason,
        )

    @staticmethod
    def _compatibility_reasons(
        row: sqlite3.Row,
        manifest: ModelManifest,
    ) -> list[str]:
        """Static schema/loader compatibility reasons (no bundle loading, no probe)."""
        reasons: list[str] = []
        schema = tuple(manifest.ordered_feature_schema)
        if not schema or len(set(schema)) != len(schema):
            reasons.append(f"FEATURE_SCHEMA_INVALID: {schema!r}")
        if manifest.schema_version != "v1":
            reasons.append(
                f"SCHEMA_VERSION_UNSUPPORTED: {manifest.schema_version!r} (expected 'v1')"
            )
        loader_id = ARCHITECTURE_LOADERS.get(manifest.architecture)
        if loader_id is None or loader_id not in LOADER_ALLOWLIST:
            reasons.append(
                f"LOADER_NOT_ALLOWLISTED: architecture {manifest.architecture!r} has no "
                "allowlisted loader"
            )
        elif row["loader_id"] != loader_id:
            reasons.append(
                f"LOADER_DRIFT: registered loader {row['loader_id']!r} != {loader_id!r}"
            )
        return reasons

    def _unregistered_entries(
        self,
        referenced: set[tuple[str, str, str]],
    ) -> list[ModelEntry]:
        """List stored model objects that no published manifest identity references."""
        model_root = self._root / "objects" / "model"
        if not model_root.is_dir():
            return []
        entries: list[ModelEntry] = []
        for path in sorted(model_root.rglob("*")):
            if not path.is_file():
                continue
            parts = path.relative_to(model_root).parts
            if len(parts) != 3:
                continue
            artifact_id, version, sha256 = parts
            if (artifact_id, version, sha256) in referenced:
                continue
            entries.append(
                ModelEntry(
                    model_id=artifact_id,
                    version=version,
                    manifest_ref=None,
                    object_sha256=sha256,
                    registered=False,
                    verified=False,
                    compatible=False,
                    runtime_eligible=False,
                    reason=(
                        f"NOT_REGISTERED: object {artifact_id}:{version} has no published "
                        "manifest identity"
                    ),
                )
            )
        return entries
