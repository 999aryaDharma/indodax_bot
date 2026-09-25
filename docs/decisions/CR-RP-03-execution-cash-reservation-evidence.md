# CR-RP-03 — Order-scoped cash reservation evidence

Status: IMPLEMENTED IN RP-03; independent review pending — 2026-09-25

## Problem

The authoritative execution snapshot reports `available_cash` after open-order
reservations. Rechecking an already-approved proposal against that net cash counted
its own reservation twice, while blindly adding the amount in `TradingPipeline`
would manufacture authority evidence and could release cash reserved for another
order.

## Change

- Add an order-ID keyed `cash_reservations` map to `ExecutionSnapshot`. The
  authoritative snapshot producer reports each unfilled order's cash reservation,
  including its fee reserve, and includes the map in the snapshot digest.
- `AuthorityGate` may add back only the reservation keyed to the exact approved BUY
  order. That reservation must cover the approved notional; all other orders remain
  netted from `available_cash`.
- Manual proposal recheck uses the same target reservation evidence and converts
  authoritative Decimal position quantities to the risk engine's position type.
- Missing reservation evidence does not bypass the existing cash gate. Missing
  strategy/stop lineage under an active strategy risk budget remains fail-closed.

## Impact and rollback

This is an additive field in the execution evidence contract. Snapshot digests change
when the reservation map changes. Existing producers that omit it remain valid for
orders whose available cash independently covers the order; fully reserved approvals
must supply the target reservation or remain blocked. No ledger, OMS persistence,
permit lifecycle, accounting rule, or venue authority is widened. Reverting restores
the prior double-count behavior for fully reserved approvals.

## Evidence basis

RP-03 acceptance requires pending exposure and fees to be reserved exactly once. The
independent reviewer identified that the existing `ExecutionSnapshot` did not carry
order-scoped reservation ownership through the final authority gate. The added field
is limited to that missing evidence and does not infer reservations from market data.
