# SIM-02 handoff

Status: REVIEW

## Identity
- Sprint ID: SIM-02 — Portfolio risk and circuit breakers
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/sim-02-portfolio-risk-and-circuit-breakers`
- Base SHA: `d045d5f`
- Code target: `feat(sim-02): portfolio risk and circuit breakers`
- Evidence SHA relation: `f024999`

## Files and contracts
- Planned files:
  - `src/indodax_lab/backtest/risk.py` (RiskPolicy, RiskAssessmentResult, PortfolioRiskManager)
  - `src/indodax_lab/backtest/__init__.py` (Public backtest exports)
  - `tests/unit/lab/backtest/test_risk.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `equity + open risk + intent + versioned risk policy -> approved size or reasoned rejection`.
  - Position sizing respects shared capital, max position fraction, and available cash.
  - Sizing below minimum order notional is strictly rejected (never rounded up).
  - Daily and weekly loss limits include unrealized mark-to-market PnL.
  - Hard drawdown halt state persists durable across system restarts via serialization.
- Migration and compatibility:
  - Additive backtest risk module; backward compatible.
  - Dependencies: LED-01 (DONE), SIM-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SIM-02-AC0 (RED) | `test_sim_02_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_risk.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-02-AC0 (GREEN) | `test_sim_02_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_risk.py::test_sim_02_valid_contract` | Exit 0 (Passed, sizing caps to position fraction) | `f024999` |
| SIM-02-AC1 (RED) | `test_sim_02_contract_1` | `python -m pytest tests/unit/lab/backtest/test_risk.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-02-AC1 (GREEN) | `test_sim_02_contract_1` | `python -m pytest tests/unit/lab/backtest/test_risk.py::test_sim_02_contract_1` | Exit 0 (Passed, sub-minimum size rejected, not rounded up) | `f024999` |
| SIM-02-AC2 (RED) | `test_sim_02_contract_2` | `python -m pytest tests/unit/lab/backtest/test_risk.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-02-AC2 (GREEN) | `test_sim_02_contract_2` | `python -m pytest tests/unit/lab/backtest/test_risk.py::test_sim_02_contract_2` | Exit 0 (Passed, daily loss includes unrealized mark losses) | `f024999` |
| SIM-02-AC3 (RED) | `test_sim_02_contract_3` | `python -m pytest tests/unit/lab/backtest/test_risk.py` | Exit 1 (`NotImplementedError`) | `working tree` |
| SIM-02-AC3 (GREEN) | `test_sim_02_contract_3` | `python -m pytest tests/unit/lab/backtest/test_risk.py::test_sim_02_contract_3` | Exit 0 (Passed, drawdown halt persists after restart) | `f024999` |

All 4 tests in `tests/unit/lab/backtest/test_risk.py` passed (0.42s).
Combined suite verification (34 tests across backtest, risk, execution, ledger, costs, features) passed (1.57s).

## Review
- Spec verdict: PASS (meets all functional requirements of SIM-02 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (zero network, strictly immutable policy schemas, Decimal precision, UTC-aware).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SIM-02.
- Next unlocked capabilities: SIM-03 (Deterministic replay judge) once DATA-06 is joined, and SHADOW-02.
