# CR-S09 — Tail-risk gate ownership and breach history

Status: PENDING OWNER APPROVAL

## Problem

S09-01 is catalogued as a stateless Strategy/`DecisionFrame` candidate, but its acceptance requires existing exposure to follow an exit policy and a gate reset to preserve historical breaches. `DecisionFrame` has no portfolio/exposure or durable breach-history context. `RiskEngine` is the existing authority for entry gating and kill-switch state; a strategy-local state store or duplicate risk engine would create conflicting authority. The pump-gap producer is also absent.

## Proposed decision

Treat S09-01 as a Research risk-gate capability integrated at the existing RiskEngine boundary, not as an alpha strategy:

- Consume causally available pump-gap and registered `amihud_24_1h` evidence alongside reservation-aware portfolio exposure and a risk-period identity.
- Unknown/stale data or a pump-gap breach blocks new BUY exposure; protective exits and SELL intents remain eligible under the existing risk policy.
- A risk-period reset requires separate explicit operator approval. It starts a new period identity and preserves all prior breach records; it never resets historical losses or edits the prior period.
- Keep Research state, stores, and credentials isolated from Production Main. Do not add a second risk engine or give the candidate order authority.

Thresholds and data-age limits must be frozen in a versioned research policy before implementation. No profitability claim follows from this gate.

## Impact

- Reassign the sprint's owning boundary from `strategies/` to the existing risk authority plus a Research-only durable risk-period record.
- Define typed causal inputs for pump-gap evidence, exposure/reservations, period identity, and breach history. `amihud_24_1h` is already registered; pump-gap production is not.
- Add transaction/restart tests proving old breach records survive reset and new-entry blocking does not disable exits.
- No Production runtime, live account, live order, key, or ledger change is authorized by this CR.

## Validation and rollback

Before implementation, validate the revised owning interface, source/provenance and versioned thresholds; test unknown data, pump breach, exposure and pending reservations, reset authorization, restart durability, preserved history, and exit behavior. If rejected, leave S09-01 READY and retain the current strategy boundary. If accepted but later rolled back, disable only the Research S09 gate and preserve immutable risk-period history.

## Decision

Owner approval: pending.
