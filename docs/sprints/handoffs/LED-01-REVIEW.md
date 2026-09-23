# LED-01 independent review

Status: PASS on Round 2; reviewed content SHA `4933dcb7fd99a14dfac175cfb2eabab7424a8fcf` (docs update SHA `2773d9e`). Maximum five rounds; history preserved below.

## Identity

- Sprint ID: LED-01 — Balanced research postings
- Implementation owner: Antigravity
- Independent reviewer: Antigravity Independent Reviewer
- Reviewed SHA (Round 1): `e93575e55a059ebc4afab0558f92694676d651d3`
- Reviewed SHA (Round 2): `4933dcb7fd99a14dfac175cfb2eabab7424a8fcf`
- Audit/base SHA: `61735bf`
- Branch: `docs/architecture-runtime-plan`
- Scope: Double-entry research ledger, positions, exact cost basis, order fills, unit separation, and property invariants
- Round: 2

## Formal verdicts

- Spec verdict: PASS
- Quality verdict: PASS
- Overall verdict: PASS

## Findings summary

| Finding | Severity | Location | Failure mechanism | Reproduction | Required regression | Status |
|---|---|---|---|---|---|---|
| F-01: Ruff lint gate failures | Important | `orders.py`, `ledger.py`, `test_ledger.py`, `test_ledger_invariants.py` | 13 lint errors (UP035 deprecated `typing.Mapping`, UP037 unnecessary quote in type annotation, F401 unused imports, I001 unsorted import blocks). Ruff check exits with code 1. | `python -m ruff check src/indodax_lab/backtest/orders.py src/indodax_lab/backtest/ledger.py tests/unit/lab/backtest/test_ledger.py tests/property/lab/test_ledger_invariants.py` | Run `ruff check --fix` and ensure `ruff check` exits with code 0 across all scoped files. | RESOLVED (Round 2 verified clean, exit code 0) |
| F-02: Intermediate Decimal division before multiplication causes precision residual | Minor | `src/indodax_lab/backtest/ledger.py:287` | `(fill.qty / pos.base_qty) * pos.cost_basis` divides first; for non-terminating decimals (e.g. 1/3), 28-digit context rounding produces `1E-25` residual basis. `(fill.qty * pos.cost_basis) / pos.base_qty` avoids premature truncation. | Buy 3 @ 1000 IDR, sell 1. `pos.cost_basis` becomes `2000.000000000000000000000000`, `total_realized_gross_pnl` shows `1E-25`. | Reorder arithmetic to `(fill.qty * pos.cost_basis) / pos.base_qty`. | RESOLVED (Round 2 verified reordered calculation) |
| F-03: `_total_net_pnl` internal attribute is shadowed and diverges on buy fees | Minor | `src/indodax_lab/backtest/ledger.py:108, 232, 296, 341` | `self._total_net_pnl` is updated on SELL but not decremented on BUY fees (`next_fees += fee` does not touch `next_net_pnl`). The public `@property def total_net_pnl` calculates `_total_realized_gross_pnl - _total_fees_paid` correctly, leaving the internal attribute dead/inconsistent. | Inspect `ledger._total_net_pnl` vs `ledger.total_net_pnl` after buy with fees. | Remove unused `_total_net_pnl` attribute or maintain consistency in BUY branch. | RESOLVED (Round 2 dead attribute cleaned up, dynamic property active) |
| F-04: Test suite lacks explicit negative test cases for invalid Fill inputs | Minor | `tests/unit/lab/backtest/test_ledger.py` | While `Fill` Pydantic validators properly reject negative/zero qty, negative price, negative fees, and naive timestamps with `ValueError`, no unit test in `test_ledger.py` explicitly tests these validation boundaries. | Code review inspection of test suite. | Add test cases asserting `ValueError` for negative qty, negative price, negative fees, and naive timestamps. | RESOLVED (Round 2 added `test_fill_negative_boundary_validation`) |

## Round 2 independent verification evidence

### Acceptance criteria verification

