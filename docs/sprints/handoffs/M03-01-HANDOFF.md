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


## Review fix cycle evidence (sprint review CHANGES_REQUESTED)
- Agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Base: branch `feat/feat-02-finalization` @ `0e2a0ab`; all changes are uncommitted working-tree edits, coordinator commits centrally.
- Owning suite before this fix cycle: `python -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` -> `102 passed` (exit 0).
- Owning suite after this fix cycle: the same command -> `175 passed` (exit 0).
- Capability gaps recorded: `ruff` is not installed in this environment, so the lint gate could not be executed; `pyarrow` is not installed, so `tests/unit/lab/models/lob/` plus the `test_deeplob_smoke.py` and `test_tlob_smoke.py` integration modules cannot be collected.
- TDD shape used: behavioural RED captured first, then the minimal source change, then GREEN. No assertion was weakened, deleted or skipped.
- Wave B RED (M01-01..M06-01 together): `python -m pytest tests/unit/lab/models/test_m01_logistic.py tests/unit/lab/models/test_m02_xgboost.py tests/unit/lab/models/test_m03_rf_regime.py tests/unit/lab/models/test_m04_quantile_risk.py tests/unit/lab/models/test_m05_meta_label.py tests/unit/lab/models/test_m06_anomaly_gate.py -p no:cacheprovider -q` -> `10 failed, 34 passed` (exit 1), every failure a real assertion failure or leaked exception.

### Findings fixed in this cycle

- **Important** - `downside_risk` was computed as `np.std` over the negative-return subset, which collapses to exactly `0.0` whenever the losing entries are identical in size or when there is only one of them. Probing confirmed `downside_risk == 0.0` both for a steady -0.001 loss on every one of 40 entries and for a single -0.029 crash among winners. A strategy that loses on 100% of its trades was therefore reported as having no downside risk at all, which defeats the purpose of the AC3 risk report. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Replaced the expression with a new module-level `downside_semideviation()` implementing the second-order lower partial moment, `sqrt(mean(min(r, 0) ** 2))` over all entries. Gains contribute zero, so the measure stays a pure downside metric, and it is `0.0` only when nothing lost. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/m03_rf_regime.py`, `tests/unit/lab/models/test_m03_rf_regime.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_m03_rf_regime.py -p no:cacheprovider -q` -> `8 passed` (exit 0). Three tests pin the steady-bleed case (> 0), the single-crash case (> 0) and the all-winning book (exactly 0.0), so the fix cannot invent risk either. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
