"""Service lifecycle, single-writer locking, and host profiles (OPS-01).

Contract: systemd service/timer or equivalent local host supervisor -> start/stop/restart with explicit roots and env.

Guarantees:
1. OPS-01-AC0: Services start/stop/restart with explicit environment and host profile.
2. OPS-01-AC1: Cold boot single-writer lock strictly prevents two concurrent writers (ConcurrentWriterLockError).
3. OPS-01-AC2: SIGTERM signal triggers buffer flush and releases active lease lock.
4. OPS-01-AC3: Missing secrets fail closed without printing secret contents in error messages or logs.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import BinaryIO, Callable, Mapping, Sequence
from pydantic import BaseModel, ConfigDict, Field


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
    ) -> None:
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

    def start(self) -> None:
        """Start the managed service, refusing to run unconfigured."""
        # Credentials are resolved first: a start hook must never observe a
        # half-configured process, and a refusal must publish no RUNNING state.
        self._verify_required_secrets()
        self._run_hook("start", self._start_hook)
        self.status = "RUNNING"
        self.is_flushed = False

    def stop(self) -> None:
        """Stop the managed service."""
        self._run_hook("stop", self._stop_hook)
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
            self.is_flushed = True
            self.active_lease = None
            self.status = "STOPPED"


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
        )
        self._services[service_name] = srv
        return srv

    def get_service(self, service_name: str) -> ManagedService | None:
        """Return the registered service, or None when it was never registered."""
        return self._services.get(service_name)

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
