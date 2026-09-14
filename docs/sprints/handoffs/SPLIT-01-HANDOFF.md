# SPLIT-01 handoff

Status: REVIEW

## Identity
- Sprint ID: SPLIT-01 — Sealed purged chronological folds
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/split-01-sealed-purged-chronological-folds`
- Base SHA: `5732d28`
- Code target: `feat(split-01): sealed purged chronological folds`
- Evidence SHA relation: `96671cb7bbf991354cb7cc355bee693b92d53f47`

## Files and contracts
- Planned files:
  - `src/indodax_lab/labels/splits.py` (SampleRole, FoldWindow, SplitPolicy, SampleRecord, FoldAssignment, SplitManifest, assign_folds)
  - `configs/splits/annual_v1.yaml` (Canonical annual_v1 split configuration)
  - `src/indodax_lab/labels/__init__.py` (Package exports)
  - `tests/unit/lab/labels/test_splits.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `sample IDs + label_end_ts + declared exposure history -> versioned roles, purge and embargo manifest.`
  - Chronological role separation: pure point-in-time train, validation, and sealed test without label leakage.
  - Boundary purging: any training sample whose label outcome horizon crosses into validation/test window is purged (`LABEL_OVERLAPS_FOLD_BOUNDARY`).
  - Minimal embargo: policy strictly requires embargo >= max horizon; samples in inter-fold embargo are marked `EMBARGOED`.
  - Exposure history enforcement: periods declared exposed in `exposure_log` cannot be claimed as `SEALED_TEST` (`EXPOSED_PERIOD_CANNOT_BE_SEALED`).
- Migration and compatibility:
  - Additive split/fold assignment subsystem; backward compatible with LABEL-01 and LABEL-02.
  - Dependencies: LABEL-02 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SPLIT-01-AC0 (RED) | `test_split_01_valid_contract` | `python -m pytest tests/unit/lab/labels/test_splits.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SPLIT-01-AC0 (GREEN) | `test_split_01_valid_contract` | `python -m pytest tests/unit/lab/labels/test_splits.py::test_split_01_valid_contract` | Exit 0 (Passed, generates valid SplitManifest) | `96671cb` |
| SPLIT-01-AC1 (RED) | `test_split_01_contract_1` | `python -m pytest tests/unit/lab/labels/test_splits.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SPLIT-01-AC1 (GREEN) | `test_split_01_contract_1` | `python -m pytest tests/unit/lab/labels/test_splits.py::test_split_01_contract_1` | Exit 0 (Passed, boundary crosser purged) | `96671cb` |
| SPLIT-01-AC2 (RED) | `test_split_01_contract_2` | `python -m pytest tests/unit/lab/labels/test_splits.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SPLIT-01-AC2 (GREEN) | `test_split_01_contract_2` | `python -m pytest tests/unit/lab/labels/test_splits.py::test_split_01_contract_2` | Exit 0 (Passed, embargo >= max horizon enforced) | `96671cb` |
| SPLIT-01-AC3 (RED) | `test_split_01_contract_3` | `python -m pytest tests/unit/lab/labels/test_splits.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| SPLIT-01-AC3 (GREEN) | `test_split_01_contract_3` | `python -m pytest tests/unit/lab/labels/test_splits.py::test_split_01_contract_3` | Exit 0 (Passed, exposed period cannot be sealed) | `96671cb` |

All 4 tests in `tests/unit/lab/labels/test_splits.py` passed (1.14s).
Combined suite verification (100 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, evaluation, and orchestration).

## Review
- Spec verdict: PASS (meets all functional requirements of SPLIT-01 and specs/09-labels-splits-and-training-data.md).
- Quality verdict: PASS (zero lookahead leakage, strict boundary purging, verified embargo bounds, and tamper-proof exposure audit).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SPLIT-01.
- Next unlocked consumers: TRAIN-01, EVAL-03.
