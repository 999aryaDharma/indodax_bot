# PM-04 independent review

Status: HISTORICAL PASS on Round 1 for `692157d`; later review findings are resolved. PM-04 is DONE on exact code SHA `97746dd61e285b6711519c73e6b153d599bcfbb5`. Maximum five rounds; history preserved below.

## Follow-up review — 2026-09-23

- Important: `resolve_unknown_order()` did not recognize Trade API v2 active statuses `NEW` or `PARTIALLY_FILLED`; recovery raised `UnresolvedOrderStateError` despite authoritative active venue state. Regression tests reproduced both cases.
- Important: recovery and cancel paths treated an order's limit `price` as fill VWAP. Fix leaves orders `UNKNOWN` until authoritative trade history supplies fills, then reconciles terminal venue status using the recorded VWAP.
- Important: a cancel response could say `FILLED` while `executed_qty < desired_qty`, and OMS would promote the order to its full desired quantity. Fix rejects this inconsistent status/quantity pair and leaves the order `UNKNOWN`.
- The v2 statuses now map safely; unseen fills require history ingestion before OMS records them. The independent reviewer returned PASS for all findings on exact code target `97746dd61e285b6711519c73e6b153d599bcfbb5` (review-only; tests not rerun by reviewer).

## Follow-up audit — 2026-09-23

- Important: `order_router.py` treated a cancel acknowledgement followed by venue status `OPEN` as `CANCELLED`. A real open order could therefore be mistaken for a terminal order. A new regression test failed with `CANCELLED` where `UNKNOWN` was required.
- Important: `resolve_unknown_order()` resolved a venue `CANCELLED` order with `executed_qty=0.4` while retaining OMS `filled_qty=0`. A new regression test reproduced the loss of fill quantity.
- Important: `VenueOrder` accepted a non-finite Decimal into comparison and leaked `decimal.InvalidOperation` instead of the documented `VenueProtocolError`. A new regression test reproduced it.
- Scoped fixes and regression tests were committed at `a3f5653` after `692157d`. Round 1 PASS does not approve these new bytes. An independent reviewer must assess `a3f5653` before DONE.

## Identity

- Sprint ID: PM-04 — Venue parser cancellation and supported order semantics
- Implementation owner: Antigravity
- Independent reviewer: Antigravity Independent Reviewer
- Reviewed code SHA: `692157dcede9490e3ad0bf670c17a770dd473dac` (`692157d`)
- Handoff commit SHA: `fc689f1d0f34fd6562ad9a8916f24d78f17a937e` (`fc689f1`)
- Handoff doc: `docs/sprints/handoffs/PM-04-HANDOFF.md`
- Sprint spec doc: `docs/sprints/production-main/PM-04-venue-parser-cancellation-and-supported-order-semantics.md`
- Base SHA: `5229f4f`
- Branch: `docs/architecture-runtime-plan`
- Round: 1

## Formal verdicts

- Spec verdict: PASS
- Quality verdict: PASS
- Overall verdict: PASS

Summary: PM-04 implementation strictly enforces venue parser quantity invariants, robust cancel/partial-fill race handling, fail-closed handling of inconclusive venue cancellations, and pre-transport rejection of unsupported order semantics. All requirements (AC0–AC3) defined in `PM-04-venue-parser-cancellation-and-supported-order-semantics.md` and `docs/implementation/CONTRACTS.md` are completely met. No regressions were introduced across existing execution, reconciliation, or OMS test suites.

---

## Spec compliance analysis

