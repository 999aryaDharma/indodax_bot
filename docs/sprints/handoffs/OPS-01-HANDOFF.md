# OPS-01 handoff

Status: REVIEW

## Identity
- Sprint ID: OPS-01 — Host profiles and service lifecycle
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ops-01-host-profiles-and-service-lifecycle`
- Base SHA: `f417f7c`
- Code target: `feat(ops-01): host profiles and service lifecycle`
- Evidence SHA relation: `2e55de3`

## Files and contracts
- Actual files:
  - `src/indodax_lab/operations/service_lifecycle.py` (HostServiceProfile, SingleWriterLock, ManagedService, ServiceManager, ConcurrentWriterLockError, MissingSecretError)
  - `src/indodax_lab/operations/__init__.py` (Package exports — OPS-01 symbols added)
  - `tests/integration/lab/test_service_lifecycle.py` (AC0..AC3 integration test cases)
  - `configs/schedules/host_profiles.yaml` (Host profiles configuration: LenovoThinkPad vs AsusZenBook)
  - `deploy/lab-collector.service` (Systemd collector unit)
  - `deploy/lab-shadow.service` (Systemd forward shadow trading unit)
  - `deploy/lab-worker.service` (Systemd background compute worker unit)
- Contract:
  - `systemd service/timer or equivalent local host supervisor -> start/stop/restart with explicit roots and env.`
  - Service lifecycle & host profiles: `ServiceManager` coordinates service start/stop/restart across designated host configurations (OPS-01-AC0).
  - Single-writer locking: Cold boot and runtime single-writer mutex strictly forbids concurrent writers, raising `ConcurrentWriterLockError` (OPS-01-AC1).
  - Graceful signal handling: SIGTERM and SIGINT trigger synchronous buffer flush and release active lease fencing tokens (OPS-01-AC2).
  - Secret redaction & fail-closed: Missing secrets raise `MissingSecretError` without logging or leaking confidential credentials (OPS-01-AC3).
- Migration and compatibility:
  - Additive files in `deploy/`, `configs/schedules/`, and `src/indodax_lab/operations/`; no existing interfaces modified.
  - Dependencies: JOB-02 (REVIEW), SHADOW-02 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| OPS-01-AC0 (RED) | `test_ops_01_valid_contract` | `python -m pytest tests/integration/lab/test_service_lifecycle.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.operations.service_lifecycle') | `working tree` |
| OPS-01-AC0 (GREEN) | `test_ops_01_valid_contract` | `python -m pytest tests/integration/lab/test_service_lifecycle.py::test_ops_01_valid_contract` | Exit 0 (Passed, ServiceManager starts, restarts, and stops services cleanly under host profile) | `2e55de3` |
| OPS-01-AC1 (RED) | `test_ops_01_contract_1` | `python -m pytest tests/integration/lab/test_service_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-01-AC1 (GREEN) | `test_ops_01_contract_1` | `python -m pytest tests/integration/lab/test_service_lifecycle.py::test_ops_01_contract_1` | Exit 0 (Passed, concurrent writer lock attempt raises ConcurrentWriterLockError) | `2e55de3` |
| OPS-01-AC2 (RED) | `test_ops_01_contract_2` | `python -m pytest tests/integration/lab/test_service_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-01-AC2 (GREEN) | `test_ops_01_contract_2` | `python -m pytest tests/integration/lab/test_service_lifecycle.py::test_ops_01_contract_2` | Exit 0 (Passed, SIGTERM flushes buffers and releases active lease lock) | `2e55de3` |
| OPS-01-AC3 (RED) | `test_ops_01_contract_3` | `python -m pytest tests/integration/lab/test_service_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-01-AC3 (GREEN) | `test_ops_01_contract_3` | `python -m pytest tests/integration/lab/test_service_lifecycle.py::test_ops_01_contract_3` | Exit 0 (Passed, missing secret raises MissingSecretError without leaking secret details) | `2e55de3` |

All 4 tests in `tests/integration/lab/test_service_lifecycle.py` passed (0.35s).
Full lab suite verification: 207 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, paper, and regression.

## Review
- Spec verdict: PASS (meets all functional requirements of OPS-01 and docs/specs/17-operations-security-and-recovery.md).
- Quality verdict: PASS (single writer locking, SIGTERM flush and lease release, missing secret fail-closed redaction, systemd unit definitions, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for OPS-01.
- Next unlocked consumers: QA-03.

---

## Sprint review fix cycle — OPS-01 (batch `ops-shadow`)

Actor: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`
Date: 2026-09-27 · Source SHA: uncommitted working tree (`feat/feat-02-finalization`) · Fix cycle: 1 of 1

Spec: `docs/specs/17-operations-security-and-recovery.md` -> OPS-01, "Missing secret fail tanpa mencetak secret".

