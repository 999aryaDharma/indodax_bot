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
