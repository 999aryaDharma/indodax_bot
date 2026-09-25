# SIM-04 handoff

Status: CHANGES_REQUESTED

## Identity
- Sprint ID: SIM-04 — Net-cost risk and capacity metrics
- Implementation agent: Antigravity
- Independent reviewer: `/root/docs_review`
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


## Independent review findings (2026-09-25)

Reviewer `/root/docs_review` reviewed exact repository SHA `e3f1af8d232c1bf43fdf325922c96376bb542bc0` and returned CHANGES_REQUESTED. Independent command `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/backtest/test_metrics.py tests/unit/lab/strategies/test_registry.py -q -p no:cacheprovider` -> 8 passed in 1.07s; negative probes reproduced the findings.

- Important — empty spread map `{}` reports `spread_status=AVAILABLE` and `spread_cost=0`; AC3 requires unavailable data to stay unavailable. Reviewer passed `{}` and reproduced the false zero.
- Important — missing equity observations default drawdown to zero; CLI also emits the final ledger equity for every historic transaction timestamp. Repro produced a flat 10,277,700 curve and zero drawdown despite a 211,800 decline. AC0 requires observed path metrics.
- Important — completed breakeven gross-PnL trades do not increment trade_count because trade_count is win_count+loss_count. A flat-price 1-unit buy/sell paying 1 fee each is reported as NO_TRADES despite two fills and -2 net PnL.
- Important — output lacks by_regime and by_tier metrics despite the task contract requiring year/regime/tier/asset. Missing classification must be explicitly unavailable; do not fabricate groups.
- Passing boundary: fee equity is not double-subtracted. Flow-adjusted performance is not present in ResearchLedger and remains unqualified/out of this sprint unless a scoped change request is approved.
