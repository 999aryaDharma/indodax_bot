# OPS-03 handoff

Status: REVIEW

## Identity
- Sprint ID: OPS-03 — Storage retention and integrity maintenance
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ops-03-storage-retention-and-integrity-maintenance`
- Base SHA: `497ede7`
- Code target: `feat(ops-03): storage retention and integrity maintenance`
- Evidence SHA relation: `2a8c12ea258a794d83401677fcff07dc801e70f2`

## Files and contracts
- Planned files:
  - `src/indodax_lab/orchestration/maintenance.py` (StorageCleaner, RetentionPolicy, CleanupReport, SymlinkEscapeError)
  - `src/indodax_lab/orchestration/__init__.py` (Package exports)
  - `tests/integration/lab/test_retention.py` (AC0..AC3 integration tests)
- Contract:
  - `registry reachability + retention policy -> deletion candidates, approved apply report.`
  - Dry-run protection: By default, cleanup executes an audit dry-run listing deletion candidates without removing files. Only an approved apply run (`dry_run=False`) performs deletions.
  - Critical asset preservation: Artifacts referenced by champion or sealed models/inputs are strictly preserved regardless of age.
  - Symlink & path traversal guard: Any path escaping the designated storage root raises `SymlinkEscapeError`.
  - Idempotent recovery: Interrupted or partial cleanup operations can safely rerun without deleting live or protected data.
- Migration and compatibility:
  - Additive storage maintenance engine and audit reporting.
  - Dependencies: OPS-02 (DONE), EVAL-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| OPS-03-AC0 (RED) | `test_ops_03_valid_contract` | `python -m pytest tests/integration/lab/test_retention.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.orchestration.maintenance') | `working tree` |
| OPS-03-AC0 (GREEN) | `test_ops_03_valid_contract` | `python -m pytest tests/integration/lab/test_retention.py::test_ops_03_valid_contract` | Exit 0 (Passed, dry-run audits candidates and approved run removes unreferenced expired files) | `2a8c12e` |
| OPS-03-AC1 (RED) | `test_ops_03_contract_1` | `python -m pytest tests/integration/lab/test_retention.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-03-AC1 (GREEN) | `test_ops_03_contract_1` | `python -m pytest tests/integration/lab/test_retention.py::test_ops_03_contract_1` | Exit 0 (Passed, champion and sealed inputs strictly preserved even past retention age) | `2a8c12e` |
| OPS-03-AC2 (RED) | `test_ops_03_contract_2` | `python -m pytest tests/integration/lab/test_retention.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-03-AC2 (GREEN) | `test_ops_03_contract_2` | `python -m pytest tests/integration/lab/test_retention.py::test_ops_03_contract_2` | Exit 0 (Passed, path traversal and symlink escape strictly rejected) | `2a8c12e` |
| OPS-03-AC3 (RED) | `test_ops_03_contract_3` | `python -m pytest tests/integration/lab/test_retention.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| OPS-03-AC3 (GREEN) | `test_ops_03_contract_3` | `python -m pytest tests/integration/lab/test_retention.py::test_ops_03_contract_3` | Exit 0 (Passed, interrupted cleanup safely reruns without deleting live data) | `2a8c12e` |

All 4 tests in `tests/integration/lab/test_retention.py` passed (0.48s).
Full lab suite verification: 125 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, and retention.

## Review
- Spec verdict: PASS (meets all functional requirements of OPS-03 and specs/17-operations-security-and-recovery.md).
- Quality verdict: PASS (dry-run audit guard, path traversal defense, protected asset immunity, crash idempotency).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for OPS-03.
- Next unlocked consumers: QA-03.
