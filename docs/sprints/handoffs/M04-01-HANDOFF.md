# M04-01 handoff

Status: REVIEW

## Identity
- Sprint ID: M04-01 — Quantile risk regression
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/m04-01-quantile-risk-regression`
- Base SHA: `49826a3`
- Code target: `feat(m04-01): quantile risk regression`
- Evidence SHA relation: `f642f48`

## Files and contracts
- Actual files:
  - `src/indodax_lab/models/m04_quantile_risk.py` (M04Config, M04FittedBundle, M04QuantileTrainer, QuantileCoverageReport, QuantileCrossingError, TailTargetLeakageError)
  - `src/indodax_lab/models/__init__.py` (Package exports — M04-01 symbols added)
  - `tests/unit/lab/models/test_m04_quantile_risk.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `Registered return volatility or tail quantile target -> interval forecast.`
  - Interval forecast: `M04QuantileTrainer.train()` fits dual GradientBoostingRegressor models (for lower and upper quantiles). `predict_interval()` returns `(lower_bound, upper_bound)` (M04-01-AC0).
  - Explicit quantile crossing handling: `M04Config` validates `lower_quantile < upper_quantile`, raising `QuantileCrossingError` if crossed. Predictions enforce `lower <= upper` by taking min/max (M04-01-AC1).
  - Coverage reporting: `evaluate_coverage(X_val, y_val)` calculates empirical coverage rate and compares against nominal coverage interval in `QuantileCoverageReport` (M04-01-AC2).
  - Tail target leakage prevention: Training validates that no target, tail-target, or realized return columns are in `feature_names`, raising `TailTargetLeakageError` fail-closed (M04-01-AC3).
- Migration and compatibility:
  - Additive extension model; no existing interfaces modified.
  - Dependencies: ML-04 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| M04-01-AC0 (RED) | `test_m04_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.m04_quantile_risk') | `working tree` |
| M04-01-AC0 (GREEN) | `test_m04_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py::test_m04_01_valid_contract` | Exit 0 (Passed, dual quantile predictions return lower and upper bounds) | `f642f48` |
| M04-01-AC1 (RED) | `test_m04_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M04-01-AC1 (GREEN) | `test_m04_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py::test_m04_01_contract_1` | Exit 0 (Passed, lower >= upper raises QuantileCrossingError, predictions guarantee lower <= upper) | `f642f48` |
| M04-01-AC2 (RED) | `test_m04_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M04-01-AC2 (GREEN) | `test_m04_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py::test_m04_01_contract_2` | Exit 0 (Passed, QuantileCoverageReport records empirical vs nominal coverage) | `f642f48` |
| M04-01-AC3 (RED) | `test_m04_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M04-01-AC3 (GREEN) | `test_m04_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py::test_m04_01_contract_3` | Exit 0 (Passed, leaky feature names raise TailTargetLeakageError) | `f642f48` |

All 5 tests in `tests/unit/lab/models/test_m04_quantile_risk.py` passed (2.52s).
Full lab suite verification: 179 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of M04-01 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (explicit crossing handling, empirical coverage reporting, causal leakage prevention, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for M04-01.
- Next unlocked consumers: No mandatory downstream (EXTENSION tier).
