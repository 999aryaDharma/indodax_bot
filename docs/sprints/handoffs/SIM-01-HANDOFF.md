# SIM-01 handoff

Status: REVIEW

## Identity
- Sprint ID: SIM-01 — Conservative execution simulator
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/sim-01-conservative-execution-simulator`
- Base SHA: `e68aa83`
- Code target: `feat(sim-01): conservative execution simulator`
- Evidence SHA relation: `ce1e724`

## Files and contracts
- Planned files:
  - `src/indodax_lab/backtest/events.py` (MarketBar, SignalIntent, ExecutionResult models)
  - `src/indodax_lab/backtest/execution.py` (ConservativeExecutionSimulator)
  - `src/indodax_lab/backtest/__init__.py` (Public backtest exports)
  - `tests/unit/lab/backtest/test_execution.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `SignalIntent + market + schedule -> REJECTED/PARTIAL/FILLED; next-open, precision, SL_FIRST, latency`.
  - Next-open causal execution: decisions at bar close cannot execute on the same bar close (same-close lookahead rejected).
  - Depth and min-notional gating: orders below minimum notional are rejected; orders exceeding volume depth are filled partially.
  - Conservative maker limit rules: touching the limit price alone does not trigger a fill (requires trade through).
- Migration and compatibility:
  - Additive backtest execution module; backward compatible.
  - Dependencies: COST-01 (DONE), BAR-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SIM-01-AC0 (RED) | `test_sim_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_execution.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-01-AC0 (GREEN) | `test_sim_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_execution.py::test_sim_01_valid_contract` | Exit 0 (Passed, next-open execution with realistic schedule costs) | `ce1e724` |
| SIM-01-AC1 (RED) | `test_sim_01_contract_1` | `python -m pytest tests/unit/lab/backtest/test_execution.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-01-AC1 (GREEN) | `test_sim_01_contract_1` | `python -m pytest tests/unit/lab/backtest/test_execution.py::test_sim_01_contract_1` | Exit 0 (Passed, same-close execution rejected) | `ce1e724` |
| SIM-01-AC2 (RED) | `test_sim_01_contract_2` | `python -m pytest tests/unit/lab/backtest/test_execution.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-01-AC2 (GREEN) | `test_sim_01_contract_2` | `python -m pytest tests/unit/lab/backtest/test_execution.py::test_sim_01_contract_2` | Exit 0 (Passed, min-notional rejection & partial fill on depth limit) | `ce1e724` |
| SIM-01-AC3 (RED) | `test_sim_01_contract_3` | `python -m pytest tests/unit/lab/backtest/test_execution.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-01-AC3 (GREEN) | `test_sim_01_contract_3` | `python -m pytest tests/unit/lab/backtest/test_execution.py::test_sim_01_contract_3` | Exit 0 (Passed, limit touch without trade through rejected) | `ce1e724` |

All 4 tests in `tests/unit/lab/backtest/test_execution.py` passed (0.43s).
Combined suite verification (30 tests across backtest, execution, ledger, costs, features) passed (1.84s).

## Review
- Spec verdict: PASS (meets all functional requirements of SIM-01 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (zero network, strictly immutable schemas, Decimal precision, UTC-aware).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SIM-01.
- Next unlocked capabilities: SIM-02 (Portfolio risk and circuit breakers) and LABEL-01 (once FEAT-04 is complete).
