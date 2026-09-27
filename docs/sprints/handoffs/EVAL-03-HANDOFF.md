# EVAL-03 handoff

Status: REVIEW

## Identity
- Sprint ID: EVAL-03 — Sealed candidate lifecycle
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/eval-03-sealed-candidate-lifecycle`
- Base SHA: `1503658`
- Code target: `feat(eval-03): sealed candidate lifecycle`
- Evidence SHA relation: `05ffd1a0cfc380d33612ffa510c324959102d032`

## Files and contracts
- Planned files:
  - `src/indodax_lab/evaluation/lifecycle.py` (CandidateStage, CandidateRecord, CandidateLifecycleManager, ExposureAuditRecord, LeaderboardEntry, errors)
  - `src/indodax_lab/evaluation/__init__.py` (Package exports)
  - `tests/unit/lab/evaluation/test_lifecycle.py` (AC0..AC3 unit tests)
- Contract:
  - `IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.`
  - Frozen candidate mutation guard: Any attempt to mutate the configuration of a validated or sealed candidate in-place raises `CandidateFrozenError`. Spawning a new challenger (`fork_challenger`) is required, resetting lifecycle status for the branched version while preserving the frozen candidate.
  - Single-use sealed gate with audit trail: The sealed evaluation gate can only be opened once per candidate version. Reopening raises `GateAlreadyOpenedError`. Each opening event is recorded in `ExposureAuditRecord`.
  - Leaderboard integrity guard: Runs marked as `INVALID_RUN` or failed are strictly excluded from candidate leaderboards.
- Migration and compatibility:
  - Additive candidate lifecycle state machine and SQLite exposure audit tables.
  - Dependencies: EVAL-02 (DONE), SPLIT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| EVAL-03-AC0 (RED) | `test_eval_03_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.evaluation.lifecycle') | `working tree` |
