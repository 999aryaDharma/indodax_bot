# LED-01 independent review

Status: CHANGES_REQUESTED on Round 1; reviewed content SHA `e93575e55a059ebc4afab0558f92694676d651d3` (HEAD). Maximum five rounds; history preserved below.

## Identity

- Sprint ID: LED-01 — Balanced research postings
- Implementation owner: Antigravity
- Independent reviewer: Antigravity (Independent Reviewer subagent `871561c9`)
- Reviewed SHA: `e93575e55a059ebc4afab0558f92694676d651d3`
- Audit/base SHA: `61735bf`
- Branch: `docs/architecture-runtime-plan`
- Scope: Double-entry research ledger, positions, exact cost basis, order fills, unit separation, and property invariants
- Round: 1

## Formal verdicts

- Spec verdict: PASS
- Quality verdict: CHANGES_REQUESTED (blocked by exit code 1 on Ruff lint quality gate)
- Overall verdict: CHANGES_REQUESTED

## Findings summary

| Finding | Severity | Location | Failure mechanism | Reproduction | Required regression | Status |
|---|---|---|---|---|---|---|
| F-01: Ruff lint gate failures | Important | `orders.py`, `ledger.py`, `test_ledger.py`, `test_ledger_invariants.py` | 13 lint errors (UP035 deprecated `typing.Mapping`, UP037 unnecessary quote in type annotation, F401 unused imports, I001 unsorted import blocks). Ruff check exits with code 1. | `python -m ruff check src/indodax_lab/backtest/orders.py src/indodax_lab/backtest/ledger.py tests/unit/lab/backtest/test_ledger.py tests/property/lab/test_ledger_invariants.py` | Run `ruff check --fix` and ensure `ruff check` exits with code 0 across all scoped files. | OPEN (Blocks DONE) |
| F-02: Intermediate Decimal division before multiplication causes precision residual | Minor | `src/indodax_lab/backtest/ledger.py:287` | `(fill.qty / pos.base_qty) * pos.cost_basis` divides first; for non-terminating decimals (e.g. 1/3), 28-digit context rounding produces `1E-25` residual basis. `(fill.qty * pos.cost_basis) / pos.base_qty` avoids premature truncation. | Buy 3 @ 1000 IDR, sell 1. `pos.cost_basis` becomes `2000.000000000000000000000000`, `total_realized_gross_pnl` shows `1E-25`. | Reorder arithmetic to `(fill.qty * pos.cost_basis) / pos.base_qty`. | OPEN (Disposition: fix in Round 2) |
| F-03: `_total_net_pnl` internal attribute is shadowed and diverges on buy fees | Minor | `src/indodax_lab/backtest/ledger.py:108, 232, 296, 341` | `self._total_net_pnl` is updated on SELL but not decremented on BUY fees (`next_fees += fee` does not touch `next_net_pnl`). The public `@property def total_net_pnl` calculates `_total_realized_gross_pnl - _total_fees_paid` correctly, leaving the internal attribute dead/inconsistent. | Inspect `ledger._total_net_pnl` vs `ledger.total_net_pnl` after buy with fees. | Remove unused `_total_net_pnl` attribute or maintain consistency in BUY branch. | OPEN (Disposition: cleanup in Round 2) |
| F-04: Test suite lacks explicit negative test cases for invalid Fill inputs | Minor | `tests/unit/lab/backtest/test_ledger.py` | While `Fill` Pydantic validators properly reject negative/zero qty, negative price, negative fees, and naive timestamps with `ValueError`, no unit test in `test_ledger.py` explicitly tests these validation boundaries. | Code review inspection of test suite. | Add test cases asserting `ValueError` for negative qty, negative price, negative fees, and naive timestamps. | OPEN (Disposition: add tests in Round 2) |

## Independent verification evidence

### Acceptance criteria verification