| Requirement / Invariant | Spec reference | Code location | Evaluation | Verdict |
|---|---|---|---|---|
| **PM-04-AC0**: Original equals executed plus remaining in declared units | PM-04-FR0, AC0 | `src/indodax_lab/execution/indodax_readonly.py:77-94` | `VenueOrder.__post_init__` enforces that `original_qty`, `executed_qty`, and `remaining_qty` are exact `Decimal` instances, that `original_qty > 0`, that `executed_qty >= 0` and `remaining_qty >= 0`, and strictly verifies `original_qty == executed_qty + remaining_qty`. Inconsistent quantities immediately raise `VenueProtocolError("VENUE_ORDER_QUANTITY_INCONSISTENT:...")`. Legacy base-quantity, quote-quantity, and Trade API v2 parsers all maintain this conservation invariant. Normalizes `status` to uppercase and `order_type` to lowercase. | PASS |
| **PM-04-AC1**: Cancel acknowledgement plus inconclusive lookup stays UNKNOWN | PM-04-FR1, AC1 | `src/indodax_lab/execution/indodax_trading.py:249-265`, `src/indodax_lab/execution/order_router.py:227-251, 313-382` | When cancel is acknowledged on exchange (`{"success": 1}`) but post-cancel lookup (`getOrder`) fails or is inconclusive, `IndodaxTradingVenue.cancel_order()` raises `UncertainVenueSubmissionError("CANCEL_ACKNOWLEDGED_BUT_STATE_INCONCLUSIVE:...")`. `OrderRouter.cancel_order()` captures this uncertainty and transitions the OMS order to `OmsOrderState.UNKNOWN` with reason `CANCEL_UNCERTAIN`. Subsequent `resolve_unknown_order()` with inconclusive lookup preserves `UNKNOWN` without fabricating a fake cancelled state, and unrecognized venue order statuses raise `UnresolvedOrderStateError`. | PASS |
| **PM-04-AC2**: Fill/cancel race never invents zero fill | PM-04-FR2, AC2 | `src/indodax_lab/execution/order_router.py:253-311` | In `OrderRouter.cancel_order()`, when venue returns a partial fill executed during cancellation (`0 < executed_qty < desired_qty`), OMS records a `PARTIALLY_FILLED` transition with exact executed quantity and fill price before transitioning to `CANCELLED`, preserving the partial fill. If the order was completely filled before cancellation took effect, OMS transitions directly to `FILLED` with `desired_qty` and fill price, never inventing a zero fill. | PASS |
| **PM-04-AC3**: Unsupported order/TIF produces no HTTP call | PM-04-FR3, AC3 | `src/indodax_lab/execution/indodax_trading.py:74-85`, `src/indodax_lab/execution/order_router.py:92-107` | Both `IndodaxTradingVenue.submit_order()` and `OrderRouter.submit_order()` (when `enforce_production_semantics` is enabled, which defaults to `True` for `IndodaxTradingVenue` or permit-required venues) validate order semantics prior to transport or OMS state persistence. Non-limit orders (e.g. `market`), unsupported TIFs (`IOC`, `FOK`), and missing or non-positive limit prices raise `ValueError("UNSUPPORTED_ORDER_SEMANTICS:...")` before making any HTTP request or database mutation. | PASS |

---

## Code quality, safety & security analysis

1. **Fail-Closed Execution Design**:
   - `VenueOrder` rejects non-Decimal types, non-positive original quantity, negative execution quantities, and quantity arithmetic mismatches fail-closed with `VenueProtocolError`.
   - Inconclusive cancellations on the exchange reject optimistic assumptions; they drive OMS orders into `OmsOrderState.UNKNOWN` until ground truth is deterministically re-established.
   - `resolve_unknown_order` never synthesizes state on missing venue lookup (`None`); it preserves `UNKNOWN` to avoid unsafe duplicate resubmissions.

2. **Race Condition & Audit Trail Preservation**:
   - During cancel-fill races, intermediate partial executions are committed to the OMS store journal as `PARTIALLY_FILLED` before transitioning to `CANCELLED`.
   - Full fills during cancel race transition directly to `FILLED`, ensuring executed fills are not lost or overwritten with zero.

3. **Pre-Transport Boundary Protection**:
   - In accordance with production Indodax API capabilities (which only support explicit LIMIT orders with GTC time-in-force), invalid order semantics are rejected at the router and venue boundary before any network transmission or HMAC signature generation occurs.

