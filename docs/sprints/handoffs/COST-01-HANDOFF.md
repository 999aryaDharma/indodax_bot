# COST-01 handoff

## Recovery audit addendum (2026-09-23)

The provenance section below is retained as historical source evidence; its claims
are not accepted as current verification. Current audited implementation is on
`fix/feat-01-immutable-params` at code SHA
`627a74c994f29ecffd6e8270a1c459d731c7acd8` (base cost remediation
`a42b242b99c286911c5968ea2f59ce932387ebac`). COST-01 remains REVIEW.

- Corrected handoff's invalid historical code SHA: original implementation is
  `9c9504fc113e79488c73258f6cc93e04fdd56f46`; historical SHA was not used as fresh
  test evidence.
- `lookup_cost` uses `fee_basis_ts`; limit orders bind fees at decision/order-creation
  time, market orders at execution time. Execution, replay sizing, labels, and
  paper/shadow callers have been migrated. Unverified fee schedules block lookup;
  labels exclude those samples.
- Canonical config contains 28 intervals, all `evidence_verified: false`. Fee-source
  evidence is still incomplete, so this config cannot support fee claims or
  promotion. The reviewer independently verified fail-closed behavior on the exact
  code SHA; the external evidence blocker still prevents a status transition.
- TDD: resting-limit boundary test failed before caller migration (`event_ts`
  unexpected keyword); passed after. Unverified-label exclusion test also passes.
- Verification on this exact code SHA: `C:\Users\User\miniconda3\envs\ML\python.exe
  -m pytest -q -p no:cacheprovider` → 998 passed, 2 skipped (Linux `/proc` resource
  smoke and Windows symlink privilege), 3 sklearn `OptimizeWarning`s. Focused COST /
  execution / label / paper suite → 48 passed. `rtk ruff check` on `costs.py` and
  `test_cost_schedule.py` passed; broader touched legacy modules have pre-existing
  lint debt. `git diff --check` passed.
- Independent exact-SHA review: PASS for code/spec quality, no Critical or Important
  findings, by `/root/cost01_independent_review`; targeted reviewer run 11 passed.
  Reviewer did not rerun full suite; full-suite result above is owner evidence. See
  `COST-01-REVIEW.md`.
- External blocker: authoritative, complete fee matrix and effective boundaries
  remain unverified. Do not mark DONE, do not use live fees, and do not enable live
  trading. Public Indodax guidance directs members to the authenticated profile for
  maker/taker buy/sell fee details ([fee menu](https://help.indodax.com/hc/en-us/articles/40043754266265-Where-can-I-find-the-Indodax-Trading-Fee-menu));
  its public fee page documents the tax change and limit-order fee timing
  ([transaction fees](https://help.indodax.com/hc/en-us/articles/4416646599705-Details-of-Transaction-Fees-on-INDODAX)),
  and the public CFX rate change ([CFX update](https://blog.indodax.com/penurunan-biaya-cfx/)).
  These public sources do not disclose the complete account-applicable trading-fee
  matrix for all historical intervals; historical fixtures cannot fill that gap.

Status: REVIEW

## Owner evidence update (2026-09-24)

Owner confirmed the following values were read directly from the INDODAX app's
Trading Fees screen in PRO mode. This is a current observation, not evidence of
the rates' historical effective start dates:

| Market | Side | Maker: service / tax / CFX = all-in | Taker: service / tax / CFX = all-in |
|---|---|---|---|
| IDR | Buy | 0.10% / 0% / 0.0111% = 0.1111% | 0.20% / 0% / 0.0111% = 0.2111% |
| IDR | Sell | 0.10% / 0.21% / 0.0111% = 0.3211% | 0.20% / 0.21% / 0.0111% = 0.4211% |
| USDT | Buy | 0.03% / 0.21% / 0.0222% = 0.2622% | 0.06% / 0.21% / 0.0222% = 0.2922% |
| USDT | Sell | 0.03% / 0.21% / 0.0222% = 0.2622% | 0.06% / 0.21% / 0.0222% = 0.2922% |

The public [INDODAX fee article](https://help.indodax.com/hc/id/articles/4416646599705-Rincian-Biaya-Transaksi-di-INDODAX)
corroborates the fee components, market/side/order-role coverage, PMK 50/2025
tax effective time, and Pro minimum. This owner observation supports current
matrix values only. Prior intervals and the effective start of this exact
matrix remain unverified; keep their schedules fail-closed and COST-01 in REVIEW.

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
