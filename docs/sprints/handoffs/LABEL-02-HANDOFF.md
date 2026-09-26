# LABEL-02 handoff

Status: REVIEW

## Identity
- Sprint ID: LABEL-02 — Triple barrier outcomes
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/label-02-triple-barrier-outcomes`
- Base SHA: `e42e7cb`
- Code target: `feat(label-02): triple barrier outcomes`
- Evidence SHA relation: `54b6de07b5a7e11d63d50ed6b5885a30c4b74508`

## Files and contracts
- Planned files:
  - `src/indodax_lab/labels/triple_barrier.py` (BarrierTouch, TripleBarrierConfig, TripleBarrierLabel, build_triple_barrier_label, compute_concurrency_weights)
  - `src/indodax_lab/labels/__init__.py` (Public package exports)
  - `configs/labels/triple_barrier_v1.yaml` (Canonical triple barrier configuration)
  - `tests/unit/lab/labels/test_triple_barrier.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `entry + decision-time volatility + barrier config -> first_touch, label_end_ts, MAE/MFE, concurrency weight.`
  - Causal execution: entry at next eligible open after decision timestamp.
  - Frozen barrier levels calculated once from decision-time volatility; future volatility never shifts barriers.
  - Conservative same-bar touch resolution: when both upper and lower barriers are hit in the same candle, lower (stop-loss) barrier is chosen.
  - Fail-closed incomplete horizon: missing exit data before vertical barrier produces EXCLUDED/CENSORED label, never zero.
  - Temporal overlap tracking and concurrency weighting across concurrent label intervals.
