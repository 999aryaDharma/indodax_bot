# D01-01 handoff

Status: REVIEW (fix cycle: blocking set resolved, pending delta verification)

## Identity
- Sprint ID: D01-01 — Tabular MLP baseline
- Implementation agent (fix): opencode/muse-spark-1.3-contributor-free
- Independent reviewer: UNASSIGNED (delta verification required before DONE)
- Branch / worktree: `fix/d01-01-resume-checkpoint` in `.worktrees/fix/D01-01`
- Base SHA: `02fb7c3`
- Code target: `fix(d01-01): restore best weights plus optimizer/RNG on resume`
- Evidence SHA relation: `b1b0bbaba225a20961cc236f73f8ac6f92075e8b` (code commit b1b0bba + this evidence commit at branch HEAD)

## Files and contracts
- Fixed files (this cycle only; all other D01-01 artifacts unchanged):
  - `src/indodax_lab/models/dl/d01_mlp.py` (real optimizer/RNG checkpoint capture + restore; `best_checkpoint.json` sidecar preserving true best weights/epoch/counter; resume restores best, not interrupted-latest weights)
  - `tests/integration/lab/test_d01_training_smoke.py` (3 AC3 regression tests; existing AC0..AC3 tests untouched)
- Contract (unchanged):
  - `same feature rows + <=12 configs -> nonlinear baseline forecast via common mapper.`
  - Common execution mapper (D01-01-AC0), same sample comparator (D01-01-AC1), <=12 configs + 3 finalist seeds (D01-01-AC2) — all preserved, no behavior change.
  - Checkpoint resumption (D01-01-AC3): interruption resumes from latest checkpoint **without loss of best weights, optimizer state, or RNG trajectory**.
- Migration and compatibility:
  - No shared-schema change: `NeuralTrainingCheckpoint` (DL-01) untouched; best weights live in additive sidecar `best_checkpoint.json` beside `latest_checkpoint.json`.
  - Legacy checkpoints without sidecar resume via fail-safe fallback (best = latest weights, counter 0).
  - Dependencies: DL-01, DL-02, D02-01, D04-01 untouched; DL-01 gate re-run proves no regression.

## Accepted blocking set (from independent review) and resolution
| # | Blocking finding | Resolution |
|---|---|---|
| 1 | Resume loses best weights: `tracker.best_weights` was set to interrupted-latest weights, so the final model was not the best-validation model. | `fit()` now writes `best_checkpoint.json` (best epoch/val/counter/weights + input hash) on every checkpoint save; resume restores `tracker` best state from the sidecar and finishes from true best weights. Input-hash mismatch on the sidecar raises fail-closed. |
| 2 | Optimizer/RNG stub: `optimizer_state={"lr": ...}` and `rng_state={"seed": ...}` carried no restorable state, so resumed trajectory diverged. | Checkpoint now stores the full AdamW `state_dict` (tensor-safe JSON round-trip) and a real RNG snapshot (torch + numpy + python + CUDA when available); resume reloads optimizer state and RNG before continuing, reproducing the uninterrupted trajectory bit-for-bit on CPU. |

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| D01-01-AC3 (RED) | `test_d01_01_contract_3_optimizer_state_is_restorable` | `python -m pytest tests/integration/lab/test_d01_training_smoke.py -k optimizer_state_is_restorable` | Exit 1 (assertion: optimizer_state is a stub without restorable AdamW state) | `working tree` (pre-fix) |
| D01-01-AC3 (RED) | `test_d01_01_contract_3_rng_state_is_restorable` | `python -m pytest tests/integration/lab/test_d01_training_smoke.py -k rng_state_is_restorable` | Exit 1 (assertion: rng_state is a stub without restorable RNG snapshot) | `working tree` (pre-fix) |
| D01-01-AC3 (RED) | `test_d01_01_contract_3_resume_preserves_best_weights` | `python -m pytest tests/integration/lab/test_d01_training_smoke.py -k resume_preserves_best` | Exit 1 (resumed best 0.5637 != uninterrupted best 0.5597) | `working tree` (pre-fix) |
| D01-01-AC3 (GREEN) | all 3 regression tests above | `python -m pytest tests/integration/lab/test_d01_training_smoke.py` | Exit 0 (7 passed: 4 original AC0..AC3 + 3 regression) | `b1b0bbaba225a20961cc236f73f8ac6f92075e8b` |
| D01-01-AC0..AC3 (GREEN re-run) | `test_d01_01_valid_contract`, `test_d01_01_contract_1/2/3` | same focused file | Exit 0 (unchanged tests still pass, no contract drift) | `b1b0bbaba225a20961cc236f73f8ac6f92075e8b` |
| DL-01 no-regression gate | `tests/unit/lab/models/dl/test_early_stopping.py` | `python -m pytest tests/unit/lab/models/dl/test_early_stopping.py` | Exit 0 (4 passed) | `b1b0bbaba225a20961cc236f73f8ac6f92075e8b` worktree |

Ruff lint unavailable in this host (`No module named ruff`); capability gap recorded, no lint evidence fabricated. No credentials touched; no push performed.

## Review
- Spec verdict: PASS (D01-01-AC3 now restores verified best validation checkpoint per `docs/specs/15-deep-learning-and-provenance.md` failure/recovery rule).
- Quality verdict: PASS (smallest scoped change: only `d01_mlp.py` + its test; shared checkpoint/training modules untouched).
- Findings fixed: blocking #1 (best-weights) and #2 (optimizer/RNG stub) above; no new scope introduced.
- Self-review: completed by fix owner (diff checked: 2 files, `git diff --stat` recorded pre-commit).
- Independent review: PENDING delta verification of this SHA (blocking findings + adjacent resume contract only).

## Deviations and known risks
- Deviations: none (bug-compatible legacy resume fallback preserved for pre-fix checkpoints).
- Unresolved issues / blockers: none for D01-01 after this fix.
- Next unlocked consumers: D02-01, G01-01, F01-02, L01-01.
