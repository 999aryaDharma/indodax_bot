# UI-09 — Same-origin Production API access

> Implement this sprint only. Make the Production dashboard work behind Tailscale Serve without exposing API keys to the browser.

**Goal:** Route Production dashboard requests through the same origin as the dashboard and retain a safe local development proxy.

**Architecture:** Browser defaults to relative `/api/v1`; Vite proxies that prefix to the local API in development. Production reverse proxy serves frontend and forwards `/api/v1` to the loopback API. No cross-origin credential or Indodax key is sent by browser code.

**Tech Stack:** Existing Vite/React; no new dependency.

**Spec:** [CR](../../decisions/CR-20260924-production-dashboard-auth.md), [ADR-011](../../decisions/ADR-011-tailscale-operator-identity.md).

## Metadata

Status: DONE

Priority: P0 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: `/root` | Independent Reviewer: `/root/api03_security`

Recommended Branch: feat/ui-04-same-origin-production-api

Requirements: FR-23 | Legacy tasks: none

Risk level: medium | Complexity: S

## Goal

Ensure the Production browser calls its same-origin API path in deployed use and a local Vite proxy in development.

## Why This Sprint Exists

The current default absolute `127.0.0.1:8000` points at the dashboard operator's device, not the ASUS backend, and can bypass Tailscale Serve routing.

## Depends On

- UI-02 — Read-only Production operational pages
- API-02 — Read-only Production API application and routes

## Unlocks

UI-03

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/decisions/CR-20260924-production-dashboard-auth.md`
- `docs/decisions/ADR-011-tailscale-operator-identity.md`
- `frontend/src/api/client.ts`
- `frontend/vite.config.ts`
- `docs/specs/20-testing-strategy.md`

## Current Context

The typed client currently defaults to absolute `http://127.0.0.1:8000/api/v1` and omits browser credentials. Vite has no API proxy configured.

## In Scope

Change the default API base URL to `/api/v1`, add Vite development proxy to `127.0.0.1:8000`, and update focused tests to prove requests are same-origin and still omit credentials.

## Out of Scope

Production server/reverse-proxy configuration, Tailscale setup, new authentication UI, Indodax credentials, API behavior, CORS or deployment changes.

## User / Actor Behavior

Operator opens the dashboard through Tailscale Serve; browser requests remain under that origin so Serve authenticates and forwards API requests.

## Functional Requirements

- Default browser API target is relative `/api/v1`.
- Development API calls route through the Vite proxy to local backend.
- Browser fetch uses no Indodax credential or cross-origin auth material.

## Domain Rules / Invariants

Backend remains the sole capability authority. UI cannot grant operator identity or write access.

## Architecture / Design Contract

Reuse existing typed client and Vite configuration. Preserve optional explicit API URL override only if current tests/build need it; production default must stay same-origin.

## Planned Files / Artifacts

- `frontend/src/api/client.ts`
- `frontend/src/api/client.test.ts`
- `frontend/vite.config.ts`
- `docs/sprints/handoffs/UI-09-HANDOFF.md`

## Interfaces & Contracts

No API schema change. Browser API base defaults to `/api/v1`; Vite dev proxy targets `http://127.0.0.1:8000`.

## Data / Persistence Impact

None.

## API / External Contract Impact

No API route or payload changes.

## UI / UX Behavior

No visual change. Dashboard data fetches inherit Tailscale Serve's same-origin operator session.

## Implementation Steps

Add/update focused client tests; change base URL/proxy; run frontend tests, typecheck and build; commit only owned files and handoff.

## Required Tests

- Default fetch URL is same-origin `/api/v1/...`.
- Fetch continues to use `credentials: omit` and no Indodax headers.
- Vite proxy maps `/api/v1` to local backend and strips no API path segment incorrectly.

## Failure / Edge Cases

Missing backend produces existing API_UNAVAILABLE behavior; environment override cannot silently reintroduce browser-held secrets.

## Security / Privacy / Safety

No token/key in local storage, browser headers, query string or logs. Tailscale Serve remains the operator identity boundary.

## Concurrency / Idempotency

Read-only request behavior is unchanged; existing request IDs remain stable per request.

## Performance Constraints

No new polling, retry loop or bundle dependency.

## Observability

Preserve existing request ID and typed API error display.

## Migration / Backward Compatibility

Local development remains supported through Vite proxy. Existing explicit test URL overrides may remain supported.

## Rollback / Recovery

Revert only UI-09-owned files; dashboard pages are unchanged.

## Acceptance Criteria

- **UI-09-AC0**: Default API calls use same-origin /api/v1 (test_ui_09_0).
- **UI-09-AC1**: Browser requests omit credentials and never include Indodax keys (test_ui_09_1).
- **UI-09-AC2**: Vite development proxy forwards API paths to local backend (test_ui_09_2).

## Definition of Done

Acceptance tests, focused frontend checks and exact-SHA independent review pass; handoff records results and external gates.

## Reviewer Checklist

- [x] Production default is relative same-origin URL.
- [x] Browser does not hold backend or Indodax credentials.
- [x] Vite proxy preserves `/api/v1` path correctly.

## Commit Guidance

Stage only UI-09-owned frontend files and handoff. Preserve user design artifacts.

## Handoff Requirements

Create `docs/sprints/handoffs/UI-09-HANDOFF.md` with SHA, commands/results, review state and reverse-proxy external gate.

## Ready-to-Run Implementation Prompt

Implement UI-09 only. Follow Impeccable for frontend changes; preserve dashboard.pen and design-prototype unchanged.
