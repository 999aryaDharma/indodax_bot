# Private read-only integration and OMS phase

Status: **IMPLEMENTED IN CODE / NOT YET VENUE-PROVEN**

Date: 2026-09-21

This phase removes three architectural gaps without granting the bot permission to place
real orders.

## Implemented boundaries

Canonical code lives under `src/indodax_lab/execution/`.

- `IndodaxReadOnlyClient`: signed private account/view access only.
- `PrivateReadOnlyReconciliationService`: fetches account balances, open orders and
  recent fills, then performs fail-closed reconciliation.
- `ReconciliationEngine`: compares venue truth with ledger/order expectations.
- `OmsStateMachine`: deterministic order lifecycle including `UNKNOWN`.
- `OmsStore`: SQLite WAL + FULL synchronous persistence, event journal, integrity hash,
  and optimistic version fencing.
- `normalize_venue_fill`: converts verified quote-fee venue executions into the
  canonical ledger Fill contract.

The read-only client deliberately contains no trade, cancel or withdrawal method.

## Current Indodax API contract used

Verified against official Indodax documentation on 2026-09-21:

- legacy Private REST `POST https://indodax.com/tapi` is used only for current view
  operations such as `getInfo`, `openOrders`, `getOrder`, and
  `getOrderByClientOrderId`;
- authentication uses API key plus HMAC-SHA512 signature over the encoded request;
- historical `tradeHistory` and `orderHistory` legacy methods are not used because
  they were decommissioned on 2026-04-07;
- current history reads use Trade API v2:
  - `GET https://tapi.indodax.com/api/v2/order/histories`;
  - `GET https://tapi.indodax.com/api/v2/myTrades`.

API behavior must be re-verified again before any live release.

## Reconciliation safety rules

A reconciliation cycle requires an explicit fill-history start cursor. There is no
implicit last-N-hours fallback.

New exposure is blocked when, among other things:

- IDR ledger cash differs from venue IDR total beyond reviewed tolerance;
- a tracked base-asset quantity differs from venue balance;
- an internal expected open order is missing at the venue;
- an unexpected venue open order exists;
- venue returns a fill absent from the ledger;
- the account snapshot is stale or has an invalid UTC timestamp;
- the history result saturates its configured limit and completeness is not proven.

A mismatch never edits the ledger and never auto-flattens a position.

## OMS uncertainty contract

The lifecycle is:

~~~text
NEW
 -> SUBMITTING
 -> ACKNOWLEDGED
 -> PARTIALLY_FILLED
 -> FILLED

ACKNOWLEDGED/PARTIALLY_FILLED
 -> CANCEL_PENDING
 -> CANCELLED

SUBMITTING/ACKNOWLEDGED/PARTIALLY_FILLED/CANCEL_PENDING
 -> UNKNOWN
~~~

`UNKNOWN` means the write outcome cannot be safely inferred, for example after a
network timeout occurring after a request may have reached the venue. The order remains
durable across restart and must be resolved from venue evidence before another action.

Blind resubmission from `UNKNOWN` is forbidden.

## Real-fill accounting boundary

For real fills, runtime cost estimates must not overwrite venue evidence.

The initial normalizer accepts a venue commission only when it is denominated in the
ledger valuation currency (IDR) and the venue quote quantity agrees with
`qty * price` within explicit tolerance. A non-IDR commission fails closed until an
audited multi-currency fee valuation path exists.

This prevents silently inventing a conversion rate for a fee paid in another asset.

## What is not proven yet

The code in this phase does **not** mean G5 is passed. Remaining evidence:

1. create a dedicated Indodax API key with view-only permission; trade and withdrawal
   permissions disabled at the exchange;
2. inject the key outside the repository;
3. run private API smoke tests against the designated account;
4. verify actual timestamp/recvWindow, auth failure, rate-limit and outage behavior;
5. capture redacted reconciliation evidence;
6. prove reconciliation restart/cursor behavior over an extended run;
7. verify how every fee/tax component appears in actual venue fill/balance evidence.

No order-write credential is required or permitted for this phase.

## Gate to the next phase

A write-capable venue adapter may be developed behind the OMS only after the read-only
integration is venue-proven. Even then, initial activation remains MANUAL_APPROVAL with
bounded capital and reconciliation after fills.
