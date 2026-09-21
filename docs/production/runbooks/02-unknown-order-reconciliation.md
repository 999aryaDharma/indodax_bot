# Runbook 02: UNKNOWN Order Resolution and In-Flight Recovery

## Purpose

This runbook defines the authoritative procedure for resolving orders left in the `UNKNOWN` state in the Order Management System (OMS).

## The Invariant

> **Strict Non-Negotiable Rule:** Blind retries or guesses on `UNKNOWN` orders are strictly forbidden. An order in `UNKNOWN` state can ONLY transition based on definitive venue evidence.

## What Causes `UNKNOWN` State?

1. **Post-write Network Drop / ReadTimeout:** The bot sends an order write request to Indodax, but the transport disconnects before the HTTP 200 response with `order_id` is received.
2. **Server HTTP 500 / 502 / 504 Gateway Errors:** The exchange processed the order or partially executed it, but replied with an error code.
3. **Cancel-Write Uncertainty:** Cancel was sent, but network failed before confirmation.

## Resolution Procedure

### 1. Identify Non-Terminal / UNKNOWN Orders

Inspect the SQLite database:
```sql
SELECT internal_order_id, client_order_id, venue_order_id, state, version, updated_at_utc
FROM oms_orders
WHERE state = 'UNKNOWN';
```

### 2. Query Exchange Truth via Read-Only Client

Use `OrderRouter.resolve_unknown_order`:
```python
from indodax_lab.execution.oms_store import OmsStore
from indodax_lab.execution.order_router import OrderRouter
from indodax_lab.execution.indodax_trading import IndodaxTradingVenue

oms_store = OmsStore("data/oms_orders.sqlite3")
venue = IndodaxTradingVenue(api_key=KEY, secret_key=SECRET)
router = OrderRouter(oms_store=oms_store, venue=venue)

order = oms_store.load_order("target_internal_order_id")
resolved_order = router.resolve_unknown_order(order)
print(f"Order {resolved_order.internal_order_id} resolved to: {resolved_order.state}")
```

### 3. Resolution Matrix

| Exchange Evidence | Target OMS State | Action Taken |
| :--- | :--- | :--- |
| **Order found: Status 'open'** | `ACKNOWLEDGED` | Bind `venue_order_id`, supervise for future fills. |
| **Order found: Status 'filled'** | `FILLED` | Journal executions into `ResearchLedger` via `VenueFillIngester`. |
| **Order found: Status 'cancelled'** | `CANCELLED` | Check for partial fills, update executed quantity. |
| **Order NOT found (by client_order_id or venue_id)** | `REJECTED` | Confirm order never hit matching engine; record reason `RESOLVED_NOT_FOUND_ON_VENUE`. |
| **Exchange API unreachable / 503** | Remain `UNKNOWN` | Halt new orders, wait for exchange status recovery. |

### 4. Post-Resolution Verification

Run an immediate reconciliation cycle:
```python
report = reconciliation_service.run(...)
assert report.healthy, f"Reconciliation failed after resolving order: {report.issues}"
```
Advance the durable reconciliation cursor only after `HEALTHY` status is verified.
