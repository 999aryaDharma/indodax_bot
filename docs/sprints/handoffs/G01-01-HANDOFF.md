# G01-01 handoff

Status: REVIEW

## Identity
- Sprint ID: G01-01 — Point-in-time graph challenger
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/g01-01-point-in-time-graph-challenger`
- Base SHA: `172759b`
- Code target: `feat(g01-01): point-in-time graph challenger`
- Evidence SHA relation: `0aad539`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/graph/g01_cross_asset.py` (PointInTimeGraphConfig, PointInTimeGraphBuilder, GraphSnapshot, CrossAssetGNNRanker, GraphBaselineComparator, RankedAsset, GraphBaselineComparison, FullSampleAdjacencyLeakageError, PrematureNodeInclusionError, GraphBudgetExceededError)
  - `src/indodax_lab/models/graph/__init__.py` (Package exports)
  - `tests/unit/lab/models/test_g01_01.py` (AC0..AC3 test cases)
- Contract:
  - `Eligible nodes + train-only rolling edges -> cross-asset rank; <=8 configurations`
  - Cross-asset ranking & execution: Message passing over rolling point-in-time correlation graph scores and ranks active assets, routing top-K picks to `CostAwareExecutionMapper` (G01-01-AC0).
  - Full-sample leakage defense: Adjacency matrices must strictly be estimated using rolling historical return windows; future-looking correlation matrices are rejected fail-closed with `FullSampleAdjacencyLeakageError` (G01-01-AC1).
  - Point-in-time node eligibility: Newly listed assets ($T_{list} > T$) are barred from graph snapshots fail-closed (`PrematureNodeInclusionError`), ensuring no survivorship or premature node leakage (G01-01-AC2).
  - Three-way baseline comparison: Evaluates G01 graph performance against no-edge MLP ($A = I$) and panel OLS regression on identical cross-asset evaluation snapshots (G01-01-AC3).
- Migration and compatibility:
  - Additive package `src/indodax_lab/models/graph/` with zero breaking changes to existing models.
  - Dependencies: D01-01 (REVIEW), C04-01 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| G01-01-AC0 (RED) | `test_g01_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_g01_01.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.graph') | `working tree` |
| G01-01-AC0 (GREEN) | `test_g01_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_g01_01.py::test_g01_01_valid_contract` | Exit 0 (Passed, PIT graph scores cross-asset universe and routes to CostAwareExecutionMapper) | `0aad539` |
| G01-01-AC1 (RED) | `test_g01_01_contract_1` | `python -m pytest tests/unit/lab/models/test_g01_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| G01-01-AC1 (GREEN) | `test_g01_01_contract_1` | `python -m pytest tests/unit/lab/models/test_g01_01.py::test_g01_01_contract_1` | Exit 0 (Passed, full-sample future adjacency strictly rejected fail-closed) | `0aad539` |
| G01-01-AC2 (RED) | `test_g01_01_contract_2` | `python -m pytest tests/unit/lab/models/test_g01_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| G01-01-AC2 (GREEN) | `test_g01_01_contract_2` | `python -m pytest tests/unit/lab/models/test_g01_01.py::test_g01_01_contract_2` | Exit 0 (Passed, unlisted asset excluded and premature node inclusion rejected fail-closed) | `0aad539` |
| G01-01-AC3 (RED) | `test_g01_01_contract_3` | `python -m pytest tests/unit/lab/models/test_g01_01.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| G01-01-AC3 (GREEN) | `test_g01_01_contract_3` | `python -m pytest tests/unit/lab/models/test_g01_01.py::test_g01_01_contract_3` | Exit 0 (Passed, comparative rank correlations evaluated against no-edge MLP and panel OLS) | `0aad539` |

All 4 tests in `tests/unit/lab/models/test_g01_01.py` passed (1.93s).
Full lab suite verification: 255 passed across all domains.

## Review
- Spec verdict: PASS (meets all requirements of G01-01 and docs/specs/15-deep-learning-and-provenance.md).
- Quality verdict: PASS (clean rolling adjacency, strict listing eligibility, multi-baseline comparison, budget <= 8 configs).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for G01-01.
- Next unlocked consumers: Research comparison complete.

