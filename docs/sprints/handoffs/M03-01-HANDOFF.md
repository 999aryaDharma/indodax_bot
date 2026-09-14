# M03-01 handoff

Status: REVIEW

## Identity
- Sprint ID: M03-01 — Random forest regime gate
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/m03-01-random-forest-regime-gate`
- Base SHA: `4a9729e`
- Code target: `feat(m03-01): random forest regime gate`
- Evidence SHA relation: `c9403f4`

## Files and contracts
- Actual files:
  - `src/indodax_lab/models/m03_rf_regime.py` (M03Config, M03FittedBundle, M03RFRegimeTrainer, RegimeAbstainError, RegimeLabel, RegimeUtilityReport)
  - `src/indodax_lab/models/__init__.py` (Package exports — M03-01 symbols added)
  - `tests/unit/lab/models/test_m03_rf_regime.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `Train-only regime labels -> calibrated risk classification.`
  - Train-only: `M03RFRegimeTrainer.train()` fits RandomForestClassifier on train split only; no test data in training (M03-01-AC0, AC1).
  - Test does not retrain: `predict_regime_proba()` is pure inference; `bundle.bundle_hash` unchanged after inference (M03-01-AC1).
  - Abstain for unknown class: `predict_regime_for_unknown(unknown_class_label)` raises `RegimeAbstainError` if label not in training classes (M03-01-AC2).
  - Downside and net utility report: `evaluate_utility()` returns `RegimeUtilityReport` with `net_utility`, `downside_risk` (semi-deviation of negative returns), `n_entries`, `n_abstains` (M03-01-AC3).
- Migration and compatibility:
  - Additive extension model; no existing interfaces modified.
  - Dependencies: ML-04 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| M03-01-AC0 (RED) | `test_m03_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.m03_rf_regime') | `working tree` |
| M03-01-AC0 (GREEN) | `test_m03_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py::test_m03_01_valid_contract` | Exit 0 (Passed, 3-class proba sums to 1.0; feature_names and model_id captured) | `c9403f4` |
| M03-01-AC1 (RED) | `test_m03_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M03-01-AC1 (GREEN) | `test_m03_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py::test_m03_01_contract_1` | Exit 0 (Passed, bundle_hash unchanged after inference on test data) | `c9403f4` |
| M03-01-AC2 (RED) | `test_m03_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M03-01-AC2 (GREEN) | `test_m03_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py::test_m03_01_contract_2` | Exit 0 (Passed, unseen class label 99 raises RegimeAbstainError) | `c9403f4` |
| M03-01-AC3 (RED) | `test_m03_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M03-01-AC3 (GREEN) | `test_m03_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py::test_m03_01_contract_3` | Exit 0 (Passed, RegimeUtilityReport with net_utility and downside_risk fields) | `c9403f4` |

All 5 tests in `tests/unit/lab/models/test_m03_rf_regime.py` passed (2.10s).
Full lab suite verification: 174 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of M03-01 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (train-only fitting, inference-only predict, abstain for unknown class, downside+net utility report, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for M03-01.
- Next unlocked consumers: No mandatory downstream (EXTENSION tier).