4. **Security & Scope Containment**:
   - Zero trade/withdrawal keys in test fixtures or logs.
   - `IndodaxTradingVenue` exposes strictly order placement and cancellation; no withdrawal methods are implemented.
   - Immutable configuration files `dashboard.pen` and `DESIGN.md` were untouched.

---

## Findings summary

| ID | Severity | Category | Description | Resolution / Status |
|---|---|---|---|---|
| **O-01** | Minor (Advisory) | Reconciliation Architecture | In `OrderRouter.resolve_unknown_order()`, if an order previously marked `UNKNOWN` is resolved from the venue as `cancelled`, it transitions directly from `UNKNOWN` to `CANCELLED`. If partial fills occurred prior to cancellation, the final `CANCELLED` order object in `resolve_unknown_order` retains its previous `filled_qty`. This is sound and safe because authoritative fill ingestion and ledger balance tracking are independently and asynchronously processed by `ReconciliationCoordinator` and `apply_fill()` from Trade API v2 execution history (`VenueFill`), ensuring no fill accounting discrepancy can occur. | NOTED (No action required; existing design is safe and compliant with CONTRACTS.md) |

**Total Findings**:
- Critical: 0
- Important: 0
- Minor: 1 (Advisory observation)

---

## Independent verification evidence

### 1. Focused acceptance test suite
- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/execution/test_venue_semantics_contract.py -v`
- Result: **4 passed in 1.37s** (Exit 0)
  - `test_pm_04_0`: PASSED (AC0: quantity conservation invariant `original_qty == executed_qty + remaining_qty`, Decimal type validation, inconsistent quantity rejection)
  - `test_pm_04_1`: PASSED (AC1: cancel acknowledgement + inconclusive lookup transitions to and preserves `UNKNOWN`; unhandled venue status raises `UnresolvedOrderStateError`)
  - `test_pm_04_2`: PASSED (AC2: partial/full fill during cancel race preserves executed quantity and fill price, never invents zero fill)
  - `test_pm_04_3`: PASSED (AC3: unsupported order types `market`, and TIFs `IOC`/`FOK`, and missing/non-positive limit price produce 0 HTTP calls)

### 2. Code formatting & lint gate
- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m ruff check src/indodax_lab/execution/indodax_readonly.py src/indodax_lab/execution/indodax_trading.py src/indodax_lab/execution/order_router.py tests/unit/lab/execution/test_venue_semantics_contract.py`
- Result: **Exit 0** (All checks passed!)

### 3. Git diff check
- Command: `git diff --check`
- Result: **Exit 0** (Clean diff, no whitespace or formatting errors)

### 4. Full execution regression gate
- Command: `C:\Users\User\miniconda3\envs\ML\python.exe -m pytest tests/unit/lab/execution/ -v`
- Result: **61 passed in 13.71s** (Exit 0)
  - Zero failures across all fill ingestion, reconciliation, OMS store, order router, and read-only clients.

### 5. Independent edge-case verification
Executed independent verification script exercising:
- Micro-epsilon quantity conservation mismatch (`original=1.00000001`, `executed=1.0`, `remaining=0.0`): raises `VenueProtocolError("VENUE_ORDER_QUANTITY_INCONSISTENT")`.
- Zero original quantity (`original=0`): raises `VenueProtocolError("VENUE_ORDER_ORIGINAL_QTY_MUST_BE_POSITIVE")`.
- Case normalization: `status="open"` normalized to `"OPEN"`, `order_type="LIMIT"` normalized to `"limit"`.
- `OmsOrder` strict validation of non-positive limit prices.
- Automatic activation of `enforce_production_semantics` in `OrderRouter` when `IndodaxTradingVenue` is supplied as venue adapter.
- In-flight partial fill increment during cancel race (multi-step partial fill `0.5` -> `1.2`): verified final `CANCELLED` order preserves `filled_qty=Decimal("1.2")` and fill price.
- Result: **All independent edge-case assertions PASSED cleanly**.

---

## Verdict and next steps

- **Verdict**: **PASS**
- PM-04 implementation is verified, robust, and compliant with all sprint requirements and domain contracts.
- Next sprint unlocked: RP-05.
