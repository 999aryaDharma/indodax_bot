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
