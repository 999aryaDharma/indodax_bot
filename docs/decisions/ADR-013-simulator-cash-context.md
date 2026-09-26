# ADR-013 — Simulator cash context in DecisionFrame

Status: ACCEPTED — 2026-09-26

## Context

C11 requires simulator-available capital to emit candidate-sized intents. Strategies must remain isolated from Production account state and must not own ledger or reservation authority.

## Decision

`DecisionFrame` may carry optional `available_cash_idr: Decimal | None`. A Research simulator caller supplies a finite, nonnegative Decimal representing unreserved IDR cash at the frame's `as_of`. `None` means unavailable, never zero by implication. The strategy layer validates the representation but cannot establish freshness or reservation correctness; that remains the simulator caller's contract. Live account/Production ledger sources are prohibited.

The field is appended as an optional argument to preserve existing constructors and factories. Non-C11 strategies ignore it. C11 abstains if it is absent or zero.

## Consequences

- Shared strategy frame contract changes; all callers remain source-compatible.
- Simulator orchestration must explicitly pass cash before C11 can produce intents.
- This field grants no capital reservation, fill, ledger, or order authority.

## Rejected alternatives

- Read cash from a live/Production account: violates frozen Research isolation.
- Embed a simulator or ledger dependency in C11: reverses dependency direction and makes the strategy impure.
- Fixed quantity: does not satisfy candidate-sized capital allocation.
