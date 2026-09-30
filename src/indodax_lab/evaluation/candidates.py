"""Immutable candidate packaging and lifecycle (RW4-01).

Thin registry over existing contracts: RW3-01-shaped experiment evidence,
content-addressed artifact bytes, CandidateManifest / VerifiedCandidate /
CandidateRuntime linkage. No credentials, no network, no live authority.

Lineage is always re-resolved by content hash and re-hashed at verify
time; filename identity is never trusted. Publication is no-clobber:
identical bytes are idempotent, conflicting bytes under one identity
reject. Lifecycle transitions only append events; frozen configuration
bytes can never change through metadata.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.contracts.workbench import (
    CandidateManifest,
    PipelineManifest,
    VerifiedCandidate,
    VerifiedRuntimePlan,
)

_LIFECYCLE_EVENTS = ("NOTE", "SHADOW_REGISTER", "RETIRE")


def _utcnow(clock: Callable[[], datetime] | None) -> datetime:
    return clock() if clock is not None else datetime.now(UTC)


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_json(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _ref_json(ref: ArtifactRef) -> dict[str, str]:
    return {
        "kind": ref.kind,
        "id": ref.id,
        "version": ref.version,
        "sha256": ref.sha256,
    }


def _ref_from_json(data: dict[str, Any]) -> ArtifactRef:
    return ArtifactRef(
        kind=str(data["kind"]),
        id=str(data["id"]),
        version=str(data["version"]),
        sha256=str(data["sha256"]),
    )


class ExperimentEvidence(BaseModel):
    """Completed-experiment evidence consumed by packaging (RW3-01 shaped)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str
    status: str
    plan: VerifiedRuntimePlan
    result_digest: str
    artifact_path: str


