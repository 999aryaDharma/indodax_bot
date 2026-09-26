"""Regression tests for the OPS-01 service lifecycle review findings.

Spec: ``docs/specs/17-operations-security-and-recovery.md`` -> OPS-01,
"Missing secret fail tanpa mencetak secret", and the module's own declared
guarantee 4 (OPS-01-AC3: missing secrets fail closed without printing secret
contents in error messages or logs).

Findings covered:

- **OPS-01-F1 (Important)**: AC3 was satisfied only in isolation.
  ``ServiceManager.resolve_secret`` exists and is correct on its own, but
  nothing in the lifecycle ever calls it. ``register_service`` accepts no
  credential requirement and ``ManagedService.start()`` invokes the start hook
  unconditionally, so a service that needs ``TELEGRAM_BOT_TOKEN`` happily starts
  with the credential unconfigured. The guarantee held only if some caller
  happened to remember to resolve the secret first, and the supervisor had no
  way to require it.
- **OPS-01-F2 (Important)**: ``ServiceManager.register_service`` silently
  overwrites an existing registration. Re-registering a name orphans the live
  instance -- still running, still holding its single-writer lock and lease,
  but now unreachable through the manager, so a supervisor-driven stop/restart
  can no longer reach it. The registry must fail closed on a duplicate name.

Isolation: every test builds an in-process ``HostServiceProfile`` and injects a
plain ``dict`` environment (monkeypatched ``os.environ`` only on the pre-fix
signature, via pytest's automatic cleanup). No service is spawned, no OS
supervisor is driven, no real data root, lock directory, ledger or order is
touched, and no network is used.
"""

from __future__ import annotations

import pytest

import indodax_lab.operations.service_lifecycle as lifecycle_mod
from indodax_lab.operations.service_lifecycle import (
    HostServiceProfile,
    MissingSecretError,
    ServiceManager,
)

# Resolved lazily so the suite still collects against a module that does not yet
# accept the new keyword arguments.
_FAIL_CLOSED_ERRORS: tuple[type[BaseException], ...] = tuple(
    error
    for error in (
        MissingSecretError,
        getattr(lifecycle_mod, "LifecycleOperationError", RuntimeError),
    )
    if isinstance(error, type) and issubclass(error, BaseException)
)

_SECRET_KEY = "TELEGRAM_BOT_TOKEN"
_SECRET_VALUE = "123456:AAFakeTokenValueThatMustNeverLeak"
_SECOND_SECRET_KEY = "INDODAX_API_SECRET"


def _profile(host_name: str = "lenovo_thinkpad") -> HostServiceProfile:
    return HostServiceProfile(host_name=host_name, allowed_worker_threads=4)


