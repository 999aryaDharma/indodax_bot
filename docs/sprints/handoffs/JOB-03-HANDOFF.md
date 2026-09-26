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

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ## Sprint-review fix cycle (CHANGES_REQUESTED)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 1 - CRITICAL - the INVALID_RUN config-immutability guard was skippable by omission, and the decision lied about verifying it

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): JOB-03-AC2 requires that an INVALID_RUN retry "must not change config". The guard was `if original_retry_config is not None:` and the parameter defaulted to `None`, so the config comparison was skipped entirely on the default call path. Any caller that forgot to pass the anchor could mutate `config_hash` on every INVALID_RUN retry and still receive `outcome=ALLOWED`. That is precisely the "changing evaluator gates or adding retry/search budget to make results pass" path the sprint lists as out of scope, and the module docstring's own "no silent evaluator policy changes" guarantee. Compounding it, the returned `RepeatDecision.reason` unconditionally ended with "Config hash verified unchanged." — so the decision record asserted a verification that had never been performed, and the artifact looked like verified evidence to any downstream reader. Untested: the pre-existing AC2 test only exercised sub-case C, which does pass an anchor.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/orchestration/test_repeat_policy.py:242: AssertionError: assert 'Config hash...ed unchanged' not in 'INVALID_RUN...d unchanged.'` with `'Config hash verified unchanged' is contained here: retries. Config hash verified unchanged.`; and `:255: Failed: DID NOT RAISE <class 'indodax_lab.orchestration.dag.InvalidRunRetryConfigRequiredError'>`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the config anchor is now mandatory for INVALID_RUN retries. A new `InvalidRunRetryConfigRequiredError` with a `RETRY_CONFIG_ANCHOR_REQUIRED:` prefix is raised when no anchor is supplied, and the "Config hash verified unchanged" phrase is now only reachable on the anchored path where a real comparison happened. The message itself states plainly that config immutability could not be verified rather than implying it had been.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED purity note: `InvalidRunRetryConfigRequiredError` was added as a class declaration only, with no behavior change, before the RED run, precisely so the two failures above could be observed as real behavioral assertion failures rather than as an `ImportError` at collection.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Contract change flagged for the coordinator: `decide_repeat(prior_outcome=INVALID_RUN, ...)` without `original_retry_config` previously returned `ALLOWED` and now always raises. The pre-existing `test_job_03_contract_2` sub-cases A and B were updated to pass an `InvalidRunRetryConfig` anchor, which is the call shape AC2 requires. Sub-case C was already anchored and is unchanged. No assertion was weakened or deleted. A repository-wide grep confirms `decide_repeat` has no caller in `src/` outside the module, so there is no other production impact.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `12 passed in 0.97s`, from `5 failed, 7 passed` at RED.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/dag.py`, `src/indodax_lab/orchestration/__init__.py`, `tests/unit/lab/orchestration/test_repeat_policy.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 2 - IMPORTANT - a negative attempt count bypassed the INVALID_RUN retry cap entirely

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important): the cap check is `if attempt_count > self.policy.max_invalid_run_retries`, which is trivially false for any negative count. A caller whose attempt bookkeeping had gone negative, or who passed an unset/zeroed counter as `-1`, was granted an unlimited retry allowance while the policy cap still appeared to be enforced in the reason string as "attempt -1 of 2 allowed retries". The cap is the primary bound AC2 places on retry budget, so an unbounded path around it defeats the guarantee. Untested.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py -p no:cacheprovider -q --tb=line`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/orchestration/test_repeat_policy.py:287: Failed: DID NOT RAISE <class 'ValueError'>`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: `decide_repeat` now rejects a negative `attempt_count` with `ATTEMPT_COUNT_INVALID:` before any policy evaluation. The check is ordered before the config anchor and cap checks so a malformed counter is reported as the malformed input it is. The off-by-one question in the cap itself was checked and found correct: with `max_invalid_run_retries=2` and `attempt_count` meaning prior attempts, attempts 0, 1 and 2 are allowed and 3 is refused, which is exactly two retries after the initial run. `test_retry_cap_boundary_is_exact` now pins that boundary; it passes pre-fix and is therefore a regression guard rather than a RED.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN command: `python -m pytest tests/unit/lab/orchestration/test_repeat_policy.py -p no:cacheprovider -q --tb=short`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `12 passed in 0.97s`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/dag.py`, `tests/unit/lab/orchestration/test_repeat_policy.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 3 - MINOR - `hard_fail_reopenable` was a policy knob the scheduler never read

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Minor): `RepeatPolicy.hard_fail_reopenable` was never consulted by `decide_repeat`. The scheduler blocked HARD_FAIL unconditionally, which is the correct and safe behavior, but a caller could construct `RepeatPolicy(hard_fail_reopenable=True)` and receive false assurance that the permanent gate had been relaxed, when in fact the field was inert. Classified Minor because the unsafe direction was never reachable: no input could reopen a HARD_FAIL.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: rather than honoring the field, which would be exactly the evaluator-gate relaxation the sprint forbids, `RepeatPolicy` now rejects `hard_fail_reopenable=True` at construction with `HARD_FAIL_REOPEN_NOT_SUPPORTED:`. The field is kept so existing `hard_fail_reopenable=False` construction still works, and `test_policy_cannot_claim_hard_fail_is_reopenable` asserts both that `True` is refused and that the honest `False` value still constructs. The unconditional HARD_FAIL block in `decide_repeat` is unchanged.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/orchestration/test_repeat_policy.py:328: Failed: DID NOT RAISE <class 'ValueError'>`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `12 passed in 0.97s`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/dag.py`, `tests/unit/lab/orchestration/test_repeat_policy.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding 4 - MINOR - a negative retry cap blocked even the first run while looking like a valid policy

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Minor): `max_invalid_run_retries` had no lower bound, so `RepeatPolicy(max_invalid_run_retries=-1)` constructed successfully and then refused even `attempt_count=0`, the first-ever run of a recipe. The direction was fail-closed, but a policy that blocks initial execution is a misconfiguration, not a policy.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the field is now `Field(default=2, ge=0)` with a `validate_retry_cap` field validator raising `RETRY_CAP_INVALID:` and an explicit explanation. `ge=0` is retained alongside the validator so the constraint is visible in the model schema as well as in the message.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `tests/unit/lab/orchestration/test_repeat_policy.py:337: Failed: DID NOT RAISE <class 'ValueError'>`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - GREEN result: `12 passed in 0.97s`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/orchestration/dag.py`, `tests/unit/lab/orchestration/test_repeat_policy.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Affected-subsystem gate

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Command: `python -m pytest tests/unit/lab/orchestration tests/unit/lab/reporting tests/unit/lab/verification tests/integration/lab/test_telegram_status.py tests/regression/test_release_candidate.py tests/research/test_rl_reward_contract.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Result: `96 passed in 3.14s`, up from the 89-test post-R01-01 baseline by exactly the 7 tests added in this cycle, with no regression.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Out of scope - coordinator action required

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important, not fixed here): `ResearchDAGJob` carries `prior_outcome`, `attempt_count`, and `decision`, but no code path in the module ever populates it, so the model that represents a scheduled DAG job is dead. Implementing the scheduling/persistence path is new capability requiring a CR, not a fix cycle.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important, not fixed here): `DAGScheduler.decide_repeat` is a pure function with no durable state, so nothing persists an attempt count between calls. The bound is therefore only as trustworthy as its caller, and the mandatory config anchor now forces callers to hold that state explicitly. A durable attempt ledger is new capability requiring a CR.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Capability gap per AGENTS.md: `ruff` is not installed, so no lint gate was run. `pyarrow` is not installed, so `tests/unit/lab/models/lob/` fails collection and was excluded.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Deferred (Minor) - not blocking

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: `ExperimentRecipe.parameters` uses a mutable `{}` as a pydantic default. Pydantic deep-copies field defaults per instance, so this is safe, but `Field(default_factory=dict)` would express the intent more clearly. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: `decide_repeat` returns `RepeatDecision` with only `ALLOWED` and `BLOCKED` outcomes, but every blocked path raises rather than returning a `BLOCKED` decision, so `RepeatOutcome.BLOCKED` is never actually produced. Either the enum member or the raise-on-block style is redundant. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: `RepeatDecision` has no timestamp or policy-version field, so a stored decision record cannot be traced back to the `RepeatPolicy` that produced it. Recorded as backlog.
