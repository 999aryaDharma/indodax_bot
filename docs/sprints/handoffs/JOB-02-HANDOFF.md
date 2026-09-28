# JOB-02 handoff

Status: REVIEW

## Identity
- Sprint ID: JOB-02 — Resource-aware idle admission
- Implementation agent: Antigravity
- Independent reviewer: `/root/ready_sprint_explore` (PASS for remediation code at exact SHA `becc27902590aba816d1f84d7c4e08fcafa79f55`; AC4/AC5 remain pending)
- Branch / worktree: `feat/job-02-resource-aware-idle-admission`
- Base SHA: `33cee17`
- Code target: `feat(job-02): resource-aware idle admission`
- Current remediation SHA: `becc27902590aba816d1f84d7c4e08fcafa79f55` (initial implementation SHA: `29b4e570417e9edd7fa5df6ba36c8b1de3d9cb9f`)

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

## Current remediation evidence — code review PASS; capacity qualification pending

- Exact code SHA: `becc279` (`fix(job-02): fence leases and reject invalid sensors`).
- Regression coverage rejects NaN/Infinity sensor readings, keeps a one-second queue lease alive through a 1.2-second step, and requires valid current worker claims for execution/resume.
- Focused command: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/orchestration/test_resources.py -q -p no:cacheprovider` -> **18 passed**.
- `git diff --check` passed. Independent review of `becc279` is PASS for lease renewal/ownership fencing, non-finite sensor rejection, and checkpoint resume. Previous CHANGES_REQUESTED findings applied to earlier SHA `9771d4627b01065225537f3e938050fa107c3d50`.
- Owner-approved capacity decision: sensor-age, Production deadline-headroom, and disk-reserve limits remain unset until approved host measurements exist; unset required values and unknown path/device mappings fail closed. JOB-02-AC4/AC5 host measurement, mount mapping, and fail-closed integration evidence remain outstanding. Do not qualify workload capacity or mark JOB-02 DONE from the offline suite.

## Independent delta review record — AC4/AC5 capacity guard (2026-09-27)

- Reviewed SHA: `92e538d` (`feat(JOB-02): add fail-closed capacity guard for AC4/AC5`), delta against prior reviewed `becc279`; strictly additive (`resources.py` +136/-0).
- Reviewer: independent session `ses_f1ccd0d11ffevtqOYyw9XamX6i` (did not implement the change). Verdict: **PASS** — 0 Critical, 0 Important, 6 Minor.
- Evidence re-run by the reviewer: `tests/unit/lab/orchestration/test_resources.py` 20 passed; orchestration+operations 113 passed; `tests/unit/lab` 1459 passed; ruff on the 3 touched files = 13 findings forming a byte-identical rule/file set to the pre-change baseline (`92e538d^` via `--stdin-filename`) → 0 introduced. Full `tests -q` outside the lab scope: only pre-existing environment gaps in untouched legacy modules (`pandas_ta_classic` ×2 collection, `telegram` ×5).
- Behavior proven by the reviewer: `capacity=None` preserves the pre-commit path byte-for-byte (zero deletions, no non-test callers changed); an enabled guard rejects unset required limits (`CAPACITY_LIMIT_UNSET:*`), stale sensors (`SENSOR_STALE:reading.timestamp`), sheds optional Research before/without a Production deadline (`RESEARCH_SHED_PRE_DEADLINE:*` / `PRODUCTION_DEADLINE_UNKNOWN:optional_research_shed`), blocks unresolved mounts (`PATH_MOUNT_UNRESOLVED:*`), and multiplies shared-device reserve demand (`DISK_RESERVE_EXCEEDED:... x N paths`); a naive deadline raises `UTC_TIMEZONE_AWARE_REQUIRED:production_deadline`.
- Backlog (Minor, non-blocking, deliberately not fixed in this sprint — attach to the pending measurement gate or a future CR):
  1. `CapacityGuardPolicy` accepts non-finite/negative limits (a NaN age silently admits stale readings) — add model validation or treat them as unset.
  2. Empty `configured_storage_paths` makes the mount dimension vacuous while the guard reports enabled.
  3. Future-dated `reading.timestamp` passes (no `SENSOR_FUTURE_TIMESTAMP` check).
  4. A path with an embedded NUL raises `ValueError` instead of returning `PATH_MOUNT_UNRESOLVED` (fails loud, not open).
  5. The AC4 test lacks an unknown-sensor-under-guard case, a headroom-unset case, and a differential threshold proof for `x N` multiplication.
  6. Contention groups by volume `dev-{st_dev}`, not physical disk — physical-disk scope depends on the measured mount inventory.
  Pre-existing, unrelated (separate CR): unknown `cpu_load_pct` is admitted although `max_cpu_load_pct` is always enforced (no `SENSOR_UNKNOWN:cpu_load_pct`).
- Open external gate unchanged: AC4/AC5 measured host artifact + measured mount inventory pending SSH access to `asus-server` (offline per Tailscale at last check; strictly read-only probe watcher running). Do not mark JOB-02 DONE from the offline suite.
- Lint capability gap closed 2026-09-27: ruff 0.16.9 installed to user-site (owner ruling, recorded as R5 in the coordinator ledger); the gate now runs on every change and its repo baseline predates the gate.

## Minor fix round - six backlog findings from the AC4/AC5 delta review

- Branch / base: `fix/minors-job-02` on `0c0d10d`. Fix commit: `91715d3` (`fix(JOB-02): fail closed on invalid or missing capacity guard limits`). This appendix is appended in a follow-up docs commit on the same branch.
- Files changed (scope only): `src/indodax_lab/orchestration/resources.py`, `tests/unit/lab/orchestration/test_resources.py`, plus this handoff. `docs/sprints/sprint-manifest.json` untouched; no push, merge, branch/worktree deletion.
- Environment: Python 3.14.0, pytest 9.0.3, ruff 0.16.9. Verified before testing that pytest's `pythonpath = ["src"]` imports this worktree's `src` (temporary path-check test, deleted before commit), so no gate ran against the main checkout.

### M1 - invalid limits counted as "set" (NaN age admitted a 6h-stale reading)

- RED: `python -m pytest tests/unit/lab/orchestration/test_resources.py -q -p no:cacheprovider -k invalid_capacity_limits --tb=short` -> exit 1, `AssertionError: assert True is False` at `test_resources.py:913`: `NaN max_sensor_age_seconds` admitted a 6h-stale reading.
- Pre-fix behavior probe over `evaluate_admission` (same fixture, all six cases): `admitted=True reason=None` for NaN age + stale, `inf` age + stale, NaN headroom + near deadline, negative headroom + near deadline, `disk_reserve_bytes=0`, `disk_reserve_bytes=-1`.
- Fix: new `_capacity_limit_is_set()` helper - a limit counts as set only when it is finite and positive; anything else joins the unset list and admission reports `CAPACITY_LIMIT_UNSET:<name>`. Nothing invalid can silently disable a dimension.
- GREEN: `python -m pytest tests/unit/lab/orchestration/test_resources.py -q -p no:cacheprovider` -> **21 passed, exit 0**.
- Interpretation flagged for the coordinator: the brief's scenario "NaN headroom + near deadline sheds" is asserted as fail-closed with `CAPACITY_LIMIT_UNSET:production_deadline_headroom_seconds` (the finding's fix rule: invalid -> "exactly like unset ... at admission"). The near-deadline optional Research job does not admit under either reading; if `RESEARCH_SHED_PRE_DEADLINE` was the intended reason code instead, that is a one-line reorder to request.

### M2 - empty `configured_storage_paths` passed vacuously

- RED: `-k empty_storage_paths` -> exit 1, `assert True is False` (empty tuple admitted while the guard reported enabled).
- Fix: an empty path tuple is appended to the unset list after the three numeric limits, so `CAPACITY_LIMIT_UNSET:max_sensor_age_seconds` keeps first priority (existing assertion unchanged) and a fully-measured policy with no paths reports `CAPACITY_LIMIT_UNSET:configured_storage_paths`.
- GREEN: **22 passed, exit 0**.

### M3 - future-dated `reading.timestamp`

- RED: `-k future_sensor_timestamp` -> exit 1, `assert True is False` (reading stamped +6h admitted with negative age).
- Fix: module constant `FUTURE_TIMESTAMP_TOLERANCE_SECONDS = 5.0`; age below `-5s` returns `SENSOR_FUTURE_TIMESTAMP:reading.timestamp:<age>s < -5s` before the stale check. The +2s-inside-tolerance case admits (it passes pre- and post-fix; reported as coverage, not RED).
- GREEN: **23 passed, exit 0**.

### M4 - embedded-NUL path raised out of the guard

- RED: `-k unresolvable_path` -> exit 1 with `ValueError: stat: embedded null character in path` escaping `evaluate_admission` (raised at `operations/recovery.py:404` inside `resolve_path_mount`, previously caught only `OSError`).
- Fix: `except (OSError, ValueError)` -> `PATH_MOUNT_UNRESOLVED:<path>:<detail>` (fails loud today, now also fails closed).
- GREEN: **24 passed, exit 0**.

### M5 - coverage gaps (no RED: these assert already-correct behavior)

- (a) `SENSOR_UNKNOWN:ac_power_connected` still rejects under an enabled guard (unknown-sensor checks precede the capacity guard).
- (b) unset `production_deadline_headroom_seconds` -> `CAPACITY_LIMIT_UNSET:production_deadline_headroom_seconds`.
- (c) differential contention proof: `disk_reserve_bytes = shutil.disk_usage(str(tmp_path)).free // 2 + 1` -> one configured path admits, two same-device paths reject with `x 2 paths`.
- The full test file was run 3x consecutively -> `24 passed` each time (the (c) threshold is sensitive only to a half-drive free-space swing; stable in practice).