## Independent review findings -- remediation evidence (fix cycle 1)

- Remediation agent: `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`
- Branch / worktree: `D:\bot-trading` working tree on `feat/feat-02-finalization`
- Base SHA at remediation start: `faeac7a` (no commit created by this agent; all edits are uncommitted working-tree changes for the coordinator to commit)
- Scope: accepted blocking findings from the sprint review only. No acceptance assertion was weakened, deleted or skipped.

### RED (behavioral, run against the pre-fix source)

| Command | Exit / result |
|---|---|
| `python -m pytest tests/unit/lab/models/test_g01_01.py -p no:cacheprovider` | Exit 1 -- `7 failed, 5 passed`: `Failed: DID NOT RAISE` x2 (`MissingGraphColumnError`, `PrematureNodeInclusionError(NO_OBSERVATIONS_AT_EVAL_TS)`, `GraphSnapshotUnderdeterminedError`), `AttributeError: 'GraphSnapshot' object has no attribute 'edge_method'`, `TypeError: GraphBaselineComparator() takes no arguments`, `AttributeError: 'CrossAssetGNNRanker' object has no attribute 'compute_budget'`, and the constant-target correlation assertion |

The three new exception classes were added to the source first, without their guards, so the
RED was a behavioral assertion failure rather than a collection `ImportError`. The 5
passing tests at RED are the 4 pre-existing AC tests plus the new future-perturbation
positive-evidence test, which is expected to pass both before and after the fix.

### GREEN

| Command | Exit / result |
|---|---|
| `python -m pytest tests/unit/lab/models/test_g01_01.py -p no:cacheprovider` | Exit 0 -- `14 passed in 1.86s` |

### Critical findings fixed

1. **A missing `forward_return` column silently became a constant `0.0` target.**
   `last_row.get("forward_return", 0.0)` produced `[0. 0. 0.]` forward returns, so every
   Spearman correlation computed against a constant target and reported `0.0` -- a clean
   "the graph adds nothing over the baselines" result derived from a missing column.
   Fix: `PointInTimeGraphBuilder.REQUIRED_COLUMNS` is validated up front and a missing
   column raises `MissingGraphColumnError("MISSING_GRAPH_COLUMN")`.
   Regression: `test_g01_01_snapshot_requires_forward_return_column`.

2. **An undefined Spearman correlation was reported as a real `0.0`.** `0.0` conflates
   "perfectly uncorrelated" with "not computable", and it is exactly the number a
   graph-vs-baseline promotion decision reads.
   Fix: the three correlation fields are now `float | None`;
   `_spearman_or_none` returns `None` for a non-finite result (constant score or target
   vector) and suppresses `ConstantInputWarning`. `0.0` now only ever means a genuinely
   uncorrelated score.
   Regression: `test_g01_01_constant_target_reports_undefined_correlation_not_zero`.

3. **A listed-but-dateless node produced a malformed snapshot.** The node was zero-filled
   (`[0.0] * 3` features, `0.0` target) while still consuming a row and a column of the
   adjacency matrix. Reproduced on the pre-fix source: a 4-node snapshot with a 3x3 adjacency
   matrix, then an opaque `ValueError: matmul: Input operand 1 has a mismatch in its core
   dimension 0` downstream.
   Fix: `MIN_OBSERVATIONS_PER_NODE = 2`; any active node with fewer observations at or
   before `eval_ts` raises `PrematureNodeInclusionError("NO_OBSERVATIONS_AT_EVAL_TS")`.
   The zero-fill branches are removed entirely and the unreachable residual case also fails
   closed. `return_piv` is additionally `reindex`-ed to `active_nodes` so adjacency rows
   cannot silently desynchronise from the requested node set.
   Regression: `test_g01_01_forced_node_without_observations_is_rejected`.

### Important findings fixed

4. **`GraphBaselineComparator.compare` benchmarked a different model than the caller's.**
   It hardcoded `PointInTimeGraphConfig(rolling_window=10)` with the default seed 42, so any
   caller using a different window or seed silently got a benchmark of an unrelated model.
   Fix: `GraphBaselineComparator(ranker=None)` accepts the ranker in use; the comparison
   reports `ranker_seed` so the benchmarked configuration is self-describing.
   Regression: `test_g01_01_comparator_benchmarks_the_ranker_in_use`.