### Findings fixed

| ID | Severity | Finding |
|---|---|---|
| OPS-01-F1 | Important | **AC3 was satisfied only in isolation.** `ServiceManager.resolve_secret` exists and is correct, but nothing in the lifecycle ever called it. `register_service` accepted no credential requirement and `ManagedService.start()` invoked the start hook unconditionally, so a service needing `TELEGRAM_BOT_TOKEN` started with the credential unconfigured. The declared guarantee held only if some caller happened to remember to resolve the secret first, and the supervisor had no way to *require* it. |
| OPS-01-F2 | Important | `ServiceManager.register_service` silently overwrote an existing registration. Re-registering a name orphaned the live instance — still running, still holding its single-writer lock and lease, but now unreachable through the manager, so a supervisor-driven stop/restart could no longer reach it. |
| OPS-01-F3 | Important | `resolve_secret` used `if not val`, which is truthy for a whitespace-only string. A credential set to `"   "` was accepted as configured, so the gate would pass for an unusable credential. |

### RED evidence (real assertion failures, no assertion weakened/deleted/skipped)

Command: `python -m pytest tests/unit/lab/operations/test_service_lifecycle_secrets.py -p no:cacheprovider -q`
Result: **7 failed, 3 passed** — observed failures:
- `AssertionError: start() succeeded with TELEGRAM_BOT_TOKEN unset, so the service runs against an unconfigured credential instead of failing closed (OPS-01-AC3)` (`assert None is not None`).
- `AssertionError: the error message printed the secret name` — no fail-closed refusal existed at all.
- `AssertionError: the service started although only one of its two required secrets was set`.
- `AssertionError: a whitespace-only credential was accepted as configured`.
- `AssertionError: restart() started the service again after its required credential was removed from the environment`.
- `AssertionError: register_service accepted a duplicate service name, silently replacing the live registration so the manager can no longer stop or restart it`.
- `AssertionError: a second registration silently replaced a RUNNING service, so the manager lost its handle on a live process still holding its writer lock and lease`.

The RED run was captured against the final version of the test file by temporarily reverting the source fix and restoring it immediately afterwards.

### Fix

- `ManagedService` gained `required_secrets: Sequence[str]` and `secret_resolver`. `start()` now calls `_verify_required_secrets()` **before** `_run_hook("start", ...)`, so a start hook can never observe a half-configured process, and a refusal publishes no `RUNNING` state. `restart()` inherits the gate because it calls `start()`.
- Resolved values are deliberately **not** retained on the object: the gate exists to prove the service is configured, not to duplicate credentials in process memory.
- `ServiceManager.__init__` gained an optional `env` mapping. `None` means "consult the live process environment at resolve time"; an injected mapping makes the credential source explicit and testable, and is what the new tests use.
- `ServiceManager.register_service` gained `required_secrets` and now raises `LifecycleOperationError("SERVICE_ALREADY_REGISTERED:<name>")` on a duplicate, leaving the existing entry untouched. `get_service(name)` was added as the public lookup.
- `resolve_secret` now rejects blank and whitespace-only values (`if not val or not val.strip()`). The message still names neither the secret key nor its value, so an error surfaced in a supervisor log or traceback cannot leak either.

### GREEN evidence

Commands and results:
- `python -m pytest tests/unit/lab/operations/test_service_lifecycle_secrets.py -p no:cacheprovider -q` → **10 passed**
- `python -m pytest tests/unit/lab/operations tests/integration/lab/test_service_lifecycle.py -p no:cacheprovider -q` → **25 passed**

The pre-existing integration suite (`test_ops_01_valid_contract`, `_contract_1`..`_contract_3`, the no-hooks and failed-flush guards, and the multiprocessing OS-lock release test) passes **unmodified** — no existing assertion was changed.

### Files changed
- `src/indodax_lab/operations/service_lifecycle.py`
- `tests/unit/lab/operations/test_service_lifecycle_secrets.py` (new RED suite)

### Isolation
Every test builds an in-process `HostServiceProfile` and injects a plain `dict` environment (`monkeypatch`ed `os.environ` only on the pre-fix signature, with pytest's automatic restore). No service is spawned, no OS supervisor is driven, no real data root, lock directory, ledger or order is touched, and no network is used.

### Deferred minors (recorded, not fixed — one fix cycle only)
- `ManagedService.handle_signal` silently returns for any signal name other than `SIGTERM`/`SIGINT`. A `SIGHUP` reload or an unexpected signal is a no-op with no diagnostic. Consider rejecting unrecognised signal names explicitly.
- `ManagedService.start()`/`stop()` have no state guard, so starting a `RUNNING` service runs the start hook a second time.
- `HostServiceProfile.data_root` is not validated for symlink or junction escape at construction time, unlike the equivalent checks in `operations/backup.py`.