### M6 - volume-level contention scope documented, grouping key unchanged

- `dev-{st_dev}` grouping deliberately kept (physical-disk scope waits for the measured mount inventory). Volume-level scope now stated in the `CapacityGuardPolicy` docstring, the `evaluate_admission` invariant 5 text, the module docstring, and the inline comment at the grouping loop.

### Gates

| # | Command (inside the worktree) | Result / exit |
|---|---|---|
| 1 | `python -m pytest tests/unit/lab/orchestration/test_resources.py -q` | 24 passed (20 pre-existing + 4 new), exit 0 |
| 2 | `python -m pytest tests/unit/lab/orchestration/ tests/unit/lab/operations/ -q` | 117 passed (113 baseline + 4), exit 0 |
| 3 | `python -m pytest tests/unit/lab -q` | 1478 passed = 1474 + 4 new, exit 0 (1 pre-existing `FutureWarning` in `strategies/test_s07.py`) |
| 4 | `python -m ruff check src/indodax_lab/orchestration/resources.py tests/unit/lab/orchestration/test_resources.py` | 11 findings; byte-identical rule set to the `0c0d10d` baseline (`--stdin-filename`: resources 5, tests 6) -> 0 introduced in added lines |
| 5 | `git diff --check` | exit 0 (before each commit) |

### Legacy path preservation and contract changes

- `capacity=None` is untouched: every change sits inside the `if capacity is not None:` block or is module-level, and all pre-existing tests pass unchanged (20/20 in this file before the 4 new ones were added; full lab 1478 with no edits to earlier assertions).
- Behavior change flagged for the coordinator: an invalid limit (NaN, `inf`, or a zero/negative reserve, plus a zero/negative age/headroom) and an empty `configured_storage_paths` now reject with `CAPACITY_LIMIT_UNSET:<name>` where they previously admitted; a future-dated reading beyond 5s now rejects with `SENSOR_FUTURE_TIMESTAMP`; an unresolvable path that raised `ValueError` now returns `PATH_MOUNT_UNRESOLVED`. No owner-approved production value was invented - all limits remain unset by default.
- Open external gate unchanged: AC4/AC5 measured host artifact + measured mount inventory remain pending; do not mark JOB-02 DONE from the offline suite.
