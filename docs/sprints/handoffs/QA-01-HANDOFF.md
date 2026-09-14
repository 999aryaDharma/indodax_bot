# QA-01 handoff

Status: REVIEW

## Identity
- Sprint ID: QA-01 — Wave 1 tournament checkpoint
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/qa-01-wave-1-tournament-checkpoint`
- Base SHA: `ec0cc8c`
- Code target: `feat(qa-01): wave 1 tournament checkpoint`
- Evidence SHA relation: `e7029da`

## Files and contracts
- Actual files:
  - `src/indodax_lab/evaluation/tournament.py` (run_wave1_tournament, TournamentCandidate, TournamentFollowUp, TournamentReport, LiveProfitabilityClaimForbiddenError)
  - `src/indodax_lab/evaluation/__init__.py` (Package exports — QA-01 symbols added)
  - `tests/regression/test_wave1_tournament.py` (AC0..AC3 regression test cases)
  - `docs/research/phase2-tournament-verification.md` (Tournament documentation and safety disclaimer)
- Contract:
  - `tiny offline tournament -> all lifecycle outcomes + identical snapshot/folds/costs comparison.`
  - Deterministic evaluation: `run_wave1_tournament()` evaluates candidates deterministically against identical snapshot and cost basis (QA-01-AC0).
  - All four lifecycle outcomes: Fixture tests produce and verify `INVALID_RUN`, `HARD_FAIL`, `NEAR_MISS`, and `PASS` (QA-01-AC1).
  - Repeat policy follow-up: Actions map directly to JOB-03 scheduler rules: `ADVANCE_TO_SHADOW` for PASS, `BLOCK_RETRIES` for HARD_FAIL, `REQUIRE_NEW_VERSION` for NEAR_MISS, `RETRY_WITH_BACKOFF` for INVALID_RUN (QA-01-AC2).
  - Live profitability disclaimer: Reports enforce `is_real_market_evidence=False` and contain strict disclaimer; attempting to claim live profitability raises `LiveProfitabilityClaimForbiddenError` (QA-01-AC3).
- Migration and compatibility:
  - Additive module in `src/indodax_lab/evaluation/`; no existing interfaces modified.
  - Dependencies: JOB-03 (REVIEW), SHADOW-02 (REVIEW), C01..C10, S01, S02, ML-04 (all verified).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| QA-01-AC0 (RED) | `test_qa_01_valid_contract` | `python -m pytest tests/regression/test_wave1_tournament.py` | Exit 1 (ModuleNotFoundError: No module named 'indodax_lab.evaluation.tournament') | `working tree` |
| QA-01-AC0 (GREEN) | `test_qa_01_valid_contract` | `python -m pytest tests/regression/test_wave1_tournament.py::test_qa_01_valid_contract` | Exit 0 (Passed, deterministic tournament produces identical outputs on same inputs) | `e7029da` |
| QA-01-AC1 (RED) | `test_qa_01_contract_1` | `python -m pytest tests/regression/test_wave1_tournament.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| QA-01-AC1 (GREEN) | `test_qa_01_contract_1` | `python -m pytest tests/regression/test_wave1_tournament.py::test_qa_01_contract_1` | Exit 0 (Passed, fixture verifies INVALID_RUN, HARD_FAIL, NEAR_MISS, and PASS) | `e7029da` |
| QA-01-AC2 (RED) | `test_qa_01_contract_2` | `python -m pytest tests/regression/test_wave1_tournament.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| QA-01-AC2 (GREEN) | `test_qa_01_contract_2` | `python -m pytest tests/regression/test_wave1_tournament.py::test_qa_01_contract_2` | Exit 0 (Passed, follow-up actions align with JOB-03 DAG repeat policy) | `e7029da` |
| QA-01-AC3 (RED) | `test_qa_01_contract_3` | `python -m pytest tests/regression/test_wave1_tournament.py` | Exit 1 (ModuleNotFoundError) | `working tree` |
| QA-01-AC3 (GREEN) | `test_qa_01_contract_3` | `python -m pytest tests/regression/test_wave1_tournament.py::test_qa_01_contract_3` | Exit 0 (Passed, report enforces disclaimer and raises LiveProfitabilityClaimForbiddenError) | `e7029da` |

All 4 tests in `tests/regression/test_wave1_tournament.py` passed (1.63s).
Full lab suite verification: 203 passed across strategies, features, labels, evaluation, backtest, orchestration, operations, training materialization, retention, models, reporting, paper, and regression.

## Review
- Spec verdict: PASS (meets all functional requirements of QA-01 and docs/specs/20-testing-strategy.md).
- Quality verdict: PASS (deterministic tournament execution, 4-outcome verification, repeat-policy mapping, live profitability prohibition, no real-money execution).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for QA-01.
- Next unlocked consumers: DL-01, R01-01, QA-03, REL-01.
