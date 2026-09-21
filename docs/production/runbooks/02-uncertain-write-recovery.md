# Runbook 02: Uncertain-Write Recovery Operations

## Purpose

This runbook defines the operational protocol when an order submission or order cancellation results in an `UNKNOWN` state due to network timeouts, exchange drops, or crash recovery.

In institutional spot trading, **blind retries are strictly forbidden** because retrying an order whose request actually reached the exchange results in double execution and unhedged exposure.

## Triggers

1. Order submission request raises `TimeoutError` or socket reset during HTTP POST.
2. Order state in `oms_orders` is `OmsOrderState.UNKNOWN`.
3. Process crashes while an order was in `SUBMITTING` or `CANCEL_PENDING` state.

## Step-by-Step Procedure

### 1. Identify the Uncertain Order
Inspect the persistent OMS order store:
```sql
SELECT internal_order_id, client_order_id, pair, side, desired_qty, state, version, updated_at
FROM oms_orders
WHERE state = 'UNKNOWN';
```

Note the `client_order_id` (e.g. `clord_btc_idr_20260921_abc123`).

### 2. Query Exchange Truth by `client_order_id`
Execute query against Indodax Private API using the deterministic client order identifier:
```python
from indodax_lab.execution.order_router import OrderRouter

# Router automatically probes venue by client_order_id
resolved_order = router.resolve_unknown_order(internal_order_id)
```

The router executes the following logic:
- If venue returns the order with state `open`:
  Updates OMS state: `UNKNOWN` → `ACKNOWLEDGED` with venue order ID.
- If venue returns the order with state `filled`:
  Updates OMS state: `UNKNOWN` → `FILLED` with filled quantity and average price.
- If venue returns order NOT FOUND (`ORDER_NOT_FOUND`):
  Updates OMS state: `UNKNOWN` → `REJECTED` (confirming order never existed on book).

### 3. Automated Disaster Drill Invariant
Ensure that the recovery procedure obeys the deterministic state machine rules:
- An order in `UNKNOWN` state **cannot transition directly** to `NEW` or be re-submitted with the same ID.
- Any fill reported by the venue must be ingested through `VenueFillIngester` into `ResearchLedger`.

### 4. Post-Resolution Verification
1. Confirm zero `UNKNOWN` orders remain:
   ```sql
   SELECT count(*) FROM oms_orders WHERE state = 'UNKNOWN';
   ```
2. Run a full reconciliation cycle:
   ```bash
   python -m indodax_lab.cli.reconcile --scope-id indodax_main --pairs btc_idr,eth_idr
   ```
3. Resume normal trading pipeline if reconciliation returns `HEALTHY`.
