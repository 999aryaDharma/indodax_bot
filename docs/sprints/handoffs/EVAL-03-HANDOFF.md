# EVAL-03 handoff

Status: REVIEW

## Identity
- Sprint ID: EVAL-03 — Sealed candidate lifecycle
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/eval-03-sealed-candidate-lifecycle`
- Base SHA: `1503658`
- Code target: `feat(eval-03): sealed candidate lifecycle`
- Evidence SHA relation: `05ffd1a0cfc380d33612ffa510c324959102d032`

## Files and contracts
- Planned files:
  - `src/indodax_lab/evaluation/lifecycle.py` (CandidateStage, CandidateRecord, CandidateLifecycleManager, ExposureAuditRecord, LeaderboardEntry, errors)
  - `src/indodax_lab/evaluation/__init__.py` (Package exports)
  - `tests/unit/lab/evaluation/test_lifecycle.py` (AC0..AC3 unit tests)
- Contract:
  - `IDEA -> IMPLEMENTED -> BACKTESTED -> VALIDATED -> SEALED_PASS -> SHADOW -> CHAMPION; immutable transitions.`
  - Frozen candidate mutation guard: Any attempt to mutate the configuration of a validated or sealed candidate in-place raises `CandidateFrozenError`. Spawning a new challenger (`fork_challenger`) is required, resetting lifecycle status for the branched version while preserving the frozen candidate.
  - Single-use sealed gate with audit trail: The sealed evaluation gate can only be opened once per candidate version. Reopening raises `GateAlreadyOpenedError`. Each opening event is recorded in `ExposureAuditRecord`.
  - Leaderboard integrity guard: Runs marked as `INVALID_RUN` or failed are strictly excluded from candidate leaderboards.
- Migration and compatibility:
  - Additive candidate lifecycle state machine and SQLite exposure audit tables.
  - Dependencies: EVAL-02 (DONE), SPLIT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| EVAL-03-AC0 (RED) | `test_eval_03_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.evaluation.lifecycle') | `working tree` |
| EVAL-03-AC0 (GREEN) | `test_eval_03_valid_contract` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_valid_contract` | Exit 0 (Passed, promotes candidate through sequential lifecycle stages with exposure audit) | `05ffd1a` |
| EVAL-03-AC1 (RED) | `test_eval_03_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-03-AC1 (GREEN) | `test_eval_03_contract_1` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_contract_1` | Exit 0 (Passed, sealed config modification rejected in place, forks new challenger) | `05ffd1a` |
| EVAL-03-AC2 (RED) | `test_eval_03_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-03-AC2 (GREEN) | `test_eval_03_contract_2` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_contract_2` | Exit 0 (Passed, sealed gate opened once and recorded; reopening attempt fails closed) | `05ffd1a` |
| EVAL-03-AC3 (RED) | `test_eval_03_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| EVAL-03-AC3 (GREEN) | `test_eval_03_contract_3` | `python -m pytest tests/unit/lab/evaluation/test_lifecycle.py::test_eval_03_contract_3` | Exit 0 (Passed, invalid runs strictly excluded from leaderboard ranking) | `05ffd1a` |

All 4 tests in `tests/unit/lab/evaluation/test_lifecycle.py` passed (1.28s).
Full lab suite verification: 121 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, and training materialization.

## Review
- Spec verdict: PASS (meets all functional requirements of EVAL-03 and specs/11-evaluation-and-experiment-lifecycle.md).
- Quality verdict: PASS (immutable state machine transitions, fail-closed unseal guard, strict exclusion of invalid runs from ranking).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for EVAL-03.
- Next unlocked consumers: ML-04, JOB-03, SHADOW-01, SHADOW-03, REPORT-01.
