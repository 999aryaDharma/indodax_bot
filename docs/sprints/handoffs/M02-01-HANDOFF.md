# M02-01 handoff

Status: REVIEW

## Identity
- Sprint ID: M02-01 — XGBoost challenger
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/m02-01-xgboost-challenger`
- Base SHA: `b5ef7c3`
- Code target: `feat(m02-01): xgboost challenger`
- Evidence SHA relation: `8eeee18`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/m02_xgboost.py` (M02Config, M02FittedBundle, M02XGBoostTrainer, M02MultiSeedAudit)
  - `configs/models/M02_xgboost_v1.yaml` (Production recipe config)
  - `src/indodax_lab/models/__init__.py` (Package exports)
  - `tests/unit/lab/models/test_m02_xgboost.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `XGBoost config + data -> fitted XGBoost bundle with calibrated probabilities and sealed-partition guard.`
  - Reproducible gradient-boosted tree challenger: XGBClassifier fitted with deterministic seed, Platt-scaling calibrated on inner held-out validation data; produces semantic bundle hash stable across re-runs.
  - Sealed-partition guard: `val_partition_type` containing any element of `FORBIDDEN_EVAL_PARTITIONS = {"sealed_test", "test", "outer_test", "sealed", "holdout"}` is rejected fail-closed with `ForbiddenEvalPartitionError`.
  - Canonical feature ordering: `predict_proba()` reorders input DataFrame columns to match `bundle.feature_names` order; raises `FeatureSetMismatchError` on mismatch.
  - Multi-seed audit: `audit_multi_seed()` records median and worst utility across seeds; neither accesses sealed partitions.
- Migration and compatibility:
  - Additive challenger model; downstream consumer of ML-01 preprocessor, ML-02 calibrator, and ML-03 search space.
  - Dependencies: M01-01 (DONE), ML-02 (DONE), ML-03 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| M02-01-AC0 (RED) | `test_m02_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.m02_xgboost') | `working tree` |
| M02-01-AC0 (GREEN) | `test_m02_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_valid_contract` | Exit 0 (Passed, reproducible XGBoost bundle training, calibration, probability prediction) | `8eeee18` |
| M02-01-AC1 (RED) | `test_m02_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M02-01-AC1 (GREEN) | `test_m02_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_contract_1` | Exit 0 (Passed, sealed-partition val_partition_type rejected fail-closed) | `8eeee18` |
| M02-01-AC2 (RED) | `test_m02_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M02-01-AC2 (GREEN) | `test_m02_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_contract_2` | Exit 0 (Passed, canonical feature ordering enforced; FeatureSetMismatchError on mismatch) | `8eeee18` |
| M02-01-AC3 (RED) | `test_m02_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M02-01-AC3 (GREEN) | `test_m02_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m02_xgboost.py::test_m02_01_contract_3` | Exit 0 (Passed, multi-seed audit records median and worst utility across seeds) | `8eeee18` |

All 5 tests in `tests/unit/lab/models/test_m02_xgboost.py` passed (< 2s).
Full lab suite verification: 154 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of M02-01 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (gradient-boosted challenger with Platt calibration, sealed-partition guard, canonical feature ordering, multi-seed audit, fail-closed parameter validation).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for M02-01.
- Next unlocked consumers: ML-04.