class CandidateRecord(BaseModel):
    """Append-only lifecycle record; configuration bytes live in the manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    version: str
    config_digest: str
    lifecycle: str = "REGISTERED"
    events: tuple[dict[str, Any], ...] = ()


class CandidateRegistry:
    """No-clobber candidate packages bound to reviewed experiment evidence."""

    def __init__(
        self,
        root: Path | str,
        *,
        clock: Callable[[], datetime] | None = None,
        artifact_resolver: Callable[[ArtifactRef], bytes],
    ) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._resolve_raw = artifact_resolver
        self._db = sqlite3.connect(str(self._root / "candidates.sqlite"), timeout=30.0)
        self._db.row_factory = sqlite3.Row
        with self._db:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    manifest_digest TEXT NOT NULL,
                    lineage_json TEXT NOT NULL,
                    PRIMARY KEY (candidate_id, version)
                )
                """
            )
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_events (
                    candidate_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    PRIMARY KEY (candidate_id, version, seq)
                )
                """
            )

    # -- artifact resolution (bytes by content hash, never filenames) ----

    def _resolve(self, ref: ArtifactRef) -> bytes:
        try:
            return bytes(self._resolve_raw(ref))
        except ValueError:
            raise
        except LookupError as exc:
            raise ValueError(f"EVIDENCE_MISSING:{ref.kind}:{ref.id}") from exc
        except Exception as exc:
            raise ValueError(f"EVIDENCE_MISSING:{ref.kind}:{ref.id}") from exc

    # -- queries ----------------------------------------------------------

    def count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) AS n FROM candidates").fetchone()
        return int(row["n"])

    def _load_manifest(self, candidate_id: str, version: str) -> CandidateManifest:
        row = self._db.execute(
            "SELECT manifest_json, manifest_digest FROM candidates "
            "WHERE candidate_id = ? AND version = ?",
            (candidate_id, version),
        ).fetchone()
        if row is None:
            raise KeyError(f"CANDIDATE_NOT_FOUND:{candidate_id}:{version}")
        manifest = CandidateManifest.model_validate_json(row["manifest_json"])
        if manifest_digest(manifest) != row["manifest_digest"]:
            raise ValueError(f"CANDIDATE_STORE_CORRUPT:{candidate_id}:{version}")
        return manifest

    def _load_lineage(self, candidate_id: str, version: str) -> dict[str, Any]:
        row = self._db.execute(
            "SELECT lineage_json FROM candidates WHERE candidate_id = ? AND version = ?",
            (candidate_id, version),
        ).fetchone()
        if row is None:
            raise KeyError(f"CANDIDATE_NOT_FOUND:{candidate_id}:{version}")
        return dict(json.loads(row["lineage_json"]))

    def _latest_version(self, candidate_id: str) -> str:
        rows = self._db.execute(
            "SELECT version FROM candidates WHERE candidate_id = ? ORDER BY version DESC",
            (candidate_id,),
        ).fetchall()
        if not rows:
            raise KeyError(f"CANDIDATE_NOT_FOUND:{candidate_id}")
        return str(rows[0]["version"])

    def get(self, ref: ArtifactRef) -> CandidateManifest:
        manifest = self._load_manifest(ref.id, ref.version)
        if manifest_digest(manifest) != ref.sha256:
            raise ValueError(
                f"CANDIDATE_IDENTITY_MISMATCH:{ref.id}:{ref.version}: "
                "reference digest does not match stored manifest"
            )
        return manifest

    # -- lineage ------------------------------------------------------------

    def _compute_lineage(
        self, plan_digest: str, pipeline_ref: ArtifactRef,
        policy_refs: dict[str, ArtifactRef],
        extra_model_refs: tuple[ArtifactRef, ...] = (),
    ) -> dict[str, Any]:
        pipeline_bytes = self._resolve(pipeline_ref)
        pipeline = PipelineManifest.model_validate_json(pipeline_bytes)
        pipeline_model_refs = [
            ref for ref in pipeline.component_refs if ref.kind == "model"
        ]
        model_hashes = sorted(
            _sha_bytes(self._resolve(ref))
            for ref in pipeline_model_refs + list(extra_model_refs)
        )
        policies = {
            name: _sha_bytes(self._resolve(ref)) for name, ref in policy_refs.items()
        }
        return {
            "plan_digest": plan_digest,
            "pipeline_sha": _sha_bytes(pipeline_bytes),
            "pipeline_model_refs": [_ref_json(ref) for ref in pipeline_model_refs],
            "extra_model_refs": [_ref_json(ref) for ref in extra_model_refs],
            "model_hashes": model_hashes,
            "policies": policies,
        }

    # -- publication ----------------------------------------------------------

    def _insert(
        self, manifest: CandidateManifest, lineage: dict[str, Any]
    ) -> tuple[CandidateManifest, bool]:
        digest = manifest_digest(manifest)
        try:
            with self._db:
                self._db.execute(
                    "INSERT INTO candidates (candidate_id, version, manifest_json, "
                    "manifest_digest, lineage_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        manifest.candidate_id,
                        manifest.version,
                        manifest.model_dump_json(),
                        digest,
                        json.dumps(lineage, sort_keys=True),
                    ),
                )
        except sqlite3.IntegrityError:
            stored = self._load_manifest(manifest.candidate_id, manifest.version)
            if manifest_digest(stored) != digest:
                raise ValueError(
                    f"CANDIDATE_VERSION_CONFLICT:{manifest.candidate_id}:"
                    f"{manifest.version}: same identity carries different bytes"
                ) from None
            return stored, False
        self._record_event(
            manifest.candidate_id, manifest.version, "REGISTER", {}, digest
        )
        return manifest, True

    def publish_manifest(self, manifest: CandidateManifest) -> CandidateManifest:
        """No-clobber insert: identical bytes idempotent, conflicts reject.

        Republication path shared by package()/retrain() and direct callers.
        """
        try:
            self._load_manifest(manifest.candidate_id, manifest.version)
        except KeyError:
            lineage = self._compute_lineage(
                manifest.runtime_plan_ref.sha256,
                manifest.pipeline_ref,
                {
                    "risk": manifest.risk_policy_ref,
                    "cost": manifest.cost_policy_ref,
                    "execution": manifest.execution_policy_ref,
                },
            )
            stored, _ = self._insert(manifest, lineage)
            return stored
        stored = self._load_manifest(manifest.candidate_id, manifest.version)
        if manifest_digest(stored) != manifest_digest(manifest):
            raise ValueError(
                f"CANDIDATE_VERSION_CONFLICT:{manifest.candidate_id}:"
                f"{manifest.version}: same identity carries different bytes"
            )
        return stored

    # -- package / retrain ------------------------------------------------------

    def _checked_experiment(
        self, experiment_id: str, review_ref: str, experiment: ExperimentEvidence
    ) -> VerifiedRuntimePlan:
        if experiment.experiment_id != experiment_id:
            raise ValueError("EXPERIMENT_ID_MISMATCH")
        if experiment.status != "SUCCESS":
            raise ValueError(
                f"EXPERIMENT_NOT_COMPLETED:{experiment_id}:{experiment.status}"
            )
        if not review_ref or not str(review_ref).strip():
            raise ValueError("REVIEW_REF_REQUIRED")
        artifact_path = Path(experiment.artifact_path)
        if not artifact_path.is_file():
            raise ValueError(
                f"EVIDENCE_MISSING:result-artifact:{artifact_path}: "
                "filename identity alone never authorizes packaging"
            )
        plan = experiment.plan
        if manifest_digest(plan.plan) != plan.plan_digest:
            raise ValueError("PLAN_DIGEST_MISMATCH")
        return plan

    def package(
        self,
        experiment_id: str,
        review_ref: str,
        *,
        experiment: ExperimentEvidence,
    ) -> CandidateManifest:
        plan = self._checked_experiment(experiment_id, review_ref, experiment)
        lineage = self._compute_lineage(
            plan.plan_digest,
            plan.plan.pipeline_ref,
            {
                "risk": plan.plan.risk_policy_ref,
                "cost": plan.plan.cost_policy_ref,
                "execution": plan.plan.execution_policy_ref,
            },
        )
        manifest = CandidateManifest(
            candidate_id=f"cand_{experiment_id}",
            version="v1",
            runtime_plan_ref=ArtifactRef(
                kind="plan",
                id=plan.plan.plan_id,
                version=plan.plan.version,
                sha256=plan.plan_digest,
            ),
            completed_experiment_ref=ArtifactRef(
                kind="experiment-result",
                id=experiment_id,
                version="v1",
                sha256=_sha_bytes(Path(experiment.artifact_path).read_bytes()),
            ),
            pipeline_ref=plan.plan.pipeline_ref,
            strategy_hashes=(),
            model_hashes=tuple(lineage["model_hashes"]),
            ordered_feature_schema_hash=plan.plan.feature_schema_hash,
            universe=plan.plan.universe,
            timeframe=plan.plan.timeframe,
            risk_policy_ref=plan.plan.risk_policy_ref,
            cost_policy_ref=plan.plan.cost_policy_ref,
            execution_policy_ref=plan.plan.execution_policy_ref,
            git_sha=plan.plan.git_sha,
            environment_digest=plan.plan.environment_digest,
            evaluation_evidence_refs=(),
        )
        stored, created = self._insert(manifest, lineage)
        if created:
            self._record_event(
                stored.candidate_id,
                stored.version,
                "BACKTEST_VERIFIED",
                {"review_ref": str(review_ref).strip()},
                manifest_digest(stored),
            )
        return stored

    def retrain(
        self,
        experiment_id: str,
        review_ref: str,
        *,
        experiment: ExperimentEvidence,
        model_refs: tuple[ArtifactRef, ...],
    ) -> CandidateManifest:
        """Retraining always yields a new candidate version, never a mutation."""
        if not model_refs:
            raise ValueError("RETRAIN_ARTIFACTS_REQUIRED")
        for ref in model_refs:
            self._resolve(ref)
        plan = self._checked_experiment(experiment_id, review_ref, experiment)
        current = self._latest_version(f"cand_{experiment_id}")
        number = int(current.lstrip("v")) + 1
        lineage = self._compute_lineage(
            plan.plan_digest,
            plan.plan.pipeline_ref,
            {
                "risk": plan.plan.risk_policy_ref,
                "cost": plan.plan.cost_policy_ref,
                "execution": plan.plan.execution_policy_ref,
            },
            extra_model_refs=model_refs,
        )
        manifest = CandidateManifest(
            candidate_id=f"cand_{experiment_id}",
            version=f"v{number}",
            runtime_plan_ref=ArtifactRef(
                kind="plan",
                id=plan.plan.plan_id,
                version=plan.plan.version,
                sha256=plan.plan_digest,
            ),
            completed_experiment_ref=ArtifactRef(
                kind="experiment-result",
                id=experiment_id,
                version="v1",
                sha256=_sha_bytes(Path(experiment.artifact_path).read_bytes()),
            ),
            pipeline_ref=plan.plan.pipeline_ref,
            strategy_hashes=(),
            model_hashes=tuple(lineage["model_hashes"]),
            ordered_feature_schema_hash=plan.plan.feature_schema_hash,
            universe=plan.plan.universe,
            timeframe=plan.plan.timeframe,
            risk_policy_ref=plan.plan.risk_policy_ref,
            cost_policy_ref=plan.plan.cost_policy_ref,
            execution_policy_ref=plan.plan.execution_policy_ref,
            git_sha=plan.plan.git_sha,
            environment_digest=plan.plan.environment_digest,
            evaluation_evidence_refs=(),
        )
        stored, created = self._insert(manifest, lineage)
        if created:
            self._record_event(
                stored.candidate_id,
                stored.version,
                "BACKTEST_VERIFIED",
                {"review_ref": str(review_ref).strip(), "retrained": True},
                manifest_digest(stored),
            )
        return stored

    # -- verify / get / transition --------------------------------------------------

    def verify(self, ref: ArtifactRef) -> VerifiedCandidate:
        manifest = self.get(ref)
        stored = self._load_lineage(manifest.candidate_id, manifest.version)
        extra = tuple(_ref_from_json(raw) for raw in stored["extra_model_refs"])
        current = self._compute_lineage(
            stored["plan_digest"],
            manifest.pipeline_ref,
            {
                "risk": manifest.risk_policy_ref,
                "cost": manifest.cost_policy_ref,
                "execution": manifest.execution_policy_ref,
            },
            extra_model_refs=extra,
        )
        if current != stored:
            raise ValueError(
                f"CANDIDATE_LINEAGE_MISMATCH:{manifest.candidate_id}:"
                f"{manifest.version}: stored bytes no longer match packaged lineage"
            )
        digest = manifest_digest(manifest)
        return VerifiedCandidate(
            candidate=manifest,
            candidate_digest=digest,
            verified_at_utc=_utcnow(self._clock),
        )

    def transition(
        self,
        candidate_id: str,
        event: str,
        *,
        evidence_refs: tuple[ArtifactRef, ...] = (),
        note: str = "",
    ) -> CandidateRecord:
        if event not in _LIFECYCLE_EVENTS:
            raise ValueError(f"CANDIDATE_EVENT_UNKNOWN:{event}")
        manifest = self._load_manifest(candidate_id, self._latest_version(candidate_id))
        frozen = manifest_digest(manifest)
        evidence = [ref.sha256 for ref in evidence_refs]
        for ref in evidence_refs:
            self._resolve(ref)
        snapshot: dict[str, Any] = {"config_digest": frozen, "evidence": evidence}
        if note:
            snapshot["note"] = note
        if event == "SHADOW_REGISTER":
            snapshot["runtime_plan_digest"] = manifest.runtime_plan_ref.sha256
            snapshot["policy_digests"] = {
                "risk": manifest.risk_policy_ref.sha256,
                "cost": manifest.cost_policy_ref.sha256,
                "execution": manifest.execution_policy_ref.sha256,
            }
        self._record_event(candidate_id, manifest.version, event, snapshot, frozen)
        if manifest_digest(self._load_manifest(candidate_id, manifest.version)) != frozen:
            raise ValueError(f"FROZEN_CONFIG_MUTATED:{candidate_id}")
        return self.record(candidate_id, manifest.version)

    def _record_event(
        self,
        candidate_id: str,
        version: str,
        event: str,
        snapshot: dict[str, Any],
        config_digest: str,
    ) -> None:
        with self._db:
            row = self._db.execute(
                "SELECT COUNT(*) AS n FROM candidate_events "
                "WHERE candidate_id = ? AND version = ?",
                (candidate_id, version),
            ).fetchone()
            entry = {
                "event": event,
                "at": _utcnow(self._clock).isoformat(),
                "config_digest": config_digest,
                **snapshot,
            }
            self._db.execute(
                "INSERT INTO candidate_events (candidate_id, version, seq, event_json) "
                "VALUES (?, ?, ?, ?)",
                (candidate_id, version, int(row["n"]), json.dumps(entry, sort_keys=True)),
            )

    def record(self, candidate_id: str, version: str) -> CandidateRecord:
        manifest = self._load_manifest(candidate_id, version)
        rows = self._db.execute(
            "SELECT event_json FROM candidate_events "
            "WHERE candidate_id = ? AND version = ? ORDER BY seq ASC",
            (candidate_id, version),
        ).fetchall()
        events = tuple(dict(json.loads(row["event_json"])) for row in rows)
        lifecycle = events[-1]["event"] if events else "REGISTERED"
        return CandidateRecord(
            candidate_id=candidate_id,
            version=version,
            config_digest=manifest_digest(manifest),
            lifecycle=lifecycle,
            events=events,
        )
