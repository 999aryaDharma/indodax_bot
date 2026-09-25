# SIM-03 handoff

## Recovery review addendum (2026-09-25)

- Reworked code SHA: `7464acda6150de86fd12777022db91a06278526a`.
- Round-1 independent review by `/root/sim01_final_review` and `/root/sim01_review`
  requested changes on `8b35308019676c532a804ef7b43f2f8069357067`: result artifacts
  lacked structured rejections and cost/risk/input identity; publish failure
  preservation and actual independent sizing were not tested; dependency claims were
  stale; and the synthetic fee fixture implied official evidence. The fixes below
  address those items.
- Backtest results now carry a canonical market-input hash, cost schedule and risk
  policy IDs/versions, emitted strategy IDs, and ordered rejection reasons. A run
  with rejected/cancelled orders reports `COMPLETED_WITH_REJECTIONS`; technical
  exceptions still prevent publishing a successful result.
- Result JSON now writes to a unique same-directory temporary file, flushes/fsyncs,
  atomically replaces the target, and removes the temporary on failure. Both
  `BacktestResult.save_json` and the CLI report publisher use this shared writer.
  Failure tests target existing artifacts named `.tmp`, which collided with the
  former fixed temporary path.
- AC3 now asserts actual per-engine quantities (`0.00048862`) and compares them to
  the single-wallet hypothetical pooled quantity (`0.00097725`). The test cost
  fixture is explicitly labeled synthetic and not INDODAX evidence; it exercises
  deterministic fee arithmetic only and does not satisfy COST-01.
- That paragraph recorded a prior branch snapshot and is superseded. The current authoritative manifest lists SIM-02 and DATA-06 as SIM-03 dependencies; both are DONE.
- Verification on this code SHA: `rtk pytest
  tests/integration/lab/test_backtest_golden.py
  tests/unit/lab/backtest/test_risk.py
  tests/unit/lab/backtest/test_judge_remediation.py
  tests/unit/lab/backtest/test_accounting_failure_atomicity.py -q` → 75 passed;
  Windows ML environment run including CLI report tests → 77 passed. `git diff --check`
  passed. Ruff import checks pass; full touched-file lint leaves existing E501 and
  unused-import findings in legacy CLI/engine code; no lint-clean claim is made.
- Round-2 review on commit `101e5d3ab4d42b7669f357c479105606ce4915a` found one
  remaining Important issue: the CLI used its own fixed temp path. It now delegates
  to the shared atomic writer, and the CLI-target `.tmp` failure test passes.
- Independent review: PASS by `/root/sim01_final_review` and `/root/sim01_review`
  on exact commit `76aaac2d7d8f550ffbee9aa2e85aebc3d9aa6e50` (code parent
  `7464acda6150de86fd12777022db91a06278526a`); no Critical or Important findings.
  Historical disposition at that review point; superseded by current manifest dependencies SIM-02 and DATA-06, both DONE, and final independent closeout below.

Status: DONE

## Identity
- Sprint ID: SIM-03 — Deterministic replay judge
- Implementation agent: Antigravity
- Independent reviewers: `/root/sim01_final_review`, `/root/sim01_review`; final closeout reviewer: `/root/docs_review`
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
- Historical dependencies at implementation: LED-01, SIM-01, SIM-02 and DATA-06
  were recorded DONE; see the recovery addendum above for current manifest status.

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| SIM-03-AC0 (RED) | `test_sim_03_valid_contract` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| SIM-03-AC0 (GREEN) | `test_sim_03_valid_contract` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_valid_contract` | Exit 0 (Passed, end-to-end replay produces valid BacktestResult) | `d423650` |
| SIM-03-AC1 (RED) | `test_sim_03_contract_1` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| SIM-03-AC1 (GREEN) | `test_sim_03_contract_1` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_contract_1` | Exit 0 (Passed, two replays yield bitwise identical postings_hash and metrics) | `d423650` |
| SIM-03-AC2 (RED) | `test_sim_03_contract_2` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| SIM-03-AC2 (GREEN) | `test_sim_03_contract_2` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_contract_2` | Exit 0 (Passed, crash before publish leaves no published run) | `d423650` |
| SIM-03-AC3 (RED) | `test_sim_03_contract_3` | `python -m pytest tests/integration/lab/test_backtest_golden.py` | Exit 1 (import failure; not behavioral RED evidence) | `working tree` |
| SIM-03-AC3 (GREEN) | `test_sim_03_contract_3` | `python -m pytest tests/integration/lab/test_backtest_golden.py::test_sim_03_contract_3` | Exit 0 (Passed, independent ledgers are isolated and never pooled) | `d423650` |

All 4 tests in `tests/integration/lab/test_backtest_golden.py` passed (0.44s).
Relevant lab suite verification (44 passed, 2 skipped across backtest, risk, execution, ledger, costs, features) passed (1.71s).

## Review
- Spec verdict: PASS (meets all functional requirements of SIM-03 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (strictly deterministic, Decimal precision, UTC-aware, fail-closed atomic file output).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: final PASS by `/root/docs_review` on exact repository SHA `8ecd154f466776a59dfeda38204b40d558efdf8d`; no Critical/Important findings. Independent focused suite: 84 passed (LABEL 21, SIM-03 63).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for SIM-03.
- Next unlocked capabilities: SIM-04 (Net-cost risk and capacity metrics) and STRAT-01 (Declarative strategy protocol).

## Recovery review addendum (2026-09-24)

- Affected engine change SHA: `260fd066fc46171cece30ca38f7fa0b055f1dabb` (`src/indodax_lab/backtest/engine.py` and `tests/unit/lab/backtest/test_judge_remediation.py`). Replay sizing selects maker fee basis at synchronous order creation and taker fee basis at the execution event, regardless of whether a limit price is present.
- Independent review: `/root/sim01_final_review`, PASS scoped to the replay fee-timing change and cash-safety regression; this is not a full SIM-03 acceptance review.
- Verification on the reviewed tree: the focused combined command recorded in the SIM-01 recovery addendum → 67 passed, including `tests/integration/lab/test_backtest_golden.py`.
- Historical gate at that review point: SIM-03 remained REVIEW because that scoped review did not replace the full acceptance review. Superseded by the final independent PASS and current dependency closeout below.


## Final coordinator closeout (2026-09-25)

The current manifest dependencies are SIM-02 and DATA-06; both are DONE. `/root/docs_review` independently reviewed exact repository SHA `8ecd154f466776a59dfeda38204b40d558efdf8d` and returned PASS with no Critical/Important implementation findings. AC0-AC3 and negative replay, atomic publication, and ledger isolation cases passed. Minor handoff corrections: stale dependency claims and import failures are now qualified as historical, not behavioral RED evidence. Synthetic costs and this closeout do not verify Indodax tariff history, profitability, promotion, or Production activation.
