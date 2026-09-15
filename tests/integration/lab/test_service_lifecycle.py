"""Integration tests for OPS-01: Host profiles and service lifecycle.

RED tests written before implementation.

Contract: systemd service/timer or equivalent local host supervisor -> start/stop/restart with explicit roots and env.

AC boundaries:
- AC0: Services start/stop/restart with explicit environment and host profile.
- AC1: Cold boot single-writer lock strictly prevents two concurrent writers (ConcurrentWriterLockError).
- AC2: SIGTERM signal triggers buffer flush and releases active lease lock.
- AC3: Missing secrets fail-closed without printing secret contents in error messages or logs.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import pytest

# These imports will fail until implementation exists — RED phase
from indodax_lab.operations.service_lifecycle import (
    ConcurrentWriterLockError,
    HostServiceProfile,
    ManagedService,
    MissingSecretError,
    ServiceManager,
    SingleWriterLock,
)


# ---------------------------------------------------------------------------
# AC0: Services start/stop/restart with explicit environment and host profile
# ---------------------------------------------------------------------------

def test_ops_01_valid_contract():
    """OPS-01-AC0: ServiceManager starts, restarts, and stops services under Lenovo host profile."""
    profile = HostServiceProfile(
        host_name="lenovo_thinkpad",
        allowed_worker_threads=8,
        data_root="/var/data/indodax_lab",
    )
    manager = ServiceManager(profile=profile)
    events: list[str] = []
    service = manager.register_service(
        service_name="lab-collector",
        start_hook=lambda: events.append("start") or True,
        stop_hook=lambda: events.append("stop") or True,
        flush_hook=lambda: events.append("flush") or True,
    )

    assert service.status == "STOPPED"

    service.start()
    assert service.status == "RUNNING"

    service.restart()
    assert service.status == "RUNNING"

    service.stop()
    assert service.status == "STOPPED"
    assert events == ["start", "stop", "start", "stop"]


# ---------------------------------------------------------------------------
# AC1: Cold boot single-writer lock prevents concurrent writers
# ---------------------------------------------------------------------------

def test_ops_01_contract_1(tmp_path: Path):
    """OPS-01-AC1: Attempting to acquire a writer lock when one is already held raises ConcurrentWriterLockError."""
    lock = SingleWriterLock(resource_id="db_writer_lease", lock_root=tmp_path)
    independent_lock = SingleWriterLock(resource_id="db_writer_lease", lock_root=tmp_path)

    # First writer acquires lock successfully
    lock.acquire(writer_id="host_lenovo_primary")
    assert lock.is_locked is True
    assert lock.current_writer == "host_lenovo_primary"

    # Second concurrent writer attempts to acquire the same lock
    with pytest.raises(ConcurrentWriterLockError):
        independent_lock.acquire(writer_id="host_asus_secondary")

    # Release and ensure lock is freed
    with pytest.raises(ConcurrentWriterLockError, match="OWNER"):
        lock.release(writer_id="host_asus_secondary")
    lock.release(writer_id="host_lenovo_primary")
    assert lock.is_locked is False


# ---------------------------------------------------------------------------
# AC2: SIGTERM signal flushes buffers and releases lease
# ---------------------------------------------------------------------------

def test_ops_01_contract_2():
    """OPS-01-AC2: SIGTERM triggers graceful flush and active lease release."""
    profile = HostServiceProfile(host_name="lenovo_thinkpad", allowed_worker_threads=4)
    manager = ServiceManager(profile=profile)
    events: list[str] = []
    service = manager.register_service(
        service_name="lab-shadow",
        start_hook=lambda: events.append("start") or True,
        stop_hook=lambda: events.append("stop") or True,
        flush_hook=lambda: events.append("flush") or True,
    )

    service.start()
    service.acquire_lease(lease_token="lease_shadow_123")

    # Simulate SIGTERM signal handling
    service.handle_signal(signal_name="SIGTERM")

    assert service.status == "STOPPED"
    assert service.is_flushed is True
    assert service.active_lease is None, "Lease must be released on SIGTERM"
    assert events == ["start", "flush", "stop"]


# ---------------------------------------------------------------------------
# AC3: Missing secret fails closed without printing secret contents
# ---------------------------------------------------------------------------

def test_ops_01_contract_3():
    """OPS-01-AC3: Missing secret raises MissingSecretError without leaking secret name or content."""
    profile = HostServiceProfile(host_name="lenovo_thinkpad", allowed_worker_threads=4)
    manager = ServiceManager(profile=profile)

    # Attempt to initialize service requiring unconfigured secret
    with pytest.raises(MissingSecretError) as excinfo:
        manager.resolve_secret(secret_key="TELEGRAM_BOT_TOKEN", env_dict={})

    err_msg = str(excinfo.value)
    assert "MISSING_SECRET" in err_msg
    # Ensure error does not print raw secret or dummy credentials
    assert "ghp_" not in err_msg
    assert "token123" not in err_msg


def test_managed_service_without_hooks_fails_closed() -> None:
    profile = HostServiceProfile(host_name="offline", allowed_worker_threads=1)
    unsupported = ManagedService("unsupported", profile)

    with pytest.raises(RuntimeError, match="UNSUPPORTED"):
        unsupported.start()
    with pytest.raises(RuntimeError, match="UNSUPPORTED"):
        unsupported.handle_signal("SIGTERM")

    assert unsupported.status == "STOPPED"
    assert unsupported.is_flushed is False
    assert unsupported.active_lease is None


def test_failed_flush_does_not_release_lease_or_claim_success() -> None:
    profile = HostServiceProfile(host_name="offline", allowed_worker_threads=1)
    service = ManagedService(
        "guarded",
        profile,
        start_hook=lambda: True,
        stop_hook=lambda: True,
        flush_hook=lambda: False,
    )
    service.start()
    service.acquire_lease("lease")

    with pytest.raises(RuntimeError, match="FLUSH_FAILED"):
        service.handle_signal("SIGTERM")

    assert service.status == "RUNNING"
    assert service.is_flushed is False
    assert service.active_lease == "lease"


def _hold_process_lock(lock_root: str, connection) -> None:
    lock = SingleWriterLock("process-death", lock_root=Path(lock_root))
    lock.acquire("child")
    connection.send("locked")
    connection.recv()


def test_os_lock_is_released_when_owner_process_dies(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe()
    process = context.Process(
        target=_hold_process_lock,
        args=(str(tmp_path), child_connection),
    )
    process.start()
    try:
        assert parent_connection.poll(10), "child did not acquire lock within 10 seconds"
        assert parent_connection.recv() == "locked"
        assert process.is_alive()

        contender = SingleWriterLock("process-death", lock_root=tmp_path)
        with pytest.raises(ConcurrentWriterLockError):
            contender.acquire("parent-before-death")

        process.terminate()
        process.join(timeout=10)
        assert not process.is_alive()

        contender.acquire("parent-after-death")
        assert contender.current_writer == "parent-after-death"
        contender.release("parent-after-death")
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        parent_connection.close()
        child_connection.close()
