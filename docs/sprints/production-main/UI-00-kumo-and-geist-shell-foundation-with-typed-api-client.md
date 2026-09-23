# UI-00 — Kumo and Geist shell foundation with typed API client Implementation Plan

> For agentic workers: implement this sprint only. Display live Production data from the read API; do not create trading authority. Independent review is required before DONE.

**Goal:** Build shared desktop/smartphone dashboard shell and typed client against the frozen API contract while backend read models progress independently.

**Architecture:** React/TypeScript/Vite uses @cloudflare/kumo 2.14.0 accessible components, local Vercel Geist Sans/Mono WOFF2 assets and DESIGN.md tokens. Client validates full envelope shape and timezone-aware timestamps, preserves Decimal strings, request IDs and stable errors, and clears prior snapshots after a failed refresh; no secret persistence.

**Tech Stack:** React, TypeScript, Vite, Kumo UI 2.14.0, locally hosted Geist Sans/Mono.

**Spec:** DESIGN.md and CR-2026-09-23.

## Metadata

Status: DONE

Priority: P1 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: /root | Independent Reviewer: /root/prod_mvp_final_reviewer

Recommended Branch: feat/ui-00-production-control-plane

Requirements: FR-23 | Legacy tasks: none

Risk level: medium | Complexity: L

Classification: Planned implementation; dependencies and activation gates are separate.

## Goal

Build shared desktop/smartphone dashboard shell and typed client against the frozen API contract while backend read models progress independently.

## Why This Sprint Exists

This sprint is part of the read-only Production MVP admitted by CR-2026-09-23 and supplies a separately reviewable dependency for later nodes.

## Depends On

None. This capability can establish its own offline acceptance fixture.

## Unlocks

