# PM-02 independent review

Status: CHANGES_REQUESTED on Round 1; reviewed content SHA `cab8b7a7cabfba37ff1d847860ee5dca6cf69d7d`. Maximum five rounds; history preserved below.

## Identity

- Sprint ID: PM-02 — Atomic financial execution state and recovery
- Implementation owner: Antigravity
- Independent reviewer: Antigravity Independent Reviewer
- Reviewed SHA (Round 1): `cab8b7a7cabfba37ff1d847860ee5dca6cf69d7d` (`cab8b7a`)
- Base SHA: `4876551`
- Branch: `docs/architecture-runtime-plan`
- Scope: Authoritative transactional SQLite execution store, crash boundary atomicity, OMS/inbox/outbox consolidation, fill idempotency/quarantine, hash chain tamper detection, fail-closed recovery, and read-only migration
- Round: 1

## Formal verdicts

- Spec verdict: CHANGES_REQUESTED
- Quality verdict: CHANGES_REQUESTED
- Overall verdict: CHANGES_REQUESTED

## Findings summary

| Finding | Severity | Location | Failure mechanism | Reproduction | Required remediation | Status |
|---|---|---|---|---|---|---|
| F-01: `migrate_readonly()` crashes with `AttributeError` on `sqlite3.Row` | Important | `src/indodax_lab/execution/state_store.py:1149-1161, 1184-1190` | `src_conn.row_factory = sqlite3.Row` causes fetched rows to be `sqlite3.Row` instances. `sqlite3.Row` does not provide `.get()`. Any call to `migrate_readonly()` on a populated SQLite source DB raises `AttributeError: 'sqlite3.Row' object has no attribute 'get'`. | In Python: invoke `store.migrate_readonly([valid_source_db_path], "target_namespace")`. | Convert `row` to `dict(row)` before `.get(...)` calls, or use `dict(row).get(...)`. Add test coverage in `tests/integration/lab/test_execution_transaction_recovery.py`. | OPEN (Blocks DONE) |
| F-02: `acknowledge_event()` does not verify outbox completion before advancing cursor | Important | `src/indodax_lab/execution/state_store.py:686-727` | CONTRACTS.md line 69 requires `acknowledge_event` to advance feed cursor only after every decision outbox entry has a durable submit result, rejection, or UNKNOWN outcome. Currently, `acknowledge_event()` unconditionally updates envelope status to `ACKNOWLEDGED` and advances `feed_cursor` even when outbox submissions remain `PENDING` or `ATTEMPTING`. | Call `commit_decision` producing orders, leave outbox `PENDING`, then call `acknowledge_event()`. Cursor advances prematurely without durable submission outcome. | Query `events_outbox WHERE envelope_id=?` in `acknowledge_event()`. If any entry is `PENDING` or `ATTEMPTING`, raise `ExecutionStateError("UNFINISHED_OUTBOX_SUBMISSIONS")`. | OPEN (Blocks DONE) |
| F-03: Unclosed SQLite connection handles hold Windows file locks | Minor | `src/indodax_lab/execution/state_store.py:202-208` | `with sqlite3.connect(...) as conn:` manages transaction context (commit/rollback) but does not close the connection object. Connections remain open until Python garbage collection runs, causing `PermissionError: [WinError 32]` or file lock contention during rapid fixture cleanup on Windows. | Run rapid temporary database creation/deletion tests without explicit GC. | Wrap connections in deterministic closing helper (e.g. `contextlib.closing(self._connect())` or explicit `try ... finally conn.close()`). | OPEN |
| F-04: Overfill and unmatched fill quarantine does not latch `halted=1` in metadata | Minor | `src/indodax_lab/execution/state_store.py:771-812` | CONTRACTS.md line 54 specifies "Overfill quarantines the observation and halts; it is not silently booked into an invalid state." Currently, `apply_fill()` inserts into `quarantined_fills` and raises typed errors, but does not persist `halted=1` into `state_metadata`. | Call `apply_fill` with overfill, catch `OverfillInvariantError`, and check `store.restore().halted`. It remains `False`. | Persist `halted=1` into `state_metadata` when quarantining an overfill or unmatched fill to permanently lock the store until reconciliation. | OPEN |
| F-05: `MigrationReport` payload omits CONTRACTS.md line 90 metadata fields | Minor | `src/indodax_lab/execution/state_store.py:148-154` | CONTRACTS.md line 90 specifies `read-only source hashes/revisions, target schema/namespace/revision, reconciliation deltas, verified bool, blocking reasons; never credentials`. Current `MigrationReport` only tracks `target_namespace`, `migrated_orders`, `migrated_transactions`, and `status`. | Inspect `MigrationReport` fields against CONTRACTS.md line 90. | Add optional/defaulted fields (`verified: bool = True`, `source_hashes: list[str] = ...`, `blocking_reasons: list[str] = ...`) to align with shared report schema. | OPEN |

