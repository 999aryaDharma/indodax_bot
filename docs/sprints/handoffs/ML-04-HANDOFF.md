# ML-04 handoff

Status: REVIEW

## Identity
- Sprint ID: ML-04 — Portable model bundles and replay
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ml-04-portable-model-bundles-and-replay`
- Base SHA: `c498dfe`
- Code target: `feat(ml-04): portable model bundles and replay`
- Evidence SHA relation: `d170c42`

## Files and contracts
- Actual files (spec listed `artifacts.py`, `trainer.py`, `cli/train_model.py`, `test_ml_walk_forward.py`; implemented minimal scope):
  - `src/indodax_lab/models/artifacts.py` (PortableBundle, PortableBundleLoader, BundleChecksumMismatchError, MissingCalibrationMetadataError, BundleFeatureMismatchError)
  - `src/indodax_lab/models/__init__.py` (Package exports — ML-04 symbols added)
  - `tests/unit/lab/models/test_ml04_bundle_loader.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `model + preprocessor + calibrator + thresholds + hashes + feature order -> verified bundle, replay forecast.`
  - Portable serialization: `PortableBundle.to_bytes()` produces UTF-8 JSON with all weights, calibration parameters, feature order, bundle hash and weights checksum. No pickle deserialization.
  - Checksum guard: `PortableBundleLoader.load_from_bytes()` recomputes SHA-256 of `{coefficients, intercept}` and rejects any mismatch with `BundleChecksumMismatchError` (ML-04-AC1).
  - Calibration guard: Missing or incomplete `calibration` block raises `MissingCalibrationMetadataError` before any inference attempt (ML-04-AC2).
  - Replay fidelity: Reloaded `PortableBundle.predict_proba()` reconstructs Platt sigmoid math from stored (a, b) parameters and enforces canonical feature ordering; predictions match original within rtol=1e-6 (ML-04-AC3).
- Deviation note: `trainer.py`, `cli/train_model.py`, and `test_ml_walk_forward.py` are listed as planned files in the spec but are integration-layer consumers (JOB-03, SHADOW-01, etc.) not required by the four ACs. Implemented the minimal scope that satisfies all ACs. Actual path recorded here.
- Migration and compatibility:
  - Additive capability; existing M01/M02 bundles compatible via `PortableBundle.from_m01()` factory.
  - Dependencies: M01-01 (REVIEW), M02-01 (REVIEW), EVAL-03 (REVIEW).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| ML-04-AC0 (RED) | `test_ml_04_valid_contract` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.artifacts') | `working tree` |
| ML-04-AC0 (GREEN) | `test_ml_04_valid_contract` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py::test_ml_04_valid_contract` | Exit 0 (Passed, complete bundle round-trip; reload predicts allclose within rtol=1e-6) | `d170c42` |
| ML-04-AC1 (RED) | `test_ml_04_contract_1` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-04-AC1 (GREEN) | `test_ml_04_contract_1` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py::test_ml_04_contract_1` | Exit 0 (Passed, corrupted weights_checksum raises BundleChecksumMismatchError fail-closed) | `d170c42` |
| ML-04-AC2 (RED) | `test_ml_04_contract_2` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-04-AC2 (GREEN) | `test_ml_04_contract_2` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py::test_ml_04_contract_2` | Exit 0 (Passed, absent calibration block raises MissingCalibrationMetadataError) | `d170c42` |
| ML-04-AC3 (RED) | `test_ml_04_contract_3` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-04-AC3 (GREEN) | `test_ml_04_contract_3` | `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py::test_ml_04_contract_3` | Exit 0 (Passed, reloaded bundle reorders shuffled feature columns; predictions allclose to canonical) | `d170c42` |

All 5 tests in `tests/unit/lab/models/test_ml04_bundle_loader.py` passed (1.91s).
Full lab suite verification: 159 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of ML-04 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (JSON-only serialization, no pickle, checksum guard, calibration guard, canonical feature ordering, replay-identical inference).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviation: `trainer.py`, `cli/train_model.py`, `test_ml_walk_forward.py` listed in spec planned files are integration-layer consumers (JOB-03, SHADOW-01) outside this sprint's acceptance criteria. Not implemented; scope limited to `artifacts.py` which satisfies all four ACs. Deviation recorded here per AGENTS.md.
- Unresolved issues / blockers: None for ML-04.
- Next unlocked consumers: JOB-03, SHADOW-01, QA-01, M03-01, M04-01, M05-01, M06-01.


## Review fix cycle evidence (sprint review CHANGES_REQUESTED)
- Agent: opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- Base: branch `feat/feat-02-finalization` @ `0e2a0ab`; all changes are uncommitted working-tree edits, coordinator commits centrally.
- Owning suite before this fix cycle: `python -m pytest tests/unit/lab/models/ --ignore=tests/unit/lab/models/lob/ -p no:cacheprovider -q` -> `102 passed` (exit 0).
- Owning suite after this fix cycle: the same command -> `175 passed` (exit 0).
- Capability gaps recorded: `ruff` is not installed in this environment, so the lint gate could not be executed; `pyarrow` is not installed, so `tests/unit/lab/models/lob/` plus the `test_deeplob_smoke.py` and `test_tlob_smoke.py` integration modules cannot be collected.
- TDD shape used: behavioural RED captured first, then the minimal source change, then GREEN. No assertion was weakened, deleted or skipped.
- Wave A RED (ML-01..ML-04 together): `python -m pytest tests/unit/lab/models/test_preprocessing.py tests/unit/lab/models/test_execution_mapper.py tests/unit/lab/models/test_tuning_budget.py tests/unit/lab/models/test_ml04_bundle_loader.py -p no:cacheprovider -q` -> `24 failed, 40 passed` (exit 1), every failure a real assertion failure or leaked exception.

### Findings fixed in this cycle

- **Important** - The bundle loader served predictions from a calibration artifact fitted on a forbidden segment. `calibration.segment_type` of `sealed_test`, `train`, `outer_validation` or `test` all loaded and scored successfully, so the held-out replay contract was not actually enforced at load time. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Important** - A non-numeric calibration `a`/`b` value was not rejected, so a corrupt calibration could be replayed. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Fix** - Added `PortableBundle._assert_inner_heldout_calibration()` and called it from both `_validate_replay_contract` and `load_from_bytes`, immediately after the required-fields check. It raises `CALIBRATION_SEGMENT_FORBIDDEN` for any segment other than the inner held-out one, and reuses the existing `FINITE_VALUE_REQUIRED:` code for non-finite or non-numeric `calibration.a` / `calibration.b` so the error surface stays consistent with the existing contract. - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **Files** - `src/indodax_lab/models/artifacts.py`, `tests/unit/lab/models/test_ml04_bundle_loader.py` - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
- **GREEN** - `python -m pytest tests/unit/lab/models/test_ml04_bundle_loader.py -p no:cacheprovider -q` -> `22 passed` (exit 0). - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)

- Independent review: still PENDING; the coordinator runs the delta verification pass on the committed SHA - opencode/muse-spark-1.3-contributor-free (Muse Spark 1.3 Free)
