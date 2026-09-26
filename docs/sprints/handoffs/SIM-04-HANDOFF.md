# SIM-04 handoff

Status: DONE

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

## Remediation candidate (2026-09-26)

- Code commit: `389d9163fc103530d33ea724662c7ce4dfaa2e60` (`fix(sim-04): retain latest market-time equity mark`).
- Finding corrected: delayed older bars no longer replace a newer observed mark. Cash/ledger postings still replay by availability; the mark is selected by market close timestamp.
- Regression: `test_late_older_bar_does_not_replace_newer_equity_mark`.
- Focused check: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/cli/test_run_backtest_report.py tests/unit/lab/strategies/test_registry.py -q -p no:cacheprovider` -> 14 passed (the command includes STRAT-01 checks).
- Full check on combined code HEAD `3f2623b884a5066cdbaf8a27f85e517c03fa9885`: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest -q -p no:cacheprovider` -> 1,103 passed, 2 platform-specific skipped, 4 warnings.
- Independent review of the remediation commit is pending. Keep status CHANGES_REQUESTED until reviewer PASS and manifest update.

### Same-time availability remediation

- Code commit: `e4ca5ad3116bc6c05d44f09ddfb57102015fa007` (`fix(sim-04): consolidate same-time equity observations`).
- Finding corrected: bars sharing one `available_at` are applied as a group and emit one equity observation; marks still select the greatest market close time.
- Regression extends `test_late_older_bar_does_not_replace_newer_equity_mark` to assert unique curve timestamps.
- Full verification on combined code HEAD `b177691d19713b901d3a4f2f1b8a5d38779efe0a`: 1,107 passed, 2 platform-specific skipped, 4 warnings.
- Independent exact-SHA review remains pending; status stays CHANGES_REQUESTED.

## Independent review closeout (2026-09-26)

- `/root/docs_review` reviewed exact code SHA `b177691d19713b901d3a4f2f1b8a5d38779efe0a`: **PASS**, no Critical/Important findings. Review confirmed latest market-time marks survive delayed older bars and same-availability observations are emitted once.
- Independent focused evidence: metrics, CLI reports, strategy registry and labels -> 55 passed in 1.32s. Full local suite on the same source tree -> 1,107 passed, 2 platform-specific skipped, 4 warnings; full suite was not independently rerun.
- Code commits: `389d9163fc103530d33ea724662c7ce4dfaa2e60` and `e4ca5ad3116bc6c05d44f09ddfb57102015fa007`.
- External limitations remain: flow-adjusted returns, verified historical fees, empirical spread and production qualification are outside this evidence.
