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

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ## Sprint-review fix cycle (CHANGES_REQUESTED)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 1 - CRITICAL - a persisted job lost its declared resource class, so the ASUS training prohibition silently stopped applying

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `JobRecord` carried no `parameters` field, so `resolve_resource_class` had nothing to read for a job that had been through the queue. Every queued job fell through to the `job_type` substring guess (`gpu`/`neural`/`train`/`tune`/`sweep`/`backtest`). A job submitted as `parameters={"resource_class": "GPU"}` with `job_type="model_fit"` came back out of `get_job` classified `LOW`. Because `is_training_job` derives from the class, a GPU job was no longer recognised as training: `evaluate_admission` returned `admitted=True` on the ASUS host, and `execute_steps` skipped `guard_asus_training_import` entirely, so training ran on the laptop that the JOB-02 contract forbids it from ("ASUS profile tidak mengimpor atau menjalankan training", "ASUS host strictly cannot admit training jobs or import training modules"). The same decay also disabled every HIGH/GPU threshold. `resolve_resource_class` is also the single entry point used by admission, so the blast radius was the whole resource-policy subsystem. Nothing tested a class declaration surviving a persistence round trip.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/orchestration/test_resources.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `6 failed, 7 passed`. Behavioral failure at `tests/unit/lab/orchestration/test_resources.py:389` in `test_queued_gpu_job_cannot_run_on_the_asus_profile`: `AssertionError: assert True is False` where `True = AdmissionDecision(admitted=True, reason=None, resource_class=ResourceClass.LOW, host_profile=HostProfile.ASUS)` - a declared GPU job was admitted on the ASUS host. The same test then also reaches the `AsusProfileTrainingProhibitedError` guard that never fired.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED disclosure: the first assertion of the companion test `test_queued_gpu_job_keeps_its_declared_resource_class` failed first with `AttributeError: 'JobRecord' object has no attribute 'parameters'`, because the fix adds that field. That line is new-field coverage, not behavioral evidence, and is reported as such; the behavioral RED is the ASUS admission above and the `resolve_resource_class(record) == ResourceClass.GPU` assertion immediately after the reordered first line.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: `JobRecord` now carries `parameters: dict[str, Any]`, populated by `get_job` from the already-persisted `parameters_json` column, so the declared class is durable instead of re-guessed. `resolve_resource_class` reads `job.parameters` for `JobRecord` the same way it already read `JobDefinition.parameters`; the `job_type` heuristic remains only as the fallback for a job that genuinely declared nothing. `get_job` fails closed on unreadable state rather than defaulting: a row whose `parameters_json` is not decodable JSON, or is not a JSON object, raises `ValueError("JOB_PARAMETERS_CORRUPT:")` naming the job, because silently falling back to `{}` would re-open this exact bypass for any hand-edited or legacy row.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Contract change flagged for the coordinator: a `JobRecord` read from a corrupt `parameters_json` now raises instead of returning a partially-populated record, and `JobRecord` gained a `parameters` field. `JobRecord` is constructed in `src/` only by `SqliteJobQueue`, and a repository-wide grep shows no caller of `resolve_resource_class` / `is_training_job` / `evaluate_admission` outside the orchestration package, so the affected-subsystem gate below is the proof that nothing else regressed.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/orchestration/test_resources.py -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `13 passed in 1.28s`, from `6 failed, 7 passed` at RED. `test_queued_gpu_job_cannot_run_on_the_asus_profile` additionally proves the restored guard: the worker now raises `AsusProfileTrainingProhibitedError` and executes no step.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/jobs.py`, `src/indodax_lab/orchestration/queue.py`, `src/indodax_lab/orchestration/resources.py`, `src/indodax_lab/orchestration/__init__.py`, `tests/unit/lab/orchestration/test_resources.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 2 - CRITICAL - an unvalidated checkpoint could fabricate a SUCCESS, replay phantom steps, or escape as a raw decoder error

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `resume_from_checkpoint` read `data["last_completed_step"]` and `data["job_id"]` straight out of an untrusted on-disk file and acted on them. Four distinct safety failures, none tested: (a) a checkpoint claiming `last_completed_step=999` for a 3-step workload returned `status="SUCCESS"` with `reason="ALREADY_COMPLETED"` having executed nothing, fabricating a completed run and defeating the JOB-01 duplicate-result guarantee; (b) a checkpoint belonging to a different job was consumed by the wrong job because the path is derived from the job id but the contents were never cross-checked against it; (c) a negative `last_completed_step` produced a negative `start_step`, so `range(-4, total_steps)` re-ran already-completed steps, violating "checkpoint enables deterministic resume without duplicating prior steps"; (d) an unparseable checkpoint escaped as `json.decoder.JSONDecodeError` and a malformed one as `KeyError`/`TypeError`, so a corrupted file crashed the worker instead of being refused, and there was no way for a caller to tell corruption apart from a real failure.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/orchestration/test_resources.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `3 failed` with `Failed: DID NOT RAISE <class 'indodax_lab.orchestration.worker.CheckpointIntegrityError'>` at `test_resources.py:445` (`..._claiming_more_steps_than_exist`), `:484` (`..._for_a_different_job`) and `:521` (`..._negative_step_index`), plus `test_resume_refuses_a_corrupt_checkpoint_file` failing with `json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)` instead of the expected refusal.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the checkpoint is now validated before any step executes, in a new `ResearchWorker._load_verified_checkpoint` helper, and every unverifiable case is refused with a distinct machine-readable prefix. Unreadable bytes, a non-UTF8 file, invalid JSON, or a top-level value that is not a JSON object raise `CheckpointIntegrityError("CHECKPOINT_UNREADABLE:")`; a recorded `job_id` that does not equal the resuming job's id raises `CheckpointIntegrityError("CHECKPOINT_JOB_ID_MISMATCH:")`; and a `last_completed_step` that is not an integer, or that falls outside `[-1, total_steps - 1]`, raises `CheckpointIntegrityError("CHECKPOINT_STEP_OUT_OF_RANGE:")`. The boundary is inclusive of both ends, so a checkpoint at `total_steps - 1` is still legitimately complete and a checkpoint at `-1` is still legitimately "nothing done". Validation happens before the `execute_steps` call in every branch, so a rejected checkpoint executes zero steps, and the check is fail-closed rather than a silent restart, because silently restarting from step 0 on a corrupt file is exactly the duplicated-work behavior the checkpoint exists to prevent. `CheckpointIntegrityError` is exported from `indodax_lab.orchestration` so callers outside the module can catch it.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Contract change flagged for the coordinator: `resume_from_checkpoint` now raises `CheckpointIntegrityError` on unreadable, mismatched, or out-of-range checkpoint state where it previously fabricated a result, crashed with a raw decoder error, or silently restarted. The healthy paths are unchanged: a missing checkpoint still starts at step 0, a valid partial checkpoint still resumes at the next step, and a valid complete checkpoint still returns `ALREADY_COMPLETED`; the two regression guards added for exactly those paths are recorded below.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/orchestration/test_resources.py -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `13 passed in 1.28s`, from `3 failed` for this finding at RED. `test_valid_checkpoint_still_resumes_from_the_next_step` (resumes at step 2 of 4, no duplicate) and `test_completed_workload_still_reports_already_completed` (`last_completed_step == total_steps - 1` is not corrupt) pass at the pre-fix state and are reported as coverage rather than as RED.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/worker.py`, `src/indodax_lab/orchestration/__init__.py`, `tests/unit/lab/orchestration/test_resources.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Affected-subsystem gate

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Command: `python -m pytest tests/unit/lab/orchestration tests/unit/lab/reporting tests/unit/lab/verification tests/integration/lab/test_telegram_status.py tests/regression/test_release_candidate.py tests/research/test_rl_reward_contract.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Result: `104 passed in 3.75s`, up from the 96-test post-JOB-03 baseline by exactly the 8 tests added in this cycle (2 new tests beyond the 6 RED cases), with no regression.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Capability gaps and deferred items

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Capability gap per AGENTS.md: `ruff` is not installed, so no lint gate was run. `pyarrow` is not installed, so `tests/unit/lab/models/lob/` fails collection and was excluded.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Deferred (Minor) - not blocking: `JobRecord.parameters` defaults to `{}`, so a job persisted before this change, or one submitted with no `parameters` at all, still resolves by the `job_type` substring heuristic. Persisting an explicit class column rather than reconstructing it from a JSON blob would be a schema change and is listed for a CR rather than added here.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Deferred (Minor) - not blocking: `resolve_resource_class` returns the first match in the `job_type` heuristic and never reports that it guessed, so a genuinely undeclared job that happens to contain a keyword is indistinguishable from one that declared its class. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Deferred (Minor) - not blocking: `resume_from_checkpoint` validates the checkpoint but does not quarantine or delete it, so every call re-raises on the same corrupt file until an operator removes it. A `*.corrupt` rename on rejection would be a new state machine and is recorded as backlog.
