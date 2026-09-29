"""Service lifecycle, single-writer locking, and host profiles (OPS-01).

Contract: systemd service/timer or equivalent local host supervisor -> start/stop/restart with explicit roots and env.

Guarantees:
1. OPS-01-AC0: Services start/stop/restart with explicit environment and host profile.
2. OPS-01-AC1: Cold boot single-writer lock strictly prevents two concurrent writers (ConcurrentWriterLockError).
3. OPS-01-AC2: SIGTERM signal triggers buffer flush and releases active lease lock.
4. OPS-01-AC3: Missing secrets fail closed without printing secret contents in error messages or logs.
5. OPS-01-AC4: Supervised start admits only within a configured thread budget that
   preserves Production headroom; Research load breaching headroom is rejected.
6. OPS-01-AC5: Supervised start resolves each configured storage path to its
   actual mount/device (via recovery.resolve_path_mount) and enforces a shared
   per-device reserve; unresolvable paths fail closed.
7. OPS-01-AC6: Unattended-recovery windows are recorded as operator-pending
   artifacts; blind order retry or bypassed entry blocks can never be recorded.
8. ADR-009: Production vs Research domain split is verified fail-closed
   (distinct names, data roots, credentials, writer resources).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from indodax_lab.operations.recovery import MountCapacityInfo


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConcurrentWriterLockError(RuntimeError):
    """Raised when a concurrent writer attempts to acquire an active writer lease."""


class MissingSecretError(ValueError):
    """Raised when an environment secret is missing, without leaking the secret name or contents."""


class LifecycleOperationError(RuntimeError):
    """Raised when no concrete lifecycle hook exists or a hook fails."""


# ---------------------------------------------------------------------------
# Service domains (ADR-009) and capacity budgets (OPS-01-AC4)
# ---------------------------------------------------------------------------

_SERVICE_DOMAINS = ("production", "research", "unspecified")


class ServiceCapacityBudget(BaseModel):
    """Thread budget for one host with a reserved Production headroom (OPS-01-AC4).

    Test fixtures supply their own numbers; none of these values are measured
    production defaults. The 24h soak / measured ASUS numbers remain an
    operator-owned pending item: this model enforces the admission arithmetic,
    not the physical measurement.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_total_threads: int = Field(ge=1)
    production_reserved_threads: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_reserve_within_total(self) -> ServiceCapacityBudget:
        if self.production_reserved_threads > self.max_total_threads:
            raise ValueError("PRODUCTION_RESERVE_EXCEEDS_TOTAL")
        return self

    @property
    def research_headroom_threads(self) -> int:
        """Threads Research may occupy without touching Production headroom."""
        return self.max_total_threads - self.production_reserved_threads


def verify_production_research_isolation(services: Sequence[ManagedService]) -> None:
    """Fail closed when Production and Research authority domains overlap (ADR-009).

    Production Main owns live credentials and write paths; Research Runtime
    must not share them. Every violation raises LifecycleOperationError with a
    stable code. Credential *names* are never echoed: AC3 redaction applies to
    isolation diagnostics too.
    """
    productions = [
        s for s in services if getattr(s, "service_domain", "unspecified") == "production"
    ]
    researches = [
        s for s in services if getattr(s, "service_domain", "unspecified") == "research"
    ]
    for prod in productions:
        for res in researches:
            if prod.service_name == res.service_name:
                raise LifecycleOperationError(
                    "DOMAIN_ISOLATION_VIOLATION:SHARED_SERVICE_NAME: Production and Research "
                    "must run as distinct service identities (ADR-009)."
                )
            if prod.profile.data_root == res.profile.data_root:
                raise LifecycleOperationError(
                    "DOMAIN_ISOLATION_VIOLATION:SHARED_DATA_ROOT: Production and Research "
                    "must not share one data root (ADR-009)."
                )
            if set(prod.required_secrets) & set(res.required_secrets):
                raise LifecycleOperationError(
                    "DOMAIN_ISOLATION_VIOLATION:SHARED_CREDENTIAL: Production and Research "
                    "declare overlapping credential requirements (ADR-009)."
                )
            prod_lock = getattr(prod, "writer_lock", None)
            res_lock = getattr(res, "writer_lock", None)
            if (
                prod_lock is not None
                and res_lock is not None
                and prod_lock.lock_path == res_lock.lock_path
            ):
                raise LifecycleOperationError(
                    "DOMAIN_ISOLATION_VIOLATION:SHARED_WRITER_LOCK: Production and Research "
                    "must hold distinct writer resources (ADR-009)."
                )


