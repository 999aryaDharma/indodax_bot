# FEAT-04 handoff

Status: REVIEW

## Identity
- Sprint ID: FEAT-04 — Immutable feature materialization
- Implementation agent: Antigravity
- Independent reviewer: PENDING; exact current code SHA submitted after remediation below.
- Branch / worktree: `feat/feat-04-immutable-feature-materialization`
- Base SHA: `cefb580`
- Code target: `feat(feat-04): immutable feature materialization`
- Evidence SHA relation: `a4bce4d`

## Files and contracts
- Planned files:
  - `src/indodax_lab/features/builder.py` (build_feature_frame, deterministic sample_id, warmup & missingness guards)
  - `src/indodax_lab/cli/build_features.py` (CLI entrypoint, dry-run non-mutating validation, output serialization)
  - `src/indodax_lab/features/context.py` (calendar, listing, and benchmark helper functions)
  - `src/indodax_lab/features/__init__.py` (Public feature engineering exports)
  - `tests/integration/lab/test_feature_materialization.py` (Explicit AC0..AC3 test cases and canonical 41-feature test)
- Contract:
  - `snapshot IDs + registry hash -> features manifest, ordered columns, row_ready_at, eligibility`.
  - Content-addressed deterministic `sample_id` (`sha256:{hash}`).
  - Strict warmup masking: rows with available bars < lookback have null feature values, `reason_codes=("INSUFFICIENT_LOOKBACK",)`, and `eligible=False`.
  - Required feature missingness makes row ineligible (`eligible=False`, `missing_feature_count >= 1`).
  - Strict anti-leakage: labels (`net_return`, `binary_label`, `label_*`) and future columns (`future_*`, `exit_*`, `entry_*`) never enter feature schema or output.
  - Multi-root value equivalence: independent materialization runs produce bitwise/tolerance-equivalent feature values.
- Migration and compatibility:
  - Additive feature materialization subsystem; backward compatible.
  - Activates previously skipped tests in `tests/unit/lab/features/test_availability.py` (now 8 passed, 0 skipped).
  - Dependencies: FEAT-02 (DONE), FEAT-03 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| FEAT-04-AC0 (RED) | `test_feat_04_valid_contract` | `python -m pytest tests/integration/lab/test_feature_materialization.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| FEAT-04-AC0 (GREEN) | `test_feat_04_valid_contract` | `python -m pytest tests/integration/lab/test_feature_materialization.py::test_feat_04_valid_contract` | Exit 0 (Passed, builds feature matrix with sample identity, warmup mask, and lineage) | `a4bce4d` |
| FEAT-04-AC1 (RED) | `test_feat_04_contract_1` | `python -m pytest tests/integration/lab/test_feature_materialization.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| FEAT-04-AC1 (GREEN) | `test_feat_04_contract_1` | `python -m pytest tests/integration/lab/test_feature_materialization.py::test_feat_04_contract_1` | Exit 0 (Passed, required feature null makes row ineligible) | `a4bce4d` |
| FEAT-04-AC2 (RED) | `test_feat_04_contract_2` | `python -m pytest tests/integration/lab/test_feature_materialization.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| FEAT-04-AC2 (GREEN) | `test_feat_04_contract_2` | `python -m pytest tests/integration/lab/test_feature_materialization.py::test_feat_04_contract_2` | Exit 0 (Passed, labels and future columns strictly excluded from schema) | `a4bce4d` |
| FEAT-04-AC3 (RED) | `test_feat_04_contract_3` | `python -m pytest tests/integration/lab/test_feature_materialization.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| FEAT-04-AC3 (GREEN) | `test_feat_04_contract_3` | `python -m pytest tests/integration/lab/test_feature_materialization.py::test_feat_04_contract_3` | Exit 0 (Passed, two roots produce value-equivalent features within tolerance) | `a4bce4d` |

Historical original-target results above refer to implementation SHA `a4bce4d`; they are not current-SHA verification.

## Review
- Spec verdict: PASS (meets all functional requirements of FEAT-04, dataset §7.3, and specs/07-feature-engineering.md).
- Quality verdict: PASS (zero network, strictly immutable schemas, no forward-looking lookahead, float64 types, strict causality).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Review remediation (2026-09-23)

- Continuation owner: Codex; user-requested active worktree branch `feat/feat-02-finalization`, based on `b601db3`.
- Current exact code target: `dde250fe22319c37ba06d5eecbba1c113653df25` (`fix(feat-04): publish feature artifacts immutably`).
- Finding 1: CLI wrote directly to the requested output and manifest, allowing failed/repeated runs to overwrite prior artifacts. Output now stages to a same-directory partial, fsyncs, publishes with the repository's immutable no-clobber primitive, and rolls back a newly published output if manifest publication fails.
- Finding 2: feature manifest omitted the validated registry YAML source identity. It now records `feature_registry_source_id` alongside dataset snapshot ID, feature-set version, ordered feature names, and output checksum.
- RED 1: `python -m pytest tests/integration/lab/test_feature_materialization.py -q -p no:cacheprovider -k never_overwrites_existing_artifact` — failed because the old CLI overwrote the existing artifact and did not raise.
- GREEN: the same immutable-output test passed; `python -m pytest tests/integration/lab/test_feature_materialization.py tests/unit/lab/features/test_availability.py -q -p no:cacheprovider` — 33 passed.
- RED 2: `python -m pytest tests/unit/lab/features/test_availability.py -q -p no:cacheprovider -k persists_parquet_and_companion_manifest` — failed because `feature_registry_source_id` was absent.
- GREEN: full verification `python -m pytest -q -p no:cacheprovider` — 1008 passed, 2 environment-specific skips, 3 sklearn warnings (exit 0).
- Lint: import-order checks passed for changed CLI/integration files; focused safety/syntax/name checks passed with pre-existing `E712` ignored. Existing unrelated `I001` findings remain in builder and availability tests; broad legacy lint debt was not changed.
- Re-review status: PENDING; do not mark DONE until independent PASS on the exact code SHA above.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: Independent review pending for the current exact SHA.
- Next consumers after FEAT-04 completion: LABEL-01, TRAIN-01, LOB-01, STRAT-01 (subject to their other dependencies).
