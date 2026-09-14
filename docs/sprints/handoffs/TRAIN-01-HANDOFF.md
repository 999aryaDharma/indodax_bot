# TRAIN-01 handoff

Status: REVIEW

## Identity
- Sprint ID: TRAIN-01 — Verified training dataset assembly
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/train-01-verified-training-dataset-assembly`
- Base SHA: `3c18507`
- Code target: `feat(train-01): verified training dataset assembly`
- Evidence SHA relation: `9b91569b526773cf78019e728cfbdef3b5b1c39f`

## Files and contracts
- Planned files:
  - `src/indodax_lab/labels/materializer.py` (materialize_training_dataset, TrainingDatasetManifest, TrainingDatasetArtifact, error types)
  - `src/indodax_lab/cli/build_training_dataset.py` (CLI entrypoint, dry-run, output serialization)
  - `src/indodax_lab/labels/__init__.py` (Package exports)
  - `tests/integration/lab/test_training_materialization.py` (AC0..AC3 integration tests)
- Contract:
  - `dataset/feature/label/split/universe/cost IDs -> training manifest and role-restricted tables.`
  - Content-addressed dataset ID: derived from snapshot, feature registry, split policy, target, and row count.
  - Duplicate sample join rejection: Duplicate `sample_id` values in features, labels, or splits raise `DuplicateSampleError`.
  - Target leakage guard: Target column, return/label outcomes (`net_return`, `binary_label`, `label_*`, `future_*`, `exit_*`) are strictly forbidden from entering inference features (`TargetLeakageError`).
  - Cryptographic checksum & temporal causality guards: Artifact checksum mismatch raises `ArtifactIntegrityError`; lookahead violations (`row_ready_at > decision_ts` or `label_end_ts < decision_ts`) raise `AvailabilityMismatchError`.
- Migration and compatibility:
  - Additive training dataset assembly subsystem; clean integration with SPLIT-01 and FEAT-04.
  - Dependencies: SPLIT-01 (DONE), FEAT-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| TRAIN-01-AC0 (RED) | `test_train_01_valid_contract` | `python -m pytest tests/integration/lab/test_training_materialization.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.labels.materializer') | `working tree` |
| TRAIN-01-AC0 (GREEN) | `test_train_01_valid_contract` | `python -m pytest tests/integration/lab/test_training_materialization.py::test_train_01_valid_contract` | Exit 0 (Passed, materializes role-restricted tables with verified IDs and manifest) | `9b91569` |
| TRAIN-01-AC1 (RED) | `test_train_01_contract_1` | `python -m pytest tests/integration/lab/test_training_materialization.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| TRAIN-01-AC1 (GREEN) | `test_train_01_contract_1` | `python -m pytest tests/integration/lab/test_training_materialization.py::test_train_01_contract_1` | Exit 0 (Passed, duplicate sample IDs strictly rejected) | `9b91569` |
| TRAIN-01-AC2 (RED) | `test_train_01_contract_2` | `python -m pytest tests/integration/lab/test_training_materialization.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| TRAIN-01-AC2 (GREEN) | `test_train_01_contract_2` | `python -m pytest tests/integration/lab/test_training_materialization.py::test_train_01_contract_2` | Exit 0 (Passed, target column in inference feature list strictly rejected) | `9b91569` |
| TRAIN-01-AC3 (RED) | `test_train_01_contract_3` | `python -m pytest tests/integration/lab/test_training_materialization.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| TRAIN-01-AC3 (GREEN) | `test_train_01_contract_3` | `python -m pytest tests/integration/lab/test_training_materialization.py::test_train_01_contract_3` | Exit 0 (Passed, checksum and availability mismatches block output) | `9b91569` |

All 4 integration tests in `tests/integration/lab/test_training_materialization.py` passed (1.01s).
Full lab suite verification: 117 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, and training materialization.

## Review
- Spec verdict: PASS (meets all functional requirements of TRAIN-01, specs/09-labels-splits-and-training-data.md, and dataset contracts).
- Quality verdict: PASS (zero lookahead leakage, strict role segregation, fail-closed causality and checksum assertions).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for TRAIN-01.
- Next unlocked consumers: ML-01.
