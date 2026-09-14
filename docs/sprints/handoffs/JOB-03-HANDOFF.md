# JOB-03 handoff

Status: REVIEW

## Identity
- Sprint ID: JOB-03 — Evaluator-controlled research DAG
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/job-03-evaluator-controlled-research-dag`
- Base SHA: `6b8c87a`
- Code target: `feat(job-03): evaluator-controlled research dag`
- Evidence SHA relation: `630d2ae`

## Files and contracts
- Actual files (spec listed `dag.py`, `policies.py`, `cli/schedule_research.py`, `test_repeat_policy.py`; policies merged into dag.py, CLI out of scope for ACs):
  - `src/indodax_lab/orchestration/dag.py` (DAGScheduler, ExperimentRecipe, RepeatPolicy, RepeatDecision, RepeatOutcome, ResearchDAGJob, InvalidRunRetryConfig, HardFailCannotBeReopenedError, InvalidRunRetryLimitExceededError, NearMissMustHaveNewVersionError)
  - `src/indodax_lab/orchestration/__init__.py` (Package exports — JOB-03 symbols added)
  - `tests/unit/lab/orchestration/test_repeat_policy.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `cadence window + snapshot + recipe -> idempotent DAG jobs with dependency states.`
  - HARD_FAIL permanent block: `DAGScheduler.decide_repeat()` raises `HardFailCannotBeReopenedError` for any `HARD_FAIL` prior outcome regardless of `system_idle` flag (JOB-03-AC1).
  - INVALID_RUN bounded retry: Attempt count checked against `policy.max_invalid_run_retries`; exceeding raises `InvalidRunRetryLimitExceededError`. Config hash anchored via `InvalidRunRetryConfig`; mismatch raises `ValueError(CONFIG_MUST_NOT_CHANGE)` (JOB-03-AC2).
  - NEAR_MISS new version required: If `recipe.recipe_version == prior_recipe_version` and `near_miss_requires_new_version=True`, raises `NearMissMustHaveNewVersionError`. New version accepted (JOB-03-AC3).
  - Idempotent PASS scheduling: Same inputs always produce the same `RepeatDecision` (deterministic, no mutable state) (JOB-03-AC0).
- Deviation note: `policies.py` was merged into `dag.py` (no separate file needed). `cli/schedule_research.py` is an integration-layer CLI consumer outside the four ACs. Actual paths recorded here.
- Migration and compatibility:
  - Additive capability; no existing orchestration interfaces modified.
  - Dependencies: JOB-02 (REVIEW), EVAL-03 (REVIEW), ML-04 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| JOB-03-AC0 (RED) | `test_job_03_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.orchestration.dag') | `working tree` |
| JOB-03-AC0 (GREEN) | `test_job_03_valid_contract` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py::test_job_03_valid_contract` | Exit 0 (Passed, PASS outcome produces ALLOWED RepeatDecision with reason) | `630d2ae` |
| JOB-03-AC1 (RED) | `test_job_03_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-03-AC1 (GREEN) | `test_job_03_contract_1` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py::test_job_03_contract_1` | Exit 0 (Passed, HARD_FAIL raises HardFailCannotBeReopenedError even when system_idle=True) | `630d2ae` |
| JOB-03-AC2 (RED) | `test_job_03_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-03-AC2 (GREEN) | `test_job_03_contract_2` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py::test_job_03_contract_2` | Exit 0 (Passed, INVALID_RUN within limit=ALLOWED; exceeded limit=InvalidRunRetryLimitExceededError; config change=ValueError CONFIG_MUST_NOT_CHANGE) | `630d2ae` |
| JOB-03-AC3 (RED) | `test_job_03_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| JOB-03-AC3 (GREEN) | `test_job_03_contract_3` | `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py::test_job_03_contract_3` | Exit 0 (Passed, same version NEAR_MISS raises NearMissMustHaveNewVersionError; new version=ALLOWED) | `630d2ae` |

All 5 tests in `tests/unit/lab/orchestration/test_repeat_policy.py` passed (1.10s).
Full lab suite verification: 164 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of JOB-03 and docs/specs/13-jobs-resource-policy-and-repeats.md).
- Quality verdict: PASS (deterministic/pure scheduler, permanent HARD_FAIL block, bounded INVALID_RUN retry, NEAR_MISS version gate, no HTTP/mutable state, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviation: `policies.py` (planned) merged into `dag.py` — no separate file needed; policy model is `RepeatPolicy` in `dag.py`. `cli/schedule_research.py` out of scope (AC-layer consumers are downstream). Actual paths recorded here.
- Unresolved issues / blockers: None for JOB-03.
- Next unlocked consumers: QA-01, AGENT-01.
