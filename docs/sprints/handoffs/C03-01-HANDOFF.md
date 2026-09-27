# C03-01 handoff

Status: REVIEW

## Identity
- Sprint ID: C03-01 — Time series momentum
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/c03-01-time-series-momentum`
- Base SHA: `678a873`
- Code target: `feat(c03-01): time series momentum`
- Evidence SHA relation: `1f28c723a73ffde02113585f1280b3a00126559d`

## Files and contracts
- Planned files:
  - `src/indodax_lab/strategies/c03.py` (load_c03_specification, c03_decide)
  - `src/indodax_lab/strategies/__init__.py` (Package exports)
  - `configs/strategies/C03_v1.yaml` (Canonical C03 configuration)
  - `tests/unit/lab/strategies/test_c03.py` (Explicit AC0..AC3 test cases)
- Contract:
  - `Positive historical multi-horizon return plus trend filter -> versioned LONG/FLAT intent, never direct orders.`
  - Stateless decision function over causal `DecisionFrame`; long-only spot intents (`BUY` / `SELL`, positive desired qty).
  - Multi-horizon momentum rule: all configured lookbacks (`horizons_bars`, e.g., [12, 24, 72]) must exhibit positive return (`close - past_close > 0`).
  - Non-positive return on any horizon immediately gates/abstains from buy intent.
  - Insufficient history (rows < max(horizons_bars) + 1) strictly abstains (FLAT / empty intents).
  - Volatility-adjusted sizing via ATR stop distance.
  - Strategies only produce declarative order intents (`SignalIntent`); zero authority over fills, executions, or ledger balances.
- Migration and compatibility:
  - Additive classical strategies catalog; backward compatible.
  - Dependencies: STRAT-01 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| C03-01-AC0 (RED) | `test_c03_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c03.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C03-01-AC0 (GREEN) | `test_c03_01_valid_contract` | `python -m pytest tests/unit/lab/strategies/test_c03.py::test_c03_01_valid_contract` | Exit 0 (Passed, produces valid BUY SignalIntent with ATR stop) | `1f28c72` |
| C03-01-AC1 (RED) | `test_c03_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c03.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C03-01-AC1 (GREEN) | `test_c03_01_contract_1` | `python -m pytest tests/unit/lab/strategies/test_c03.py::test_c03_01_contract_1` | Exit 0 (Passed, non-positive return rejects buy) | `1f28c72` |
| C03-01-AC2 (RED) | `test_c03_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c03.py` | Exit 0 (Initial pass / returns empty) | `working tree` |
| C03-01-AC2 (GREEN) | `test_c03_01_contract_2` | `python -m pytest tests/unit/lab/strategies/test_c03.py::test_c03_01_contract_2` | Exit 0 (Passed, insufficient history abstains) | `1f28c72` |
| C03-01-AC3 (RED) | `test_c03_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c03.py` | Exit 1 (Failed: assert 0 == 1) | `working tree` |
| C03-01-AC3 (GREEN) | `test_c03_01_contract_3` | `python -m pytest tests/unit/lab/strategies/test_c03.py::test_c03_01_contract_3` | Exit 0 (Passed, positive momentum across all horizons emits LONG intent) | `1f28c72` |

All 4 tests in `tests/unit/lab/strategies/test_c03.py` passed (1.01s).
Full lab test suite verification (80+ passing across backtest, risk, execution, ledger, costs, features, labels, strategies, and evaluation).

## Review
- Spec verdict: PASS (meets all functional requirements of C03-01 and specs/10-strategy-catalog-and-protocol.md).
- Quality verdict: PASS (pure stateless decision protocol, zero ledger mutation, strict multi-horizon momentum gating, and causality enforcement).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for C03-01.
- Next unlocked consumers: QA-01.

## Current remediation evidence

- Corrective implementation SHA: `a543e5942d9d28ba955f4d872fce3ed4ce1ef144` (initial implementation source remains `1f28c723a73ffde02113585f1280b3a00126559d`).
- Targeted command: `C:/Users/User/miniconda3/envs/ML/python.exe -m pytest tests/unit/lab/strategies/test_c03.py -q` — 8 passed.
- Targeted lint: `C:/Users/User/miniconda3/envs/ML/python.exe -m ruff check src/indodax_lab/strategies/c03.py tests/unit/lab/strategies/test_c03.py` — passed.
- Added regression coverage for invalid ATR, nonpositive/nonfinite prices, an interior hourly gap, stale decision rows, and positive momentum with zero realized volatility.
- Independent review of corrective SHA: pending.

## Delta re-review of the corrective SHA — closes this (2026-09-27)

- Second corrective commit surfaced by review: `f33a86e20313c32c2edceb056dff73d2d5f249e9`
  (timestamp-precision normalization before gap math) — also ancestor of HEAD;
  both corrective commits reviewed together.
- Verdict: **DELTA-PASS**, independent reviewer opencode session
  `ses_f1d0016f1ffePWl2xK1iRr4ysE` (read-only, wrote no code) at HEAD
  `577e5d498a8977734b569c14961c45972ff39820`. Full diff inspected: momentum
  window completeness, hourly-gap/stale-row/look-ahead refusal,
  nonpositive/nonfinite price refusal, invalid-ATR refusal, zero-volatility
  and nonpositive-momentum cash fallback, spec-parameter fail-closed raise —
  all fail-closed (abstain to cash, no intent emitted). No Critical/Important
  findings; no contract change.
- Fresh evidence in review env (Python 3.14.0 / pytest 9.0.3 / pandas 2.3.3):
  `test_c03.py` **9 passed** exit 0 (the "8 passed" above was the a543e59-era
  count; the 9th test arrived with f33a86e); `tests/unit/lab/strategies/`
  **168 passed** exit 0; `tests/unit/lab` **1457 passed** exit 0.
- Capability gap: ruff not installed in review env — the conda-env ruff claim
  above is unverifiable here, recorded as a capability gap, not a failure.
- Minor backlog: over-indented `stop_loss=` kwarg at
  `src/indodax_lab/strategies/c03.py:144` (cosmetic).
