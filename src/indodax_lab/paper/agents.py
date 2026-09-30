"""Isolated durable forward-shadow agents (RW5-01).

``AgentFactory`` binds one immutable candidate to one exclusive namespace
with immutable starting cash, and drives each agent through the shared
RP-04 ``RuntimeKernel`` over simulator/shadow venues plus one
``ExecutionStateStore`` per agent namespace.

Guarantees (docs/implementation/CONTRACTS.md):
- Agent A effects cannot move B cash/positions/orders/cursor: each agent
  owns one SQLite store file under the factory root, keyed by its unique
  namespace; kernels and venues are per-agent instances.
- Namespace collision or candidate replacement rejects with a specific
  reason; prior committed evidence is preserved.
- Duplicate same-bytes events are no-op replays via store idempotency;
  conflicting bytes halt only the affected agent.
- Corruption halts the affected agent with an incident ref; others trade on.
- Retire preserves every evidence row; retired agents reject processing.
- Lifecycle: REGISTERED -> RUNNING <-> PAUSED -> RETIRED; failures enter
  HALTED; recover() enters RECOVERY (store recovery) and verified
  restoration permits PAUSED (or HALTED when the store latched halt),
  then explicit resume via start().
- No live execution authority: this module never imports a live venue.

No network / credentials / live DB. Fake clocks and tmp storage in tests.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, ConfigDict

from indodax_lab.contracts.identity import ArtifactRef, manifest_digest
from indodax_lab.contracts.workbench import AgentManifest
from indodax_lab.execution.state_store import (
    CorruptStateError,
    EventConflictError,
    ExecutionStateError,
    ExecutionStateStore,
    HaltedStateError,
    RevisionMismatchError,
)
from indodax_lab.runtime.kernel import RuntimeKernel

_LIFECYCLES = ("REGISTERED", "RUNNING", "PAUSED", "HALTED", "RETIRED")


class AgentError(Exception):
    """Fail-closed agent lifecycle/admission rejection with a reason code."""


class AgentRecord(BaseModel):
    """Durable agent identity: manifest ref, lifecycle, cursor, incidents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    version: str
    manifest_digest: str
    candidate_ref: ArtifactRef
    cohort_id: str
    namespace: str
    lifecycle: str
    cursor: str | None = None
    coverage_gap: str | None = None
    incident_refs: tuple[str, ...] = ()
    initial_cash: str = "0"
    venue_name: str = "simulator"


