# ML-03 handoff

Status: REVIEW

## Identity
- Sprint ID: ML-03 — Bounded trial search
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/ml-03-bounded-trial-search`
- Base SHA: `e4d3262`
- Code target: `feat(ml-03): bounded trial search`
- Evidence SHA relation: `5b17c3bccb20a55262272f953fe0acae5a13a3a5`

## Files and contracts
- Planned files:
  - `src/indodax_lab/models/tuning.py` (SealedTestObjectiveForbiddenError, TrialBudgetExhaustedError, RevisionBudgetExhaustedError, ResumeConfigMismatchError, TrialStatus, SearchSpace, TrialBudget, TrialOutcome, BoundedTrialSearch)
  - `src/indodax_lab/models/__init__.py` (Package exports)
  - `tests/unit/lab/models/test_tuning_budget.py` (AC0..AC3 unit tests and edge cases)
- Contract:
  - `versioned search space + inner folds + family budget -> frozen winning recipe, all trial outcomes.`
  - Search budget accountability: Search tracks trial budget consumption (`max_trials`, `consumed_trials`, `remaining_trials`) and strictly rejects objectives pointing to sealed or test partitions with `SealedTestObjectiveForbiddenError`.
  - Failed trial budget consumption: Execution or convergence failures (`TrialStatus.FAILED`) decrement remaining trial budget identically to successful trials; budget cannot be bypassed by discarding failed trials.
  - Resume configuration parity: Checkpoint resumption validates deterministic hash and identifier parity with the current `SearchSpace`; any discrepancy in search parameters or versions raises `ResumeConfigMismatchError`.
  - Bounded trial and revision caps: Enforces ADR-003 research budget constraints (maximum 30 trials; maximum 1 near-miss revision per model). Revisions update search space without resetting the consumed trial count.
- Migration and compatibility:
  - Additive hyperparameter exploration subsystem; consumes ML-02 execution mapper and EVAL-01 registry primitives.
  - Dependencies: ML-02 (DONE), EVAL-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| ML-03-AC0 (RED) | `test_ml_03_valid_contract` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.models.tuning') | `working tree` |
| ML-03-AC0 (GREEN) | `test_ml_03_valid_contract` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py::test_ml_03_valid_contract` | Exit 0 (Passed, sealed test forbidden as objective, inner validation tracked within trial budget) | `5b17c3b` |
| ML-03-AC1 (RED) | `test_ml_03_contract_1` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-03-AC1 (GREEN) | `test_ml_03_contract_1` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py::test_ml_03_contract_1` | Exit 0 (Passed, failed trials consume budget and lead to budget exhaustion) | `5b17c3b` |
| ML-03-AC2 (RED) | `test_ml_03_contract_2` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-03-AC2 (GREEN) | `test_ml_03_contract_2` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py::test_ml_03_contract_2` | Exit 0 (Passed, resume with matching configuration succeeds; parameter mutation is rejected) | `5b17c3b` |
| ML-03-AC3 (RED) | `test_ml_03_contract_3` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| ML-03-AC3 (GREEN) | `test_ml_03_contract_3` | `python -m pytest tests/unit/lab/models/test_tuning_budget.py::test_ml_03_contract_3` | Exit 0 (Passed, max 30 trials enforced, max 1 revision permitted without trial count reset) | `5b17c3b` |

All 5 tests in `tests/unit/lab/models/test_tuning_budget.py` passed (1.33s).
Full lab suite verification: 144 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, and reporting.

## Review
- Spec verdict: PASS (meets all functional requirements of ML-03 and docs/specs/12-tabular-models-and-training.md).
- Quality verdict: PASS (leak-free inner validation objectives, strict ADR-003 trial/revision budgeting, deterministic state serialization).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for ML-03.
- Next unlocked consumers: M01-01, M02-01.
