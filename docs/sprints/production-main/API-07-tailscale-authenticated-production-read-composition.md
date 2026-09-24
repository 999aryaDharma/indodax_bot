# API-07 — Tailscale-authenticated Production read composition

> Implement this sprint only. Connect the read-only API to the existing Production-owned Indodax client; never create trading authority.

**Goal:** Authenticate allow-listed Tailscale operators and compose the real Indodax view-only provider for Production reads.

**Architecture:** An explicit runtime composition reads the existing server-side view-only environment variables, validates Production namespace/state root, wraps `IndodaxReadOnlyClient` as the marked `VenueAccountProvider`, and injects a principal resolver that trusts Tailscale Serve identity headers only behind the loopback proxy boundary. Only `production.read` is granted.

**Tech Stack:** Existing Python/FastAPI/Pydantic/IndodaxReadOnlyClient; no new dependencies.

**Spec:** [CR](../../decisions/CR-20260924-production-dashboard-auth.md), [ADR-011](../../decisions/ADR-011-tailscale-operator-identity.md).

## Metadata

Status: REVIEW

Priority: P0 | Type: security | Domain: production-main | Portfolio: CORE

Implementation Owner: `/root` | Independent Reviewer: PENDING

Recommended Branch: feat/api-05-tailscale-production-read

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: M

## Goal

Serve Production dashboard read models from the existing Indodax view-only client only to authenticated, allow-listed operators.

## Why This Sprint Exists

API-02 exposes read routes but has no production composition/provider or trusted operator resolver. Indodax credentials and operator identity are separate trust boundaries.

## Depends On

- API-02 — Read-only Production API application and routes
- API-03 — Fail-closed read capability policy and audit context

## Unlocks

