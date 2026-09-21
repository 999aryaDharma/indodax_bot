# Runbook 03: Emergency Kill Switch Operations

## Purpose

This runbook provides unambiguous instructions to immediately stop all automated order routing and cancel outstanding exposure across the Indodax trading platform.

## Triggers

Activate the emergency kill switch when:
1. Critical balance or position discrepancy detected during reconciliation.
2. Market data feed reports invalid timestamps, severe clock skew, or stale prices.
3. Multiple consecutive order submissions result in `UNKNOWN` state.
4. Drawdown limit or risk loss ceiling breached.
5. Operator discovers anomalous account activity on the exchange.

## Step-by-Step Procedure

### 1. Trip the Kill Switch

#### Option A: Operator CLI (Recommended)
```bash
python -m indodax_lab.cli.kill_switch trip --reason "OPERATOR_EMERGENCY_HALT"
```

#### Option B: Filesystem Sentinel
Touch the sentinel file directly:
```bash
# Linux / macOS
touch emergency_kill_switch

# Windows PowerShell
New-Item -ItemType File -Path ".\emergency_kill_switch" -Force
```

### 2. Verify Halting State
Check the kill switch status via CLI:
```bash
python -m indodax_lab.cli.kill_switch status
```
Expected output:
```json
{
  "details": "HALTED:OPERATOR_EMERGENCY_HALT:...",
  "kill_switch_active": true,
  "ok": true,
  "sentinel_path": "emergency_kill_switch"
}
```

The `RiskEngine` will now reject 100% of incoming order intents with reason code:
`KILL_SWITCH_ACTIVE`.

### 3. Handle Active & In-Flight Orders
1. Inspect active orders in OMS:
   ```sql
   SELECT internal_order_id, client_order_id, pair, state, venue_order_id
   FROM oms_orders
   WHERE state IN ('SUBMITTING', 'ACKNOWLEDGED', 'PARTIALLY_FILLED', 'CANCEL_PENDING');
   ```
2. Request immediate cancellation through `OrderRouter.cancel_order()` or exchange web UI if API is impaired.
3. Record all cancel acknowledgments in OMS.

### 4. Disarming the Kill Switch
Before clearing the kill switch, the operator MUST verify:
- [ ] Root cause of the halt has been identified and resolved.
- [ ] All pending `UNKNOWN` orders have been resolved.
- [ ] Reconciliation returns `status: "HEALTHY"` with zero discrepancies.
- [ ] No unhedged or unrecorded open positions exist.

To disarm:
```bash
python -m indodax_lab.cli.kill_switch clear
```
Confirm disarm status:
```bash
python -m indodax_lab.cli.kill_switch status
```
