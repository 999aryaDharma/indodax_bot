# ML-02 handoff

Status: REVIEW

## Identity
- Sprint ID: ML-02 — Held-out calibration and cost mapper
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ml-02-held-out-calibration-and-cost-mapper`
- Base SHA: `b6db9c3`
- Code target: `feat(ml-02): held-out calibration and cost mapper`
- Evidence SHA relation: `40cf3a76f13958123f36ca7fb82560bb96f90c79`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/calibration.py` (CalibrationSegmentError, InsufficientCalibrationDataError, FittedCalibratorArtifact, HeldOutCalibrator)
  - `src/indodax_lab/models/execution_mapper.py` (ForecastKind, DecisionAction, PayoffStructure, CostBasis, ForecastPayload, ExecutionDecision, CostAwareExecutionMapper)
  - `src/indodax_lab/models/__init__.py` (Package exports)
  - `tests/unit/lab/models/test_execution_mapper.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `forecast(kind=NET_RETURN/GROSS_RETURN/PROBABILITY) + payoff/cost basis -> abstain or intent; net costs applied once.`
  - Calibrated forecast converts to order intent ONLY when net edge strictly exceeds safety margin.
  - Held-out calibration isolation: Calibrator requires an inner held-out segment (e.g. `inner_heldout`, `validation`); training and test/sealed segments are strictly forbidden and rejected with `CalibrationSegmentError`.
  - Fail-closed small calibration data: Datasets with fewer than minimum calibration samples (default 50) or insufficient class representations (default 10 positives/negatives) block with `InsufficientCalibrationDataError`.
  - Equivalent gross and net forecasts: Gross returns with subtracted round-trip transaction costs yield identical execution decisions, net edge, and order parameters as equivalent net return forecasts.
  - Exact cost application per ADR-002: NET_RETURN compares directly to safety margin, GROSS_RETURN subtracts round-trip cost once, and PROBABILITY computes expected gross return before subtracting round-trip cost once.
- Migration and compatibility:
  - Additive models subsystem components; integrates with SIM-01 SignalIntent and ML-01 preprocessing.
  - Dependencies: ML-01 (DONE), SIM-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| ML-02-AC0 (RED) | `test_ml_02_valid_contract` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.calibration') | `working tree` |
| ML-02-AC0 (GREEN) | `test_ml_02_valid_contract` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_valid_contract` | Exit 0 (Passed, forecast only becomes SignalIntent when net edge exceeds safety margin; abstains otherwise) | `40cf3a7` |
| ML-02-AC1 (RED) | `test_ml_02_contract_1` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-02-AC1 (GREEN) | `test_ml_02_contract_1` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_contract_1` | Exit 0 (Passed, training/test segments rejected, inner held-out segment accepted and calibrated) | `40cf3a7` |
| ML-02-AC2 (RED) | `test_ml_02_contract_2` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-02-AC2 (GREEN) | `test_ml_02_contract_2` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_contract_2` | Exit 0 (Passed, small dataset <50 samples and skewed dataset <10 positives fail closed) | `40cf3a7` |
| ML-02-AC3 (RED) | `test_ml_02_contract_3` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-02-AC3 (GREEN) | `test_ml_02_contract_3` | `python -m pytest tests/unit/lab/models/test_execution_mapper.py::test_ml_02_contract_3` | Exit 0 (Passed, gross and net equivalent forecasts yield identical decisions and net edge) | `40cf3a7` |

All 5 tests in `tests/unit/lab/models/test_execution_mapper.py` passed (1.33s).
Full lab suite verification: 139 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of ML-02 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (Platt scaling on inner held-out data, ADR-002 exact cost application, strict timezone/payoff validation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for ML-02.
- Next unlocked consumers: ML-03.
