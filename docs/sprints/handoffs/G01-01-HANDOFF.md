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

## Fix cycle — mixed frame + actual ranker + missing label (2026-09-26)
- Findings G01-01: (a) mixed past+future frame silently filtered (`min>eval` only rejected all-future); (b) `GraphBaselineComparator.compare(snapshot)` built an internal ranker instead of scoring with the actual evaluated ranker; (c) missing `forward_return` zero-filled via `.get(...,0.0)` violating "unknown never→zero".
- Fix owner: opencode/muse-spark-1.3-contributor-free | Branch: `fix/g01-01-mixed-frame-comparator` | Base SHA: `fa6d4b5` | Worktree: `.worktrees/fix-g01-01` (main checkout untouched).
- Files:
  - `src/indodax_lab/models/graph/g01_cross_asset.py` — required-columns check (`MISSING_FORWARD_LABEL`) first; `max>eval_ts` rejects any future row including mixed frames (`FULL_SAMPLE_LEAKAGE_FORBIDDEN`); NaN/empty forward labels rejected (no zero-fill); `compare(snapshot, ranker)` uses caller-provided `CrossAssetGNNRanker` for graph + no-edge scores.
  - `tests/unit/lab/models/test_g01_01.py` — AC0/AC2/AC3 updated to pass causally-filtered frames (`df[timestamp<=eval]`); regressions `test_g01_01_mixed_frame_rejected_fail_closed`, `test_g01_01_comparator_uses_actual_ranker`, `test_g01_01_missing_forward_label_rejected`.
- TDD RED→GREEN:
  - RED: 4 failed (contract_3 TypeError missing ranker + 3 new DID NOT RAISE/TypeError); direct repros: `MIXED_ACCEPTED`, internal-ranker `compare` source, `MISSING_LABEL_ACCEPTED fwd=[0.]`.
  - GREEN: `python -m pytest tests/unit/lab/models/test_g01_01.py -q` → Exit 0, 7 passed.
- Scope: L01-01 untouched. No push. Note: callers must now pre-filter frames to `<=eval_ts`; unfiltered mixed frames are intentionally breaking (fail-closed).