# ---------------------------------------------------------------------------
# Host Profiles
# ---------------------------------------------------------------------------


class HostServiceProfile(BaseModel):
    """Resource and filesystem profile for a host machine executing lab services."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host_name: str
    allowed_worker_threads: int = Field(ge=1)
    data_root: str = "/var/data/indodax_lab"


# ---------------------------------------------------------------------------
# Single Writer Lock (OPS-01-AC1)
# ---------------------------------------------------------------------------


class SingleWriterLock:
    """Fenced single-writer lock protecting data stores against concurrent write split-brain."""

    def __init__(self, resource_id: str, *, lock_root: Path | str | None = None) -> None:
        if not resource_id:
            raise ValueError("LOCK_RESOURCE_ID_REQUIRED")
        self.resource_id = resource_id
        self.current_writer: str | None = None
        root = Path(lock_root) if lock_root is not None else Path(tempfile.gettempdir()) / "indodax_lab_writer_locks"
        self.lock_root = root
        safe_name = hashlib.sha256(resource_id.encode("utf-8")).hexdigest()
        self.lock_path = root / f"{safe_name}.lock"
        self._lock_file: BinaryIO | None = None

    @property
    def is_locked(self) -> bool:
        return self.current_writer is not None

    def acquire(self, writer_id: str) -> None:
        """Acquire the single writer lock for writer_id.

        Raises:
            ConcurrentWriterLockError: If the lock is already held by another writer.
        """
        if not writer_id:
            raise ValueError("LOCK_WRITER_ID_REQUIRED")
        if self.current_writer == writer_id and self._lock_file is not None:
            return
        if self.current_writer is not None:
            raise ConcurrentWriterLockError(
                f"CONCURRENT_WRITER_FORBIDDEN: Lock for '{self.resource_id}' is already held "
                f"by '{self.current_writer}'. Simultaneous writers are strictly prohibited (OPS-01-AC1)."
            )
        self.lock_root.mkdir(parents=True, exist_ok=True)
        lock_file = self.lock_path.open("a+b")
        try:
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            lock_file.close()
            raise ConcurrentWriterLockError(
                f"CONCURRENT_WRITER_FORBIDDEN: resource '{self.resource_id}' is already locked"
            ) from exc

        try:
            metadata = json.dumps(
                {
                    "owner": writer_id,
                    "pid": os.getpid(),
                    "resource_id": self.resource_id,
                },
                sort_keys=True,
            ).encode("utf-8")
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(metadata)
            lock_file.flush()
            os.fsync(lock_file.fileno())
        except Exception:
            self._unlock_file(lock_file)
            lock_file.close()
            raise
        self._lock_file = lock_file
        self.current_writer = writer_id

    def release(self, writer_id: str) -> None:
        """Release the single writer lock."""
        if self.current_writer != writer_id or self._lock_file is None:
            raise ConcurrentWriterLockError(
                f"LOCK_OWNER_MISMATCH: writer '{writer_id}' does not own resource '{self.resource_id}'"
            )
        lock_file = self._lock_file
        self._unlock_file(lock_file)
        lock_file.close()
        self._lock_file = None
        self.current_writer = None

    @staticmethod
    def _unlock_file(lock_file: BinaryIO) -> None:
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Managed Service (OPS-01-AC0, AC2)
# ---------------------------------------------------------------------------


class ManagedService:
    """Supervised service process responding to lifecycle commands and signals."""

    def __init__(
        self,
        service_name: str,
        profile: HostServiceProfile,
        *,
        start_hook: Callable[[], bool] | None = None,
        stop_hook: Callable[[], bool] | None = None,
        flush_hook: Callable[[], bool] | None = None,
        required_secrets: Sequence[str] = (),
        secret_resolver: Callable[[str], str] | None = None,
        writer_lock: SingleWriterLock | None = None,
        writer_id: str | None = None,
        service_domain: str = "unspecified",
        worker_threads: int = 1,
    ) -> None:
        if service_domain not in _SERVICE_DOMAINS:
            raise ValueError(f"UNKNOWN_SERVICE_DOMAIN:{service_domain}")
        if worker_threads < 1:
            raise ValueError("WORKER_THREADS_MUST_BE_POSITIVE")
        self.service_name = service_name
        self.profile = profile
        self.status = "STOPPED"
        self.is_flushed = False
        self.active_lease: str | None = None
        self.required_secrets: tuple[str, ...] = tuple(required_secrets)
        self._start_hook = start_hook
        self._stop_hook = stop_hook
        self._flush_hook = flush_hook
        self._secret_resolver = secret_resolver
        # OPS-01-AC1: the writer lock is acquired at start, not merely available.
        self.writer_lock = writer_lock
        self.writer_id = writer_id or service_name
        # ADR-009: authority domain this service runs in.
        self.service_domain = service_domain
        # OPS-01-AC4: thread demand counted against the host capacity budget.
        self.worker_threads = worker_threads

    def _verify_required_secrets(self) -> None:
        """Fail closed before any start hook runs when a credential is unset.

        OPS-01-AC3 is only real if the lifecycle itself enforces it. Every
        declared requirement is resolved through the supervisor's resolver, which
        raises ``MissingSecretError`` for an absent or blank credential. Values
        are deliberately not retained here: the gate exists to prove the service
        is configured, not to duplicate credentials in process memory.
        """
        if not self.required_secrets:
            return
        if self._secret_resolver is None:
            raise LifecycleOperationError("SECRET_RESOLVER_UNAVAILABLE")
        for secret_key in self.required_secrets:
            self._secret_resolver(secret_key)

    def _run_hook(self, operation: str, hook: Callable[[], bool] | None) -> None:
        if hook is None:
            raise LifecycleOperationError(f"LIFECYCLE_UNSUPPORTED:{operation}")
        try:
            succeeded = hook()
        except Exception as exc:
            raise LifecycleOperationError(f"{operation.upper()}_FAILED") from exc
        if succeeded is not True:
            raise LifecycleOperationError(f"{operation.upper()}_FAILED")

    def _acquire_writer_lock(self) -> bool:
        """Acquire the writer lock when one is configured (OPS-01-AC1).

        Returns True when this call took ownership. A lock held by another
        writer raises ConcurrentWriterLockError and the service never starts.
        """
        lock = self.writer_lock
        if lock is None:
            return False
        if lock.is_locked and lock.current_writer == self.writer_id:
            return False
        lock.acquire(self.writer_id)
        return True

    def _release_writer_lock(self) -> None:
        """Release the writer lock when this service owns it."""
        lock = self.writer_lock
        if lock is None:
            return
        if lock.current_writer == self.writer_id:
            lock.release(self.writer_id)

    def start(self) -> None:
        """Start the managed service, refusing to run unconfigured."""
        # Credentials are resolved first: a start hook must never observe a
        # half-configured process, and a refusal must publish no RUNNING state.
        self._verify_required_secrets()
        # OPS-01-AC1: take the single-writer lease before any start hook runs,
        # so a duplicate writer can never reach RUNNING beside us.
        acquired_here = self._acquire_writer_lock()
        try:
            self._run_hook("start", self._start_hook)
        except BaseException:
            if acquired_here:
                self._release_writer_lock()
            raise
        self.status = "RUNNING"
        self.is_flushed = False

    def stop(self) -> None:
        """Stop the managed service."""
        self._run_hook("stop", self._stop_hook)
        self._release_writer_lock()
        self.status = "STOPPED"

    def restart(self) -> None:
        """Restart the managed service cleanly."""
        self.stop()
        self.start()

    def acquire_lease(self, lease_token: str) -> None:
        """Attach an active fencing lease to this service instance."""
        self.active_lease = lease_token

    def handle_signal(self, signal_name: str) -> None:
        """Handle POSIX shutdown signals (SIGTERM, SIGINT) gracefully (OPS-01-AC2)."""
        if signal_name in ("SIGTERM", "SIGINT"):
            # Only publish successful lifecycle state after concrete flush and
            # process-stop evidence has completed.
            self._run_hook("flush", self._flush_hook)
            self._run_hook("stop", self._stop_hook)
            self._release_writer_lock()
            self.is_flushed = True
            self.active_lease = None
            self.status = "STOPPED"


# ---------------------------------------------------------------------------
# Unattended recovery recording (OPS-01-AC6)
# ---------------------------------------------------------------------------


class UnattendedRecoveryRecord(BaseModel):
    """Recorded intent for a 12-hour unattended incident window (OPS-01-AC6).

    The recording framework validates the safety shape (entry blocks
    preserved, manual resume required, no blind order retry) and persists the
    artifact. The physical 12-hour watch itself cannot be synthesized: a fresh
    record stays UNVERIFIED with no operator acknowledgement until an operator
    completes the run on the host.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    host_name: str
    window_started_at_utc: datetime
    window_hours: int = 12
    scenarios: tuple[str, ...]
    entry_blocks_preserved: bool = True
    manual_resume_required: bool = True
    blind_order_retry_detected: bool = False
    operator_acknowledged_at_utc: datetime | None = None
    workload_status: str = "UNVERIFIED"