- Migration and compatibility:
  - Additive labels subsystem; backward compatible.
  - Dependencies: LABEL-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| LABEL-02-AC0 (RED) | `test_label_02_valid_contract` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py` | Exit 1 (Failed: outcome != 1) | `working tree` |
| LABEL-02-AC0 (GREEN) | `test_label_02_valid_contract` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py::test_label_02_valid_contract` | Exit 0 (Passed, upper barrier hit at 12:00, outcome 1, MFE/MAE computed) | `54b6de0` |
| LABEL-02-AC1 (RED) | `test_label_02_contract_1` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py` | Exit 1 (Failed: UPPER chosen instead of LOWER) | `working tree` |
| LABEL-02-AC1 (GREEN) | `test_label_02_contract_1` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py::test_label_02_contract_1` | Exit 0 (Passed, same-bar touch conservative resolution chooses LOWER barrier) | `54b6de0` |
| LABEL-02-AC2 (RED) | `test_label_02_contract_2` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py` | Exit 1 (Failed: barriers not computed/frozen) | `working tree` |
| LABEL-02-AC2 (GREEN) | `test_label_02_contract_2` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py::test_label_02_contract_2` | Exit 0 (Passed, barriers frozen by decision-time volatility, never shifted by future) | `54b6de0` |
| LABEL-02-AC3 (RED) | `test_label_02_contract_3` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py` | Exit 1 (Failed: status != EXCLUDED) | `working tree` |
| LABEL-02-AC3 (GREEN) | `test_label_02_contract_3` | `python -m pytest tests/unit/lab/labels/test_triple_barrier.py::test_label_02_contract_3` | Exit 0 (Passed, incomplete horizon without touch is EXCLUDED/CENSORED) | `54b6de0` |

All 5 tests in `tests/unit/lab/labels/test_triple_barrier.py` passed (1.08s).
Combined suite verification (72 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation) passed (2.84s).

## Review
- Spec verdict: PASS (meets all functional requirements of LABEL-02 and specs/09-labels-splits-and-training-data.md).
- Quality verdict: PASS (conservative lower touch on conflict, frozen barriers, explicit exclusion on incomplete data, concurrency weighting).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for LABEL-02.
- Next unlocked consumers: SPLIT-01, D03-01.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ## Sprint-review fix cycle (CHANGES_REQUESTED)

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Remediation agent: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`. All source and test changes below exist in the working tree only: nothing is committed, staged, pushed or merged, and no mutating git command was run in this cycle.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Correction to an earlier fix attempt in this cycle - the wrong finding was actioned first

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Correction: an earlier attempt in this cycle implemented a change for a finding described as `AMBIGUOUS_BAR_TOUCHED_BOTH_BARRIERS`. That change was wrong and has been reverted. It contradicted the frozen acceptance criterion LABEL-02-AC1, "Dua barrier dalam candle sama memilih lower", which requires that a single candle touching both barriers resolves to the LOWER barrier. The AC1 fixture in `tests/unit/lab/labels/test_triple_barrier.py` is restored to its pristine committed content, with only a clarifying comment added. A regression guard for AC1 is retained in the new test file so the rule cannot be "fixed" away again. The real finding is LABEL-02-F1 below.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Finding LABEL-02-F1 - IMPORTANT - a label horizon reaching past the end of the covered data was still emitted as VALID

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important): the triple-barrier loop stopped at the last available bar without checking whether that bar actually covers the declared label horizon. When a bar opened after the point at which coverage would already have been decided, the walk terminated and the sample was returned with `status="VALID"` and a concrete `outcome`, even though no bar in the supplied data was ever able to establish the outcome. A label that was never resolvable was published as a resolved truth value, and `outcome=1` was fabricated for samples whose barrier had not been reached at all. This directly contradicts the sprint contract that an undecidable horizon is excluded rather than guessed.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED command: `python -m pytest tests/unit/lab/labels/test_triple_barrier_fail_closed.py -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - RED observed failure: `test_label_02_interior_gap_is_excluded` asserted `status == "EXCLUDED"` and received `'VALID'`, and the outcome assertion received `outcome=1`. `test_label_02_touch_before_gap_stands` passed at RED, proving the pre-existing touch behaviour was correct and that the defect is specifically the interior-bar gap. RED was `2 failed, 4 passed`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Fix summary: the labeler now tracks `coverage_end`, the latest instant for which the supplied bars actually provide coverage. When the next bar's `open_time` is after `coverage_end`, the horizon cannot be decided from this data, so the sample returns `status="EXCLUDED"` with `exclusion_reason="INTERIOR_BAR_GAP"` and no outcome. After each non-returning bar, `coverage_end` advances to `max(coverage_end, b_close_time)`, so a genuine interior bar that does resolve a barrier still returns normally and a genuine terminal-bar return is unaffected.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Files changed: `src/indodax_lab/labels/triple_barrier.py`, `tests/unit/lab/labels/test_triple_barrier_fail_closed.py`.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Affected-subsystem gate

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Command: `python -m pytest tests/unit/lab/evaluation tests/unit/lab/labels tests/unit/lab/security -q -p no:cacheprovider`
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Result: `157 passed in 4.49s` (evaluation 74, labels 71, security 12). `tests/unit/lab/labels` alone is `71 passed in 0.78s` and `test_triple_barrier_fail_closed.py` is `6 passed in 0.59s`.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - AC1 non-regression proof: `test_label_02_ambiguous_bar_resolves_to_lower_barrier` in the new fail-closed file asserts that a wild candle spanning both barriers still resolves to LOWER, so the reverted change is now covered by a test rather than only by a comment.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Repository gate: `python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors` gives `34 failed, 1109 passed, 30 errors in 40.75s`, Exit 1, with every failure and error attributable to a missing third-party package and zero behavioural failures. See the EVAL-02 handoff section for the full breakdown.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Capability gap per AGENTS.md: `ruff` is not installed, so no lint gate was run. `pyarrow` is not installed, so the parquet-dependent label pipelines could not be executed.

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Deferred (Minor) - not blocking

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: `exclusion_reason` is an optional string rather than a closed enumeration, so a new reason token can be added without a schema change and without a test forcing the addition to be intentional. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Minor: `coverage_end` is tracked as a local variable inside the labeling loop and is not surfaced on the result object, so a consumer cannot see how far coverage actually extended. Recorded as backlog.
- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | ### Out of scope - coordinator action required

- Actor: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free) | - Finding (Important, not fixed here): the excluded-with-reason result is returned as a normal return value rather than raising, so a caller that ignores `status` can still consume the record. Making the exclusion type-safe for every consumer is a contract change across the label consumers and was not attempted inside this single fix cycle.
