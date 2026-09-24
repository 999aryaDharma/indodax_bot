# SIM-02 handoff

## Recovery review addendum (2026-09-25)

- Reworked code SHA: `edb597a736f380b3dd0ea234190e5c1d9c3fa97d`.
- Independent review round 1 by `/root/sim01_final_review` requested changes on
  `f0249993d317f93e8be2afd5c02b41f718b452fc`. Review identified period-opening
  equity being reset too late and missing weekly-loss evidence. Both are addressed:
  observed equity now rolls daily/ISO-week baselines using the last pre-boundary
  observation, period-mismatched orders fail closed until an observation arrives,
  and the state round-trips these fields. Legacy state without last-observation
  fields uses the high-water equity as a conservative fallback.
- Nonblank policy identity and positive minimum notional are now validated. The
  review's additional claims that fraction bounds, existing pair exposure, and
  leverage were unenforced were checked against the reviewed source: `Field`
  constraints and both exposure-cap calculations were already present. Regression
  tests now pin those existing guards.
- New UTC-boundary test first failed because the daily-loss assertion was approved;
  after the fix, the suite verifies both daily and weekly loss, boundary gaps,
  and missing-period observation rejection.
- Round-2 review on `9aa7080a7daf75e885c83adf321f5f6e9c3dad80` confirmed code review
  PASS and cleared its earlier policy/exposure findings. Acceptance remained
  CHANGES_REQUESTED because the handoff had not yet been refreshed and JSON snapshot
  writes could truncate prior halt state on interruption. Snapshot writes now use a
  same-directory temporary file, flush/fsync, then atomic replacement; a failure
  regression test proves the previous file is preserved and the temporary file is
  removed.
- Verification on the reworked code: `rtk pytest
  tests/unit/lab/backtest/test_risk.py
  tests/unit/lab/backtest/test_judge_remediation.py
  tests/integration/lab/test_backtest_golden.py -q` → 60 passed;
  `git diff --check` passed. Ruff reports legacy lint findings in the touched
  files; no lint-clean claim is made.
- Independent review of the final code SHA and refreshed evidence is pending. SIM-02 remains
  REVIEW. COST-01 fee-source evidence remains externally blocked; no manifest
  transition is claimed.

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
