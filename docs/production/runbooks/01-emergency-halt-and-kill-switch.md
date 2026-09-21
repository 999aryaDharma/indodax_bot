# Runbook 01: Emergency Halt and Kill Switch Operations

## Purpose

This runbook defines the emergency operational procedure for immediate halts of all trading activities across the Indodax trading bot platform.

## Triggers

An emergency halt MUST be triggered immediately if:
1. An order submission ends in `UNKNOWN` state that cannot be resolved automatically.
2. Reconciliation returns `ReconciliationStatus.HALT_NEW_ORDERS` with unverified balance discrepancy.
3. An unexpected venue order or untracked execution fill is detected on the exchange.
4. System clock regression or NTP synchronization jump exceeds threshold (`CLOCK_UNSAFE`).
5. Excessive slippage or market data anomalies are reported.

## Action Steps

### 1. Trip the Emergency Kill Switch

#### Option A: Filesystem Touch (Preferred Operator Method)
Create the emergency kill switch sentinel file on the node:
```bash
# Linux / macOS
touch /var/run/indodax_bot/emergency_kill_switch

# Windows PowerShell
New-Item -ItemType File -Path ".\emergency_kill_switch" -Force
```

#### Option B: Programmatic Trigger via CLI or Python
```python
from indodax_lab.risk.engine import RiskEngine

risk_engine.trigger_kill_switch(reason="OPERATOR_MANUAL_HALT")
```

### 2. Verify Halting State

1. Confirm that `RiskEngine.is_kill_switch_active` evaluates to `True`.
2. Check that the active `TradingPipeline` step reports:
   - `kill_switch_triggered: True`
   - Any further order intents receive `reason_code: KILL_SWITCH_ACTIVE`.
3. Inspect `oms_orders.sqlite3`:
   ```sql
   SELECT internal_order_id, state, updated_at_utc FROM oms_orders
   WHERE state NOT IN ('FILLED', 'CANCELLED', 'REJECTED');
   ```

### 3. Open Order Handling

1. Do NOT immediately force-cancel without verifying in-flight state.
2. Query the open orders on the venue:
   - Match each internal order with its exchange `order_id`.
   - If in `SUBMITTING` or `CANCEL_PENDING`, resolve via `OrderRouter.resolve_unknown_order`.
3. If safe to cancel all open orders:
   - Execute cancellation through `OrderRouter.cancel_order` for each active order to capture any cancel-fill races.

### 4. Recovery and Disarming

The kill switch MUST NOT be removed until:
1. Root cause is documented in an incident ticket.
2. All non-terminal OMS orders are verified in terminal state (`FILLED`, `CANCELLED`, `REJECTED`).
3. Reconciliation cycle returns `ReconciliationStatus.HEALTHY`.
4. Run:
   ```python
   risk_engine.reset_kill_switch()
   ```
   Or remove the sentinel file:
   ```bash
   rm /var/run/indodax_bot/emergency_kill_switch
   ```
