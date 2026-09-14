# COST-01 handoff

Status: REVIEW

## Identity
- Sprint ID: COST-01 — Time-valid exchange cost schedules
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/cost-01-time-valid-exchange-cost-schedules`
- Base SHA: `faf1698`
- Code SHA: `9c9504feea4ca33320f7724fe282a5bc651ec30f`
- Evidence SHA relation: recorded in this handoff

## Files and contracts
- Planned files:
  - `configs/costs/indodax_idr_v1.yaml` (newly created)
  - `src/indodax_lab/backtest/__init__.py` (newly created)
  - `src/indodax_lab/backtest/costs.py` (newly created)
  - `tests/unit/lab/backtest/test_cost_schedule.py` (newly created)
- Contract:
  - `market, side, role, event_ts -> service/tax/exchange components and min notional with sources; [valid_from,valid_to)`.
  - All rates Decimal, exact accounting, no negative or non-finite rates.
  - Overlapping schedule intervals for the same market/side/role rejected.
  - Boundary end belongs to next interval.
  - Unknown period raises UnknownCostScheduleError (never falls back to today's fee).
- Migration and compatibility:
  - Additive backtest subsystem; backward compatible.
  - Dependencies: DATA-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| COST-01-AC0 (RED) | `test_cost_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py` | Exit 1 (`NotImplementedError`) | working tree |
| COST-01-AC0 (GREEN) | `test_cost_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_valid_contract` | Exit 0 (Passed, resolves historical and current schedules) | working tree |
| COST-01-AC1 | `test_cost_01_contract_1` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_contract_1` | Exit 0 (Passed, rejects overlapping intervals) | working tree |
| COST-01-AC2 | `test_cost_01_contract_2` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_contract_2` | Exit 0 (Passed, boundary end selects next interval) | working tree |
| COST-01-AC3 | `test_cost_01_contract_3` | `python -m pytest tests/unit/lab/backtest/test_cost_schedule.py::test_cost_01_contract_3` | Exit 0 (Passed, unknown period raises UnknownCostScheduleError) | working tree |

All 5 tests in `tests/unit/lab/backtest/test_cost_schedule.py` passed (0.42s).
Combined verification with previous capabilities (29 tests total) passed (1.33s).

## Review
- Spec verdict: PASS (meets all functional requirements of COST-01 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (zero network, strictly immutable schemas, Decimal precision, UTC-aware).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for COST-01.
- Next unlocked capabilities: LED-01 (Balanced research postings), SIM-01 (Conservative execution simulator).
