# M05-01 handoff

Status: REVIEW

## Identity
- Sprint ID: M05-01 — Meta-label signal filter
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/m05-01-meta-label-signal-filter`
- Base SHA: `8bc2d35`
- Code target: `feat(m05-01): meta-label signal filter`
- Evidence SHA relation: `96a7bb4`

## Files and contracts
- Actual files:
  - `src/indodax_lab/models/m05_meta_label.py` (M05Config, M05FittedBundle, M05MetaLabelTrainer, ManualLabelForbiddenError, MetaFilterComparisonReport, MetaTradeSample, purge_overlapping_trades)
  - `src/indodax_lab/models/__init__.py` (Package exports — M05-01 symbols added)
  - `tests/unit/lab/models/test_m05_meta_label.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `Automatic base-strategy decisions and outcomes -> TAKE/SKIP probability.`
  - Meta-model TAKE probability: `M05MetaLabelTrainer.train()` fits binary classifier on base-strategy outcomes. `predict_take_proba()` outputs TAKE probability in [0, 1] (M05-01-AC0).
  - Manual click prohibition: Training raises `ManualLabelForbiddenError` fail-closed if any input sample is marked `is_manual=True` (M05-01-AC1).
  - Temporal overlap purging: `purge_overlapping_trades(ref, target)` purges test samples whose holding periods overlap with any reference trade to prevent lookahead/embargo leakage (M05-01-AC2).
  - Base vs filtered comparison: `compare_base_vs_filtered()` evaluates base strategy vs meta-filtered strategy on identical candidates, returning `MetaFilterComparisonReport` (M05-01-AC3).
- Migration and compatibility:
  - Additive extension model; no existing interfaces modified.
  - Dependencies: ML-04 (REVIEW), C01-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| M05-01-AC0 (RED) | `test_m05_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.m05_meta_label') | `working tree` |
| M05-01-AC0 (GREEN) | `test_m05_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py::test_m05_01_valid_contract` | Exit 0 (Passed, meta-model predicts valid TAKE probabilities in [0, 1]) | `96a7bb4` |
| M05-01-AC1 (RED) | `test_m05_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M05-01-AC1 (GREEN) | `test_m05_01_contract_1` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py::test_m05_01_contract_1` | Exit 0 (Passed, manual click input raises ManualLabelForbiddenError) | `96a7bb4` |
| M05-01-AC2 (RED) | `test_m05_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M05-01-AC2 (GREEN) | `test_m05_01_contract_2` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py::test_m05_01_contract_2` | Exit 0 (Passed, temporal holding-period overlaps between splits are purged) | `96a7bb4` |
| M05-01-AC3 (RED) | `test_m05_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| M05-01-AC3 (GREEN) | `test_m05_01_contract_3` | `python -m pytest tests/unit/lab/models/test_m05_meta_label.py::test_m05_01_contract_3` | Exit 0 (Passed, MetaFilterComparisonReport compares base vs filtered on same candidates) | `96a7bb4` |

All 4 tests in `tests/unit/lab/models/test_m05_meta_label.py` passed (2.03s).
Full lab suite verification: 183 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, and paper.

## Review
- Spec verdict: PASS (meets all functional requirements of M05-01 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (manual click prohibition, overlap purging, base vs filtered comparison, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for M05-01.
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

- **Important** - The meta-label trainer took its feature schema from `trades[0]` alone and then built rows with `trade.features.get(f, 0.0)`. A trade missing a key was silently padded with a fabricated `0.0`, and a trade carrying an unexpected key had that key dropped without any trace. A fabricated `0.0` is a real feature value to the random forest, so the model was trained on data that never existed, and the bundle hash and the published `feature_names` did not describe the rows actually used. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Added `InconsistentFeatureSchemaError` and a schema check in `train()` that compares every trade's feature key set against the canonical schema derived from `trades[0]`, raising with the exact `missing` and `unexpected` key lists. Row construction now indexes `trade.features[f]` directly, so no value can be fabricated or dropped. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/m05_meta_label.py`, `tests/unit/lab/models/test_m05_meta_label.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_m05_meta_label.py -p no:cacheprovider -q` -> `6 passed` (exit 0). A companion test pins the homogeneous case still trains and still publishes all three sorted feature names. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
