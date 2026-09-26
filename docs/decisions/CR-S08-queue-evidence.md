# CR-S08 — Queue evidence and promotion boundary

Status: ACCEPTED — owner approved boundary and 5-second Research freshness default on 2026-09-27.

## Problem

S08-01 is listed as a strategy sprint, but it requires observed queue evidence to qualify promotion and durable partial-cancel accounting. `ConservativeExecutionSimulator` currently models causal maker fills from bars and participation, while the TLOB `QueueFillModel` estimates fill probability from configured inputs; neither establishes point-in-time queue position for a given quote. The canonical research feature registry does not publish a queue-evidence contract. Treating a heuristic probability as observed queue evidence would overstate promotion readiness.

## Proposed decision

Define a versioned `lob_queue_v1` research contract at the execution/promotion boundary:

- LOB trigger inputs carry pair, event/availability UTC timestamps, session ID, sequence continuity, book imbalance/depth and spread.
- Queue evidence carries explicit known/unknown status, `queue_ahead_base_qty`, observation timestamp, source identity and model/contract version.
- Missing, stale, future-dated, or sequence-invalid queue evidence makes that simulated sample `QUEUE_UNAVAILABLE` and blocks promotion. The strategy may emit an intent only when its market-data gates pass; it cannot mark a fill successful.
- Partial fill/cancel remains owned by existing OMS/ledger reconciliation. Tests must prove filled quantity, remaining quantity, released reservation and ledger balance from real shared components; do not implement a strategy-local ledger.

Freshness uses an explicit versioned Research policy with a default maximum evidence age of 5 seconds, measured from `observed_at` to decision/quote time. Missing policy or evidence remains fail-closed. The default does not qualify a producer or establish real queue coverage; S08 promotion remains blocked until a qualified producer supplies evidence. A model-estimated queue fill probability is labeled as a model estimate, never observed queue state.

## Impact

- Add an exact versioned queue-data contract to the research feature contract and promotion evidence.
- S08 implementation/tests span the strategy intent, shared simulator, and promotion/ledger acceptance boundaries.
- Real Indodax queue reconstruction and book/trade history coverage remain external qualification gates.
- No Production, live order, account, credential, or running-host changes are authorized.

## Validation and rollback

Before implementation, approve the exact queue fields, unknown/freshness behavior and promotion status. Test valid queue observations, unknown/stale/future/sequence-gap rejection, quote touch without fill, partial cancellation with balanced ledger, and promotion rejection without queue evidence. Rollback disables only `lob_queue_v1` S08 qualification while retaining raw immutable data and prior reports.

## Decision

Owner approval: boundary and 5-second Research default accepted on 2026-09-27. The versioned `QueueEvidencePolicy` defaults `max_evidence_age_seconds` to 5; age is measured from `observed_at` at decision/quote time. Unknown or evidence older than 5 seconds blocks promotion. The policy still pins source identity and approval reference; real queue reconstruction and coverage remain external qualification gates. Partial-cancel accounting remains in the existing OMS/ledger.