API-04, UI-03

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/implementation/CONTRACTS.md`
- `docs/decisions/CR-20260924-production-dashboard-auth.md`
- `docs/decisions/ADR-011-tailscale-operator-identity.md`
- `src/indodax_lab/api/app.py`
- `src/indodax_lab/api/auth.py`
- `src/indodax_lab/execution/indodax_readonly.py`
- `docs/specs/20-testing-strategy.md`

## Current Context

`create_app` accepts an injected provider and principal resolver. API policy denies anonymous principals. `IndodaxReadOnlyClient` already supports `get_account_snapshot`; no runtime composition connects these pieces.

## In Scope

Implement a small Production composition entrypoint/provider adapter and trusted Tailscale Serve principal resolver. Read `INDODAX_VIEW_API_KEY`, `INDODAX_VIEW_SECRET_KEY`, `PRODUCTION_NAMESPACE`, `PRODUCTION_STATE_ROOT` and `PRODUCTION_OPERATOR_ALLOWLIST` only at runtime. Require namespace exactly `production`, an absolute state root, nonempty credentials and allowlist; deny by default. Only an allow-listed `Tailscale-User-Login` resolves to `ActorClass.OPERATOR` with `production.read`.

## Out of Scope

Any live credential inspection, trading/order/cancel/withdrawal capability, `production.control`, Research identity/provider, host/Tailscale configuration, Docker/deployment, or live account call.

## User / Actor Behavior

An authenticated allow-listed operator can view Production data. Missing, malformed, disallowed, or spoofed-at-the-application-boundary identity fails closed and is audited without logging header values or secrets.

## Functional Requirements

- Compose only the existing read-only Indodax client and Production-marked provider.
- Resolve Tailscale identity by exact normalized login allowlist; never trust an alternate client credential.
- Missing credentials/configuration or operator identity fails closed.
- No write client, write route, or `production.control` capability is exposed.

## Domain Rules / Invariants

Production remains the authority for its account reads. Research/shadow namespaces and state roots cannot compose this app. Browser state is never authority.

## Architecture / Design Contract

Reuse existing `create_app`, `Principal`, `Capability` and `IndodaxReadOnlyClient`. Keep the adapter minimal. Proxy identity is trusted only with loopback binding and exclusive proxy reachability; Research co-hosting requires an external network/process isolation gate before activation.

## Planned Files / Artifacts

- `src/indodax_lab/api/auth.py`
- `src/indodax_lab/runtimes/production/control_plane.py`
- `tests/unit/lab/api/test_tailscale_operator_auth.py`
- `tests/integration/lab/api/test_production_runtime_composition.py`
- `docs/sprints/handoffs/API-07-HANDOFF.md`

## Interfaces & Contracts

`create_production_app_from_env()` validates env configuration (`PRODUCTION_NAMESPACE=production`) and returns the existing read-only FastAPI app. Resolver maps the exact allow-listed Tailscale login to a principal with only `production.read`.

## Data / Persistence Impact

Read-only; no new database, schema or persistence.

## API / External Contract Impact

No route or response changes. Unauthenticated reads return the existing stable capability denial.

## UI / UX Behavior

No UI changes in this sprint. Operator login/access is provided by Tailscale Serve.

## Implementation Steps

Add failing tests for missing/disallowed identity and runtime config; implement resolver/provider/composition using existing code; verify focused tests and secret redaction; commit only sprint-owned code/tests and handoff.

## Required Tests

- Missing, malformed and non-allowlisted Tailscale login denied; exact allowed login receives only `production.read`.
- Environment config missing or Research namespace rejected without calling Indodax.
- Provider constructs read-only client and returns account snapshot; no writer import or route.
- Secrets and identity header values never appear in API responses or logs.

## Failure / Edge Cases

Empty allowlist, whitespace/invalid login, missing one key, malformed namespace/root, Indodax read failure all fail closed or return existing unavailable read evidence without leaking credential details.

## Security / Privacy / Safety

Never log or return keys. Never read `.env` during implementation. Proxy identity is trusted only when the network boundary guarantees requests originate from Tailscale Serve. Do not use Funnel or tagged nodes for operator sessions. Loopback alone is insufficient while Research shares ASUS; activation requires evidence that Research cannot reach the API listener.

## Concurrency / Idempotency

Read-only requests preserve existing request ID behavior and have no mutation effects.

## Performance Constraints

Reuse existing timeout/rate behavior of `IndodaxReadOnlyClient`; do not add polling or cache policy.

## Observability

Existing request audit records denial/allow decisions; redact secrets and identity header contents.

## Migration / Backward Compatibility

Keep injected `create_app` API compatible for tests and other explicit callers; add the environment composition as an opt-in entrypoint.

## Rollback / Recovery

Revert only API-07-owned files; existing read API continues to fail closed without injected identity/provider.

## Acceptance Criteria

- **API-07-AC0**: Missing/disallowed identity is denied and allowlisted identity gets only production.read (test_api_07_0).
- **API-07-AC1**: Runtime composition rejects missing config and Research namespace before any venue call (test_api_07_1).
- **API-07-AC2**: Provider uses the existing view-only client and no credential is exposed/logged (test_api_07_2).

## Definition of Done

All criteria pass on exact SHA, handoff records commands and external gates, and independent review passes with no Critical/Important findings.

## Reviewer Checklist

- [ ] Identity trust is restricted to Tailscale Serve and exact allowlist.
- [ ] Provider only performs Indodax view reads.
- [ ] No credentials or `production.control` leak to browser/logs.
- [ ] ASUS isolation remains an external activation gate.

## Commit Guidance

Stage only API-07 code, tests and handoff. Preserve all existing user edits.

## Handoff Requirements

Create `docs/sprints/handoffs/API-07-HANDOFF.md` with SHA, commands/results, review state and Tailscale/ASUS external gates.

## Ready-to-Run Implementation Prompt

Implement API-07 only with fake network and temporary/fake services. Do not inspect live env values or contact Indodax/ASUS. Stop if dependencies are not DONE.