UI-01

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/implementation/CHANGE-REQUEST-PRODUCTION-CONTROL-PLANE.md`
- `docs/implementation/CONTROL-PLANE-ROADMAP.md`
- `docs/superpowers/plans/2026-09-22-unified-dashboard-plan.md`
- `DESIGN.md`
- `dashboard.pen`
- `docs/specs/20-testing-strategy.md`

## Current Context

UI-00 shell and typed API client are implemented and independently reviewed at source SHA `3bb7e0a89fb268c06de279f140e9004455a526b1`. Production API routes are not available yet.

## In Scope

Build shared desktop/smartphone dashboard shell and typed client against the frozen API contract while backend read models progress independently.

Contract: React/TypeScript/Vite uses @cloudflare/kumo 2.14.0 accessible components, local Vercel Geist Sans/Mono WOFF2 assets and DESIGN.md tokens. Client validates full envelope shape and timezone-aware UTC timestamps, preserves Decimal strings, request IDs and stable errors, clears prior snapshots after a failed refresh, hides data for EMPTY/UNAVAILABLE, displays a live WITA clock and snapshot age, and persists no secrets.

## Out of Scope

Real-money activation, credentials, order submission, withdrawal, venue writer access, ledger repair, Research feature implementation, Docker deployment and ASUS host changes.

## User / Actor Behavior

The operator sees only explicit backend state and safe blocked/unavailable outcomes. Production and Research identity remain separate.

## Functional Requirements

FR-23 in the admitted read-only scope.

- Shell renders at desktop workstation and smartphone widths using DESIGN.md layout tokens
- Kumo controls use graphite product tokens rather than default branded colors
- Typed client validates complete response envelopes, preserves Decimal strings, hides operational data for EMPTY/UNAVAILABLE, distinguishes error states and displays live WITA time/snapshot age

## Domain Rules / Invariants

Backend domain services own financial and operational truth. Unknown is distinct from zero. No UI state grants backend capability.

## Architecture / Design Contract

Keep API namespaces and health-source labels explicit. The browser consumes the control-plane API; it never connects to Indodax WebSocket or treats ASUS Research Runtime as Production authority. Event streaming is outside this sprint.

React/TypeScript/Vite uses @cloudflare/kumo 2.14.0 accessible components, local Vercel Geist Sans/Mono WOFF2 assets and DESIGN.md tokens. Client validates full envelope shape and timezone-aware timestamps, preserves Decimal strings, request IDs and stable errors, and clears prior snapshots after a failed refresh; no secret persistence.

## Planned Files / Artifacts

- frontend/package.json
- frontend/package-lock.json
- frontend/tsconfig.json
- frontend/vite.config.ts
- frontend/src/main.tsx
- frontend/src/app/App.tsx
- frontend/src/api/client.ts
- frontend/src/api/types.ts
- frontend/src/styles/tokens.css
- frontend/src/assets/fonts/
- frontend/src/api/client.test.ts

## Interfaces & Contracts

React/TypeScript/Vite uses @cloudflare/kumo 2.14.0 accessible components, local Vercel Geist Sans/Mono WOFF2 assets and DESIGN.md tokens. Client validates full envelope shape and timezone-aware timestamps, preserves Decimal strings, request IDs and stable errors, and clears prior snapshots after a failed refresh; no secret persistence.

## Data / Persistence Impact

Read-only. No schema migration, new database, credential store or cross-host SQLite access.

## API / External Contract Impact

Only the versioned read/API contract specified for this sprint. No exchange network calls or write-capable endpoint.

## UI / UX Behavior

Use Kumo UI components plus local Geist Sans/Mono; match DESIGN.md tokens; desktop and smartphone only.

## Implementation Steps

Inspect assigned paths and dependencies; write focused behavior tests; implement the smallest scoped change; run and record required checks; self-review and commit only owned files.

## Required Tests

- Shell renders at desktop workstation and smartphone widths using DESIGN.md layout tokens
- Kumo controls use graphite product tokens rather than default branded colors
- Typed client validates complete response envelopes, preserves Decimal strings and distinguishes unavailable/error/empty states

## Failure / Edge Cases

- Shell renders at desktop workstation and smartphone widths using DESIGN.md layout tokens
- Kumo controls use graphite product tokens rather than default branded colors
- Typed client validates complete response envelopes, preserves Decimal strings and distinguishes unavailable/error/empty states
- Missing service, stale snapshot, permission denial and malformed input fail closed.

## Security / Privacy / Safety

No secrets in schemas, browser storage, responses or logs. No production writer construction. API capability is enforced server-side; UI guard is never authority.

## Concurrency / Idempotency

Read operations are side-effect free. Request identity is explicit; unsupported mutation is rejected.

## Performance Constraints

Paginate/stably order large lists and avoid loading unbounded history or event streams.

## Observability

Return safe request identity, UTC timestamp, source revision, status and provenance; redact private payloads.

## Migration / Backward Compatibility

Add a versioned API/UI surface only. Do not mutate legacy APIs or runtime stores.

## Rollback / Recovery

Revert sprint-owned files; no runtime data or host state changes need rollback.

## Acceptance Criteria

- **UI-00-AC0**: Shell renders at desktop workstation and smartphone widths using DESIGN.md layout tokens (test_ui_00_0).
- **UI-00-AC1**: Kumo controls use graphite product tokens rather than default branded colors (test_ui_00_1).
- **UI-00-AC2**: Typed client validates complete response envelopes, preserves Decimal strings and distinguishes unavailable/error/empty states (test_ui_00_2).

## Definition of Done

All acceptance criteria are demonstrated; exact SHA and commands/results are recorded; independent reviewer passes; no Critical/Important finding remains.

## Reviewer Checklist

- [ ] Shell renders at desktop workstation and smartphone widths using DESIGN.md layout tokens
- [ ] Kumo controls use graphite product tokens rather than default branded colors
- [ ] Typed client validates complete response envelopes, preserves Decimal strings and distinguishes unavailable/error/empty states
- [ ] Verify no unrelated paths or authority boundaries changed.

## Commit Guidance

Commit only paths owned by this sprint. Preserve dashboard.pen, design-prototype and unrelated user WIP.

## Handoff Requirements

Create docs/sprints/handoffs/UI-00-HANDOFF.md with exact SHA, commands/results, review result and unresolved external gates.

## Ready-to-Run Implementation Prompt

Implement UI-00 only. Display live Production data from the read API without creating trading authority; stop if any dependency is not DONE.
