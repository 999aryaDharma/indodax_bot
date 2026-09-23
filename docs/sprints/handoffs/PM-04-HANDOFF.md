# PM-04 handoff

Status: DONE

## Identity
- Sprint ID: PM-04 — Venue parser cancellation and supported order semantics
- Implementation agent: Antigravity
- Independent reviewer: `/root/pm04_independent_review` — PASS on exact code SHA `97746dd61e285b6711519c73e6b153d599bcfbb5`
- Branch / worktree: `fix/pm-04-v2-recovery` / `C:\Users\User\AppData\Local\Temp\indodax-pm04-v2-recovery`
- Base SHA: `5229f4f`
- Code target: `fix(pm-04): reject inconsistent fill state`
- Code SHA: `97746dd61e285b6711519c73e6b153d599bcfbb5` (includes prior fixes `a3f5653`, `8635cc7`, and `46e51ef`; original implementation `692157d`)

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
   - `resolve_unknown_order()` recognizes `NEW` and `PARTIALLY_FILLED`; unseen execution quantities are not adopted until authoritative trade history is ingested. Existing OMS VWAP is preserved rather than using the order limit price.
   - Cancel/recovery reports with `FILLED`/`FINISHED` but incomplete or regressing executed quantity remain `UNKNOWN` instead of fabricating a full fill.

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
Follow-up targeted regressions on `97746dd`: 16 PM-04 execution/recovery tests passed; focused PM-04 suite: 6 passed. Full suite: 993 passed, 2 skipped, 3 warnings in 76.83s, exit 0. Same platform-limited skips as above. Lint and `git diff --check` passed.
Lint check: `ruff check` passed cleanly (exit 0).
Diff check: `git diff --check` passed cleanly (exit 0).

## Review
- Independent Reviewer: `/root/pm04_independent_review` — PASS for `97746dd61e285b6711519c73e6b153d599bcfbb5`; review was code/spec read-only and did not rerun tests
- Verdict: PASS on exact corrected code SHA; superseded earlier findings fixed and independently re-reviewed
- Spec compliance: 100% verified across AC0–AC3
- Quality & safety: PASS (strict Decimal quantity conservation, robust cancel uncertainty latches, exact race fill preservation, pre-transport semantics validation)
- Findings: follow-up reviews found that order limit price was misused as fill VWAP and `FILLED` status could contradict executed quantity. Fixes at `46e51ef` and `97746dd` keep uncertain fills unresolved and require exact fill-history reconciliation; both findings independently PASS on the final SHA.

## Deviations and known risks
- Deviations: None.
- Unresolved issues / blockers: venue order/TIF capability and activation gates remain externally unverified; PM-04 DONE is not production activation approval.
- Next unlocked capabilities: RP-05 remains blocked by RP-04 and PM-04 review.
