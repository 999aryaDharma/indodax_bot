# Runbook 01: Routine Reconciliation Operations

## Purpose

This runbook defines the standard operating procedure for routine, durable reconciliation between Indodax exchange truth and the internal double-entry ledger.

Reconciliation is fail-closed: any unresolved discrepancy immediately halts new order submissions.

## Frequency and Timing

- **Routine Cadence:** Run every 1 to 5 minutes in production daemon or at end-of-day rebalance cycles.
- **Triggered Cadence:** Mandatory immediately after order fills, system restart, or ungraceful failover.

## Tooling

The canonical CLI entrypoint is:
```bash
python -m indodax_lab.cli.reconcile --scope-id indodax_main --pairs btc_idr,eth_idr --cursor-db var/reconciliation_cursor.db --auto-ingest
```

Environment variables required for live private API access:
```bash
export INDODAX_VIEW_API_KEY="..."
export INDODAX_VIEW_SECRET_KEY="..."
```
*(Note: Use read-only view API credentials. Zero withdrawal or trade permissions required for read-only reconciliation.)*

## Step-by-Step Procedure

### 1. Initialize Cursor (First Run Only)
If the reconciliation cursor is not yet initialized in the SQLite database:
```bash
# Initialize cursor to 1 hour ago in milliseconds (e.g. 1774160000000)
python -m indodax_lab.cli.reconcile \
  --scope-id indodax_main \
  --pairs btc_idr,eth_idr \
  --cursor-db var/reconciliation_cursor.db \
  --init-cursor-ms 1774160000000
```

### 2. Execute Reconciliation Cycle
```bash
python -m indodax_lab.cli.reconcile \
  --scope-id indodax_main \
  --pairs btc_idr,eth_idr \
  --cursor-db var/reconciliation_cursor.db \
  --auto-ingest
```

### 3. Evaluate Result

- **Exit Code 0 (`status: "HEALTHY"`):**
  All invariants hold:
  - Cash discrepancy is within tolerance.
  - Tracked asset positions match exchange balances exactly.
  - Expected open orders match active exchange orders.
  - All venue fills are accounted for in ledger.
  - Cursor revision has advanced forward safely.
  System is clear to continue trading.

- **Exit Code 1 (`status: "HALT_NEW_ORDERS"`):**
  Discrepancy detected! Review the `issues` list:
  - `IDR_CASH_DISCREPANCY_EXCEEDS_TOLERANCE`: Escalate to [Runbook 03: Balance Mismatch Investigation](03-balance-mismatch-investigation.md).
  - `BASE_BALANCE_DISCREPANCY_EXCEEDS_TOLERANCE`: Asset balance mismatch.
  - `UNEXPECTED_VENUE_OPEN_ORDER`: Manual or phantom order on venue.
  - `MISSING_VENUE_OPEN_ORDER`: Order filled or canceled outside tracking.
  - `VENUE_FILL_NOT_IN_LEDGER`: Fill missing from internal ledger.

- **Exit Code 2 (`status: "BLOCKED_EXTERNAL"`):**
  Credentials missing or venue endpoint unreachable. Trading cannot proceed until private connectivity is restored.

### 4. Rollback and Remediation
If reconciliation remains un-healthy:
1. Trip the emergency kill switch:
   ```bash
   python -m indodax_lab.cli.kill_switch trip --reason "RECONCILIATION_FAILURE"
   ```
2. Inspect `var/reconciliation_cursor.db` and log outputs.
3. Verify no unmanaged trades were manually executed on the Indodax web UI.
