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


## Review fix cycle evidence (sprint review CHANGES_REQUESTED)
- Agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Base: branch `feat/feat-02-finalization` @ `0e2a0ab`; all changes are uncommitted working-tree edits, coordinator commits centrally.
- Owning suite before this fix cycle: `python -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` -> `102 passed` (exit 0).
- Owning suite after this fix cycle: the same command -> `175 passed` (exit 0).
- Capability gaps recorded: `ruff` is not installed in this environment, so the lint gate could not be executed; `pyarrow` is not installed, so `tests/unit/lab/models/lob/` plus the `test_deeplob_smoke.py` and `test_tlob_smoke.py` integration modules cannot be collected.
- TDD shape used: behavioural RED captured first, then the minimal source change, then GREEN. No assertion was weakened, deleted or skipped.
- Wave B RED (M01-01..M06-01 together): `python -m pytest tests/unit/lab/models/test_m01_logistic.py tests/unit/lab/models/test_m02_xgboost.py tests/unit/lab/models/test_m03_rf_regime.py tests/unit/lab/models/test_m04_quantile_risk.py tests/unit/lab/models/test_m05_meta_label.py tests/unit/lab/models/test_m06_anomaly_gate.py -p no:cacheprovider -q` -> `10 failed, 34 passed` (exit 1), every failure a real assertion failure or leaked exception.

### Findings fixed in this cycle

- **Important** - `M01Config` did not fail closed on an unsupported penalty. Only the three penalties it happened to know about were checked combinatorially, so `penalty="bogus"`, `penalty="none"` and `penalty="elastic-net"` all produced a constructible config and deferred the failure to sklearn's fit. That contradicts AC1, which requires invalid solver and penalty configurations to be rejected fail-closed. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Added the module-level `SUPPORTED_PENALTIES = frozenset({"l1", "l2", "elasticnet"})` allowlist and an up-front check in `M01Config.__init__` that raises `InvalidSolverPenaltyError` with the existing `INVALID_SOLVER_PENALTY` code, before the existing per-pair solver checks run. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/m01_logistic.py`, `tests/unit/lab/models/test_m01_logistic.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_m01_logistic.py -p no:cacheprovider -q` -> `7 passed` (exit 0). A companion assertion pins that the legitimate `penalty="l2", solver="lbfgs"` configuration still trains, so the allowlist is not over-tight. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Note** - `configs/models/M01_logistic_v1.yaml` uses the documented `elasticnet`/`saga` pair and is unaffected. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
