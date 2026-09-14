# OPS-02 handoff

Status: REVIEW

## Identity
- Sprint ID: OPS-02 — Snapshot transfer and restore
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ops-02-snapshot-transfer-and-restore`
- Base SHA: `950cc17`
- Code target: `feat(ops-02): snapshot transfer and restore`
- Evidence SHA relation: `e237eda3884f3d81f1ef286da4159f7653c6aca8`

## Files and contracts
- Planned files:
  - `deploy/backup-lab.sh` (POSIX script for generating backup bundles)
  - `deploy/restore-lab.sh` (POSIX script for restoring bundles)
  - `src/indodax_lab/operations/backup.py` (backup_sqlite_db, create_backup_bundle, compute_sha256)
  - `src/indodax_lab/operations/staging.py` (TransferManifest, stage_and_publish_transfer, ChecksumMismatchError, CorruptTransferError)
  - `src/indodax_lab/operations/restore.py` (RestoreResult, restore_snapshot_bundle)
  - `src/indodax_lab/operations/__init__.py` (Package exports)
  - `tests/integration/lab/test_backup_restore.py` (AC0..AC3 integration tests)
- Contract:
  - `manifest + checksums + SQLite consistent backup -> staged copy -> verify -> atomic publish.`
  - Fail-closed staging: Any corrupted or truncated file in transfer causes immediate failure (`ChecksumMismatchError`); active target snapshot is never overwritten.
  - Consistent SQLite backup: Online backup API (`sqlite3.Connection.backup()`) is used to produce consistent DB snapshots even under uncheckpointed WAL transactions, avoiding raw `.db-wal` or `-shm` file copies.
  - Root-invariant restore: Restoring into an alternate root preserves all IDs, hashes, and schema definitions identically.
- Migration and compatibility:
  - Cross-host operations and disaster recovery subsystem.
  - Dependencies: DATA-06 (DONE), JOB-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| OPS-02-AC0 (RED) | `test_ops_02_valid_contract` | `python -m pytest tests/integration/lab/test_backup_restore.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.operations') | `working tree` |
| OPS-02-AC0 (GREEN) | `test_ops_02_valid_contract` | `python -m pytest tests/integration/lab/test_backup_restore.py::test_ops_02_valid_contract` | Exit 0 (Passed, end-to-end staged transfer and atomic publish verified) | `e237eda` |
| OPS-02-AC1 (RED) | `test_ops_02_contract_1` | `python -m pytest tests/integration/lab/test_backup_restore.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-02-AC1 (GREEN) | `test_ops_02_contract_1` | `python -m pytest tests/integration/lab/test_backup_restore.py::test_ops_02_contract_1` | Exit 0 (Passed, corrupted transfer fails closed and leaves active snapshot 100% untouched) | `e237eda` |
| OPS-02-AC2 (RED) | `test_ops_02_contract_2` | `python -m pytest tests/integration/lab/test_backup_restore.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-02-AC2 (GREEN) | `test_ops_02_contract_2` | `python -m pytest tests/integration/lab/test_backup_restore.py::test_ops_02_contract_2` | Exit 0 (Passed, SQLite backup uses consistent API capturing WAL commits without copying raw WAL files) | `e237eda` |
| OPS-02-AC3 (RED) | `test_ops_02_contract_3` | `python -m pytest tests/integration/lab/test_backup_restore.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-02-AC3 (GREEN) | `test_ops_02_contract_3` | `python -m pytest tests/integration/lab/test_backup_restore.py::test_ops_02_contract_3` | Exit 0 (Passed, restore to new isolated root preserves identical IDs, hashes, and records) | `e237eda` |

All 4 integration tests in `tests/integration/lab/test_backup_restore.py` passed (0.61s).
Full lab suite verification: 113 passed across strategies, features, labels, evaluation, backtest, orchestration, and operations.

## Review
- Spec verdict: PASS (meets all functional requirements of OPS-02 and specs/17-operations-security-and-recovery.md).
- Quality verdict: PASS (consistent backup API, atomic staging/publishing, fail-closed checksum checks).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for OPS-02.
- Next unlocked consumers: OPS-03, QA-02.
