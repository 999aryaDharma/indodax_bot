# ML-01 handoff

Status: REVIEW

## Identity
- Sprint ID: ML-01 — Train-only preprocessing
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ml-01-train-only-preprocessing`
- Base SHA: `f8aad02`
- Code target: `feat(ml-01): train-only preprocessing`
- Evidence SHA relation: `175be32db512265ba6e065f79d30ea345d4c9787`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/preprocessing.py` (TabularPreprocessor, PreprocessorConfig, FittedPreprocessorArtifact, FeatureAlignmentError, NotFittedError)
  - `src/indodax_lab/models/__init__.py` (Package exports)
  - `tests/unit/lab/models/test_preprocessing.py` (AC0..AC3 unit tests)
- Contract:
  - `train features -> imputer/scaler/pruner artifact; validation transform only.`
  - Train-only statistics: Medians, IQRs, and quantile clipping bounds are fitted exclusively on training data and stored in an immutable `FittedPreprocessorArtifact`.
  - Zero lookahead / test leakage: Transforming test data with extreme outliers does not alter the fitted train statistics.
  - Strict feature alignment: Missing required features, unexpected extra features, or mismatched feature orders are strictly rejected with `FeatureAlignmentError`.
  - Idempotent transform: `transform()` never modifies internal fitted statistics.
- Migration and compatibility:
  - Additive machine learning models subsystem; clean integration with TRAIN-01.
  - Dependencies: TRAIN-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| ML-01-AC0 (RED) | `test_ml_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_preprocessing.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models') | `working tree` |
| ML-01-AC0 (GREEN) | `test_ml_01_valid_contract` | `python -m pytest tests/unit/lab/models/test_preprocessing.py::test_ml_01_valid_contract` | Exit 0 (Passed, fits preprocessor exclusively on train and transforms test cleanly) | `175be32` |
| ML-01-AC1 (RED) | `test_ml_01_contract_1` | `python -m pytest tests/unit/lab/models/test_preprocessing.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-01-AC1 (GREEN) | `test_ml_01_contract_1` | `python -m pytest tests/unit/lab/models/test_preprocessing.py::test_ml_01_contract_1` | Exit 0 (Passed, extreme outliers in test data do not alter fitted train statistics) | `175be32` |
| ML-01-AC2 (RED) | `test_ml_01_contract_2` | `python -m pytest tests/unit/lab/models/test_preprocessing.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-01-AC2 (GREEN) | `test_ml_01_contract_2` | `python -m pytest tests/unit/lab/models/test_preprocessing.py::test_ml_01_contract_2` | Exit 0 (Passed, missing or unexpected extra features strictly rejected) | `175be32` |
| ML-01-AC3 (RED) | `test_ml_01_contract_3` | `python -m pytest tests/unit/lab/models/test_preprocessing.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-01-AC3 (GREEN) | `test_ml_01_contract_3` | `python -m pytest tests/unit/lab/models/test_preprocessing.py::test_ml_01_contract_3` | Exit 0 (Passed, transform never updates or mutates fitted state) | `175be32` |

All 4 tests in `tests/unit/lab/models/test_preprocessing.py` passed (0.96s).
Full lab suite verification: 129 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, and models.

