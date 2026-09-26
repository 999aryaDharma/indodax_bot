# D03-01 handoff

Status: REVIEW (fix cycle: blocking set resolved, pending delta verification)

## Identity
- Sprint ID: D03-01 — ResNet LSTM challenger
- Implementation agent (fix): opencode/muse-spark-1.3-contributor-free
- Independent reviewer: UNASSIGNED (delta verification required before DONE)
- Branch / worktree: `fix/d03-01-folds-budget` in `.worktrees/fix/D03-01`
- Base SHA: `02fb7c3`
- Code target: `fix(d03-01): bind common folds and log compute budget`
- Evidence SHA relation: `6825734b35653b5f911ff87d5bb37e5271a876c4` code commit + this evidence commit at branch HEAD

## Files and contracts
- Fixed files (this cycle only; all other D03-01 artifacts unchanged):
  - `src/indodax_lab/models/dl/d03_resnet_lstm.py` (`ResNetLSTMComputeBudgetSummary`, `ResNetLSTMFoldEvaluation`, `ResNetLSTMTrainer.evaluate_on_common_folds`, `get_compute_budget_summary`, `compute_budget` in fitted bundle)
  - `src/indodax_lab/models/dl/__init__.py` (additive exports only)
  - `tests/unit/lab/models/test_d03_01.py` (2 AC3 regression tests; existing AC0..AC3 tests untouched)
- Contract (unchanged):
  - `Residual temporal blocks + recurrent head -> registered triple-barrier target`
  - Causality (AC1) and mask invariance (AC2) preserved, no behavior change.
  - Common evaluation cost dan folds (AC3): utility is now computed on the VALIDATION slice of a shared SPLIT-01 `assign_folds` manifest under the common `CostAwareExecutionMapper` cost basis; PURGED/EMBARGOED rows never enter the utility (fail-closed on empty clean slice).
  - Compute budget: every fitted bundle logs `compute_budget` (trainable parameters, estimated FLOPs/sequence, conv channels, kernel, LSTM dims, seq_len), mirroring the D02-01/D04-01 pattern.
- Migration and compatibility:
  - Additive only: `splits.py`, `execution_mapper.py`, `checkpoint.py`, D02/D04/DL modules untouched.
  - Bundle hash now binds the compute budget; old bundle hashes are superseded (research artifacts are versioned, no production migration).

## Accepted blocking set (from independent review) and resolution
| # | Blocking finding | Resolution |
|---|---|---|
| 1 | Folds: AC3 claimed "common folds" but no code path consumed SPLIT-01 folds; any ad-hoc split could pass. | New `evaluate_on_common_folds` consumes `assign_folds` output positionally aligned to input rows; regression test proves a boundary-crossing sample is PURGED and excluded from the cost-aware utility while the common cost basis still applies. |
| 2 | Budget logging: bundle carried only `total_parameters`; no FLOPs/architecture budget was recorded despite the claim. | New `ResNetLSTMComputeBudgetSummary` (params, FLOPs/sequence, blocks, channels, kernel, LSTM hidden/layers, seq_len) is computed by the model and stored in every fitted bundle; regression test pins field consistency against the config. |

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| D03-01-AC3 (RED) | `test_d03_01_contract_3_common_folds_used` + `test_d03_01_contract_3_compute_budget_logged` | `python -m pytest tests/unit/lab/models/test_d03_01.py -k "common_folds_used or compute_budget_logged"` | Exit 1 (AttributeError: no `evaluate_on_common_folds` / `compute_budget` — behavior gap, not missing env) | `working tree` (pre-fix) |
| D03-01-AC3 (GREEN) | both regression tests above | `python -m pytest tests/unit/lab/models/test_d03_01.py` | Exit 0 (6 passed: 4 original AC0..AC3 + 2 regression) | `6825734b35653b5f911ff87d5bb37e5271a876c4` |
| D03-01-AC0..AC3 (GREEN re-run) | original 4 tests | same focused file | Exit 0 (unchanged tests still pass, no contract drift) | `6825734b35653b5f911ff87d5bb37e5271a876c4` |
| No-regression gate | D02-01, D04-01, DL-01, DL-02, SPLIT-01, D01-smoke | `python -m pytest tests/unit/lab/models/test_d02_01.py tests/unit/lab/models/test_d04_01.py tests/unit/lab/models/dl/test_early_stopping.py tests/unit/lab/models/dl/test_sequence_dataset.py tests/unit/lab/labels/test_splits.py` + `tests/integration/lab/test_d01_training_smoke.py` | Exit 0 (39 + 4 passed) | `6825734b35653b5f911ff87d5bb37e5271a876c4` worktree |

Ruff lint unavailable in this host (`No module named ruff`); capability gap recorded, no lint evidence fabricated. No credentials touched; no push performed.

## Review
- Spec verdict: PASS (D03-01-FR3 now demonstrably consumes common evaluation cost and folds per `docs/specs/15-deep-learning-and-provenance.md`).
- Quality verdict: PASS (smallest scoped change: only `d03_resnet_lstm.py` + additive exports + its test; shared contracts untouched).
- Findings fixed: blocking #1 (folds) and #2 (budget logging) above; no new scope introduced.
- Self-review: completed by fix owner (diff checked: 3 files, purely additive).
- Independent review: PENDING delta verification of this SHA (blocking findings + adjacent fold/cost/budget contracts only).

## Deviations and known risks
- Deviations: none.
- Unresolved issues / blockers: none for D03-01 after this fix.
- Next unlocked consumers: research tournament comparisons (none mandatory).
