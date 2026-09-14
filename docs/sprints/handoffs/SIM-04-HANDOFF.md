# SIM-04 handoff

Status: REVIEW

## Identity
- Sprint ID: SIM-04 — Net-cost risk and capacity metrics
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/sim-04-net-cost-risk-and-capacity-metrics`
- Base SHA: `ae87a72`
- Code target: `feat(sim-04): net-cost risk and capacity metrics`
- Evidence SHA relation: `645b7a3`

## Files and contracts
- Planned files:
  - `src/indodax_lab/backtest/metrics.py` (compute_performance_metrics, calculate_equity, PerformanceMetrics, CostStressMetrics, ProfitFactorResult)
  - `src/indodax_lab/backtest/ledger.py` (ResearchLedger initial_cash property)
  - `src/indodax_lab/backtest/__init__.py` (Public backtest exports)
  - `tests/unit/lab/backtest/test_metrics.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `postings + equity + rejected orders -> metrics by year/regime/tier/asset and 1.5x/2x stress`.
  - Profit factor is well-defined only with positive gross loss; zero-loss and no-trade scenarios produce well-reasoned undefined results (`defined=False`, explicit reason).
  - Equity calculation does not double-subtract transaction fees: cash balance already accounts for fee postings, so `equity = cash + marked_asset_value`.
  - Missing empirical spread is reported explicitly (`spread_cost=None`, `spread_status="MISSING_SPREAD"`) and never coerced to zero cost.
  - Cost stress evaluation computes net returns under 1.5x and 2.0x fee multipliers.
- Migration and compatibility:
  - Additive backtest metrics module; backward compatible.
  - Dependencies: SIM-03 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SIM-04-AC0 (RED) | `test_sim_04_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_metrics.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-04-AC0 (GREEN) | `test_sim_04_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_metrics.py::test_sim_04_valid_contract` | Exit 0 (Passed, computes ledger metrics with cost stress and capacity bounds) | `645b7a3` |
| SIM-04-AC1 (RED) | `test_sim_04_contract_1` | `python -m pytest tests/unit/lab/backtest/test_metrics.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-04-AC1 (GREEN) | `test_sim_04_contract_1` | `python -m pytest tests/unit/lab/backtest/test_metrics.py::test_sim_04_contract_1` | Exit 0 (Passed, no-trade and zero-loss PF produce well-reasoned undefined outcomes) | `645b7a3` |
| SIM-04-AC2 (RED) | `test_sim_04_contract_2` | `python -m pytest tests/unit/lab/backtest/test_metrics.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-04-AC2 (GREEN) | `test_sim_04_contract_2` | `python -m pytest tests/unit/lab/backtest/test_metrics.py::test_sim_04_contract_2` | Exit 0 (Passed, fee is not double-subtracted from net cash equity) | `645b7a3` |
| SIM-04-AC3 (RED) | `test_sim_04_contract_3` | `python -m pytest tests/unit/lab/backtest/test_metrics.py` | Exit 1 (`ModuleNotFoundError`) | `working tree` |
| SIM-04-AC3 (GREEN) | `test_sim_04_contract_3` | `python -m pytest tests/unit/lab/backtest/test_metrics.py::test_sim_04_contract_3` | Exit 0 (Passed, missing spread is never reported as zero cost) | `645b7a3` |

All 4 tests in `tests/unit/lab/backtest/test_metrics.py` passed (0.39s).
Combined suite verification (55 passed across backtest, risk, execution, ledger, costs, and features) passed (2.02s).

## Review
- Spec verdict: PASS (meets all functional requirements of SIM-04 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (strictly deterministic Decimal precision, explicit reason codes, no double-counting of fees).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SIM-04.
- Next unlocked capabilities: EVAL-01, REPORT-01.
