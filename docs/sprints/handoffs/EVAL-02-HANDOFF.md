# EVAL-02 handoff

Status: REVIEW

## Identity
- Sprint ID: EVAL-02 — Hard gates and selection diagnostics
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/eval-02-hard-gates-and-selection-diagnostics`
- Base SHA: `7ae1deb`
- Code target: `feat(eval-02): hard gates and selection diagnostics`
- Evidence SHA relation: `efc973257aa9e5d4a6d8a1a6ddc9322652515d2e`

## Files and contracts
- Planned files:
  - `src/indodax_lab/evaluation/gates.py` (EvaluationOutcome, EvaluationPolicy, EvaluationResult, MultiSeedEvaluationResult, evaluate_run, evaluate_multi_seed_runs)
  - `src/indodax_lab/evaluation/statistics.py` (compute_deflated_sharpe_ratio, compute_pbo)
  - `src/indodax_lab/evaluation/__init__.py` (Package exports)
  - `tests/unit/lab/evaluation/test_gates.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `metrics + policy + trial family -> INVALID_RUN/HARD_FAIL/NEAR_MISS/REGIME_EDGE/PASS, DSR/PBO when eligible.`
  - Gate versioning and hierarchy: run validity (provenance, clean worktree, verified cost schedule) strictly precedes quality metrics.
  - High score does not conceal unknown costs: missing, unverified, or "unknown" cost model forces INVALID_RUN with reason `COST_MODEL_UNKNOWN`.
  - Small sample size produces insufficient evidence: runs with trade counts below policy threshold fail the sample size gate (`INSUFFICIENT_SAMPLE_SIZE`), resulting in `HARD_FAIL` and honest `NOT_ESTIMABLE` for DSR and PBO.
  - Multi-seed honest evaluation: selecting the "best" seed is strictly forbidden (`BEST_SEED_SELECTION_FORBIDDEN`); aggregation must use median, mean, or worst seed.
- Migration and compatibility:
  - Additive evaluation subsystem; backward compatible with EVAL-01.
  - Dependencies: EVAL-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| EVAL-02-AC0 (RED) | `test_eval_02_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_gates.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-02-AC0 (GREEN) | `test_eval_02_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_gates.py::test_eval_02_valid_contract` | Exit 0 (Passed, produces valid EvaluationOutcome.PASS) | `efc9732` |
| EVAL-02-AC1 (RED) | `test_eval_02_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_gates.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-02-AC1 (GREEN) | `test_eval_02_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_gates.py::test_eval_02_contract_1` | Exit 0 (Passed, unknown costs force INVALID_RUN) | `efc9732` |
| EVAL-02-AC2 (RED) | `test_eval_02_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_gates.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-02-AC2 (GREEN) | `test_eval_02_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_gates.py::test_eval_02_contract_2` | Exit 0 (Passed, small sample produces HARD_FAIL and NOT_ESTIMABLE) | `efc9732` |
| EVAL-02-AC3 (RED) | `test_eval_02_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_gates.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-02-AC3 (GREEN) | `test_eval_02_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_gates.py::test_eval_02_contract_3` | Exit 0 (Passed, best seed selection forbidden, median enforced) | `efc9732` |

All 4 tests in `tests/unit/lab/evaluation/test_gates.py` passed (1.63s).
Combined suite verification (92 passed across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation).

## Review
- Spec verdict: PASS (meets all functional requirements of EVAL-02 and specs/11-evaluation-and-experiment-lifecycle.md).
- Quality verdict: PASS (validity precedes quality, honest sample sizing, zero cherry-picking, robust DSR/PBO handling).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for EVAL-02.
- Next unlocked consumers: EVAL-03.
