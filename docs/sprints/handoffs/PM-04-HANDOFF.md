# PM-04 handoff

Status: REVIEW

## Identity
- Sprint ID: PM-04 — Venue parser cancellation and supported order semantics
- Implementation agent: Antigravity
- Independent reviewer: PENDING
- Branch / worktree: `docs/architecture-runtime-plan`
- Base SHA: `5229f4f`
- Code target: `feat(pm-04): venue parser cancellation and supported order semantics`
- Code SHA: `692157d`

## Implementation Summary

Verified internal type mapping, supported LIMIT/TIF semantics, and cancel/partial-fill race handling across the execution layer:
1. **Quantity Invariant and Decimal Normalization (`src/indodax_lab/execution/indodax_readonly.py`)**:
   - Invariant (PM-04-FR0 / AC0): `VenueOrder.__post_init__` validates that `original_qty`, `executed_qty`, and `remaining_qty` are finite Decimal instances, `original_qty > 0`, non-negative execution quantities, and enforces strict conservation of quantity: `original_qty == executed_qty + remaining_qty`. Fails closed with `VenueProtocolError("VENUE_ORDER_QUANTITY_INCONSISTENT:...")` on mismatch.
   - Normalizes `status` to uppercase and `order_type` to lowercase.

2. **Inconclusive Cancel Handling (`src/indodax_lab/execution/indodax_trading.py` & `src/indodax_lab/execution/order_router.py`)**:
   - Inconclusive Cancel (PM-04-FR1 / AC1): If venue cancel acknowledges success (`{"success": 1}`), but post-cancel lookup (`getOrder`) fails or is inconclusive, `IndodaxTradingVenue` raises `UncertainVenueSubmissionError("CANCEL_ACKNOWLEDGED_BUT_STATE_INCONCLUSIVE:...")`.
   - `OrderRouter.cancel_order` catches uncertainty and transitions the OMS order to `OmsOrderState.UNKNOWN` with reason `CANCEL_UNCERTAIN`. Subsequent `resolve_unknown_order()` with inconclusive lookup keeps the order definitively in `UNKNOWN` and never synthesizes a fake cancelled state.

3. **Fill/Cancel Race Handling (`src/indodax_lab/execution/order_router.py`)**:
   - Race Invariant (PM-04-FR2 / AC2): In `OrderRouter.cancel_order()`, when venue returns a partially filled cancelled order (`0 < executed_qty < desired_qty`), OMS records `PARTIALLY_FILLED` with exact executed quantity and fill price before transitioning to `CANCELLED`, preserving the partial fill. If the order was completely filled before cancel took effect, OMS transitions directly to `FILLED`, never inventing a zero fill.

4. **Supported Order and TIF Pre-Transport Validation (`src/indodax_lab/execution/indodax_trading.py` & `src/indodax_lab/execution/order_router.py`)**:
   - Pre-transport Check (PM-04-FR3 / AC3): `IndodaxTradingVenue.submit_order()` and `OrderRouter.submit_order()` (when configured for production venue via `enforce_production_semantics`) reject unsupported order semantics (e.g. non-limit orders like `market`, or non-GTC time-in-force like `IOC` / `FOK`, or missing/non-positive limit price) before making any HTTP request or mutating OMS state, raising `ValueError` matching `UNSUPPORTED_ORDER_SEMANTICS` and `ORDER_LIMIT_PRICE_REQUIRED`. Zero HTTP requests are dispatched to the exchange.

## Files and contracts
- Planned files:
  - `src/indodax_lab/execution/indodax_readonly.py` (Quantity conservation invariant and type assertions in `VenueOrder.__post_init__`)
  - `src/indodax_lab/execution/indodax_trading.py` (Fail-closed inconclusive cancel handling and pre-transport order semantics validation)
  - `src/indodax_lab/execution/order_router.py` (Pre-flight supported order semantics validation, cancel uncertainty routing, and fill/cancel race handling)
  - `tests/unit/lab/execution/test_venue_semantics_contract.py` (Comprehensive AC0–AC3 test suite)

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| PM-04-AC0 (GREEN) | `test_pm_04_0` | `pytest tests/unit/lab/execution/test_venue_semantics_contract.py::test_pm_04_0` | Exit 0 (Passed, original equals executed plus remaining in declared units; inconsistent quantities rejected) | `692157d` |
| PM-04-AC1 (GREEN) | `test_pm_04_1` | `pytest tests/unit/lab/execution/test_venue_semantics_contract.py::test_pm_04_1` | Exit 0 (Passed, cancel acknowledgement plus inconclusive lookup stays UNKNOWN; unhandled status raises UnresolvedOrderStateError) | `692157d` |
| PM-04-AC2 (GREEN) | `test_pm_04_2` | `pytest tests/unit/lab/execution/test_venue_semantics_contract.py::test_pm_04_2` | Exit 0 (Passed, partial fill or full fill during cancel race preserves executed quantity, never invents zero fill) | `692157d` |
| PM-04-AC3 (GREEN) | `test_pm_04_3` | `pytest tests/unit/lab/execution/test_venue_semantics_contract.py::test_pm_04_3` | Exit 0 (Passed, unsupported order types and TIFs rejected before transport with 0 HTTP calls) | `692157d` |

Focused suite: 4 passed in 0.89s.
Full test suite: 990 passed, 2 skipped, 3 warnings in 31.07s.
Lint check: `ruff check` passed cleanly (exit 0).
Diff check: `git diff --check` passed cleanly (exit 0).

## Review
- Independent Reviewer: PENDING
- Verdict: PENDING

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: None.
- Next unlocked capabilities: RP-05.
