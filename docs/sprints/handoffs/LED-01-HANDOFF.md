# LED-01 handoff

Status: REVIEW

## Identity
- Sprint ID: LED-01 — Balanced research postings
- Implementation agent: Antigravity
- Independent reviewer: UNASSIGNED (pending independent review)
- Branch / worktree: `feat/led-01-balanced-research-postings`
- Base SHA: `61735bf`
- Code target: `feat(led-01): balanced research postings`
- Evidence SHA relation: recorded in this handoff

## Files and contracts
- Planned files:
  - `src/indodax_lab/backtest/orders.py` (Fill and execution domain models)
  - `src/indodax_lab/backtest/ledger.py` (Balanced double-entry journal, positions, exact cost basis, equity)
  - `src/indodax_lab/backtest/__init__.py` (Subsystem exports)
  - `tests/unit/lab/backtest/test_ledger.py` (Explicit AC0..AC3 test cases)
  - `tests/property/lab/test_ledger_invariants.py` (Invariants, property tests, COST-01 integration)
- Contract:
  - `Fill -> cash/asset/fee/PnL postings in one valuation currency; quantity tracked separately; Decimal`.
  - Invariant 1: Valued double-entry journal strictly balances: `sum(p.amount for p in tx.postings) == Decimal("0")`.
  - Invariant 2: Base asset quantity tracked separately from quote currency valuation; quantity strictly non-negative.
  - Invariant 3: Equity equals cash plus marked open positions (`equity = cash + sum(pos.base_qty * mark_price)`); already-paid fees are not double-subtracted.
  - Invariant 4: Monotonicity: Higher fees cannot improve/increase fixed-path PnL.
  - Invariant 5: Idempotency: Duplicate fill ID raises `DuplicateFillError` and never duplicates postings or transactions.
- Migration and compatibility:
  - Additive backtest subsystem; backward compatible.
  - Dependencies: COST-01 (REVIEW/DONE), BASE-04 (DONE).

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| LED-01-AC0 (RED) | `test_led_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_ledger.py` | Exit 1 (`NotImplementedError`) | working tree |
| LED-01-AC0 (GREEN) | `test_led_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_valid_contract` | Exit 0 (Passed, validates exact cost basis & postings balance) | working tree |
| LED-01-AC1 (RED) | `test_led_01_contract_1` | `python -m pytest tests/unit/lab/backtest/test_ledger.py` | Exit 1 (`NotImplementedError`) | working tree |
| LED-01-AC1 (GREEN) | `test_led_01_contract_1` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_1` | Exit 0 (Passed, buy partial sell final sell keeps qty nonnegative) | working tree |
| LED-01-AC2 (RED) | `test_led_01_contract_2` | `python -m pytest tests/unit/lab/backtest/test_ledger.py` | Exit 1 (`NotImplementedError`) | working tree |
| LED-01-AC2 (GREEN) | `test_led_01_contract_2` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_2` | Exit 0 (Passed, higher fee cannot increase fixed-path PnL) | working tree |
| LED-01-AC3 (RED) | `test_led_01_contract_3` | `python -m pytest tests/unit/lab/backtest/test_ledger.py` | Exit 1 (`NotImplementedError`) | working tree |
| LED-01-AC3 (GREEN) | `test_led_01_contract_3` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_3` | Exit 0 (Passed, duplicate fill ID does not duplicate postings) | working tree |
| LED-01-INV | `test_ledger_invariants.py` | `python -m pytest tests/property/lab/test_ledger_invariants.py` | Exit 0 (Passed, transaction balance, unit separation, COST-01 integration) | working tree |

All 7 tests in `tests/unit/lab/backtest/test_ledger.py` and `tests/property/lab/test_ledger_invariants.py` passed (0.47s).
Combined suite verification (26 tests across backtest, costs, features) passed (1.68s).

## Review
- Spec verdict: PASS (meets all functional requirements of LED-01 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (zero network, strictly immutable schemas, Decimal precision, exact double-entry balancing).
- Findings: None.
- Self-review: completed by implementation owner (Antigravity).
- Independent review: PENDING (independent reviewer required before state transition to DONE).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for LED-01.
- Next unlocked capabilities: SIM-02 (Portfolio risk and circuit breakers) once SIM-01 is complete.
