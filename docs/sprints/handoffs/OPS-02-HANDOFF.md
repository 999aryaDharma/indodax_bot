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

---

## Sprint review fix cycle — OPS-02 (batch `ops-shadow`)

Actor: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`
Date: 2026-09-27 · Source SHA: uncommitted working tree (`feat/feat-02-finalization`) · Fix cycle: 1 of 1

Spec: `docs/specs/17-operations-security-and-recovery.md` -> OPS-02, "manifest + checksums + SQLite consistent backup -> staged copy -> **verify** -> **atomic publish**". The declared pipeline contains a verify step and an atomic-publish step; both were missing.

### Findings fixed

| ID | Severity | Finding |
|---|---|---|
| OPS-02-F1 | Important | **`backup_sqlite_db` performed no post-backup verification.** It copied with the SQLite backup API, fsync'd, renamed into place and returned success. A zero-byte source — a path pre-created by a supervisor, or truncated to zero by a failed checkpoint restore — produced a "successful" 4096-byte backup containing **no tables at all**, and restoring it silently empties the dataset. Verified empirically before the fix: `zero_byte: NO EXCEPTION -> returned ...out_zero_byte.db / src_size=0 dest_size=4096 / dest objects=[] integrity=ok`. |
| OPS-02-F2 | Important | If the backup API returned without copying anything, the same false success was reported — the function never compared the result against the source. |
| OPS-02-F3 | Important | On any failure the `<target>.tmp.<uuid>` staging file was **leaked** next to the target (the `finally` block only closed connections), and the raised error was a bare `sqlite3.DatabaseError` naming neither the source nor the nature of the failure — so a retry saw a polluted destination directory. |
| OPS-02-F4 | Important | **A WAL source stamped WAL mode into the copied header**, so the published target was accompanied by leftover `queue.db.tmp.<uuid>-wal` and `-shm` sidecars in the target directory. This is precisely the raw-WAL artifact the consistent-backup API exists to avoid, and a stale sidecar beside a published backup can make a later reader see inconsistent content. Caught by the new positive-control test, not by the pre-existing suite. |
| OPS-02-F5 | Important | **`create_backup_bundle` was not atomic.** It copied directly into the final output directory, so an interruption part-way through the copy loop left a populated directory containing no `transfer_manifest.json`. Because reruns were guarded by `BUNDLE_OUTPUT_NOT_EMPTY`, a single transient copy error **permanently blocked backups** until an operator hand-deleted the directory — and a partial bundle is indistinguishable from a complete one by a non-empty check alone. Violates the "atomic publish" half of the declared pipeline. |

### RED evidence (real assertion failures, no assertion weakened/deleted/skipped)

Command: `python -m pytest tests/unit/lab/operations/test_backup_verification.py -p no:cacheprovider -q`
Result: **5 failed, 3 passed** — observed failures:
- `AssertionError: backup_sqlite_db reported success for a zero-byte source database; the resulting backup is a 4096-byte database with no tables, so restoring it silently empties the dataset` (`assert None is not None`).
- `AssertionError: backup_sqlite_db reported success even though the backup API produced an empty database with none of the source schema`.
- `AssertionError: a failed backup leaked staging artifacts into the target directory, so a retry directory is polluted: [...]`.
- `AssertionError: create_backup_bundle left a populated directory after an interruption; contents: ['a.bin']`.
- `AssertionError: a bundle could not be re-run after an interruption, so a single transient copy error permanently blocks backups: ValueError('BUNDLE_OUTPUT_NOT_EMPTY:...')`.

### Fix

`src/indodax_lab/operations/backup.py`:
- New `BackupVerificationError` (exported from `indodax_lab.operations`).
- New `_database_inventory()` and `_page_count()` helpers; `_verify_sqlite_backup()` opens the staged copy **read-only** and requires `PRAGMA integrity_check == ['ok']`, an exact match of the source's user-defined `sqlite_master` inventory (type, name, tbl_name, excluding `sqlite_%` internals), and an exact `page_count` match. A mismatch raises `BACKUP_INTEGRITY_CHECK_FAILED` / `BACKUP_SCHEMA_MISMATCH` / `BACKUP_PAGE_COUNT_MISMATCH`.
- `backup_sqlite_db` now refuses a source smaller than the 16-byte SQLite header with `SOURCE_DATABASE_TOO_SMALL_TO_BACKUP` **before** copying, so a zero-byte source can never yield a valid-looking empty backup.
- `sqlite3.Error` during the copy is wrapped as `SQLITE_BACKUP_FAILED:<src>:<exc>`.
- New `_remove_sqlite_sidecars()`; the staged copy is folded back to `PRAGMA journal_mode=DELETE` after the backup and its `-wal`/`-shm`/`-journal` sidecars are removed, so the published target is a single self-contained file.
- Every failure path (copy, verify, publish) removes the staging file and its sidecars, so a retry always sees a clean destination directory.
- `create_backup_bundle` now stages into a unique sibling directory `.<name>.staging.<uuid>`, writes the manifest **last** inside staging, fsyncs, and publishes with a single atomic `os.replace` via the new `_publish_bundle_dir()`. Any failure `shutil.rmtree`s the staging directory, so an interrupted run leaves no populated output and the backup can simply be re-run.
- `_publish_bundle_dir()` re-checks `BUNDLE_OUTPUT_NOT_EMPTY` immediately before the rename, so the pre-existing guard is preserved (verified by a dedicated guard test) rather than weakened. It `rmdir`s a proven-empty output directory first because `os.replace` cannot overwrite an existing directory on Windows.

### GREEN evidence

Commands and results:
- `python -m pytest tests/unit/lab/operations/test_backup_verification.py -p no:cacheprovider -q` → **8 passed**
- `python -m pytest tests/unit/lab/operations tests/integration/lab/test_backup_restore.py -p no:cacheprovider -q` → **20 passed**

The pre-existing OPS-02 suite (`test_ops_02_valid_contract`, `_contract_1`..`_contract_3`, plus the unsafe-manifest, duplicate-path, symlink-escape, traversal, failed-active-switch and idempotent-retry tests) passes **unmodified** — no existing assertion was changed.

### Files changed
- `src/indodax_lab/operations/backup.py`
- `src/indodax_lab/operations/__init__.py` (new export: `BackupVerificationError`)
- `tests/unit/lab/operations/test_backup_verification.py` (new RED suite)

### Isolation
Every test writes only under `tmp_path` and creates throwaway SQLite files in-process. No real data directory, no live service, no network, no production database, no ledger and no orders are touched.

### Reviewed and deliberately NOT changed
- `src/indodax_lab/operations/staging.py` — already performs `verify_bundle` before and after publish and swaps `active.json` atomically. Sound; no churn.
- `src/indodax_lab/operations/restore.py` — thin wrapper over `stage_and_publish_transfer`. See deferred minors.

### Deferred minors (recorded, not fixed — one fix cycle only)
- `RestoreResult.status` in `operations/restore.py` is hardcoded to `"SUCCESS"` rather than derived from the underlying transfer result, so a future non-success path would report success. Not reachable today because the wrapper propagates the underlying exception.
- `is_sqlite_database()` trusts the file extension alone for `.db`/`.sqlite`/`.sqlite3`, so a non-SQLite file with a database extension is routed into the backup path. Now caught by the header check plus `_verify_sqlite_backup`, but the routing decision itself is still extension-first.
- `_ensure_utc()` in `backup.py` is dead code — no caller in the module.

## Independent review remediation — cycle 2

The first independent review identified three Important findings and one Minor cleanup issue. The findings are addressed at implementation SHA `6183680c76c64df05af1045f39e864f87fe42b8d`.

| Finding | Resolution | Regression evidence |
|---|---|---|
| Live SQLite `-wal`/`-shm`/`-journal` sidecars were copied as ordinary directory members. | Directory traversal and explicitly selected files now omit SQLite sidecars; database backup API preserves committed WAL rows. | `test_directory_backup_omits_live_sqlite_sidecars_but_keeps_wal_rows` |
| Internally valid staged/existing bundles were not bound to the preflight manifest identity. | Staged and final manifests must hash to the original preflight manifest before activation. | `test_staged_manifest_must_match_preflight_identity`; `test_existing_version_manifest_must_match_requested_hash` |
| Source metadata could be read outside one pinned SQLite snapshot. | Source backup opens a read transaction before inventory/page-count checks and backup. | `test_backup_verifies_schema_and_pages_from_same_read_snapshot` injects a concurrent WAL writer after the read snapshot is pinned. |
| Publish failure could leave a temporary SQLite file. | Fsync/replace now share cleanup handling with backup and verification errors. | `test_failed_atomic_replace_cleans_staged_database` |

Final review: `/root/ready_sprint_explore` returned **PASS** on exact SHA `6183680c76c64df05af1045f39e864f87fe42b8d`, with no Critical or Important findings. Reviewer independently ran `PYTHONPATH=src; rtk pytest tests/unit/lab/operations tests/integration/lab/test_backup_restore.py -q -p no:cacheprovider` → **44 passed** and confirmed OPS-02-AC0..AC3. No project runtime or real database was accessed.

Non-blocking durability caveat: if directory `fsync` fails after `os.replace` succeeds in `backup_sqlite_db`, the function raises although the verified target may already have replaced the prior target. The publish is complete but durability is uncertain; this does not create a partial/corrupt artifact. Host restore rehearsal, stopped-writer reactivation, measured RPO/RTO, and Windows/Linux filesystem durability remain operational qualification evidence, separate from the local OPS-02 acceptance gate.
