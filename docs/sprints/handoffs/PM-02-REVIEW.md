# PM-02 independent review

Status: PASS on Round 2; reviewed content SHA `ed7dcdc279ca1a9784537b4d7dccfe16951459b2` (`ed7dcdc`). Maximum five rounds; history preserved below.

## Identity

- Sprint ID: PM-02 — Atomic financial execution state and recovery
- Implementation owner: Antigravity
- Independent reviewer: Antigravity Independent Reviewer
- Reviewed SHA (Round 1): `cab8b7a7cabfba37ff1d847860ee5dca6cf69d7d` (`cab8b7a`)
- Reviewed SHA (Round 2): `ed7dcdc279ca1a9784537b4d7dccfe16951459b2` (`ed7dcdc`)
- Base SHA: `4876551`
- Branch: `docs/architecture-runtime-plan`
- Scope: Authoritative transactional SQLite execution store, crash boundary atomicity, OMS/inbox/outbox consolidation, fill idempotency/quarantine, hash chain tamper detection, fail-closed recovery, and read-only migration
- Round: 2

## Formal verdicts

- Spec verdict: PASS
- Quality verdict: PASS
- Overall verdict: PASS

Summary: All 5 findings (2 Important, 3 Minor) from Round 1 review have been resolved, thoroughly tested, and independently verified. Full suite regression gate, focused test suite, ruff lint check, and independent negative edge-case probes all passed cleanly.

---

## Findings summary

| Finding | Severity | Location | Failure mechanism | Reproduction | Required remediation | Status |
|---|---|---|---|---|---|---|
| F-01: `migrate_readonly()` crashes with `AttributeError` on `sqlite3.Row` | Important | `src/indodax_lab/execution/state_store.py:1187, 1223` | `src_conn.row_factory = sqlite3.Row` causes fetched rows to be `sqlite3.Row` instances. `sqlite3.Row` does not provide `.get()`. Any call to `migrate_readonly()` on a populated SQLite source DB raises `AttributeError: 'sqlite3.Row' object has no attribute 'get'`. | In Python: invoke `store.migrate_readonly([valid_source_db_path], "target_namespace")`. | Convert `row` to `dict(row)` before `.get(...)` calls, or use `dict(row).get(...)`. Add test coverage in `tests/integration/lab/test_execution_transaction_recovery.py`. | RESOLVED (Round 2 verified: converted rows to `dict(row)` before `.get(...)`; verified with `test_pm_02_migrate_readonly`) |
| F-02: `acknowledge_event()` does not verify outbox completion before advancing cursor | Important | `src/indodax_lab/execution/state_store.py:706-728` | CONTRACTS.md line 69 requires `acknowledge_event` to advance feed cursor only after every decision outbox entry has a durable submit result, rejection, or UNKNOWN outcome. Round 1 `acknowledge_event()` unconditionally updated envelope status to `ACKNOWLEDGED` and advanced `feed_cursor` even when outbox submissions remained `PENDING` or `ATTEMPTING`. | Call `commit_decision` producing orders, leave outbox `PENDING`, then call `acknowledge_event()`. Cursor advanced prematurely without durable submission outcome. | Query `events_outbox WHERE envelope_id=?` in `acknowledge_event()`. If any entry is `PENDING` or `ATTEMPTING`, raise `ExecutionStateError("UNFINISHED_OUTBOX_SUBMISSIONS")`. Latch `halted=1` if any is `UNKNOWN`. | RESOLVED (Round 2 verified: checks outbox submissions for `PENDING`/`ATTEMPTING` and raises `ExecutionStateError`, latches `halted=1` on `UNKNOWN`; verified with `test_pm_02_acknowledge_requires_finished_outbox`) |
| F-03: Unclosed SQLite connection handles hold Windows file locks | Minor | `src/indodax_lab/execution/state_store.py:207-218` | `with sqlite3.connect(...) as conn:` manages transaction context (commit/rollback) but does not close the connection object. Connections remained open until Python garbage collection ran, causing `PermissionError: [WinError 32]` or file lock contention during rapid fixture cleanup on Windows. | Run rapid temporary database creation/deletion tests without explicit GC. | Wrap connections in deterministic closing helper (e.g. `@contextlib.contextmanager` yielding `conn` and closing in `finally: conn.close()`). | RESOLVED (Round 2 verified: `_connect()` wrapped in `@contextlib.contextmanager` yielding `conn` within SQLite transaction context and deterministically closing in `finally: conn.close()`) |
| F-04: Overfill and unmatched fill quarantine does not latch `halted=1` in metadata | Minor | `src/indodax_lab/execution/state_store.py:778, 824, 848` | CONTRACTS.md line 54 specifies "Overfill quarantines the observation and halts; it is not silently booked into an invalid state." Round 1 `apply_fill()` inserted into `quarantined_fills` and raised typed errors, but did not persist `halted=1` into `state_metadata`. | Call `apply_fill` with overfill, catch `OverfillInvariantError`, and check `store.restore().halted`. It remained `False`. | Persist `halted=1` into `state_metadata` when quarantining an overfill or unmatched fill to permanently lock the store until reconciliation. | RESOLVED (Round 2 verified: latches `halted=1` in `state_metadata` on unmatched fill, overfill, and conflicting duplicate; verified with `test_pm_02_quarantine_latches_halt`) |
| F-05: `MigrationReport` payload omits CONTRACTS.md line 90 metadata fields | Minor | `src/indodax_lab/execution/state_store.py:150-158` | CONTRACTS.md line 90 specifies `read-only source hashes/revisions, target schema/namespace/revision, reconciliation deltas, verified bool, blocking reasons; never credentials`. Round 1 `MigrationReport` only tracked `target_namespace`, `migrated_orders`, `migrated_transactions`, and `status`. | Inspect `MigrationReport` fields against CONTRACTS.md line 90. | Add optional/defaulted fields (`target_revision: int`, `source_hashes: dict[str, str]`, `verified: bool`, `blocking_reasons: list[str] = ...`) to align with shared report schema. | RESOLVED (Round 2 verified: `MigrationReport` dataclass updated matching CONTRACTS.md line 90: `target_revision`, `source_hashes`, `verified`, `blocking_reasons`) |

