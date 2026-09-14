# M01-01 handoff

Status: REVIEW

## Identity
- Sprint ID: M01-01 — Calibrated logistic baseline
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/m01-01-calibrated-logistic-baseline`
- Base SHA: `2fa7ceb`
- Code target: `feat(m01-01): calibrated logistic baseline`
- Evidence SHA relation: `11aac98e1e4db72aae963c4e55c887b6f5a3fecd`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/m01_logistic.py` (M01Config, M01FittedBundle, ModelUtilityComparison, M01LogisticTrainer, InvalidSolverPenaltyError, ClassImbalanceError)
  - `configs/models/M01_logistic_v1.yaml` (Production recipe config)
  - `src/indodax_lab/models/__init__.py` (Package exports)
  - `src/indodax_lab/models/calibration.py` (FittedCalibratorArtifact.is_fitted convenience property)
  - `tests/unit/lab/models/test_m01_logistic.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `Logistic elastic-net solver-compatible config -> fitted preprocessor/model/calibrator bundle.`
  - Reproducible linear recipe: Regularized logistic model fitted with elastic-net/saga and Platt-scaling calibrated on inner held-out validation data; produces deterministic semantic bundle hash.
  - Solver/penalty compatibility: Rejects incompatible solver/penalty combinations (e.g. elastic-net with non-saga solver, l1 with lbfgs, elastic-net missing l1_ratio, non-positive C) fail-closed with `InvalidSolverPenaltyError`.
  - Class imbalance guard: Training data with extreme minority class deficiency (<10 positive samples or <5% minority class ratio) is blocked with `ClassImbalanceError`.
  - Utility benchmark: Forecasts evaluated on net utility accounting for transaction fees alongside cash baseline (0.0) and naive always-long baseline.
- Migration and compatibility:
  - Additive baseline model implementation; downstream consumer of ML-01 preprocessor, ML-02 calibrator, and ML-03 search space.
  - Dependencies: ML-03 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| M01-01-AC0 (RED) | `test_m01_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.m01_logistic') | `working tree` |
| M01-01-AC0 (GREEN) | `test_m01_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py::test_m01_01_valid_contract` | Exit 0 (Passed, reproducible bundle training, calibration, and probability prediction) | `11aac98` |
| M01-01-AC1 (RED) | `test_m01_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M01-01-AC1 (GREEN) | `test_m01_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py::test_m01_01_contract_1` | Exit 0 (Passed, incompatible solver/penalty combinations rejected fail-closed) | `11aac98` |
| M01-01-AC2 (RED) | `test_m01_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M01-01-AC2 (GREEN) | `test_m01_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py::test_m01_01_contract_2` | Exit 0 (Passed, extreme class imbalance <5% minority ratio blocks training) | `11aac98` |
| M01-01-AC3 (RED) | `test_m01_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M01-01-AC3 (GREEN) | `test_m01_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m01_logistic.py::test_m01_01_contract_3` | Exit 0 (Passed, model net utility compared against cash 0.0 and naive baseline) | `11aac98` |

All 5 tests in `tests/unit/lab/models/test_m01_logistic.py` passed (1.85s).
Full lab suite verification: 149 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of M01-01 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (elastic-net regularized baseline, held-out Platt calibration, explicit utility baselines, fail-closed parameter validation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for M01-01.
- Next unlocked consumers: M02-01, ML-04.