| EVAL-03-AC0 (GREEN) | `test_eval_03_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_valid_contract` | Exit 0 (Passed, promotes candidate through sequential lifecycle stages with exposure audit) | `05ffd1a` |
| EVAL-03-AC1 (RED) | `test_eval_03_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-03-AC1 (GREEN) | `test_eval_03_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_contract_1` | Exit 0 (Passed, sealed config modification rejected in place, forks new challenger) | `05ffd1a` |
| EVAL-03-AC2 (RED) | `test_eval_03_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-03-AC2 (GREEN) | `test_eval_03_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_contract_2` | Exit 0 (Passed, sealed gate opened once and recorded; reopening attempt fails closed) | `05ffd1a` |
| EVAL-03-AC3 (RED) | `test_eval_03_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-03-AC3 (GREEN) | `test_eval_03_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_contract_3` | Exit 0 (Passed, invalid runs strictly excluded from leaderboard ranking) | `05ffd1a` |

All 4 tests in `tests/unit/lab/evaluation/test_lifecycle.py` passed (1.28s).
Full lab suite verification: 121 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, and training materialization.

## Review
- Spec verdict: PASS (meets all functional requirements of EVAL-03 and specs/11-evaluation-and-experiment-lifecycle.md).
- Quality verdict: PASS (immutable state machine transitions, fail-closed unseal guard, strict exclusion of invalid runs from ranking).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for EVAL-03.
- Next unlocked consumers: ML-04, JOB-03, SHADOW-01, SHADOW-03, REPORT-01.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ## Sprint-review fix cycle (CHANGES_REQUESTED)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Remediation agent: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`. All source and test changes below exist in the working tree only: nothing is committed, staged, pushed or merged, and no mutating git command was run in this cycle.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding EVAL-03-F1 - CRITICAL - the sealed gate could be unsealed from any stage, with no VALIDATED predecessor

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `unseal_gate` accepted a candidate in any stage, so a candidate still in `TRAINING` or `EVALUATED` had its sealed gate opened. The gate is the seal on the sealed-test evidence, so opening it before validation defeats the whole leakage-prevention chain in `docs/specs/11-evaluation-and-experiment-lifecycle.md`. No predecessor check existed.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/evaluation/test_lifecycle_fail_closed.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `test_eval_03_unseal_requires_validated_stage` asserted that unsealing from a non-`VALIDATED` stage raises, and the pre-fix `unseal_gate` returned successfully for a `TRAINING` candidate.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: `_GATE_UNSEAL_PREDECESSOR = CandidateStage.VALIDATED` is now enforced. Only a candidate in exactly `VALIDATED` may open its sealed gate, and the error is retokenized to `UNSEAL_REQUIRES_VALIDATED_STAGE` naming the actual stage so the operator can see what state the candidate was in.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/evaluation/lifecycle.py`, `tests/unit/lab/evaluation/test_lifecycle_fail_closed.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding EVAL-03-F2 - CRITICAL - stage transitions and gate unsealing were not atomic, so a partial write left an inconsistent candidate

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `transition_stage` and `unseal_gate` performed their read, their validation and their write as separate statements with no enclosing transaction. A failure between the read and the write, or a concurrent writer between them, left a candidate whose recorded stage and whose transition history disagreed, or a gate flag flipped without its audit row. This is exactly the persistence/state defect class that the AGENTS.md severity policy classifies as blocking.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/evaluation/test_lifecycle_fail_closed.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `test_eval_03_transition_and_unseal_are_atomic` forced a mid-operation failure and observed committed state that did not correspond to a completed operation, rather than a rollback to the pre-call state.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: an `_atomic()` context manager now opens `BEGIN IMMEDIATE` and commits or rolls back as a unit. Both `transition_stage` and `unseal_gate` run entirely inside it, so a failure leaves the candidate exactly as it was. The stage `UPDATE` is also now conditional (`WHERE current_stage = ?`) and rejects a `rowcount != 1`, so a concurrent writer is detected instead of silently overwritten. The gate `UPDATE` carries `WHERE sealed_gate_opened = 0` for the same reason.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/evaluation/lifecycle.py`, `tests/unit/lab/evaluation/test_lifecycle_fail_closed.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding EVAL-03-F3 - CRITICAL - blank dataset-split and blank authorizer were accepted as unseal evidence

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Critical): `unseal_gate` checked that `dataset_split_id` and `authorized_by` were not `None` but did not reject empty or whitespace-only strings. An operator could therefore open the sealed gate with `""` as the split identity or as the authorizer, producing a gate that is nominally unsealed while carrying no evidence of which dataset was used or who authorised it. The whole audit value of the seal depends on those two fields.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/evaluation/test_lifecycle_fail_closed.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `test_eval_03_unseal_verifies_split_and_authorizer` and `test_eval_03_unseal_rejects_blank_split_and_authorizer` asserted the two rejections and the pre-fix `is None` checks let blank strings through to a successful unseal.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: blank `dataset_split_id` now raises `DATASET_SPLIT_ID_REQUIRED` and blank `authorized_by` raises `UNSEAL_AUTHORIZED_BY_REQUIRED`. Both are validated before any state change, so a rejected unseal leaves the gate sealed.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/evaluation/lifecycle.py`, `tests/unit/lab/evaluation/test_lifecycle_fail_closed.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding EVAL-03-F4 - IMPORTANT - non-finite leaderboard metrics were admitted to the leaderboard

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important): a leaderboard entry whose metric value was NaN or infinite was written and ranked, so a corrupt run occupied a leaderboard position and could be selected by any consumer that takes the top row. The spec rule in `docs/specs/11-evaluation-and-experiment-lifecycle.md` line 52 requires absent or unusable data to keep explicit unknown semantics rather than be silently admitted.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/evaluation/test_lifecycle_fail_closed.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: the non-finite leaderboard test asserted the entry is refused and the pre-fix path admitted the NaN entry.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: non-finite leaderboard metrics are now excluded at the write boundary, so an unusable metric never occupies a ranked position.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/evaluation/lifecycle.py`, `tests/unit/lab/evaluation/test_lifecycle_fail_closed.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding EVAL-03-F5 - IMPORTANT - the candidate was re-read outside the transaction, so the validated stage could be stale

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important): `unseal_gate` re-fetched the candidate in a separate step from the decision that relied on it, so the stage used to authorise the unseal was not the stage held under the write lock. A candidate advanced or rolled back between the two reads could be unsealed against a stage that was no longer current.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/evaluation/test_lifecycle_fail_closed.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `test_eval_03_transition_and_unseal_are_atomic` exercised the interleaving and observed the unseal proceeding against the stale read.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the candidate fetch is now `_fetch_candidate()` and is called inside the `_atomic()` block, so the stage that authorises the unseal is the stage read under the same immediate transaction that performs the write.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/evaluation/lifecycle.py`, `tests/unit/lab/evaluation/test_lifecycle_fail_closed.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Affected-subsystem gate

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Command: `python -m pytest tests/unit/lab/evaluation tests/unit/lab/labels tests/unit/lab/security -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Result: `157 passed in 4.49s` (evaluation 74, labels 71, security 12). `tests/unit/lab/evaluation/test_lifecycle_fail_closed.py` alone is `10 passed in 1.45s`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Repository gate: `python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors` gives `34 failed, 1109 passed, 30 errors in 40.75s`, Exit 1, with every failure and error attributable to a missing third-party package and zero behavioural failures. See the EVAL-02 handoff section for the full breakdown.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Capability gap per AGENTS.md: `ruff` is not installed, so no lint gate was run. `pyarrow` is not installed, so the parquet-dependent suites could not be collected.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Deferred (Minor) - not blocking

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: `_GATE_UNSEAL_PREDECESSOR` names a single predecessor stage, so a future lifecycle that inserts a stage between `VALIDATED` and the gate would need this constant changed rather than a rule set. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: the `BEGIN IMMEDIATE` transaction relies on SQLite write locking, so a non-SQLite connection object supplied by a caller would not receive the same isolation guarantee. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Out of scope - coordinator action required

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important, not fixed here): the non-finite leaderboard exclusion in EVAL-03-F4 silently drops the row rather than recording that a run was excluded for an unusable metric, so a candidate that trained and evaluated but could not be ranked leaves no trace. Persisting an explicit excluded-metric record is a schema change and therefore a change-control item rather than a defect repair inside this fix cycle.

## Independent review — coordinator DONE pass (2026-09-27)

- Verdict: CONFIRM-PASS. Fresh run `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py -v`: 4 passed, 0 failed (AC0–AC3).
- No new findings against src/indodax_lab/evaluation/lifecycle.py (atomic transitions, VALIDATED predecessor gate, single-open gate, INVALID_RUN exclusion all hold).
- First review: ses_f201210c9ffeW8lv1BTI265hiX. Verification: ses_f1f5b2f64ffeK6bxrjI9CRgTDJ.
- Reviewed at HEAD 28d89ba with uncommitted working-tree changes present; exact-SHA pinning pending at commit time.

## Independent review fix cycle — UTC timestamp validation

Implementation source SHA: `0727de02d69972bf31d644e6956da76c3eb52731`.

Independent review at `64769f883a15c76bbf680b52d6530053edae4ae0` found that naive `as_of` values were written to lifecycle/audit rows before Pydantic rejected the returned record. `transition_stage` could advance the candidate and then leave it unreadable; `unseal_gate` had the same post-commit validation hazard.

Fix: both methods now call the existing UTC validator before generating/starting their write transaction. RED at pre-fix state: both regressions failed because the public call did not produce the required early `UTC_TIMEZONE_AWARE_REQUIRED:as_of` rejection (and invalid state was committed). GREEN: `conda run -n ML python -m pytest -q tests/unit/lab/evaluation/test_lifecycle_fail_closed.py -k naive` — 2 passed; full affected EVAL unit scope — 124 passed using the current shared working-tree snapshot of `test_lifecycle_fail_closed.py` (which includes concurrent fixture corrections for EVAL-03 split exposure). The snapshot copy was temporary and removed; no concurrent owner changes were staged.

Focused Ruff `I,F401` and `git diff --check` passed. Independent delta review by `docs_review`: PASS at exact source SHA `0727de02d69972bf31d644e6956da76c3eb52731`; reviewer confirmed naive and non-UTC rejection before transaction entry and verified state/audit remain unchanged.

No Critical/Important finding remains in this delta. EVAL-03 status awaits the coordinator batch pass and any remaining dependency reconciliation; no manifest change is made here.
