# CR-C11 — Simulator cash context for volatility allocation

Status: ACCEPTED — owner approved on 2026-09-26.

## Problem

C11 inverse-volatility allocation must size pair intents against the simulator's available IDR cash. `DecisionFrame` currently carries no cash context, and sourcing live account balances would violate Research isolation.

## Decision

- Add optional `available_cash_idr: Decimal | None` to `DecisionFrame`; existing callers remain compatible.
- Only the research simulator may supply the value, representing unreserved IDR cash as of the decision. No live account or Production ledger source is permitted.
- C11 abstains when cash is absent or zero. It allocates no more than 50% of supplied cash, with a 25% of cash per-pair cap; fewer than two valid volatility candidates yields no trade.
- The simulator/capital owner remains responsible for supplying a causally correct, reservation-aware cash snapshot. Strategies do not own cash or order authority.

## Impact

This extends a shared Python strategy input contract. Keep the new field optional and append it to constructors/factories to preserve existing positional callers. Test missing, valid Decimal, and invalid values. Update C11's sprint contract before implementation.

No persistence, Production, live trading, or external venue behavior changes.

## Validation and rollback

Validate through contract and C11 tests. Rollback removes the optional field and C11 version; existing callers and strategy versions remain unchanged.
