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


## Review fix cycle evidence (sprint review CHANGES_REQUESTED)
- Agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Base: branch `feat/feat-02-finalization` @ `0e2a0ab`; all changes are uncommitted working-tree edits, coordinator commits centrally.
- Owning suite before this fix cycle: `python -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` -> `102 passed` (exit 0).
- Owning suite after this fix cycle: the same command -> `175 passed` (exit 0).
- Capability gaps recorded: `ruff` is not installed in this environment, so the lint gate could not be executed; `pyarrow` is not installed, so `tests/unit/lab/models/lob/` plus the `test_deeplob_smoke.py` and `test_tlob_smoke.py` integration modules cannot be collected.
- TDD shape used: behavioural RED captured first, then the minimal source change, then GREEN. No assertion was weakened, deleted or skipped.
- Wave B RED (M01-01..M06-01 together): `python -m pytest tests/unit/lab/models/test_m01_logistic.py tests/unit/lab/models/test_m02_xgboost.py tests/unit/lab/models/test_m03_rf_regime.py tests/unit/lab/models/test_m04_quantile_risk.py tests/unit/lab/models/test_m05_meta_label.py tests/unit/lab/models/test_m06_anomaly_gate.py -p no:cacheprovider -q` -> `10 failed, 34 passed` (exit 1), every failure a real assertion failure or leaked exception.

### Findings fixed in this cycle

- **Important** - An absent feature column escaped the module's typed error contract. `X_train[feature_names]` raised a bare `KeyError: "['spread_bps'] not in index"` in both `train()` and `score()`, so a caller handling only the documented `MissingDataDistinctFromAnomalyError` would not catch incomplete data. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Important** - The unsupervised gate accepted a directional target column as an ordinary feature. Passing `forward_return` in `feature_names` trained the IsolationForest on it, which is exactly the directional claim AC2 forbids; the guard only covered the explicit `target_direction` argument. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Added `_assert_feature_columns_present()`, which converts a missing column into `MissingDataDistinctFromAnomalyError` with code `MISSING_FEATURE_COLUMNS` and lists both the missing and the present columns, and wired it into `train()` and `score()`. Added `_assert_no_directional_features()` plus a `FORBIDDEN_FEATURE_KEYWORDS` tuple matched as substrings, raising `DirectionalClaimForbiddenError` with the existing `DIRECTIONAL_CLAIM_FORBIDDEN` code, called from `train()`. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/m06_anomaly_gate.py`, `tests/unit/lab/models/test_m06_anomaly_gate.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py -p no:cacheprovider -q` -> `8 passed` (exit 0). A companion test pins that the documented liquidity feature set `volume_base, spread_bps, depth_idr, trade_count` still trains, so the new guard is not over-tight. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

## Independent review — coordinator DONE pass (2026-09-27)

- Verdict: DELTA-PASS. The IMPORTANT keyword-coverage finding is closed in src/indodax_lab/models/m06_anomaly_gate.py (FORBIDDEN_FEATURE_KEYWORDS += direction/bull/bear/signal; substring match unchanged).
- Fresh run `python -m pytest tests/unit/lab/models/test_m06_anomaly_gate.py -v`: 12 passed, 0 failed, including new test_m06_01_directional_feature_name_rejected[direction|bull|bear|signal] with demonstrated RED (DID NOT RAISE x4) → GREEN. Legitimate liquidity set still accepted (no over-tight guard); forward_return rejection intact.
- 2 MINOR observations carried as backlog (+inf scoring fail-open; zero-row raw ValueError). Handoff RED-provenance note acknowledged.
- First review: ses_f1f5b2f1affeFJGR826OWE17WS. Delta re-review: ses_f1f004277ffe7AUq1V79yzP12T. Fix implemented in main working tree (uncommitted).
- Reviewed at HEAD 28d89ba with uncommitted working-tree changes present; exact-SHA pinning pending at commit time.
