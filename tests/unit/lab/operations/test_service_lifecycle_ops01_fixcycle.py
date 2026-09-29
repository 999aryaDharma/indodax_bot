"""Fix-cycle regression tests for the OPS-01 coordinator blocking set (2026-09-27).

Reviewer ses_f1eba02acffeFn9j3Cr7HPRGUq, IMPORTANT findings:

- **OPS-01-R1**: AC4/AC5/AC6 wholly absent — no budgets/headroom enforcement,
  no mount inventory, no unattended recovery wired into the service lifecycle.
- **OPS-01-R2**: SingleWriterLock never acquired by ManagedService — duplicate
  writers possible despite AC1.
- **OPS-01-R3**: ADR-009 isolation unproven — shared user/env/workdir/data_root,
  no Production/Research split enforced.

Each test tolerates the pre-fix API (missing kwargs/methods) via
_call_expecting_failure so RED is a real AssertionError about absent
fail-closed behavior, never a ModuleNotFoundError.

Isolation: tmp_path lock roots and injected dicts only. No service is
spawned, no OS supervisor is driven, no real data root/ledger/order is
touched, and no network is used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import indodax_lab.operations.service_lifecycle as lifecycle_mod
from indodax_lab.operations.service_lifecycle import (
    ConcurrentWriterLockError,
    HostServiceProfile,
    LifecycleOperationError,
    ManagedService,
    ServiceManager,
    SingleWriterLock,
)


def _profile(
    host_name: str = "asus", data_root: str = "/var/data/indodax_lab"
) -> HostServiceProfile:
    return HostServiceProfile(
        host_name=host_name, allowed_worker_threads=4, data_root=data_root
    )


def _hooks(events: list[str]) -> dict:
    return {
        "start_hook": lambda: events.append("start") or True,
        "stop_hook": lambda: events.append("stop") or True,
        "flush_hook": lambda: events.append("flush") or True,
    }


def _call_expecting_failure(func, *args, **kwargs) -> BaseException | None:
    try:
        func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001 - the failure mode is the assertion
        return exc
    return None


def _register(manager: ServiceManager, name: str, events: list[str], **kwargs) -> object:
    """Register tolerating the pre-fix signature; returns service or failure."""
    hooks = _hooks(events)
    hooks.update(kwargs)
    try:
        return manager.register_service(service_name=name, **hooks)  # type: ignore[arg-type]
    except TypeError as exc:
        return exc


# ---------------------------------------------------------------------------
# OPS-01-R2: ManagedService must acquire the SingleWriterLock at start
# ---------------------------------------------------------------------------


def test_duplicate_writers_rejected_at_service_start(tmp_path: Path) -> None:
    """OPS-01-R2: two services on one writer resource cannot both be RUNNING."""
    events_a: list[str] = []
    events_b: list[str] = []
    manager = ServiceManager(profile=_profile())
    first = _register(
        manager,
        "lab-collector",
        events_a,
        writer_lock=SingleWriterLock("ops01-writer", lock_root=tmp_path),
        writer_id="writer-a",
    )
    second = _register(
        manager,
        "lab-shadow",
        events_b,
        writer_lock=SingleWriterLock("ops01-writer", lock_root=tmp_path),
        writer_id="writer-b",
    )
    assert not isinstance(first, BaseException), f"precondition: {first!r}"
    assert not isinstance(second, BaseException), f"precondition: {second!r}"

    first.start()
    assert first.status == "RUNNING"

    failure = _call_expecting_failure(second.start)

    assert isinstance(failure, ConcurrentWriterLockError), (
        f"second writer on the same resource started (or failed open): {failure!r}"
    )
    assert second.status == "STOPPED"
    assert events_b == [], f"losing writer ran its start hook: {events_b}"


def test_service_stop_releases_writer_lock_for_next_writer(tmp_path: Path) -> None:
    """OPS-01-R2: stop() must hand the writer resource back (no leaked lock)."""
    events_a: list[str] = []
    manager = ServiceManager(profile=_profile())
    first = _register(
        manager,
        "lab-collector",
        events_a,
        writer_lock=SingleWriterLock("ops01-handoff", lock_root=tmp_path),
        writer_id="writer-a",
    )
    assert not isinstance(first, BaseException), f"precondition: {first!r}"
    first.start()
    first.stop()

    contender = SingleWriterLock("ops01-handoff", lock_root=tmp_path)
    contender.acquire("writer-b")
    assert contender.current_writer == "writer-b"
    contender.release("writer-b")


def test_failed_start_hook_does_not_leak_writer_lock(tmp_path: Path) -> None:
    """OPS-01-R2: a start hook failure after lock acquisition must release."""
    events: list[str] = []
    manager = ServiceManager(profile=_profile())
    service = _register(
        manager,
        "lab-collector",
        events,
        start_hook=lambda: False,
        stop_hook=lambda: True,
        flush_hook=lambda: True,
        writer_lock=SingleWriterLock("ops01-noleak", lock_root=tmp_path),
        writer_id="writer-a",
    )
    assert not isinstance(service, BaseException), f"precondition: {service!r}"

    failure = _call_expecting_failure(service.start)

    assert isinstance(failure, LifecycleOperationError), f"hook failure: {failure!r}"
    contender = SingleWriterLock("ops01-noleak", lock_root=tmp_path)
    try:
        contender.acquire("writer-b")
    except ConcurrentWriterLockError as exc:
        pytest.fail(f"failed start leaked the writer lock: {exc}")
    contender.release("writer-b")


# ---------------------------------------------------------------------------
# OPS-01-R3: ADR-009 Production/Research isolation enforced in code
# ---------------------------------------------------------------------------


def test_shared_data_root_between_domains_is_rejected() -> None:
    """OPS-01-R3: Production and Research sharing one data_root must fail closed."""
    manager = ServiceManager(profile=_profile())
    events: list[str] = []
    prod = _register(
        manager, "prod-main", events, service_domain="production",
        required_secrets=(),
    )
    research = _register(
        manager, "research-runtime", events, service_domain="research",
        required_secrets=(),
    )
    assert not isinstance(prod, BaseException), f"precondition: {prod!r}"
    assert not isinstance(research, BaseException), f"precondition: {research!r}"

    failure = _call_expecting_failure(manager.verify_isolation)

    assert failure is not None, (
        "Production and Research share data_root "
        f"{_profile().data_root!r} with no isolation verdict — split unproven (ADR-009)"
    )
    assert isinstance(failure, LifecycleOperationError), f"isolation: {failure!r}"
    assert "DOMAIN_ISOLATION_VIOLATION" in f"{failure}"


def test_shared_credential_between_domains_is_rejected() -> None:
    """OPS-01-R3: Research must not require a Production credential."""
    prod_profile = _profile(host_name="asus-prod", data_root="/var/data/prod")
    research_profile = _profile(host_name="asus-research", data_root="/var/data/research")
    prod = ManagedService(
        "prod-main", prod_profile,
        service_domain="production", required_secrets=("INDODAX_API_SECRET",),
    )
    research = ManagedService(
        "research-runtime", research_profile,
        service_domain="research", required_secrets=("INDODAX_API_SECRET",),
    )
    verify = getattr(lifecycle_mod, "verify_production_research_isolation", None)

    failure = _call_expecting_failure(verify, [prod, research]) if verify else None

    assert isinstance(failure, LifecycleOperationError), (
        f"overlapping credential across domains not rejected: {failure!r}"
    )
    assert "DOMAIN_ISOLATION_VIOLATION" in f"{failure}"


def test_genuinely_split_domains_pass_isolation() -> None:
    """OPS-01-R3 positive control: distinct roots + disjoint secrets verify clean."""
    verify = getattr(lifecycle_mod, "verify_production_research_isolation", None)
    assert verify is not None, "isolation verifier absent — split cannot be proven"
    prod_profile = _profile(host_name="asus-prod", data_root="/var/data/prod")
    research_profile = _profile(host_name="asus-research", data_root="/var/data/research")
    try:
        prod = ManagedService(
            "prod-main", prod_profile, service_domain="production",
            required_secrets=("INDODAX_API_SECRET",),
        )
        research = ManagedService(
            "research-runtime", research_profile, service_domain="research",
            required_secrets=("RESEARCH_API_TOKEN",),
        )
    except TypeError as exc:
        pytest.fail(f"domains cannot be declared on a service: {exc}")

    verify([prod, research])  # must not raise


# ---------------------------------------------------------------------------
# OPS-01-R1a (AC4): budget/headroom admission wired into the lifecycle
# ---------------------------------------------------------------------------


def test_supervised_start_requires_a_configured_budget() -> None:
    """OPS-01-AC4: supervised start with no budget configured must fail closed."""
    manager = ServiceManager(profile=_profile())
    events: list[str] = []
    service = _register(manager, "lab-collector", events)
    assert not isinstance(service, BaseException), f"precondition: {service!r}"

    start = getattr(manager, "start_service", None)
    failure = _call_expecting_failure(start, "lab-collector") if start else None

    assert isinstance(failure, LifecycleOperationError), (
        f"supervised start ran with no capacity budget: {failure!r}"
    )
    assert "CAPACITY_BUDGET_UNCONFIGURED" in f"{failure}"
    assert service.status == "STOPPED"


def test_research_admission_preserves_production_headroom() -> None:
    """OPS-01-AC4: Research load that eats Production headroom is rejected."""
    budget_cls = getattr(lifecycle_mod, "ServiceCapacityBudget", None)
    assert budget_cls is not None, "no capacity budget model — AC4 absent"
    manager = ServiceManager(profile=_profile())
    manager.configure_capacity_budget(
        budget_cls(max_total_threads=4, production_reserved_threads=3)
    )
    events: list[str] = []
    heavy = _register(
        manager, "research-heavy", events, service_domain="research", worker_threads=2,
    )
    assert not isinstance(heavy, BaseException), f"precondition: {heavy!r}"

    failure = _call_expecting_failure(manager.start_service, "research-heavy")

    assert isinstance(failure, LifecycleOperationError), f"headroom: {failure!r}"
    assert "PRODUCTION_HEADROOM_EXCEEDED" in f"{failure}" or (
        "CAPACITY_BUDGET_EXCEEDED" in f"{failure}"
    )
    assert heavy.status == "STOPPED"
    assert events == [], f"rejected service ran hooks: {events}"


def test_production_admission_within_budget_starts() -> None:
    """OPS-01-AC4 positive control: Production within budget still starts."""
    budget_cls = getattr(lifecycle_mod, "ServiceCapacityBudget", None)
    assert budget_cls is not None, "no capacity budget model — AC4 absent"
    manager = ServiceManager(profile=_profile(host_name="asus-prod", data_root="/var/data/prod"))
    manager.configure_capacity_budget(
        budget_cls(max_total_threads=4, production_reserved_threads=3)
    )
    events: list[str] = []
    prod = _register(
        manager, "prod-main", events, service_domain="production", worker_threads=1,
    )
    assert not isinstance(prod, BaseException), f"precondition: {prod!r}"

    manager.start_service("prod-main")

    assert prod.status == "RUNNING"
    assert events == ["start"]


# ---------------------------------------------------------------------------
# OPS-01-R1b (AC5): mount inventory wired into the lifecycle
# ---------------------------------------------------------------------------


def test_mount_inventory_maps_each_path_to_its_device(tmp_path: Path) -> None:
    """OPS-01-AC5: every configured path resolves to a mount + device."""
    manager = ServiceManager(profile=_profile())
    inventory = getattr(manager, "inventory_mounts", None)
    assert inventory is not None, "no mount inventory — AC5 absent"
    data_dir = tmp_path / "data"
    ledger_dir = tmp_path / "ledger"
    data_dir.mkdir()
    ledger_dir.mkdir()

    result = inventory([data_dir, ledger_dir])

    assert set(result) == {str(data_dir), str(ledger_dir)}
    for raw, info in result.items():
        assert info.mount_point, f"{raw}: empty mount point"
        assert info.device, f"{raw}: empty device"


def test_unresolvable_mount_fails_closed(tmp_path: Path) -> None:
    """OPS-01-AC5: a path with no resolvable mount blocks supervised start."""
    budget_cls = getattr(lifecycle_mod, "ServiceCapacityBudget", None)
    assert budget_cls is not None, "no capacity budget model — AC4 absent"
    manager = ServiceManager(profile=_profile())
    manager.configure_capacity_budget(
        budget_cls(max_total_threads=4, production_reserved_threads=1)
    )
    missing = tmp_path / "no-such-dir" / "db.sqlite"
    assert hasattr(manager, "configure_storage_paths"), "no storage-path guard — AC5 absent"
    manager.configure_storage_paths([missing], reserve_bytes=1)
    events: list[str] = []
    service = _register(manager, "lab-collector", events)
    assert not isinstance(service, BaseException), f"precondition: {service!r}"

    failure = _call_expecting_failure(manager.start_service, "lab-collector")

    assert isinstance(failure, (LifecycleOperationError, OSError)), f"mounts: {failure!r}"
    assert service.status == "STOPPED"


# ---------------------------------------------------------------------------
# OPS-01-R1c (AC6): unattended-recovery recording framework
# ---------------------------------------------------------------------------


def test_unattended_recovery_record_persists_pending_operator_run(tmp_path: Path) -> None:
    """OPS-01-AC6: the framework records the 12h window as operator-pending."""
    record_fn = getattr(lifecycle_mod, "record_unattended_recovery", None)
    assert record_fn is not None, "no unattended-recovery recording — AC6 absent"
    output = tmp_path / "unattended.json"

    report = record_fn(
        host_name="asus",
        output_path=output,
        scenarios=("stale_feed", "exchange_disconnection", "process_death", "uncertain_orders"),
    )

    assert output.exists(), "recording wrote no artifact"
    assert report.workload_status == "UNVERIFIED"
    assert report.operator_acknowledged_at_utc is None
    assert report.manual_resume_required is True
    assert report.entry_blocks_preserved is True


def test_unattended_record_rejects_blind_order_retry(tmp_path: Path) -> None:
    """OPS-01-AC6: recording a blind order retry must fail closed, never persist."""
    record_fn = getattr(lifecycle_mod, "record_unattended_recovery", None)
    assert record_fn is not None, "no unattended-recovery recording — AC6 absent"
    output = tmp_path / "unattended-blind.json"

    failure = _call_expecting_failure(
        record_fn,
        host_name="asus",
        output_path=output,
        scenarios=("uncertain_orders",),
        blind_order_retry_detected=True,
    )

    assert isinstance(failure, LifecycleOperationError), f"blind retry: {failure!r}"
    assert not output.exists(), "invalid unattended record was persisted"
