# PM-02 handoff

Status: REVIEW (Round 2 pending independent approval)

## Identity
- Sprint ID: PM-02 — Atomic financial execution state and recovery
- Implementation agent: Antigravity
- Independent reviewer: Antigravity Independent Reviewer (subagent `c16c7169` Round 1 CHANGES_REQUESTED)
- Branch / worktree: `docs/architecture-runtime-plan`
- Base SHA: `4876551`
- Code target: `feat(pm-02): atomic financial execution state and recovery`
- Code SHA (Round 1): `cab8b7a`
- Remediation SHA (Round 2): `ed7dcdc`

## Round 2 Remediation Summary

Remediated all findings from Round 1 review (`docs/sprints/handoffs/PM-02-REVIEW.md`):
- **F-01 (Important, FIXED)**: Fixed `migrate_readonly()` by converting rows to `dict(row)` before `.get(...)` calls, eliminating `AttributeError: 'sqlite3.Row' object has no attribute 'get'`. Added integration test `test_pm_02_migrate_readonly`.
- **F-02 (Important, FIXED)**: Added verification in `acknowledge_event()` querying `events_outbox WHERE envelope_id=?` to block cursor advancement if submissions are `PENDING` or `ATTEMPTING` (`ExecutionStateError: UNFINISHED_OUTBOX_SUBMISSIONS`). Latches `halted=1` if any submission outcome is `UNKNOWN` per CONTRACTS.md line 69. Added test `test_pm_02_acknowledge_requires_finished_outbox`.
- **F-03 (Minor, FIXED)**: Wrapped `_connect()` in `@contextlib.contextmanager` yielding `conn` within SQLite transaction context and closing it deterministically in `finally: conn.close()`, eliminating Windows file locking issues.
- **F-04 (Minor, FIXED)**: In `apply_fill()`, latched `state_metadata.halted = 1` on unmatched fill quarantine, overfill quarantine, and conflicting duplicates. Added test `test_pm_02_quarantine_latches_halt`.
- **F-05 (Minor, FIXED)**: Updated `MigrationReport` dataclass matching CONTRACTS.md line 90 (`target_revision`, `source_hashes`, `verified`, `blocking_reasons`).

## Files and contracts
- Planned files:
  - `src/indodax_lab/execution/state_store.py` (Authoritative transactional execution store and crash recovery)
  - `tests/integration/lab/test_execution_transaction_recovery.py` (Crash boundary, idempotency, quarantine, and recovery tests)
- Contract:
  - ADR-007 and `docs/implementation/CONTRACTS.md` (lines 54–75).
  - Consolidate journal, OMS, applied fill identity, event inbox/outbox, and cursor into a single local SQLite transaction per namespace.
  - Invariant 0 (Crash boundary): Crash at any state boundary yields either zero or one complete effect upon restart (AC0).
  - Invariant 1 (Fill idempotency): Duplicate replay cannot double OMS quantity, fees, or postings (AC1).
  - Invariant 2 (Quarantine & fail-closed): Conflicting duplicate, overfill, or unmatched fill halts immediately without partial posting (AC2).
  - Invariant 3 (Late fills on terminal state): Fills for cancelled orders update cumulative evidence and ledger while retaining terminal lifecycle fact (AC3).
  - Invariant 4 (Cryptographic integrity): Corrupt snapshot or broken ledger hash chain blocks restore with `CorruptStateError` (AC4).
  - Invariant 5 (Crash recovery protocol): Crashed submission becomes `UNKNOWN` pending reconciliation, latches `halted=True`, and advances cursor only once without blind resubmission (AC5).
- Migration and compatibility:
  - Read-only historical migration via `ExecutionStateStore.migrate_readonly()` preserves source DB immutability.
  - Paper/shadow execution environment: zero real order submission, zero live credential requirement.

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| PM-02-AC0 (GREEN) | `test_pm_02_0` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_0` | Exit 0 (Passed, crash boundary atomicity) | `ed7dcdc` |
| PM-02-AC1 (GREEN) | `test_pm_02_1` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_1` | Exit 0 (Passed, duplicate fill idempotency) | `ed7dcdc` |
| PM-02-AC2 (GREEN) | `test_pm_02_2` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_2` | Exit 0 (Passed, conflicting duplicate / overfill / unmatched fill halt) | `ed7dcdc` |
| PM-02-AC3 (GREEN) | `test_pm_02_3` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_3` | Exit 0 (Passed, late fill on cancelled order) | `ed7dcdc` |
| PM-02-AC4 (GREEN) | `test_pm_02_4` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_4` | Exit 0 (Passed, corrupt hash chain blocks restore) | `ed7dcdc` |
| PM-02-AC5 (GREEN) | `test_pm_02_bootstrap_recovery` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_bootstrap_recovery` | Exit 0 (Passed, partial order submission recovery) | `ed7dcdc` |
| PM-02-F02 (GREEN) | `test_pm_02_acknowledge_requires_finished_outbox` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_acknowledge_requires_finished_outbox` | Exit 0 (Passed, cursor advancement blocked while submissions in-flight) | `ed7dcdc` |
| PM-02-F04 (GREEN) | `test_pm_02_quarantine_latches_halt` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_quarantine_latches_halt` | Exit 0 (Passed, unmatched/overfill latches halted=1) | `ed7dcdc` |
| PM-02-F01 (GREEN) | `test_pm_02_migrate_readonly` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_migrate_readonly` | Exit 0 (Passed, read-only migration without source mutation) | `ed7dcdc` |

All 9 integration tests in `tests/integration/lab/test_execution_transaction_recovery.py` passed (1.43s).
Ruff lint: all checks passed (`ruff check` exit 0).
Full suite: 981 passed, 2 skipped, 0 failed in 35.01s.

## Review
- Spec verdict: PASS (meets all functional requirements of PM-02, ADR-007, and specs/CONTRACTS.md).
- Quality verdict: PASS (clean SQLite WAL isolation, cryptographic hash chaining, strict fail-closed recovery, 100% ruff clean).
- Round 1 independent review: CHANGES_REQUESTED (subagent `c16c7169`).
- Round 2 independent review: PENDING (remediation committed at `ed7dcdc`).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None.
- Next unlocked capabilities: PM-03 (Reconciliation loop), PM-04 (Paper execution engine), RP-04 (Paper execution soak).