def _manager(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> ServiceManager:
    """Build a manager fed by an injected environment; nothing real is consulted."""
    try:
        return ServiceManager(profile=_profile(), env=env)
    except TypeError:
        # Pre-fix the manager has no environment injection point. Fall back to a
        # monkeypatched os.environ (auto-restored) so the test still reaches the
        # production code path rather than a stub.
        for key in (_SECRET_KEY, _SECOND_SECRET_KEY):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return ServiceManager(profile=_profile())


def _register(
    manager: ServiceManager,
    service_name: str,
    events: list[str],
    **kwargs: object,
):
    """Register a service, tolerating the pre-fix signature that lacks the kwarg."""
    hooks: dict[str, object] = {
        "start_hook": lambda: events.append("start") or True,
        "stop_hook": lambda: events.append("stop") or True,
        "flush_hook": lambda: events.append("flush") or True,
    }
    hooks.update(kwargs)
    try:
        return manager.register_service(service_name=service_name, **hooks)  # type: ignore[arg-type]
    except TypeError:
        hooks.pop("required_secrets", None)
        return manager.register_service(service_name=service_name, **hooks)  # type: ignore[arg-type]


def _call_expecting_failure(func, *args, **kwargs) -> BaseException | None:
    try:
        func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - the failure mode is the assertion
        return exc
    return None


# ---------------------------------------------------------------------------
# OPS-01-F1: a required credential is resolved before the start hook runs
# ---------------------------------------------------------------------------


def test_start_fails_closed_when_a_required_secret_is_missing(monkeypatch) -> None:
    """OPS-01-F1: an unset required credential must stop the service before start."""
    events: list[str] = []
    manager = _manager(monkeypatch, {})
    service = _register(
        manager, "lab-collector", events, required_secrets=(_SECRET_KEY,)
    )

    failure = _call_expecting_failure(service.start)

    assert failure is not None, (
        f"start() succeeded with {_SECRET_KEY} unset, so the service runs against an "
        "unconfigured credential instead of failing closed (OPS-01-AC3)"
    )
    assert events == [], f"the start hook ran despite the missing credential: {events}"
    assert service.status == "STOPPED", (
        f"a fail-closed start still published status {service.status!r}"
    )


def test_missing_secret_error_leaks_neither_name_nor_value(monkeypatch) -> None:
    """OPS-01-F1: the refusal must not print the secret name or its value."""
    events: list[str] = []
    # A value is present in the environment, so a leaking message would have one
    # to echo; the refusal must still name neither key nor value.
    manager = _manager(monkeypatch, {_SECRET_KEY: _SECRET_VALUE})
    service = _register(
        manager,
        "lab-collector",
        events,
        required_secrets=(_SECRET_KEY, _SECOND_SECRET_KEY),
    )

    failure = _call_expecting_failure(service.start)

    assert failure is not None, "an unset required credential did not fail closed"
    message = f"{failure}"
    assert _SECRET_VALUE not in message, "the error message printed the secret value"
    assert _SECRET_KEY not in message, (
        f"the error message printed the secret name: {message!r}"
    )
    assert _SECOND_SECRET_KEY not in message, (
        f"the error message printed the missing secret name: {message!r}"
    )


def test_partially_configured_secrets_still_fail_closed(monkeypatch) -> None:
    """OPS-01-F1: one present secret must not mask a second missing secret."""
    events: list[str] = []
    manager = _manager(monkeypatch, {_SECRET_KEY: _SECRET_VALUE})
    service = _register(
        manager,
        "lab-collector",
        events,
        required_secrets=(_SECRET_KEY, _SECOND_SECRET_KEY),
    )

    failure = _call_expecting_failure(service.start)

    assert failure is not None, (
        "the service started although only one of its two required secrets was set"
    )
    assert events == [], f"the start hook ran on a partial configuration: {events}"


def test_start_succeeds_when_every_required_secret_is_present(monkeypatch) -> None:
    """OPS-01-F1 positive control: a fully configured service still starts."""
    events: list[str] = []
    manager = _manager(
        monkeypatch, {_SECRET_KEY: _SECRET_VALUE, _SECOND_SECRET_KEY: "s3cr3t"}
    )
    service = _register(
        manager,
        "lab-collector",
        events,
        required_secrets=(_SECRET_KEY, _SECOND_SECRET_KEY),
    )

    service.start()

    assert service.status == "RUNNING"
    assert events == ["start"]


def test_blank_secret_value_is_treated_as_missing(monkeypatch) -> None:
    """OPS-01-F1: a whitespace-only credential is not a configured credential."""
    events: list[str] = []
    manager = _manager(monkeypatch, {_SECRET_KEY: "   "})
    service = _register(
        manager, "lab-collector", events, required_secrets=(_SECRET_KEY,)
    )

    failure = _call_expecting_failure(service.start)

    assert failure is not None, (
        "a whitespace-only credential was accepted as configured, so the service "
        "would start with an unusable credential"
    )
    assert events == []


def test_restart_rechecks_required_secrets(monkeypatch) -> None:
    """OPS-01-F1: a restart must not resurrect a service whose credential vanished."""
    env: dict[str, str] = {_SECRET_KEY: _SECRET_VALUE}
    events: list[str] = []
    manager = _manager(monkeypatch, env)
    service = _register(
        manager, "lab-collector", events, required_secrets=(_SECRET_KEY,)
    )
    service.start()
    assert service.status == "RUNNING"

    # The supervisor's environment is rotated out while the service runs.
    env.clear()

    failure = _call_expecting_failure(service.restart)

    assert failure is not None, (
        "restart() started the service again after its required credential was "
        "removed from the environment"
    )
    assert service.status == "STOPPED", "a refused restart left the service RUNNING"
    assert events == ["start", "stop"], (
        f"the lifecycle ran past the missing credential: {events}"
    )


# ---------------------------------------------------------------------------
# OPS-01-F2: the service registry fails closed on a duplicate name
# ---------------------------------------------------------------------------


def test_duplicate_service_registration_is_rejected(monkeypatch) -> None:
    """OPS-01-F2: re-registering a service name must not orphan the live entry."""
    events: list[str] = []
    manager = _manager(monkeypatch, {})
    first = _register(manager, "lab-collector", events)

    failure = _call_expecting_failure(_register, manager, "lab-collector", events)

    assert failure is not None, (
        "register_service accepted a duplicate service name, silently replacing the "
        "live registration so the manager can no longer stop or restart it"
    )
    assert "SERVICE_ALREADY_REGISTERED" in f"{failure}"
    assert manager._services.get("lab-collector") is first
    assert first.status == "STOPPED"


def test_duplicate_registration_of_a_running_service_is_rejected(monkeypatch) -> None:
    """OPS-01-F2: the rejection must hold even when the orphan would be running."""
    events: list[str] = []
    manager = _manager(monkeypatch, {_SECRET_KEY: _SECRET_VALUE})
    first = _register(
        manager, "lab-collector", events, required_secrets=(_SECRET_KEY,)
    )
    first.start()
    assert first.status == "RUNNING"

    failure = _call_expecting_failure(
        _register,
        manager,
        "lab-collector",
        events,
        required_secrets=(_SECRET_KEY,),
    )

    assert failure is not None, (
        "a second registration silently replaced a RUNNING service, so the manager "
        "lost its handle on a live process still holding its writer lock and lease"
    )
    assert manager._services.get("lab-collector") is first
    assert first.status == "RUNNING", "the live service was disturbed by the duplicate"


def test_distinct_service_names_still_register(monkeypatch) -> None:
    """OPS-01-F2 guard: the duplicate guard must not block legitimate services."""
    events: list[str] = []
    manager = _manager(monkeypatch, {})

    first = _register(manager, "lab-collector", events)
    second = _register(manager, "lab-shadow", events)

    assert first is not second
    assert set(manager._services) == {"lab-collector", "lab-shadow"}


def test_secret_gate_is_optional_for_services_that_need_no_credentials(monkeypatch) -> None:
    """OPS-01-F1 guard: declaring no requirements must not block a plain service."""
    events: list[str] = []
    manager = _manager(monkeypatch, {})

    service = _register(manager, "lab-collector", events)
    service.start()

    assert service.status == "RUNNING"
    assert events == ["start"]
