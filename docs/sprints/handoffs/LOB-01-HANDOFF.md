# LOB-01 handoff

Status: REVIEW

## Identity
- Sprint ID: LOB-01 — Forward book dataset eligibility
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/lob-01-forward-book-dataset-eligibility`
- Base SHA: `f9930c6`
- Code target: `feat(lob-01): forward book dataset eligibility gate`
- Evidence SHA relation: `e7e1b09`

## Files and contracts
- Planned files:
  - `src/indodax_lab/features/lob.py` (extract_lob_tensor, compute_depth_imbalance, compute_spread, compute_microprice)
  - `src/indodax_lab/models/lob/dataset.py` (LOBDatasetEligibilityGate, BookSnapshot, BookLevel, LOBSessionMetadata, LOBEligibilityReport, CandleSubstitutionForbiddenError, SessionGapBrokenWindowError, InsufficientCoverageGateError)
  - `src/indodax_lab/models/lob/__init__.py`
  - `tests/unit/lab/models/lob/test_lob_data_gate.py` (AC0..AC3 test cases)
- Contract:
  - `continuous raw books -> depth/imbalance tensors with >=90 day coverage gate plus sample/regime report`
  - Dataset eligibility gate: Sessions require >=90 distinct calendar days with PASS status and sufficient effective events to pass the gate and produce an eligibility report (LOB-01-AC0).
  - Candle substitution prohibition: Any OHLCV candle dataframe or dictionary attempting to substitute for order book depth snapshots is rejected fail-closed with `CandleSubstitutionForbiddenError` (LOB-01-AC1).
  - Gap breaking: Sequence windows strictly segment upon encountering gaps exceeding `max_gap_seconds` (e.g. 10s or 60s); sequence windows never bridge or interpolate across unobserved intervals (LOB-01-AC2).
  - Calendar coverage enforcement: High row counts concentrated across fewer than 90 calendar days are rejected fail-closed with `InsufficientCoverageGateError` (LOB-01-AC3).
- Migration and compatibility:
  - Additive microstructure package `src/indodax_lab/models/lob` and `src/indodax_lab/features/lob.py` with zero breaking changes.
  - Dependencies: DATA-06 (DONE), FEAT-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| LOB-01-AC0 (RED) | `test_lob_01_valid_contract` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.lob') | `working tree` |
| LOB-01-AC0 (GREEN) | `test_lob_01_valid_contract` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_valid_contract` | Exit 0 (Passed, 92-day PASS sessions pass gate, generate depth/imbalance tensors and regime report) | `e7e1b09` |
| LOB-01-AC1 (RED) | `test_lob_01_contract_1` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| LOB-01-AC1 (GREEN) | `test_lob_01_contract_1` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_contract_1` | Exit 0 (Passed, candle OHLCV data rejected with CandleSubstitutionForbiddenError) | `e7e1b09` |
| LOB-01-AC2 (RED) | `test_lob_01_contract_2` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| LOB-01-AC2 (GREEN) | `test_lob_01_contract_2` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_contract_2` | Exit 0 (Passed, 120s gap breaks sequence window into non-overlapping runs without interpolation) | `e7e1b09` |
| LOB-01-AC3 (RED) | `test_lob_01_contract_3` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| LOB-01-AC3 (GREEN) | `test_lob_01_contract_3` | `python -m pytest tests/unit/lab/models/lob/test_lob_data_gate.py::test_lob_01_contract_3` | Exit 0 (Passed, 1,000,000 events in 15 days fails 90-day coverage gate fail-closed) | `e7e1b09` |

All 4 tests in `tests/unit/lab/models/lob/test_lob_data_gate.py` passed (2.07s).
Full lab suite verification: 267 passed across all domains (13.44s).

## Review
- Spec verdict: PASS (meets all requirements of LOB-01 and docs/specs/16-order-book-research.md).
- Quality verdict: PASS (>=90-day PASS calendar gate, candle substitution forbidden, continuous window segmentation without gap bridging).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for LOB-01. Real exchange LOB data ingestion requires production market maker feeds; synthetic/fixture validator satisfies research contract.
- Next unlocked consumers: L01-01, S04-01, S08-01.