| AC ID | Description | Independent command | Exit / Result | Spec status |
|---|---|---|---|---|
| LED-01-AC0 | Balanced double-entry postings (sum == 0), exact cost basis, Decimal precision | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_valid_contract -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-AC1 | Buy partial/sell sequence: base quantity stays non-negative throughout | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_1 -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-AC2 | Higher fee cannot increase fixed-path PnL (monotonicity) | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_2 -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-AC3 | Duplicate fill ID raises `DuplicateFillError`, never duplicates postings | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_led_01_contract_3 -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-INV1 | Property invariant: transaction balance across multi-pair, multi-trade paths | `python -m pytest tests/property/lab/test_ledger_invariants.py::test_transaction_balance_invariant -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-INV2 | Property invariant: unit separation (crypto units vs quote currency) & ADR-002 equity formula | `python -m pytest tests/property/lab/test_ledger_invariants.py::test_unit_separation_and_equity_invariant -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-INV3 | Property invariant: COST-01 integration (YAML schedules + `lookup_cost` -> Fill fees -> Ledger) | `python -m pytest tests/property/lab/test_ledger_invariants.py::test_cost_schedule_integration -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-STATE | Checkpointing & serialization roundtrip, fail-closed tamper detection | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_ledger_state_roundtrip_preserves_balanced_history tests/unit/lab/backtest/test_ledger.py::test_ledger_state_tamper_fails_closed -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |
| LED-01-NEG | Fill negative boundary input validation | `python -m pytest tests/unit/lab/backtest/test_ledger.py::test_fill_negative_boundary_validation -v` | Exit 0 (Passed, 0.38s) | OBSERVED_PASS |

### Code quality and lint gate

- Command: `python -m ruff check src/indodax_lab/backtest/orders.py src/indodax_lab/backtest/ledger.py tests/unit/lab/backtest/test_ledger.py tests/property/lab/test_ledger_invariants.py`
- Result: **Exit 0** (All checks passed!)

### Full-suite regression check

- Command: `python -m pytest -q`
- Result: **Exit 0** (972 passed, 2 skipped platform symlinks, 3 sklearn warnings in 27.60s)
- Confirmation: Zero regressions across backtest, execution, control plane, data, or models.

### Independent negative case testing

All 5 schema negative boundaries and operational boundaries re-verified:
1. Negative quantity rejected by `Fill` with `POSITIVE_DECIMAL_REQUIRED` (PASS)
2. Zero quantity rejected by `Fill` with `POSITIVE_DECIMAL_REQUIRED` (PASS)
3. Negative price rejected by `Fill` with `POSITIVE_DECIMAL_REQUIRED` (PASS)
4. Negative fee rejected by `Fill` with `NON_NEGATIVE_FEE_REQUIRED` (PASS)
5. Naive timestamp rejected by `Fill` with `UTC_TIMEZONE_AWARE_REQUIRED:timestamp` (PASS)
6. Selling more than held quantity raises `InsufficientQuantityError` (PASS)
7. Equity computation with missing/negative mark prices raises `ValueError` (PASS)
8. Ledger serialization roundtrip and tamper detection fails closed (PASS)

---

## Round 1 Historical Record

<details>
<summary>Round 1 Review Details (SHA: e93575e)</summary>

- Spec verdict: PASS
- Quality verdict: CHANGES_REQUESTED (blocked by exit code 1 on Ruff lint quality gate)
- Overall verdict: CHANGES_REQUESTED
- Round 1 findings: F-01 (Important), F-02 (Minor), F-03 (Minor), F-04 (Minor)
- Required remediation:
  1. Fix F-01: Run `ruff check --fix`, clean up imports.
  2. Fix F-02: Reorder arithmetic to `(fill.qty * pos.cost_basis) / pos.base_qty`.
  3. Fix F-03: Clean up dead `_total_net_pnl` attribute.
  4. Fix F-04: Add explicit negative boundary unit tests in `test_ledger.py`.
</details>