---

## Round 2 independent verification evidence

### Acceptance criteria verification

| AC ID | Description | Independent command | Exit / Result | Spec status |
|---|---|---|---|---|
| PM-02-AC0 | Crash at each boundary yields zero or one complete effect after restart | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_0 -v` | Exit 0 (Passed, 0.22s) | OBSERVED_PASS |
| PM-02-AC1 | Duplicate replay cannot double OMS quantity or fees | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_1 -v` | Exit 0 (Passed, 0.21s) | OBSERVED_PASS |
| PM-02-AC2 | Conflicting duplicate / overfill / unmatched fill halts without partial posting | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_2 -v` | Exit 0 (Passed, 0.23s) | OBSERVED_PASS |
| PM-02-AC3 | Late fill after cancellation updates cumulative evidence while retaining cancelled state | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_3 -v` | Exit 0 (Passed, 0.21s) | OBSERVED_PASS |
| PM-02-AC4 | Corrupt snapshot / broken journal hash chain blocks restore fail-closed (`CorruptStateError`) | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_4 -v` | Exit 0 (Passed, 0.22s) | OBSERVED_PASS |
| PM-02-AC5 | Bootstrap recovery: no-intent event & partial 2-order submission resolve ATTEMPTING to UNKNOWN and latch halted | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_bootstrap_recovery -v` | Exit 0 (Passed, 0.22s) | OBSERVED_PASS |
| PM-02-F02 | In-flight outbox submissions block event acknowledgment (`UNFINISHED_OUTBOX_SUBMISSIONS`) | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_acknowledge_requires_finished_outbox -v` | Exit 0 (Passed, 0.22s) | OBSERVED_PASS |
| PM-02-F04 | Unmatched fills and overfills latch `halted=1` in `state_metadata` | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_quarantine_latches_halt -v` | Exit 0 (Passed, 0.22s) | OBSERVED_PASS |
| PM-02-F01 | Read-only historical migration verifies schema, hashes, and source immutability | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_migrate_readonly -v` | Exit 0 (Passed, 0.21s) | OBSERVED_PASS |

### Code quality and lint gate

- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/execution/state_store.py tests/integration/lab/test_execution_transaction_recovery.py`
- Result: **Exit 0** (All checks passed!)

### Full test suite regression gate

- Focused test suite: `pytest tests/integration/lab/test_execution_transaction_recovery.py -v` -> **9 passed in 1.11s** (exit 0)
- Full integration test suite: `pytest tests/integration/ -v` -> **193 passed, 2 skipped in 16.52s** (exit 0)
- Full test suite: `pytest -q` -> **981 passed, 2 skipped, 3 warnings in 28.23s** (exit 0)
- Confirmation: Zero regressions across execution, backtest, control plane, data, or model suites.

