# JOB-02 handoff

Status: REVIEW

## Identity
- Sprint ID: JOB-02 — Resource-aware idle admission
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/job-02-resource-aware-idle-admission`
- Base SHA: `33cee17`
- Code target: `feat(job-02): resource-aware idle admission`
- Evidence SHA relation: `29b4e570417e9edd7fa5df6ba36c8b1de3d9cb9f`

## Files and contracts
- Planned files:
  - `src/indodax_lab/orchestration/resources.py` (HostProfile, ResourceClass, SystemResourceReading, ResourceProbe, StaticResourceProbe, ResourceThresholds, AdmissionPolicy, AdmissionDecision, evaluate_admission, guard_asus_training_import, is_training_job)
  - `src/indodax_lab/orchestration/worker.py` (WorkerConfig, ExecutionResult, ResearchWorker, checkpoint pause and resume)
  - `src/indodax_lab/orchestration/__init__.py` (Package exports)
  - `tests/unit/lab/orchestration/test_resources.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `Injected resource probes + LOW/MEDIUM/HIGH/GPU profile -> admit/defer with reasons.`
  - Fail-closed sensor safety: Any required sensor returning UNKNOWN (None) immediately defers admission with explicit reason `SENSOR_UNKNOWN:<sensor>`.
  - Checkpoint pause: AC power disconnection during worker step execution triggers immediate durable checkpoint save and halts execution with status `PAUSED` and reason `AC_POWER_DISCONNECTED_CHECKPOINT_SAVED`. Clean resume from checkpoint is verified.
  - ASUS profile training prohibition: ASUS host strictly cannot admit training jobs or import training modules (`AsusProfileTrainingProhibitedError`).
  - Concurrency control: Lenovo host limits execution to at most 1 HIGH/GPU or 2 MEDIUM concurrent jobs.
- Migration and compatibility:
  - Additive orchestration resource guard and worker engine.
  - Dependencies: JOB-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| JOB-02-AC0 (RED) | `test_job_02_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_resources.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.orchestration.resources') | `working tree` |
| JOB-02-AC0 (GREEN) | `test_job_02_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_resources.py::test_job_02_valid_contract` | Exit 0 (Passed, heavy job admitted when Lenovo profile, RAM, idle, AC, and thermal meet policy) | `29b4e57` |
| JOB-02-AC1 (RED) | `test_job_02_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_resources.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-02-AC1 (GREEN) | `test_job_02_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_resources.py::test_job_02_contract_1` | Exit 0 (Passed, UNKNOWN sensor reading fails closed for temp, AC, RAM, and idle) | `29b4e57` |
| JOB-02-AC2 (RED) | `test_job_02_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_resources.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-02-AC2 (GREEN) | `test_job_02_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_resources.py::test_job_02_contract_2` | Exit 0 (Passed, AC disconnection pauses worker, writes checkpoint, resumes cleanly) | `29b4e57` |
| JOB-02-AC3 (RED) | `test_job_02_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_resources.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-02-AC3 (GREEN) | `test_job_02_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_resources.py::test_job_02_contract_3` | Exit 0 (Passed, ASUS profile strictly rejects training admission and prohibits training import) | `29b4e57` |

All 5 tests in `tests/unit/lab/orchestration/test_resources.py` passed (0.18s).
Full lab suite verification: 109 passed across strategies, features, labels, evaluation, backtest, and orchestration.

## Review
- Spec verdict: PASS (meets all functional requirements of JOB-02 and specs/13-jobs-resource-policy-and-repeats.md).
- Quality verdict: PASS (fail-closed sensor invariants, durable checkpoint persistence, strict ASUS training prohibition).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for JOB-02.
- Next unlocked consumers: JOB-03, DL-01, OPS-01.