---

## Round 1 independent verification evidence

### Acceptance criteria verification

| AC ID | Description | Independent command | Exit / Result | Spec status |
|---|---|---|---|---|
| PM-02-AC0 | Crash at each boundary yields zero or one complete effect after restart | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_0 -v` | Exit 0 (Passed, 0.28s) | OBSERVED_PASS |
| PM-02-AC1 | Duplicate replay cannot double OMS quantity or fees | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_1 -v` | Exit 0 (Passed, 0.25s) | OBSERVED_PASS |
| PM-02-AC2 | Conflicting duplicate / overfill / unmatched fill halts without partial posting | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_2 -v` | Exit 0 (Passed, 0.26s) | OBSERVED_PASS |
| PM-02-AC3 | Late fill after cancellation updates cumulative evidence while retaining cancelled state | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_3 -v` | Exit 0 (Passed, 0.25s) | OBSERVED_PASS |
| PM-02-AC4 | Corrupt snapshot / broken journal hash chain blocks restore fail-closed (`CorruptStateError`) | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_4 -v` | Exit 0 (Passed, 0.26s) | OBSERVED_PASS |
| PM-02-AC5 | Bootstrap recovery: no-intent event & partial 2-order submission resolve ATTEMPTING to UNKNOWN and latch halted | `pytest tests/integration/lab/test_execution_transaction_recovery.py::test_pm_02_bootstrap_recovery -v` | Exit 0 (Passed, 0.26s) | OBSERVED_PASS |

### Code quality and lint gate

- Command: `python -m ruff check src/indodax_lab/execution/state_store.py tests/integration/lab/test_execution_transaction_recovery.py`
- Result: **Exit 0** (All checks passed!)

### Independent negative and edge-case testing

1. **Intermediate journal block tampering**: Tampering with `postings_json` in sequence 1 of a multi-transaction chain correctly raises `CorruptStateError: CORRUPT_ENTRY_HASH: seq 1 hash mismatch` during `restore()`. (PASS)
2. **Revision fencing**: Calling `prepare_event`, `commit_decision`, or `apply_fill` with mismatched revision raises `RevisionMismatchError`. (PASS)
3. **Double-entry SELL without base position**: Executing a SELL fill with zero or insufficient base inventory raises `ExecutionStateError("INSUFFICIENT_BASE_QUANTITY")` without corrupting cash or position records. (PASS)
4. **Read-only migration execution (`migrate_readonly`)**: Attempting to migrate an existing populated database failed with `AttributeError: 'sqlite3.Row' object has no attribute 'get'` at lines 1149 and 1184. (FAILED - see F-01)
5. **Premature event acknowledgment**: Calling `acknowledge_event()` on an envelope whose outbox entries are still `PENDING` succeeded and advanced the feed cursor, violating CONTRACTS.md line 69. (FAILED - see F-02)

---

## Remediation instructions for Round 2

1. **Fix F-01**: In `src/indodax_lab/execution/state_store.py` (`migrate_readonly`), convert `row` to `dict(row)` before indexing or calling `.get()`.
2. **Add migration test**: In `tests/integration/lab/test_execution_transaction_recovery.py`, add `test_pm_02_migrate_readonly` to verify that orders and ledger transactions migrate accurately without altering the source database.
3. **Fix F-02**: In `src/indodax_lab/execution/state_store.py` (`acknowledge_event`), check `events_outbox` for uncompleted submissions (`PENDING` or `ATTEMPTING`) and raise `ExecutionStateError` if outbox entries are not in terminal state (`SUBMITTED`, `REJECTED`, `UNKNOWN`). Add a corresponding test asserting this failure boundary.
4. **Address F-03 & F-04**: Ensure SQLite connections are deterministically closed and verify that quarantine events persist `halted=1` in `state_metadata`.
5. Re-run `pytest` and `ruff check` on the updated codebase, commit changes, and submit Round 2 handoff for independent review.
