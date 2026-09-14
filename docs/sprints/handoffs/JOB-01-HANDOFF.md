# JOB-01 handoff

Status: REVIEW

## Identity
- Sprint ID: JOB-01 — Durable leased jobs
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/job-01-durable-leased-jobs`
- Base SHA: `f5cd708`
- Code target: `feat(job-01): durable leased jobs`
- Evidence SHA relation: `8f00ddcaad878ed6f6fe37bc6623b4a2204715ad`

## Files and contracts
- Planned files:
  - `src/indodax_lab/orchestration/jobs.py` (JobDefinition, JobRecord, JobStatus, LeaseFencingError, PartialArtifactError)
  - `src/indodax_lab/orchestration/queue.py` (SqliteJobQueue)
  - `src/indodax_lab/orchestration/__init__.py` (Package exports)
  - `tests/unit/lab/orchestration/test_queue.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `SQLite WAL local queue: PENDING/RUNNING/SUCCESS/FAILED_RETRYABLE/FAILED_FINAL/BLOCKED_DATA/BLOCKED_POLICY/CANCELLED/STALE.`
  - Atomic claim: exactly one worker wins claim transaction under SQLite WAL.
  - Lease generation fencing: each claim increments generation counter; heartbeat and completion strictly verify active generation. Stale workers are fenced with `LeaseFencingError`.
  - Artifact integrity gate: missing, empty, or checksum-mismatched artifacts raise `PartialArtifactError` and cannot mark `SUCCESS`.
- Migration and compatibility:
  - New orchestration subsystem; local SQLite WAL storage.
  - Dependencies: EVAL-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| JOB-01-AC0 (RED) | `test_job_01_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_queue.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-01-AC0 (GREEN) | `test_job_01_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_queue.py::test_job_01_valid_contract` | Exit 0 (Passed, completes job with verified artifact) | `8f00ddc` |
| JOB-01-AC1 (RED) | `test_job_01_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_queue.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-01-AC1 (GREEN) | `test_job_01_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_queue.py::test_job_01_contract_1` | Exit 0 (Passed, atomic claim: exactly one winner) | `8f00ddc` |
| JOB-01-AC2 (RED) | `test_job_01_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_queue.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-01-AC2 (GREEN) | `test_job_01_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_queue.py::test_job_01_contract_2` | Exit 0 (Passed, stale lease generation fenced) | `8f00ddc` |
| JOB-01-AC3 (RED) | `test_job_01_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_queue.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-01-AC3 (GREEN) | `test_job_01_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_queue.py::test_job_01_contract_3` | Exit 0 (Passed, partial artifact does not mark SUCCESS) | `8f00ddc` |

All 4 tests in `tests/unit/lab/orchestration/test_queue.py` passed (0.66s).
Combined suite verification (96 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, evaluation, and orchestration).

## Review
- Spec verdict: PASS (meets all functional requirements of JOB-01 and specs/13-jobs-resource-policy-and-repeats.md).
- Quality verdict: PASS (atomic claims, strict generation lease fencing, fail-closed artifact checksums, zero data race).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for JOB-01.
- Next unlocked consumers: JOB-02, OPS-02.
