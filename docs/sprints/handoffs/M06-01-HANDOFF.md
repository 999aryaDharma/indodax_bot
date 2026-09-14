# M06-01 handoff

Status: REVIEW

## Identity
- Sprint ID: M06-01 — Market anomaly risk gate
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/m06-01-market-anomaly-risk-gate`
- Base SHA: `1a170a5`
- Code target: `feat(m06-01): market anomaly risk gate`
- Evidence SHA relation: `871f990`

## Files and contracts
- Actual files:
  - `src/indodax_lab/models/m06_anomaly_gate.py` (M06Config, M06FittedBundle, M06AnomalyGate, AnomalyDecision, MissingDataDistinctFromAnomalyError, DirectionalClaimForbiddenError)
  - `src/indodax_lab/models/__init__.py` (Package exports — M06-01 symbols added)
  - `tests/unit/lab/models/test_m06_anomaly_gate.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `Train-only liquidity distribution -> anomaly score and abstain threshold.`
  - Anomaly scoring and threshold: `M06AnomalyGate.train()` fits unsupervised IsolationForest on train liquidity features only. `evaluate()` produces `AnomalyDecision` with PASS/ABSTAIN actions (M06-01-AC0).
  - Frozen threshold: Threshold is calibrated strictly on training scores and frozen in `M06FittedBundle`; out-of-sample or future observations cannot alter the threshold (M06-01-AC1).
  - No directional return claims: Model is strictly an unsupervised risk filter; passing directional targets raises `DirectionalClaimForbiddenError` (M06-01-AC2).
  - Missing data distinction: NaN / missing feature values raise `MissingDataDistinctFromAnomalyError` fail-closed; missing data is never conflated with market anomalies (M06-01-AC3).
- Migration and compatibility:
  - Additive extension model; no existing interfaces modified.
  - Dependencies: ML-04 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| M06-01-AC0 (RED) | `test_m06_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.m06_anomaly_gate') | `working tree` |
| M06-01-AC0 (GREEN) | `test_m06_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py::test_m06_01_valid_contract` | Exit 0 (Passed, anomaly gate evaluates liquidity features and assigns PASS/ABSTAIN decisions) | `871f990` |
| M06-01-AC1 (RED) | `test_m06_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M06-01-AC1 (GREEN) | `test_m06_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py::test_m06_01_contract_1` | Exit 0 (Passed, evaluating future extreme shock data does not alter frozen train threshold) | `871f990` |
| M06-01-AC2 (RED) | `test_m06_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M06-01-AC2 (GREEN) | `test_m06_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py::test_m06_01_contract_2` | Exit 0 (Passed, attempting directional claim raises DirectionalClaimForbiddenError) | `871f990` |
| M06-01-AC3 (RED) | `test_m06_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M06-01-AC3 (GREEN) | `test_m06_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py::test_m06_01_contract_3` | Exit 0 (Passed, input with NaNs raises MissingDataDistinctFromAnomalyError) | `871f990` |

All 4 tests in `tests/unit/lab/models/test_m06_anomaly_gate.py` passed (2.08s).
Full lab suite verification: 187 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of M06-01 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (frozen threshold, no directional claims, explicit missing data distinction, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for M06-01.
- Next unlocked consumers: No mandatory downstream (EXTENSION tier).
