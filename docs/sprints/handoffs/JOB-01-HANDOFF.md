# JOB-01 handoff

Status: DONE

## Identity
- Sprint ID: JOB-01 — Durable leased jobs
- Implementation agent: Antigravity; review remediation: Codex `/root`
- Independent reviewer: `/root/docs_review` (PASS at exact source SHA `40e91215df3f99bd4ecaf2e47aeb76de19e2fb30`)
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
- Independent review: PASS at exact source SHA `40e91215df3f99bd4ecaf2e47aeb76de19e2fb30`; reviewer performed source/test inspection but could not run persistence tests in its environment.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for JOB-01.
- Next unlocked consumers: JOB-02, OPS-02.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ## Sprint-review fix cycle (CHANGES_REQUESTED)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 1 - CRITICAL - `complete_job` published SUCCESS with no result artifact at all

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `complete_job` validated the artifact only when `artifact_path is not None`. Passing `artifact_path=None` skipped the whole gate and executed the terminal transition, so a job with no result path and no result hash was published as `SUCCESS`. This directly contradicts the sprint contract "missing, empty, or checksum-mismatched artifacts raise `PartialArtifactError` and cannot mark `SUCCESS`" and the spec rule "Partial artifact tidak menandai SUCCESS". A worker that produced nothing, or that died before writing, published a successful job, which is exactly the false-success that JOB-01's duplicate-result guarantee exists to prevent. No test covered it.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/orchestration/test_queue.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/orchestration/test_queue.py:317: Failed: DID NOT RAISE <class 'indodax_lab.orchestration.jobs.PartialArtifactError'>` (test_complete_job_cannot_publish_success_without_a_result_artifact).
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: a result artifact reference is now mandatory. `complete_job` raises `PartialArtifactError` with `ARTIFACT_PATH_REQUIRED:` when `artifact_path is None`, and the job is left `RUNNING` with a null `result_artifact_path` and `result_artifact_hash`. The artifact is read and checksum-verified inside the same transaction that holds the lease, so a rejected artifact can never leave a partial write, and an `OSError` while reading is normalised to `ARTIFACT_UNREADABLE:` instead of escaping as a raw filesystem error.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Contract change flagged for the coordinator: `complete_job(artifact_path=None)` used to be an accepted way to publish a resultless SUCCESS. It now always raises. No caller in `src/` used that form, so the affected-subsystem gate below is the proof, but any external or future caller relying on it must now pass an artifact.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/orchestration/test_queue.py -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `16 passed in 1.80s`, from `3 failed, 13 passed` at RED.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/queue.py`, `tests/unit/lab/orchestration/test_queue.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 2 - CRITICAL - lease fencing was evaluated after artifact inspection, so a fenced worker was told the wrong thing

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `complete_job` performed all artifact filesystem access *before* opening the fencing transaction. A superseded worker passing a non-existent `artifact_path` received `PartialArtifactError: ARTIFACT_FILE_NOT_FOUND` naming a real filesystem path, instead of `LeaseFencingError`. Two problems: the authoritative safety check was not first, and a worker that had already been fenced could still probe the artifact filesystem and receive detailed path information about a job it no longer owns. The behavior was untested.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/orchestration/test_queue.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `indodax_lab.orchestration.jobs.PartialArtifactError: ARTIFACT_FILE_NOT_FOUND:...definitely_absent.bin` raised at `src/indodax_lab/orchestration/queue.py:308` where `test_fenced_worker_is_fenced_before_artifact_inspection` expected `STALE_LEASE_FENCED`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the ordering is inverted. `complete_job` now opens the `BEGIN IMMEDIATE` transaction and runs a `SELECT` fence check on `job_id + owner_id + generation + status=RUNNING + lease_expires_at > as_of` first. A worker that fails it gets `LeaseFencingError` immediately and never touches the filesystem. Artifact validation happens only after the fence is held, and any failure rolls the transaction back so the job stays `RUNNING`. The original `rowcount == 0` guard on the terminal `UPDATE` is retained as defence in depth.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/orchestration/test_queue.py -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `16 passed in 1.80s`. The pre-existing `test_worker_is_fenced_immediately_at_lease_expiry`, which fences with no artifact at all, still raises `LeaseFencingError`, which is why the pre-existing suite did not catch Finding 1 either.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/queue.py`, `tests/unit/lab/orchestration/test_queue.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 3 - IMPORTANT - a crashed attempt left no audit trail, so `JobStatus.STALE` was unreachable

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important): `JobStatus.STALE` is part of the declared JOB-01 lifecycle and `claim_job` treats it as claimable in both its exhaustion sweep and its candidate selection, but no code path in the repository ever wrote it. An expired-lease takeover went straight from `RUNNING` back to `RUNNING` with a new generation and left `error_message` as `NULL`, so a worker that died mid-flight was indistinguishable from one that had just been claimed, and the spec guarantee "crash dapat dipulihkan tanpa duplicate result" had no observable evidence. The existing test `test_attempt_budget_cannot_be_reset_by_state_or_worker_change` had to force the status with raw SQL precisely because the queue could not reach it.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/orchestration/test_queue.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/orchestration/test_queue.py:375: AssertionError: expired-lease takeover left no audit marker` / `assert None is not None`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the claim candidate `SELECT` now also reads `status`, `owner_id`, and `lease_expires_at`. When the claimed row was `RUNNING` with an expired lease, or was already `STALE`, `claim_job` writes a durable `STALE_LEASE_TAKEOVER:` marker into `error_message` naming the previous owner, the previous generation, the previous status, the expired lease timestamp, and the new owner and generation. A clean first-time or retry claim writes `NULL` instead, and `complete_job` clears `error_message` on `SUCCESS` so a completed job never carries a stale-takeover message.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Design note disclosed for the reviewer: `JobStatus.STALE` is still not auto-persisted as an intermediate row, deliberately. The claim is a single atomic `BEGIN IMMEDIATE` transaction, so writing `STALE` and then `RUNNING` inside it would leave the state unobservable to any reader while widening the window in which a concurrent claimer could observe it. The observable guarantee the spec actually needs, an auditable record that a prior attempt died, is provided by the persisted marker instead.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/orchestration/test_queue.py -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `16 passed in 1.80s`. `test_successful_completion_clears_the_takeover_marker` and `test_first_claim_carries_no_takeover_marker` are regression guards that pass trivially at the pre-fix state and are reported as coverage rather than as RED.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/queue.py`, `tests/unit/lab/orchestration/test_queue.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Affected-subsystem gate

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Command: `python -m pytest tests/unit/lab/orchestration tests/unit/lab/reporting tests/unit/lab/verification tests/integration/lab/test_telegram_status.py tests/regression/test_release_candidate.py tests/research/test_rl_reward_contract.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Result: `81 passed in 3.02s`, up from the 76-test post-REL-01 baseline by exactly the 5 tests added in this cycle, with no regression. A repository-wide grep confirms `complete_job` and `claim_job` have no callers in `src/` outside `queue.py`, so the stricter artifact requirement has no other production impact.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Out of scope - coordinator action required

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important, not fixed here): spec `docs/specs/13-jobs-resource-policy-and-repeats.md` also states "External immutable artifact may exist before DB success after crash, so retry verifies and reuses identical complete output rather than duplicating it." The queue records no pre-crash artifact reference, so a retry after a crash where the artifact file did land still recomputes from scratch rather than reusing the identical complete output. Implementing idempotent artifact reuse is a new capability rather than a defect repair, so it was deliberately not added in this fix cycle and is listed for a CR.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Capability gap per AGENTS.md: `ruff` is not installed, so no lint gate was run. `pyarrow` is not installed, so `tests/unit/lab/models/lob/` fails collection and was excluded.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Deferred (Minor) - not blocking

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: the `STALE_LEASE_TAKEOVER` marker is stored in the same `error_message` column as genuine failure reasons, so a consumer cannot distinguish a takeover note from an error without string matching. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: the exhaustion sweep in `claim_job` sets `error_message = "ATTEMPT_BUDGET_EXHAUSTED"` with a plain string while the new takeover marker is a longer structured line, so the column has two formats. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: `claim_job` still selects the single oldest eligible row with `LIMIT 1` and no fairness or priority column. Pre-existing and unchanged.

