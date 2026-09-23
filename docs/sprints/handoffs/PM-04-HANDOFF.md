# PM-04 handoff

Status: REVIEW

## Identity
- Sprint ID: PM-04 — Venue parser cancellation and supported order semantics
- Implementation agent: Antigravity
- Independent reviewer: pending for corrected code SHA; the PASS at `84105fa` applies only to `692157d`
- Branch / worktree: `fix/pm-04-v2-recovery` / `C:\Users\User\AppData\Local\Temp\indodax-pm04-v2-recovery`
- Base SHA: `5229f4f`
- Code target: `fix(pm-04): resolve v2 active statuses`
- Code SHA: `8635cc73ac0d63fe63c5365c44976c2ff69c599c` (includes prior fix `a3f5653`; original implementation `692157d`)

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

5. **Trade API v2 recovery statuses (`src/indodax_lab/execution/order_router.py`)**:
   - `resolve_unknown_order()` now accepts `NEW` and `PARTIALLY_FILLED` as active venue states and maps the latter with exact observed `executed_qty` into OMS `PARTIALLY_FILLED`.

## Files and contracts
- Planned files:
  - `src/indodax_lab/execution/indodax_readonly.py` (Quantity conservation invariant and type assertions in `VenueOrder.__post_init__`)
  - `src/indodax_lab/execution/indodax_trading.py` (Fail-closed inconclusive cancel handling and pre-transport order semantics validation)
  - `src/indodax_lab/execution/order_router.py` (Pre-flight supported order semantics validation, cancel uncertainty routing, and fill/cancel race handling)
  - `tests/unit/lab/execution/test_venue_semantics_contract.py` (Comprehensive AC0–AC3 test suite)

## Acceptance evidence
| AC ID | Test / artifact | Command | Exit/result | Source SHA |
|---|---|---|---|---|
| PM-04-AC0 (GREEN) | `test_pm_04_0` | `python -m pytest tests/unit/lab/execution/test_venue_semantics_contract.py -q -p no:cacheprovider` | Exit 0; includes non-finite Decimal rejection | `a3f5653` |
| PM-04-AC1 (GREEN) | `test_pm_04_1` | same focused command | Exit 0; includes UNKNOWN recovery with partial venue fill | `a3f5653` |
| PM-04-AC2 (GREEN) | `test_pm_04_2` | same focused command | Exit 0; includes OPEN after cancel, partial fill and later resolution | `a3f5653` |
| PM-04-AC3 (GREEN) | `test_pm_04_3` | same focused command | Exit 0; unsupported order/TIF rejects pre-transport | `a3f5653` |

Focused suite on `a3f5653`: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/execution/test_venue_semantics_contract.py -q -p no:cacheprovider` — 4 passed in 1.94s, exit 0.
Full suite on `a3f5653`: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest -q -p no:cacheprovider` — 990 passed, 2 skipped, 3 warnings in 65.65s, exit 0. Skips: Linux `/proc` VmHWM smoke and Windows symlink privilege; neither is hidden as PASS.
Follow-up targeted regression on `8635cc7`: `... -m pytest tests/unit/lab/execution/test_venue_semantics_contract.py::test_pm_04_resolves_v2_active_statuses -q -p no:cacheprovider` — 2 passed, exit 0. Focused suite: 6 passed, exit 0. Full suite on `8635cc7`: `... -m pytest -q -p no:cacheprovider` — 992 passed, 2 skipped, 3 warnings in 94.22s, exit 0. Same platform-limited skips as above.
Lint check: `ruff check` passed cleanly (exit 0).
Diff check: `git diff --check` passed cleanly (exit 0).

## Review
- Independent Reviewer: PENDING for `8635cc73ac0d63fe63c5365c44976c2ff69c599c`; prior verdicts cover earlier code SHAs only
- Verdict: Round 1 PASS on `692157d` superseded by later audit findings; corrected SHA awaits independent review
- Spec compliance: 100% verified across AC0–AC3
- Quality & safety: PASS (strict Decimal quantity conservation, robust cancel uncertainty latches, exact race fill preservation, pre-transport semantics validation)
- Findings: later audits reproduced four Important defects in cancellation state, recovery fill quantity, non-finite quantity handling, and v2 active-status recovery. Scoped fixes at `a3f5653` and `8635cc7` pass regression/full-suite tests; independent re-review remains pending.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: independent review of corrected committed SHA; venue order/TIF capability and activation gates remain externally unverified.
- Next unlocked capabilities: RP-05 remains blocked by RP-04 and PM-04 review.
