# LED-01 handoff

Status: REVIEW (Round 2 pending independent approval)

## Identity
- Sprint ID: LED-01 — Balanced research postings
- Implementation agent: Antigravity
- Independent reviewer: Antigravity Independent Reviewer (subagent `871561c9` Round 1 CHANGES_REQUESTED)
- Branch / worktree: `docs/architecture-runtime-plan`
- Base SHA: `61735bf`
- Code target: `feat(led-01): balanced research postings`
- Code SHA (Round 1): `e93575e`
- Remediation SHA (Round 2): `4933dcb`

## Round 2 Remediation Summary

Remediated all findings from Round 1 review (`docs/sprints/handoffs/LED-01-REVIEW.md`):
- **F-01 (Important, FIXED)**: Fixed all 13 ruff lint errors across scoped files (UP035, UP037, F401, I001); `ruff check` exits 0.
- **F-02 (Minor, FIXED)**: Reordered cost basis division: `(fill.qty * pos.cost_basis) / pos.base_qty` in `ledger.py:287`.
- **F-03 (Minor, FIXED)**: Cleaned up dead `_total_net_pnl` attribute in `ledger.py` in favor of dynamic `total_net_pnl` property.
- **F-04 (Minor, FIXED)**: Added negative boundary unit tests for `Fill` validation (negative/zero qty, price, fees, naive datetime) in `test_ledger.py`.

## Files and contracts
- Planned files:
  - `src/indodax_lab/backtest/orders.py` (Fill and execution domain models)
  - `src/indodax_lab/backtest/ledger.py` (Balanced double-entry journal, positions, exact cost basis, equity)
  - `src/indodax_lab/backtest/__init__.py` (Subsystem exports)
  - `tests/unit/lab/backtest/test_ledger.py` (Explicit AC0..AC3 test cases + negative boundary tests)
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
| LED-01-AC0 (GREEN) | `test_led_01_valid_contract` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_valid_contract` | Exit 0 (Passed, validates exact cost basis & postings balance) | `4933dcb` |
| LED-01-AC1 (GREEN) | `test_led_01_contract_1` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_1` | Exit 0 (Passed, buy partial sell final sell keeps qty nonnegative) | `4933dcb` |
| LED-01-AC2 (GREEN) | `test_led_01_contract_2` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_2` | Exit 0 (Passed, higher fee cannot increase fixed-path PnL) | `4933dcb` |
| LED-01-AC3 (GREEN) | `test_led_01_contract_3` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_3` | Exit 0 (Passed, duplicate fill ID does not duplicate postings) | `4933dcb` |
| LED-01-INV | `test_ledger_invariants.py` | `python -m pytest tests/property/lab/test_ledger_invariants.py` | Exit 0 (Passed, transaction balance, unit separation, COST-01 integration) | `4933dcb` |
| LED-01-NEG | `test_fill_negative_boundary_validation` | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_fill_negative_boundary_validation` | Exit 0 (Passed, validates all 5 negative boundary conditions) | `4933dcb` |

All 10 tests in `tests/unit/lab/backtest/test_ledger.py` and `tests/property/lab/test_ledger_invariants.py` passed (0.51s).
Ruff lint: all checks passed (exit 0).
Full suite: 972 passed, 2 skipped, 0 failed in 34.47s.

## Review
- Spec verdict: PASS (meets all functional requirements of LED-01 and specs/08-costs-ledger-and-execution.md).
- Quality verdict: PASS (Ruff clean exit 0, exact decimal precision, negative boundaries tested).
- Round 1 independent review: CHANGES_REQUESTED (subagent `871561c9`).
- Round 2 independent review: PENDING (remediation committed at `4933dcb`).

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None for LED-01.
- Next unlocked capabilities: SIM-02 (Portfolio risk and circuit breakers) once SIM-01 is complete.