| AC ID | Description | Independent command | Exit / Result | Spec status |
|---|---|---|---|---|
| LED-01-AC0 | Balanced double-entry postings (sum == 0), exact cost basis, Decimal precision | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_valid_contract -v` | Exit 0 (Passed, 0.40s) | OBSERVED_PASS |
| LED-01-AC1 | Buy partial/sell sequence: base quantity stays non-negative throughout | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_1 -v` | Exit 0 (Passed, 0.40s) | OBSERVED_PASS |
| LED-01-AC2 | Higher fee cannot increase fixed-path PnL (monotonicity) | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_2 -v` | Exit 0 (Passed, 0.40s) | OBSERVED_PASS |
| LED-01-AC3 | Duplicate fill ID raises `DuplicateFillError`, never duplicates postings | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_3 -v` | Exit 0 (Passed, 0.40s) | OBSERVED_PASS |
| LED-01-INV1 | Property invariant: transaction balance across multi-pair, multi-trade paths | `python -m pytest tests/property/lab/test_ledger_invariants.py::test_transaction_balance_invariant -v` | Exit 0 (Passed, 0.43s) | OBSERVED_PASS |
| LED-01-INV2 | Property invariant: unit separation (crypto units vs quote currency) & ADR-002 equity formula | `python -m pytest tests/property/lab/test_ledger_invariants.py::test_unit_separation_and_equity_invariant -v` | Exit 0 (Passed, 0.43s) | OBSERVED_PASS |
| LED-01-INV3 | Property invariant: COST-01 integration (YAML schedules + `lookup_cost` -> Fill fees -> Ledger) | `python -m pytest tests/property/lab/test_ledger_invariants.py::test_cost_schedule_integration -v` | Exit 0 (Passed, 0.43s) | OBSERVED_PASS |
| LED-01-STATE | Checkpointing & serialization roundtrip, fail-closed tamper detection | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_ledger_state_roundtrip_preserves_balanced_history tests/unit/lab/backtest/test_ledger.py::test_ledger_state_tamper_fails_closed -v` | Exit 0 (Passed, 0.40s) | OBSERVED_PASS |

### Full-suite regression check

- Command: `python -m pytest -q`
- Result: Exit 0 (966 passed, 2 skipped platform symlinks, 3 sklearn warnings in 39.54s)
- Confirmation: Zero regressions introduced across backtest, execution, control plane, data, or models.

### Code quality and lint gate

- Command: `python -m ruff check src/indodax_lab/backtest/orders.py src/indodax_lab/backtest/ledger.py tests/unit/lab/backtest/test_ledger.py tests/property/lab/test_ledger_invariants.py`
- Result: **Exit 1** (13 errors found, all fixable with `--fix`)
  - `src/indodax_lab/backtest/ledger.py`: 2 errors (UP035 `typing.Mapping`, UP037 unneeded quotes on `"ResearchLedger"`)
  - `src/indodax_lab/backtest/orders.py`: 2 errors (UP035 `typing.Mapping`, F401 unused `pydantic.model_validator`)
  - `tests/property/lab/test_ledger_invariants.py`: 6 errors (I001 import ordering, F401 unused `pytest`, `CostScheduleTable`, `AccountType`, `DuplicateFillError`, `InsufficientQuantityError`)
  - `tests/unit/lab/backtest/test_ledger.py`: 3 errors (I001 import ordering, F401 unused `AccountType`, `Posting`)

### Independent negative case testing

The following negative boundary tests were executed independently against the implementation:

1. **Negative quantity**: `Fill(..., qty=Decimal("-1"))`
   - Result: Raised `pydantic.ValidationError` with `POSITIVE_DECIMAL_REQUIRED` (PASS).
2. **Zero quantity**: `Fill(..., qty=Decimal("0"))`
   - Result: Raised `pydantic.ValidationError` with `POSITIVE_DECIMAL_REQUIRED` (PASS).
3. **Negative price**: `Fill(..., price=Decimal("-100"))`
   - Result: Raised `pydantic.ValidationError` with `POSITIVE_DECIMAL_REQUIRED` (PASS).
4. **Negative fee**: `Fill(..., fees=Decimal("-1"))`
   - Result: Raised `pydantic.ValidationError` with `NON_NEGATIVE_FEE_REQUIRED` (PASS).
5. **Naive / non-UTC timestamp**: `Fill(..., timestamp=datetime(2024, 1, 1))`
   - Result: Raised `pydantic.ValidationError` with `UTC_TIMEZONE_AWARE_REQUIRED:timestamp` (PASS).
6. **Sell exceeding current position (empty)**: `ledger.process_fill(sell_fill)` when held qty is 0
   - Result: Raised `InsufficientQuantityError: INSUFFICIENT_BASE_QUANTITY` (PASS).
7. **Sell exceeding current position (partial)**: held 2.0, sell 2.5
   - Result: Raised `InsufficientQuantityError: INSUFFICIENT_BASE_QUANTITY`, position remained exactly 2.0 (PASS).
8. **Equity with missing mark price**: `ledger.equity({})` when holding open position
   - Result: Raised `ValueError: MISSING_MARK_PRICE` (PASS).
9. **Equity with non-positive mark price**: `ledger.equity({"btc_idr": Decimal("-10")})`
   - Result: Raised `ValueError: INVALID_MARK_PRICE` (PASS).
10. **Multi-trade sequence with varying prices**: Verified 2 buys at different prices followed by 2 partial sells closing the position. All cash balances, position quantities, cost bases, realized gross PnL, total fees paid, and marked equity matched exact manual calculation (PASS).

## Required remediation for Round 2

1. **Fix F-01 (Blocking)**:
   - Run `ruff check --fix` on `src/indodax_lab/backtest/orders.py`, `src/indodax_lab/backtest/ledger.py`, `tests/unit/lab/backtest/test_ledger.py`, and `tests/property/lab/test_ledger_invariants.py`.
   - Remove unused imports and format import blocks so that `python -m ruff check ...` exits 0.
2. **Fix F-02**:
   - In `src/indodax_lab/backtest/ledger.py:287`, update:
     `allocated_basis = (fill.qty * pos.cost_basis) / pos.base_qty`
3. **Fix F-03**:
   - Either remove `self._total_net_pnl` (since the property dynamically computes `_total_realized_gross_pnl - _total_fees_paid`) or decrement `next_net_pnl -= fee` in the BUY branch.
4. **Fix F-04**:
   - Add unit tests in `tests/unit/lab/backtest/test_ledger.py` asserting `ValueError` for negative quantity, negative price, negative fees, and naive timestamps.

Once these scoped fixes are committed, submit the new commit SHA for Round 2 independent review.
