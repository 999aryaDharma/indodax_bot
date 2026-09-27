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


## Review fix cycle evidence (sprint review CHANGES_REQUESTED)
- Agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Base: branch `feat/feat-02-finalization` @ `0e2a0ab`; all changes are uncommitted working-tree edits, coordinator commits centrally.
- Owning suite before this fix cycle: `python -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` -> `102 passed` (exit 0).
- Owning suite after this fix cycle: the same command -> `175 passed` (exit 0).
- Capability gaps recorded: `ruff` is not installed in this environment, so the lint gate could not be executed; `pyarrow` is not installed, so `tests/unit/lab/models/lob/` plus the `test_deeplob_smoke.py` and `test_tlob_smoke.py` integration modules cannot be collected.
- TDD shape used: behavioural RED captured first, then the minimal source change, then GREEN. No assertion was weakened, deleted or skipped.
- Wave B RED (M01-01..M06-01 together): `python -m pytest tests/unit/lab/models/test_m01_logistic.py tests/unit/lab/models/test_m02_xgboost.py tests/unit/lab/models/test_m03_rf_regime.py tests/unit/lab/models/test_m04_quantile_risk.py tests/unit/lab/models/test_m05_meta_label.py tests/unit/lab/models/test_m06_anomaly_gate.py -p no:cacheprovider -q` -> `10 failed, 34 passed` (exit 1), every failure a real assertion failure or leaked exception.

### Findings fixed in this cycle

- **Important** - The AC3 tail-target leakage guard used exact set membership on the lower-cased column name, so it only refused a column literally named `target`, `label` or `outcome`. Every derived name a feature builder would realistically emit - `fwd_target_vol`, `target_vol`, `label_win`, `next_return`, `forward_return`, `realized_vol`, `outcome_up`, `future_return_5m` - passed the guard and let the tail target back into the model's own inputs. This is the causal-leakage prevention AC3 exists to provide. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Turned `FORBIDDEN_FEATURE_KEYWORDS` into an ordered tuple and switched the guard to substring matching, reporting the specific keyword that matched. The keyword set was extended with `return`, `realized`, `forward` and `future` so the derived spellings are covered. Trailing-window features that merely resemble a target, such as `volatility_20` and `depth_imbalance`, are deliberately not matched, and a companion test pins that they still train. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/m04_quantile_risk.py`, `tests/unit/lab/models/test_m04_quantile_risk.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_m04_quantile_risk.py -p no:cacheprovider -q` -> `7 passed` (exit 0). - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

## Independent review correction — M04-01

- Correction owner: Codex `/root`; reviewer: `/root/docs_review`.
- Review finding base: code commit `9b6dab1239ae89eb8edbe22c4ec194f802173cd4`; reviewed tree `a14ba0053096db4a7a0cbd2e1440140c1937cc9f`.
- Requested paths: `src/indodax_lab/models/m04_quantile_risk.py`, `tests/unit/lab/models/test_m04_quantile_risk.py`.
- Independent Important findings: AC2 accepted mismatched, 2-D or non-finite labels and reported misleading coverage; fitted bundle hash included recipe/config and feature names but did not bind fitted state or training data.
- Planned correction: validate coverage labels before scoring; bind canonical training values and both fitted quantile tree states into explicit hashes and the bundle identity.
- Delta review is required at the exact correction commit. M04 remains REVIEW; ML-04 dependency remains REVIEW and is a separate qualification gate.
- Code/test commit: `0896db0c28338b711fb82d6cd118c56e9784c061`.
- RED: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/models/test_m04_quantile_risk.py::test_m04_01_ac2_rejects_invalid_coverage_labels tests/unit/lab/models/test_m04_quantile_risk.py::test_m04_01_bundle_identity_binds_fitted_state_and_training_data -q -p no:cacheprovider` — 4 failed for the reported defects (label mismatch broadcast, 2-D/NaN labels accepted, missing fitted/training hashes).
- GREEN: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/models/test_m04_quantile_risk.py -q -p no:cacheprovider` — 13 passed.
- Owning model suite: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` — 185 passed, 9 warnings.
- Lint: `C:/Users/User/miniconda3/envs/ML/Scripts/ruff.exe check --select I,F401 src/indodax_lab/models/m04_quantile_risk.py tests/unit/lab/models/test_m04_quantile_risk.py` — passed.
- Diff check on source/tests/handoff — passed.
- Delta review: PASS at exact code SHA `0896db0c28338b711fb82d6cd118c56e9784c061`; reviewer confirmed coverage shape/finiteness guards and the fitted-state/training-data identity fix, with no new Critical/Important findings. Reviewer independently ran the focused M04 suite: 13 passed. The broader model suite was owner-run only.
- M04-01 remains REVIEW because its ML-04 dependency remains REVIEW; this PASS closes only the frozen M04 correction findings.