## Final remediation and verification

- Final implementation SHA: `40e91215df3f99bd4ecaf2e47aeb76de19e2fb30` (includes review fixes from `7c5e61d` and `4bdc2e5`).
- Mandatory valid SHA-256 completion evidence prevents nonempty partial files from publishing SUCCESS. Completion copies bytes to a content-addressed store; `read_result_artifact` verifies the persisted digest.
- A durable `(job_id, source_path, artifact_path, digest)` intent commits before object publication. Recovery can verify and reuse the immutable object, or publish the staged source when the object copy had not completed, then finalize under a newly checked live lease without rerunning the job.
- Unique per-attempt temporary files avoid same-digest publisher races; migration adds `source_path` to prior staging tables without dropping prior rows.
- Tests: `tests/unit/lab/orchestration/test_queue.py` — 23 passed; final combined affected suite including concurrency and migration regressions — 205 passed in 11.22s.
- Full suite at the final source tree: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests -q -p no:cacheprovider` — 1,646 passed, 2 platform skips, 11 warnings in 53.89s.
- Ruff on queue implementation/tests and `git diff --check`: PASS.
- Independent review history: CHANGES_REQUESTED at `9b6dab1` and `7c5e61d`; final PASS at `40e91215df3f99bd4ecaf2e47aeb76de19e2fb30`. Reviewer did not execute persistence tests; owner ran the full suite above.
- The previous artifact-reuse “out of scope” note is closed by this remediation. Historical review notes remain as provenance.