class AgentRecoveryReport(BaseModel):
    """Agent-level recovery evidence over the store recovery report."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: str
    version: str
    namespace: str
    lifecycle: str
    cursor: str | None = None
    coverage_gap: str | None = None
    reloaded_revision: int = 0
    resumed_envelopes: tuple[str, ...] = ()
    reconciled_attempts: tuple[str, ...] = ()
    halted: bool = False
    status: str = "RECOVERED"


def _utcnow(clock: Callable[[], datetime] | None) -> datetime:
    return clock() if clock is not None else datetime.now(UTC)


def _venue_name(venue: Any) -> str:
    name = type(venue).__name__
    if "Simulator" in name:
        return "simulator"
    if "Shadow" in name:
        return "shadow"
    return name


class AgentFactory:
    """Candidate-bound isolated agents over per-namespace durable stores."""

    def __init__(
        self,
        root: Path | str,
        *,
        candidate_resolver: Callable[[ArtifactRef], Any],
        behavior_resolver: Callable[[str], Callable[[Any, Any], tuple]] | None = None,
        venue_factory: Callable[[str], Any] | None = None,
        max_agents: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._root = Path(root)
        self._stores = self._root / "stores"
        self._stores.mkdir(parents=True, exist_ok=True)
        self._resolve_candidate = candidate_resolver
        self._resolve_behavior = behavior_resolver or (
            lambda _agent_id: (lambda _event, _state: ())
        )
        if venue_factory is None:
            from indodax_lab.execution.simulator_venue import SimulatorVenueAdapter

            venue_factory = lambda _agent_id: SimulatorVenueAdapter()  # noqa: E731
        self._venue_factory = venue_factory
        if max_agents is not None and max_agents < 1:
            raise ValueError("AGENT_MAX_AGENTS_INVALID: max_agents must be >= 1")
        self._max_agents = max_agents
        self._clock = clock
        self._lock = threading.RLock()
        self._kernels: dict[tuple[str, str], RuntimeKernel] = {}
        self._db = sqlite3.connect(str(self._root / "agents.sqlite"), timeout=30.0)
        self._db.row_factory = sqlite3.Row
        with self._db:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    manifest_digest TEXT NOT NULL,
                    namespace TEXT NOT NULL UNIQUE,
                    lifecycle TEXT NOT NULL,
                    cursor TEXT,
                    coverage_gap TEXT,
                    incidents_json TEXT NOT NULL,
                    venue_name TEXT NOT NULL,
                    PRIMARY KEY (agent_id, version)
                )
                """
            )

    # -- registry helpers -------------------------------------------------

    def _row(self, agent_id: str, version: str = "v1") -> sqlite3.Row:
        row = self._db.execute(
            "SELECT * FROM agents WHERE agent_id = ? AND version = ?",
            (agent_id, version),
        ).fetchone()
        if row is None:
            raise AgentError(f"AGENT_NOT_FOUND:{agent_id}:{version}")
        return row

    def _record(self, row: sqlite3.Row) -> AgentRecord:
        manifest = AgentManifest.model_validate_json(row["manifest_json"])
        return AgentRecord(
            agent_id=row["agent_id"],
            version=row["version"],
            manifest_digest=row["manifest_digest"],
            candidate_ref=manifest.candidate_ref,
            cohort_id=manifest.cohort_id,
            namespace=row["namespace"],
            lifecycle=row["lifecycle"],
            cursor=row["cursor"],
            coverage_gap=row["coverage_gap"],
            incident_refs=tuple(json.loads(row["incidents_json"])),
            initial_cash=str(manifest.initial_virtual_cash),
            venue_name=row["venue_name"],
        )

    def _set_lifecycle(
        self,
        agent_id: str,
        version: str,
        lifecycle: str,
        *,
        cursor: str | None = None,
        coverage_gap: str | None = None,
        incident: str | None = None,
    ) -> AgentRecord:
        row = self._row(agent_id, version)
        incidents = list(json.loads(row["incidents_json"]))
        if incident is not None:
            incidents.append(incident)
        with self._db:
            self._db.execute(
                "UPDATE agents SET lifecycle = ?, cursor = COALESCE(?, cursor), "
                "coverage_gap = COALESCE(?, coverage_gap), incidents_json = ? "
                "WHERE agent_id = ? AND version = ?",
                (
                    lifecycle,
                    cursor,
                    coverage_gap,
                    json.dumps(incidents),
                    agent_id,
                    version,
                ),
            )
        return self._record(self._row(agent_id, version))

    def _store_path(self, namespace: str) -> Path:
        return self._stores / f"{namespace}.db"

    def _open_store(self, row: sqlite3.Row) -> ExecutionStateStore:
        manifest = AgentManifest.model_validate_json(row["manifest_json"])
        return ExecutionStateStore(
            self._store_path(row["namespace"]),
            namespace=row["namespace"],
            initial_cash=manifest.initial_virtual_cash,
        )

    def _ensure_kernel(self, agent_id: str, version: str = "v1") -> RuntimeKernel:
        key = (agent_id, version)
        cached = self._kernels.get(key)
        if cached is not None:
            return cached
        row = self._row(agent_id, version)
        manifest = AgentManifest.model_validate_json(row["manifest_json"])
        try:
            bound = self._resolve_candidate(manifest.candidate_ref)
        except (KeyError, ValueError) as exc:
            raise AgentError(f"AGENT_CANDIDATE_UNRESOLVED:{agent_id}:{exc}") from exc
        if getattr(bound, "candidate_digest", None) != manifest.candidate_ref.sha256:
            raise AgentError(f"AGENT_CANDIDATE_IDENTITY_MISMATCH:{agent_id}")
        store = self._open_store(row)
        venue = self._venue_factory(agent_id)
        candidate_runtime = SimpleNamespace(
            plan_digest=getattr(bound, "plan_digest", f"plan_{agent_id}"),
            candidate_digest=bound.candidate_digest,
            evaluate=self._resolve_behavior(agent_id),
            held_exits={},
        )
        kernel = RuntimeKernel(
            candidate_runtime=candidate_runtime,
            store=store,
            venue=venue,
            venue_name=_venue_name(venue),
            risk_stage=lambda intents, _state: tuple(intents),
        )
        self._kernels[key] = kernel
        return kernel

    # -- lifecycle ----------------------------------------------------------

    def count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) AS n FROM agents").fetchone()
        return int(row["n"])

    def register(self, manifest: AgentManifest) -> AgentRecord:
        digest = manifest_digest(manifest)
        with self._lock:
            existing = self._db.execute(
                "SELECT * FROM agents WHERE agent_id = ? AND version = ?",
                (manifest.agent_id, manifest.version),
            ).fetchone()
            if existing is not None:
                if existing["manifest_digest"] != digest:
                    raise AgentError(
                        f"AGENT_CANDIDATE_REPLACEMENT_REJECTED:{manifest.agent_id}:"
                        f"{manifest.version}: same identity carries different bytes"
                    )
                return self._record(existing)
            clash = self._db.execute(
                "SELECT agent_id FROM agents WHERE namespace = ?",
                (manifest.namespace_id,),
            ).fetchone()
            if clash is not None:
                raise AgentError(
                    f"AGENT_NAMESPACE_COLLISION:{manifest.namespace_id}: "
                    f"already owned by '{clash['agent_id']}'"
                )
            if self._max_agents is not None:
                active = self._db.execute(
                    "SELECT COUNT(*) AS n FROM agents WHERE lifecycle != 'RETIRED'"
                ).fetchone()
                if int(active["n"]) >= self._max_agents:
                    raise AgentError(
                        f"AGENT_ADMISSION_DEFERRED:{manifest.agent_id}: "
                        f"reserved {active['n']}/{self._max_agents} agent slots; "
                        "measured host headroom required before new admission"
                    )
            try:
                bound = self._resolve_candidate(manifest.candidate_ref)
            except (KeyError, ValueError, LookupError) as exc:
                raise AgentError(
                    f"AGENT_CANDIDATE_UNRESOLVED:{manifest.agent_id}:{exc}"
                ) from exc
            if getattr(bound, "candidate_digest", None) != manifest.candidate_ref.sha256:
                raise AgentError(
                    f"AGENT_CANDIDATE_IDENTITY_MISMATCH:{manifest.agent_id}: "
                    "reference digest does not match resolved candidate"
                )
            # Exclusive namespace with immutable starting cash.
            ExecutionStateStore(
                self._store_path(manifest.namespace_id),
                namespace=manifest.namespace_id,
                initial_cash=manifest.initial_virtual_cash,
            )
            venue_name = _venue_name(self._venue_factory(manifest.agent_id))
            with self._db:
                self._db.execute(
                    "INSERT INTO agents (agent_id, version, manifest_json, "
                    "manifest_digest, namespace, lifecycle, cursor, coverage_gap, "
                    "incidents_json, venue_name) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        manifest.agent_id,
                        manifest.version,
                        manifest.model_dump_json(),
                        digest,
                        manifest.namespace_id,
                        "REGISTERED",
                        None,
                        None,
                        json.dumps([]),
                        venue_name,
                    ),
                )
            return self._record(self._row(manifest.agent_id, manifest.version))

    def start(self, agent_id: str, version: str = "v1") -> AgentRecord:
        with self._lock:
            row = self._row(agent_id, version)
            if row["lifecycle"] == "RETIRED":
                raise AgentError(f"AGENT_RETIRED:{agent_id}")
            if row["lifecycle"] == "HALTED":
                raise AgentError(
                    f"AGENT_HALTED_USE_RECOVER:{agent_id}: "
                    "recover before resume"
                )
            if row["lifecycle"] == "RUNNING":
                return self._record(row)
            return self._set_lifecycle(agent_id, version, "RUNNING")

    def pause(self, agent_id: str, version: str = "v1") -> AgentRecord:
        with self._lock:
            row = self._row(agent_id, version)
            if row["lifecycle"] == "RETIRED":
                raise AgentError(f"AGENT_RETIRED:{agent_id}")
            if row["lifecycle"] != "RUNNING":
                raise AgentError(
                    f"AGENT_NOT_RUNNING:{agent_id}:{row['lifecycle']}"
                )
            cursor = self._store_cursor(row)
            return self._set_lifecycle(
                agent_id, version, "PAUSED", cursor=cursor, coverage_gap=cursor
            )

    def retire(self, agent_id: str, version: str = "v1") -> AgentRecord:
        with self._lock:
            row = self._row(agent_id, version)
            if row["lifecycle"] == "RETIRED":
                return self._record(row)
            cursor = self._store_cursor(row)
            self._kernels.pop((agent_id, version), None)
            return self._set_lifecycle(agent_id, version, "RETIRED", cursor=cursor)

    def recover(self, agent_id: str, version: str = "v1") -> AgentRecoveryReport:
        with self._lock:
            row = self._row(agent_id, version)
            if row["lifecycle"] == "RETIRED":
                raise AgentError(f"AGENT_RETIRED:{agent_id}")
            store = self._open_store(row)
            try:
                store_report = store.recover()
            except CorruptStateError as exc:
                incident = f"AGENT_STORE_CORRUPT:{agent_id}:{exc}"
                self._set_lifecycle(agent_id, version, "HALTED", incident=incident)
                raise AgentError(incident) from exc
            self._kernels.pop((agent_id, version), None)
            try:
                cursor = store.restore().feed_cursor
            except CorruptStateError as exc:
                incident = f"AGENT_STORE_CORRUPT:{agent_id}:{exc}"
                self._set_lifecycle(agent_id, version, "HALTED", incident=incident)
                raise AgentError(incident) from exc
            lifecycle = "HALTED" if store_report.halted else "PAUSED"
            record = self._set_lifecycle(
                agent_id, version, lifecycle, cursor=cursor
            )
            return AgentRecoveryReport(
                agent_id=agent_id,
                version=version,
                namespace=row["namespace"],
                lifecycle=record.lifecycle,
                cursor=cursor,
                coverage_gap=record.coverage_gap,
                reloaded_revision=store_report.reloaded_revision,
                resumed_envelopes=tuple(store_report.resumed_envelopes),
                reconciled_attempts=tuple(store_report.reconciled_attempts),
                halted=store_report.halted,
                status=store_report.status,
            )

    def get(self, agent_id: str, version: str = "v1") -> AgentRecord:
        row = self._row(agent_id, version)
        cursor = self._store_cursor(row)
        if cursor != row["cursor"]:
            with self._db:
                self._db.execute(
                    "UPDATE agents SET cursor = ? WHERE agent_id = ? AND version = ?",
                    (cursor, agent_id, version),
                )
            row = self._row(agent_id, version)
        return self._record(row)

    def list_agents(self) -> list[AgentRecord]:
        rows = self._db.execute(
            "SELECT * FROM agents ORDER BY agent_id ASC, version ASC"
        ).fetchall()
        return [self._record(row) for row in rows]

    # -- event routing -------------------------------------------------------

    def _store_cursor(self, row: sqlite3.Row) -> str | None:
        try:
            return self._open_store(row).restore().feed_cursor
        except CorruptStateError:
            return row["cursor"]

    def _store_of(self, agent_id: str, version: str = "v1") -> ExecutionStateStore:
        return self._open_store(self._row(agent_id, version))

    def process(self, agent_id: str, event: Any, version: str = "v1") -> Any:
        with self._lock:
            row = self._row(agent_id, version)
            if row["lifecycle"] == "RETIRED":
                raise AgentError(f"AGENT_RETIRED:{agent_id}")
            if row["lifecycle"] != "RUNNING":
                raise AgentError(
                    f"AGENT_NOT_RUNNING:{agent_id}:{row['lifecycle']}"
                )
            kernel = self._ensure_kernel(agent_id, version)
            try:
                result = kernel.process(event)
            except EventConflictError as exc:
                incident = (
                    f"AGENT_EVENT_CONFLICT:{agent_id}:{event.event_id}:"
                    f"{_utcnow(self._clock).isoformat()}"
                )
                self._set_lifecycle(agent_id, version, "HALTED", incident=incident)
                raise AgentError(f"{incident}:{exc}") from exc
            except (HaltedStateError, RevisionMismatchError, CorruptStateError) as exc:
                incident = (
                    f"AGENT_STORE_FAULT:{agent_id}:{type(exc).__name__}:"
                    f"{_utcnow(self._clock).isoformat()}"
                )
                self._set_lifecycle(agent_id, version, "HALTED", incident=incident)
                raise AgentError(f"{incident}:{exc}") from exc
            except ExecutionStateError as exc:
                incident = (
                    f"AGENT_STORE_FAULT:{agent_id}:{exc}:"
                    f"{_utcnow(self._clock).isoformat()}"
                )
                self._set_lifecycle(agent_id, version, "HALTED", incident=incident)
                raise AgentError(incident) from exc
            with self._db:
                self._db.execute(
                    "UPDATE agents SET cursor = ? WHERE agent_id = ? AND version = ?",
                    (result.cursor, agent_id, version),
                )
            return result

    def apply_fill(self, agent_id: str, fill: Any, version: str = "v1") -> Any:
        with self._lock:
            row = self._row(agent_id, version)
            if row["lifecycle"] == "RETIRED":
                raise AgentError(f"AGENT_RETIRED:{agent_id}")
            if row["lifecycle"] not in ("RUNNING", "PAUSED"):
                raise AgentError(
                    f"AGENT_NOT_RUNNING:{agent_id}:{row['lifecycle']}"
                )
            store = self._open_store(row)
            try:
                return store.apply_fill(fill, store.restore().revision)
            except ExecutionStateError as exc:
                incident = (
                    f"AGENT_FILL_FAULT:{agent_id}:{type(exc).__name__}:"
                    f"{_utcnow(self._clock).isoformat()}"
                )
                self._set_lifecycle(agent_id, version, "HALTED", incident=incident)
                raise AgentError(f"{incident}:{exc}") from exc


__all__ = [
    "AgentError",
    "AgentFactory",
    "AgentRecord",
    "AgentRecoveryReport",
]
