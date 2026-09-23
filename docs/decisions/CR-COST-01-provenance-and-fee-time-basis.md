# CR-COST-01 — Verified schedule provenance and fee time basis

Status: ACCEPTED FOR AUDIT REMEDIATION — 2026-09-23

## Problem

The COST-01 lookup returns numeric schedules whose historical source evidence is incomplete, indistinguishable from verified schedules. Its `event_ts` argument also does not say whether fee validity is selected by order creation or execution. Indodax states that a limit order created before a fee change retains the prior fee even when executed later.

## Change

- Add an explicit `evidence_verified` flag to each interval, defaulting to false. Resolution of an unverified interval fails closed with `UNVERIFIED_COST_SCHEDULE`.
- Rename lookup time input to `fee_basis_ts`. Callers must use the order-created timestamp for limit orders and the execution timestamp for market orders, according to the applicable venue rule.
- Preserve all existing YAML rates as unverified assumptions until their full component values, effective boundaries, and sources are reviewed. Do not infer missing historical facts.
- Add independently expected exact-rate AC0 evidence using a self-contained reviewed contract fixture; separately assert the canonical unverified schedule is blocked.

## Impact and rollback

This is an additive validation field and an intentional keyword API rename. Repository search found no runtime consumers of `lookup_cost`; tests are the only callers. The default prevents accidental use of unverified YAML. Reverting the scoped code commit restores the prior API but also removes this safety gate; do not revert while unverified schedule data remains reachable.

No frozen system boundary, trading authority, data identity, accounting rule, or activation gate changes. Research/paper only; this request does not authorize private venue access or real orders. Historical schedule completion remains blocked pending complete authoritative fee-component evidence.

## Evidence basis

- INDODAX transaction fee guidance: `https://help.indodax.com/hc/en-us/articles/4416646599705-Details-of-Transaction-Fees-on-INDODAX` (tax changes and limit-order fee retention by order creation time).
- This CR is limited to making the existing COST-01 contract fail closed and explicit; it does not certify any schedule values.