5. **Rank correlation over fewer than 3 assets cannot separate signal from coincidence.**
   `GraphSnapshotUnderdeterminedError("UNDERDETERMINED_GRAPH_SNAPSHOT")` is raised below
   `MIN_BENCHMARK_NODES = 3`.
   Regression: `test_g01_01_comparison_requires_at_least_three_nodes`.

6. **The snapshot carried no edge provenance.** Spec 15 section 15 requires "Graph metadata
   binds edge method/window/train cutoff and availability"; without it a snapshot cannot be
   shown to have been built from pre-cutoff edges only.
   Fix: `GraphSnapshot` now binds `edge_method`
   (`rolling_pearson_thresholded_symmetric`), `edge_window`, `edge_train_cutoff` and
   `edges_available_at`; the no-edge comparator baseline inherits all four and only varies
   `edge_method`.
   Regression: `test_g01_01_snapshot_binds_edge_provenance_metadata.

7. **No compute budget was reported.** Added `GraphComputeBudgetSummary` (input_dim,
   hidden_dim, total_learned_parameters, estimated_flops_per_inference) on
   `CrossAssetGNNRanker.compute_budget` and carried into `GraphBaselineComparison`.
   Regression: `test_g01_01_reports_compute_budget.

8. **AC1 had no positive evidence.** Added
   `test_g01_01_future_perturbation_does_not_change_snapshot`, which proves that a full-sample
   frame and a pre-truncated frame yield byte-identical nodes, features, adjacency and forward
   returns -- i.e. the leakage guard is satisfied automatically, not only when it fires.

9. **Search budget and window floor had no test coverage.** Added
   `test_g01_01_search_budget_cannot_exceed_eight` and
   `test_g01_01_rolling_window_floor_is_enforced` (spec 15 "<=8 configurations").
   These pass against the pre-fix source as well and are characterised coverage, not RED.

10. Removed the unused `pydantic.Field` import and an unused local (`n_nodes`).

### Deferred (Minor) -- not blocking

- `PointInTimeGraphConfig` still has no validation for `correlation_threshold` in
  `[0, 1]` or `top_k >= 1`. Both are currently only guarded by downstream `numpy`
  behaviour, and neither was part of the accepted blocking set.
- `PointInTimeGraphBuilder` has no explicit registration path for a real 3-seed
  finalist search; `max_configurations` is a declared budget with no live registry (unlike
  the L02-01 `TLOBConfigSearch` added in this batch). Recorded as a follow-up rather than
  added here, since no G01-01 caller drives a search yet.
- The no-edge baseline and panel baseline are re-derived inside `compare` rather than being
  injectable, so a third baseline cannot be added without editing this method.

### Verification performed

- `ruff check` on all owned files: no new findings. Residual findings on these files are
  pre-existing at HEAD; the count for the owned file set is now **36** versus **55** at HEAD.
- Owned suite: `python -m pytest tests/unit/lab/models/test_f01_01.py tests/unit/lab/models/test_f01_02.py tests/unit/lab/models/test_g01_01.py tests/unit/lab/models/lob/test_l02_01.py -q -p no:cacheprovider` -> Exit 0, `50 passed in 4.16s`.
- Recorded by `opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)`.

## Independent review — coordinator pass (2026-09-27)

- Verdict: PASS. Fresh run `test_g01_01.py -v`: 14 passed, exit 0 (4 AC + 10
  remediation/characterisation). AC0–AC3 verified under strict PIT:
  future-only frames raise; mixed frames truncate byte-identically; unlisted/
  dateless nodes raise; baselines compared on identical forwards.
- MINOR: mixed-frame truncation (not raise) — clarify contract doc; "panel
  regression" baseline is unfitted momentum passthrough — fit or rename;
  threshold/top_k unvalidated.
- Process note: deps D01-01 + C04-01 REVIEW (gate for DONE).
- No Critical/Important findings. Reviewer ses_f1ebdb706ffeOQoWcpSWGb63tf.
