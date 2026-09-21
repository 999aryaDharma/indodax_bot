# Runbook 04: Operator Approval Workflow

## Purpose

This runbook defines the human-in-the-loop operational procedure for trading in `SEMI_AUTOMATED` (or canary manual gating) mode.

In this mode, algorithmic signal generation and risk checks operate automatically, but orders are held in a durable `ManualApprovalStore` until an authorized human operator grants explicit approval with an audit token before the proposal TTL expires.

## Operating Principles

1. **Strict TTL (Time-To-Live):** Every proposal has an immutable TTL (default 300 seconds / 5 minutes). Expired proposals cannot be approved under any circumstances.
2. **Deterministic Token & Audit Trail:** Approvals record the operator ID, timestamp, and justification.
3. **Fail-Closed on Rejection/Expiry:** If an order expires or is rejected, it transitions to a terminal state without venue interaction.

## Step-by-Step Procedure

### 1. Inspect Pending Proposals
List all unexpired pending proposals awaiting human review:
```bash
python -m indodax_lab.cli.approval list --store-path var/approval_store.json
```
Output format:
```json
{
  "count": 1,
  "ok": true,
  "proposals": [
    {
      "created_at": "2026-09-21T06:30:00Z",
      "expires_at": "2026-09-21T06:35:00Z",
      "order": {
        "client_order_id": "clord_btc_idr_20260921_01",
        "desired_qty": "0.005",
        "internal_order_id": "ord_a1b2c3d4",
        "pair": "btc_idr",
        "side": "buy",
        "state": "NEW"
      },
      "proposal_id": "prop_e5f6g7h8",
      "status": "PENDING"
    }
  ],
  "status_filter": "PENDING"
}
```

### 2. Operator Verification Checklist
Before approving, the operator MUST verify:
- [ ] Market order book spread and current top of book price.
- [ ] No major news or exchange maintenance announced.
- [ ] Notional exposure is within authorized personal risk tier.
- [ ] Time remaining before `expires_at` is sufficient.

### 3. Grant Approval
Execute the approval CLI command:
```bash
python -m indodax_lab.cli.approval approve prop_e5f6g7h8 \
  --operator-id "operator_alice" \
  --reason "Reviewed order book spread 0.05%, within tier 1 canary limits" \
  --store-path var/approval_store.json
```
Expected output:
```json
{
  "action": "APPROVED",
  "ok": true,
  "proposal": {
    "decided_at": "2026-09-21T06:31:12Z",
    "decided_by": "operator_alice",
    "decision_reason": "Reviewed order book spread 0.05%, within tier 1 canary limits",
    "proposal_id": "prop_e5f6g7h8",
    "status": "APPROVED"
  }
}
```

Once approved, the pipeline daemon routes the order to the venue adapter (`TradingPipeline.process_approved_proposal()`).

### 4. Reject Proposal
If market conditions have deteriorated or order details look anomalous:
```bash
python -m indodax_lab.cli.approval reject prop_e5f6g7h8 \
  --operator-id "operator_alice" \
  --reason "High spread spike detected" \
  --store-path var/approval_store.json
```

### 5. Cleanup Expired Proposals
Periodically purge or flag stale proposals:
```bash
python -m indodax_lab.cli.approval clean --store-path var/approval_store.json
```