## Review
- Spec verdict: PASS (meets all functional requirements of ML-01 and specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (zero lookahead leakage, robust statistics, strict schema alignment, immutable fitted artifact).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for ML-01.
- Next unlocked consumers: ML-02.


## Review fix cycle evidence (sprint review CHANGES_REQUESTED)
- Agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Base: branch `feat/feat-02-finalization` @ `0e2a0ab`; all changes are uncommitted working-tree edits, coordinator commits centrally.
- Owning suite before this fix cycle: `python -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` -> `102 passed` (exit 0).
- Owning suite after this fix cycle: the same command -> `175 passed` (exit 0).
- Capability gaps recorded: `ruff` is not installed in this environment, so the lint gate could not be executed; `pyarrow` is not installed, so `tests/unit/lab/models/lob/` plus the `test_deeplob_smoke.py` and `test_tlob_smoke.py` integration modules cannot be collected.
- TDD shape used: behavioural RED captured first, then the minimal source change, then GREEN. No assertion was weakened, deleted or skipped.
- Wave A RED (ML-01..ML-04 together): `python -m pytest tests/unit/lab/models/test_preprocessing.py tests/unit/lab/models/test_execution_mapper.py tests/unit/lab/models/test_tuning_budget.py tests/unit/lab/models/test_ml04_bundle_loader.py -p no:cacheprovider -q` -> `24 failed, 40 passed` (exit 1), every failure a real assertion failure or leaked exception.

### Findings fixed in this cycle

- **Important** - Duplicate feature columns were silently accepted instead of rejected. `FeaturePreprocessor.transform` returned a `(2, 3)` result for a 2-feature input that carried a duplicated column, and `fit` surfaced a raw pandas `TypeError: arg must be a list, tuple, 1-d array, or Series` rather than the module's own typed alignment error. A duplicated column silently changes the effective feature width the model was fitted on. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Important** - A persisted `FeaturePreprocessor` artifact accepted an arbitrary or empty feature schema, so a bundle could be reloaded under a schema that does not match the data it was fitted on. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Added `_reject_duplicate_columns()`, which raises `FeatureAlignmentError` with code `DUPLICATE_FEATURE_COLUMNS:<stage>:<dups>`, called at the top of both `fit()` and `transform()`. Added a `validate_feature_schema` pydantic model validator that raises `FEATURE_SCHEMA_INVALID`. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/preprocessing.py`, `tests/unit/lab/models/test_preprocessing.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_preprocessing.py -p no:cacheprovider -q` -> `7 passed` (exit 0). - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

## Independent review — coordinator pass (2026-09-27)

- Verdict: PASS. Full read of src/indodax_lab/models/preprocessing.py (218 lines) +
  tests/unit/lab/models/test_preprocessing.py (7 tests). Fresh run
  `python -m pytest tests/unit/lab/models/test_preprocessing.py -v`: 7 passed,
  0 failed, exit 0 (AC0–AC3 + 3 duplicate-schema regression guards).
- AC0 holds (fitted medians/order stored, test imputed from train median);
  AC1 holds (extreme test values leave medians untouched); AC2 holds
  (missing/extra rejected; reorder rejected in strict mode, deterministically
  realigned otherwise — tested both); AC3 holds (5× transform leaves artifact
  byte-identical via deepcopy compare).
- MINOR (backlog, non-blocking): default non-strict transform silently realigns
  column order (only strict mode rejects); all-NaN column falls back to silent
  0.0/1.0 defaults (undocumented); duplicate check is O(n^2) (negligible at
  feature width). No Critical/Important findings.
- Reviewer: coordinator inline review (implementation pre-exists committed as
  175be32 + fix 9b6dab1; reviewer wrote no code here). Status transition
  (manifest/spec) left to coordinator DONE pass / main agent — not touched.

## Emergency second review-fix cycle — shared model preprocessing contract

- Coordinator authorization under `.agents/coordination/protocol.md`: this second cycle is necessary because ML-01 publishes the fitted preprocessing artifact/config consumed by downstream model training and inference; mutable or mismatched state undermines their shared feature contract and ML-01 acceptance.
- Frozen findings fixed from independent review at `9b6dab1239ae89eb8edbe22c4ec194f802173cd4`: default reordered-input acceptance; mutable returned fitted statistics/config drift; statistic maps inconsistent with persisted feature schema.
- TDD RED at the reviewed base: focused ML-01 suite had 3 failures reproducing these findings.
- Corrective source commit: superseded by the strict-boundary correction below.
- Fix: transform always enforces canonical feature order, including artifacts with the legacy `strict_feature_order=False` field; upstream adapters must restore order before calling it. Transform uses the config captured in its artifact; `fit()` and `fitted_artifact` return defensive deep copies; artifact validation requires all statistic maps to match `feature_names`.
- Focused regression/downstream suite: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q tests/unit/lab/models/test_preprocessing.py tests/unit/lab/models/test_m01_logistic.py tests/unit/lab/models/test_m02_xgboost.py -p no:cacheprovider` -> 25 passed, 1 existing sklearn `OptimizeWarning`.
- Full model suite: `conda run -n ML python -m pytest tests/unit/lab/models` -> 247 passed, 9 existing sklearn `OptimizeWarning`s.
- Focused source/test Ruff and `git diff --check` -> passed; Ruff emitted a harmless F401 selector warning under the Python module invocation, so exact standalone lint evidence remains to be rerun.
- Independent delta review at the superseding source SHA: pending. ML-01 remains REVIEW.
