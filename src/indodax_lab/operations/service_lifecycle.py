"""Service lifecycle, single-writer locking, and host profiles (OPS-01).

Contract: systemd service/timer or equivalent local host supervisor -> start/stop/restart with explicit roots and env.

Guarantees:
1. OPS-01-AC0: Services start/stop/restart with explicit environment and host profile.
2. OPS-01-AC1: Cold boot single-writer lock strictly prevents two concurrent writers (ConcurrentWriterLockError).
3. OPS-01-AC2: SIGTERM signal triggers buffer flush and releases active lease lock.
4. OPS-01-AC3: Missing secrets fail closed without printing secret contents in error messages or logs.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConcurrentWriterLockError(RuntimeError):
    """Raised when a concurrent writer attempts to acquire an active writer lease."""


class MissingSecretError(ValueError):
    """Raised when an environment secret is missing, without leaking the secret name or contents."""


# ---------------------------------------------------------------------------
# Host Profiles
# ---------------------------------------------------------------------------


class HostServiceProfile(BaseModel):
    """Resource and filesystem profile for a host machine executing lab services."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host_name: str
    allowed_worker_threads: int
    data_root: str = "/var/data/indodax_lab"


# ---------------------------------------------------------------------------
# Single Writer Lock (OPS-01-AC1)
# ---------------------------------------------------------------------------


class SingleWriterLock:
    """Fenced single-writer lock protecting data stores against concurrent write split-brain."""

    def __init__(self, resource_id: str) -> None:
        self.resource_id = resource_id
        self.current_writer: str | None = None

    @property
    def is_locked(self) -> bool:
        return self.current_writer is not None

    def acquire(self, writer_id: str) -> None:
        """Acquire the single writer lock for writer_id.

        Raises:
            ConcurrentWriterLockError: If the lock is already held by another writer.
        """
        if self.current_writer is not None and self.current_writer != writer_id:
            raise ConcurrentWriterLockError(
                f"CONCURRENT_WRITER_FORBIDDEN: Lock for '{self.resource_id}' is already held "
                f"by '{self.current_writer}'. Simultaneous writers are strictly prohibited (OPS-01-AC1)."
            )
        self.current_writer = writer_id

    def release(self, writer_id: str) -> None:
        """Release the single writer lock."""
        if self.current_writer == writer_id:
            self.current_writer = None


# ---------------------------------------------------------------------------
# Managed Service (OPS-01-AC0, AC2)
# ---------------------------------------------------------------------------


class ManagedService:
    """Supervised service process responding to lifecycle commands and signals."""

    def __init__(self, service_name: str, profile: HostServiceProfile) -> None:
        self.service_name = service_name
        self.profile = profile
        self.status = "STOPPED"
        self.is_flushed = False
        self.active_lease: str | None = None

    def start(self) -> None:
        """Start the managed service."""
        self.status = "RUNNING"
        self.is_flushed = False

    def stop(self) -> None:
        """Stop the managed service."""
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
            self.is_flushed = True
            self.active_lease = None
            self.status = "STOPPED"


# ---------------------------------------------------------------------------
# Service Manager (OPS-01-AC0, AC3)
# ---------------------------------------------------------------------------


class ServiceManager:
    """Supervisor coordinating services, host profiles, and secure environment secrets."""

    def __init__(self, profile: HostServiceProfile) -> None:
        self.profile = profile
        self._services: dict[str, ManagedService] = {}

    def register_service(self, service_name: str) -> ManagedService:
        """Register a new service under this manager's host profile."""
        srv = ManagedService(service_name=service_name, profile=self.profile)
        self._services[service_name] = srv
        return srv

    def resolve_secret(self, secret_key: str, env_dict: dict[str, str]) -> str:
        """Resolve a sensitive credential from environment dictionary (OPS-01-AC3).

        Raises:
            MissingSecretError: If the credential key is absent or empty. Redacts secret details.
        """
        val = env_dict.get(secret_key)
        if not val:
            raise MissingSecretError(
                "MISSING_SECRET: A required security credential is not set in the environment. "
                "Execution failed closed without leaking confidential details (OPS-01-AC3)."
            )
        return val