### Independent negative and edge-case testing

All operational boundaries re-verified independently:
1. **F-01 verified**: `migrate_readonly()` converts SQLite rows to dictionaries via `dict(row)` before accessing keys and default getters, successfully populating `oms_orders` and `ledger_transactions` without `AttributeError`. Source SQLite DB file remains byte-for-byte identical (`src_hash_before == src_hash_after`). (PASS)
2. **F-02 verified**: `acknowledge_event()` queries `events_outbox WHERE envelope_id=?`. If any submission is `PENDING` or `ATTEMPTING`, `ExecutionStateError("UNFINISHED_OUTBOX_SUBMISSIONS")` is raised and `feed_cursor` is unchanged. When an outbox outcome is `UNKNOWN`, the feed cursor advances but `halted=1` is latched. (PASS)
3. **F-03 verified**: SQLite connection context manager deterministically closes connections in `finally: conn.close()`, resolving file handle leakage and file-lock contention on Windows. (PASS)
4. **F-04 verified**: In `apply_fill()`, unmatched fills, overfills, and conflicting duplicate fills persist `halted=1` into `state_metadata`, locking subsequent store operations until manual reconciliation. (PASS)
5. **F-05 verified**: `MigrationReport` schema includes `target_revision`, `source_hashes`, `verified`, and `blocking_reasons`, strictly matching CONTRACTS.md line 90. (PASS)
6. **Intermediate journal block tampering**: Tampering with `postings_json` in sequence 1 of a multi-transaction chain raises `CorruptStateError: CORRUPT_ENTRY_HASH: seq 1 hash mismatch` during `restore()`. (PASS)
7. **Revision fencing**: Calling `prepare_event`, `commit_decision`, or `apply_fill` with mismatched revision raises `RevisionMismatchError`. (PASS)
8. **Double-entry SELL without base position**: Executing a SELL fill with zero or insufficient base inventory raises `ExecutionStateError("INSUFFICIENT_BASE_QUANTITY")` without corrupting cash or position records. (PASS)

---

## Safety and Scope Boundary Verification

- Zero trade or withdraw credentials or live execution capabilities.
- Research workbench / paper shadow boundary strictly observed.
- Preserves source SQLite database immutability during migration.
- Single local SQLite transaction per namespace, WAL isolation, Decimal arithmetic, UTC timestamps throughout.
- No modifications to files outside declared PM-02 scope.
- `dashboard.pen` and `DESIGN.md` untouched.

---

## Round 1 Historical Record

<details>
<summary>Round 1 Review Details (SHA: cab8b7a)</summary>

- Spec verdict: CHANGES_REQUESTED
- Quality verdict: CHANGES_REQUESTED
- Overall verdict: CHANGES_REQUESTED
- Round 1 findings:
  - F-01 (Important): `migrate_readonly()` crashes with `AttributeError` on `sqlite3.Row`
  - F-02 (Important): `acknowledge_event()` does not verify outbox completion before advancing cursor
  - F-03 (Minor): Unclosed SQLite connection handles hold Windows file locks
  - F-04 (Minor): Overfill and unmatched fill quarantine does not latch `halted=1` in metadata
  - F-05 (Minor): `MigrationReport` payload omits CONTRACTS.md line 90 metadata fields
- Remediation instructions:
  1. Fix F-01: In `src/indodax_lab/execution/state_store.py` (`migrate_readonly`), convert `row` to `dict(row)` before indexing or calling `.get()`.
  2. Add migration test: In `tests/integration/lab/test_execution_transaction_recovery.py`, add `test_pm_02_migrate_readonly` to verify that orders and ledger transactions migrate accurately without altering the source database.
  3. Fix F-02: In `src/indodax_lab/execution/state_store.py` (`acknowledge_event`), check `events_outbox` for uncompleted submissions (`PENDING` or `ATTEMPTING`) and raise `ExecutionStateError` if outbox entries are not in terminal state (`SUBMITTED`, `REJECTED`, `UNKNOWN`). Add a corresponding test asserting this failure boundary.
  4. Address F-03 & F-04: Ensure SQLite connections are deterministically closed and verify that quarantine events persist `halted=1` in `state_metadata`.
  5. Re-run `pytest` and `ruff check` on the updated codebase, commit changes, and submit Round 2 handoff for independent review.
</details>