def record_unattended_recovery(
    host_name: str,
    output_path: Path,
    scenarios: Sequence[str],
    *,
    window_hours: int = 12,
    entry_blocks_preserved: bool = True,
    manual_resume_required: bool = True,
    blind_order_retry_detected: bool = False,
) -> UnattendedRecoveryRecord:
    """Record an unattended-recovery qualification window (OPS-01-AC6).

    Fail-closed validation: a record that bypasses entry blocks, drops the
    manual-resume requirement, or reports a blind order retry is refused and
    nothing is persisted.
    """
    if not host_name or not host_name.strip():
        raise LifecycleOperationError("UNATTENDED_RECORD_INVALID:HOST_NAME_REQUIRED")
    if not scenarios:
        raise LifecycleOperationError("UNATTENDED_RECORD_INVALID:SCENARIOS_EMPTY")
    if window_hours <= 0:
        raise LifecycleOperationError("UNATTENDED_RECORD_INVALID:WINDOW_MUST_BE_POSITIVE")
    if blind_order_retry_detected:
        raise LifecycleOperationError(
            "UNATTENDED_RECORD_INVALID:BLIND_ORDER_RETRY: uncertain orders must resume "
            "manually, never via blind retry (OPS-01-AC6)."
        )
    if not entry_blocks_preserved:
        raise LifecycleOperationError(
            "UNATTENDED_RECORD_INVALID:ENTRY_BLOCKS_BYPASSED: operator absence must not "
            "bypass entry blocks (OPS-01-AC6)."
        )
    if not manual_resume_required:
        raise LifecycleOperationError(
            "UNATTENDED_RECORD_INVALID:MANUAL_RESUME_REQUIRED: recovery after stale feed, "
            "disconnection, process death or uncertain orders requires manual resume "
            "(OPS-01-AC6)."
        )
    report = UnattendedRecoveryRecord(
        host_name=host_name,
        window_started_at_utc=datetime.now(UTC),
        window_hours=window_hours,
        scenarios=tuple(scenarios),
        entry_blocks_preserved=True,
        manual_resume_required=True,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Service Manager (OPS-01-AC0, AC3)
# ---------------------------------------------------------------------------


class ServiceManager:
    """Supervisor coordinating services, host profiles, and secure environment secrets."""

    def __init__(
        self,
        profile: HostServiceProfile,
        *,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.profile = profile
        self._services: dict[str, ManagedService] = {}
        # None means "consult the live process environment at resolve time";
        # an injected mapping makes the credential source explicit and testable.
        self._env = env
        # OPS-01-AC4: unset until the operator configures a budget; supervised
        # starts refuse while it is unset (fail closed, never a silent pass).
        self._capacity_budget: ServiceCapacityBudget | None = None
        # OPS-01-AC5: configured storage paths + per-device reserve, unset until
        # the operator configures them.
        self._storage_paths: tuple[str, ...] = ()
        self._storage_reserve_bytes: int = 0

    def _current_env(self) -> Mapping[str, str]:
        return os.environ if self._env is None else self._env

    def register_service(
        self,
        service_name: str,
        *,
        start_hook: Callable[[], bool] | None = None,
        stop_hook: Callable[[], bool] | None = None,
        flush_hook: Callable[[], bool] | None = None,
        required_secrets: Sequence[str] = (),
        writer_lock: SingleWriterLock | None = None,
        writer_id: str | None = None,
        service_domain: str = "unspecified",
        worker_threads: int = 1,
    ) -> ManagedService:
        """Register a new service under this manager's host profile.

        Raises:
            LifecycleOperationError: If the name is already registered. Silently
                replacing an entry would orphan a live service that still holds
                its writer lock and lease while the manager can no longer reach it.
        """
        if service_name in self._services:
            raise LifecycleOperationError(
                f"SERVICE_ALREADY_REGISTERED:{service_name}"
            )
        srv = ManagedService(
            service_name=service_name,
            profile=self.profile,
            start_hook=start_hook,
            stop_hook=stop_hook,
            flush_hook=flush_hook,
            required_secrets=required_secrets,
            secret_resolver=self._resolve_for_service,
            writer_lock=writer_lock,
            writer_id=writer_id,
            service_domain=service_domain,
            worker_threads=worker_threads,
        )
        self._services[service_name] = srv
        return srv

    def get_service(self, service_name: str) -> ManagedService | None:
        """Return the registered service, or None when it was never registered."""
        return self._services.get(service_name)

    def verify_isolation(self) -> None:
        """Verify the ADR-009 Production/Research split across registered services."""
        verify_production_research_isolation(list(self._services.values()))

    def configure_capacity_budget(self, budget: ServiceCapacityBudget) -> None:
        """Install the host thread budget (OPS-01-AC4)."""
        self._capacity_budget = budget

    def configure_storage_paths(
        self, paths: Sequence[str | Path], *, reserve_bytes: int
    ) -> None:
        """Install configured storage paths + per-device reserve (OPS-01-AC5)."""
        if not paths:
            raise ValueError("STORAGE_PATHS_CANNOT_BE_EMPTY")
        if reserve_bytes < 1:
            raise ValueError("STORAGE_RESERVE_MUST_BE_POSITIVE")
        self._storage_paths = tuple(str(p) for p in paths)
        self._storage_reserve_bytes = reserve_bytes

    def inventory_mounts(self, paths: Sequence[str | Path]) -> dict[str, MountCapacityInfo]:
        """Resolve each configured path to its mount + device (OPS-01-AC5).

        Reuses the recovery.py mount resolver; unknown mappings fail closed
        with PATH_MOUNT_UNRESOLVED instead of a silent pass.
        """
        from indodax_lab.operations.recovery import resolve_path_mount

        inventory: dict[str, MountCapacityInfo] = {}
        for raw in paths:
            try:
                inventory[str(raw)] = resolve_path_mount(Path(raw))
            except (OSError, ValueError) as exc:
                raise LifecycleOperationError(
                    f"PATH_MOUNT_UNRESOLVED:{raw}: mount cannot be determined (OPS-01-AC5)."
                ) from exc
        return inventory

    def _check_capacity_admission(self, service: ManagedService) -> None:
        """Enforce thread budget + Production headroom before start (OPS-01-AC4)."""
        budget = self._capacity_budget
        if budget is None:
            raise LifecycleOperationError(
                "CAPACITY_BUDGET_UNCONFIGURED: supervised start requires a configured "
                "capacity budget preserving Production headroom (OPS-01-AC4)."
            )
        running = [s for s in self._services.values() if s.status == "RUNNING"]
        total = sum(s.worker_threads for s in running)
        if total + service.worker_threads > budget.max_total_threads:
            raise LifecycleOperationError(
                f"CAPACITY_BUDGET_EXCEEDED: admitting '{service.service_name}' "
                f"({service.worker_threads} threads) would exceed host budget "
                f"{budget.max_total_threads} (OPS-01-AC4)."
            )
        if service.service_domain != "production":
            nonprod = sum(s.worker_threads for s in running if s.service_domain != "production")
            if nonprod + service.worker_threads > budget.research_headroom_threads:
                raise LifecycleOperationError(
                    f"PRODUCTION_HEADROOM_EXCEEDED: admitting '{service.service_name}' "
                    f"({service.worker_threads} threads) would consume Production "
                    f"headroom of {budget.production_reserved_threads} threads (OPS-01-AC4)."
                )

    def _check_storage_admission(self) -> None:
        """Enforce per-device mount reserve before start (OPS-01-AC5)."""
        if not self._storage_paths:
            return
        inventory = self.inventory_mounts(self._storage_paths)
        by_device: dict[str, list[str]] = {}
        for raw, info in inventory.items():
            by_device.setdefault(info.device, []).append(raw)
        for device, raws in by_device.items():
            required = self._storage_reserve_bytes * len(raws)
            free = inventory[raws[0]].free_bytes
            if free < required:
                raise LifecycleOperationError(
                    f"MOUNT_RESERVE_EXCEEDED:{device}: {free} bytes free below reserve "
                    f"{required} bytes for {len(raws)} path(s) sharing the device "
                    "(OPS-01-AC5)."
                )

    def _lookup(self, service_name: str) -> ManagedService:
        service = self._services.get(service_name)
        if service is None:
            raise LifecycleOperationError(f"UNKNOWN_SERVICE:{service_name}")
        return service

    def start_service(self, service_name: str) -> ManagedService:
        """Supervised start: isolation + budget + mount guards, then start."""
        service = self._lookup(service_name)
        self.verify_isolation()
        self._check_capacity_admission(service)
        self._check_storage_admission()
        service.start()
        return service

    def stop_service(self, service_name: str) -> ManagedService:
        """Supervised stop: stop hook, then release the writer lock."""
        service = self._lookup(service_name)
        service.stop()
        return service

    def restart_service(self, service_name: str) -> ManagedService:
        """Supervised restart: stop, then re-admit and start."""
        self.stop_service(service_name)
        return self.start_service(service_name)

    def _resolve_for_service(self, secret_key: str) -> str:
        return self.resolve_secret(secret_key, self._current_env())

    def resolve_secret(self, secret_key: str, env_dict: Mapping[str, str]) -> str:
        """Resolve a sensitive credential from environment dictionary (OPS-01-AC3).

        Raises:
            MissingSecretError: If the credential key is absent or blank. The
                message never names the key or echoes the value, so an error
                surfaced in a supervisor log or traceback cannot leak either.
        """
        val = env_dict.get(secret_key)
        if not val or not val.strip():
            raise MissingSecretError(
                "MISSING_SECRET: A required security credential is not set in the environment. "
                "Execution failed closed without leaking confidential details (OPS-01-AC3)."
            )
        return val
