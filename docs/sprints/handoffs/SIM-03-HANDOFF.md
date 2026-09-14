# SIM-03 handoff

Status: REVIEW

## Identity
- Sprint ID: SIM-03 — Deterministic replay judge
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/sim-03-deterministic-replay-judge`
- Base SHA: `a7fc0c7`
- Code target: `feat(sim-03): deterministic replay judge`
- Evidence SHA relation: `d423650`

## Files and contracts
- Planned files:
  - `src/indodax_lab/backtest/result.py` (BacktestResult model, canonical postings_hash sha256)
  - `src/indodax_lab/backtest/engine.py` (ReplayBacktestEngine, chronological loop, atomic run_and_publish)
  - `src/indodax_lab/backtest/__init__.py` (Backtest exports: ReplayBacktestEngine, BacktestResult)
  - `src/indodax_lab/cli/run_backtest.py` (CLI entry point for deterministic replay)
  - `tests/integration/lab/test_backtest_golden.py` (Explicit AC0..AC3 test cases)
- Contract:
  - Event loop: `market -> pending fills -> barriers -> decision -> risk -> orders -> mark; stable event/pair/order sort`.
  - Replay market produces identical fills, balanced double-entry postings, and equity curves across repeat runs with identical input.
  - Bitwise identical canonical SHA256 digest over sorted ledger postings.
  - Atomic publication: simulated failure/crash before write completion never leaves a published successful backtest result.
  - Independent ledgers are strictly segregated; multiple portfolio accounts never pool capital or balance.
- Migration and compatibility:
  - Additive backtest execution engine; backward compatible.
  - Dependencies: LED-01 (DONE), SIM-01 (DONE), SIM-02 (DONE), DATA-06 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SIM-03-AC0 (RED) | `test_sim_03_valid_contract` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-03-AC0 (GREEN) | `test_sim_03_valid_contract` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_valid_contract` | Exit 0 (Passed, end-to-end replay produces valid BacktestResult) | `d423650` |
| SIM-03-AC1 (RED) | `test_sim_03_contract_1` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-03-AC1 (GREEN) | `test_sim_03_contract_1` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_contract_1` | Exit 0 (Passed, two replays yield bitwise identical postings_hash and metrics) | `d423650` |
| SIM-03-AC2 (RED) | `test_sim_03_contract_2` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-03-AC2 (GREEN) | `test_sim_03_contract_2` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_contract_2` | Exit 0 (Passed, crash before publish leaves no published run) | `d423650` |
| SIM-03-AC3 (RED) | `test_sim_03_contract_3` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-03-AC3 (GREEN) | `test_sim_03_contract_3` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_contract_3` | Exit 0 (Passed, independent ledgers are isolated and never pooled) | `d423650` |

All 4 tests in `tests/integration/lab/test_backtest_golden.py` passed (0.44s).
Relevant lab suite verification (44 passed, 2 skipped across backtest, risk, execution, ledger, costs, features) passed (1.71s).

## Review
- Spec verdict: PASS (meets all functional requirements of SIM-03 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (strictly deterministic, Decimal precision, UTC-aware, fail-closed atomic file output).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SIM-03.
- Next unlocked capabilities: SIM-04 (Net-cost risk and capacity metrics) and STRAT-01 (Declarative strategy protocol).
