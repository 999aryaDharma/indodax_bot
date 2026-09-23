# API-02 — Read-only Production API application and routes Implementation Plan

> For agentic workers: implement this sprint only. Expose live Production state, including fresh Indodax account portfolio evidence, through read-only routes; do not create write authority. Independent review is required before DONE.

**Goal:** Expose Production read models through a capability-protected HTTP API with no write authority.

**Architecture:** FastAPI /api/v1/production endpoints delegate to ProductionReadService, require production.read, paginate stable lists and return common envelopes. Composition injects only the Production-owned read-only Indodax account source, explicit Production namespace and Production state root; Research providers/paths are rejected. App construction never resolves IndodaxTradingVenue.

**Tech Stack:** Python 3.11+, existing Pydantic/Decimal services and FastAPI where scoped.

**Spec:** docs/implementation/CONTRACTS.md and CR-2026-09-23.

## Metadata

Status: READY

Priority: P0 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: feat/api-02-production-control-plane

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: Planned implementation; dependencies and activation gates are separate.

## Goal

Expose live Production read models, including real Indodax account balances, through a capability-protected HTTP API with no write authority.

## Why This Sprint Exists

This sprint is part of the read-only Production MVP admitted by CR-2026-09-23 and supplies a separately reviewable dependency for later nodes.

## Depends On

- API-01 — Production service-derived read models
- API-03 — Fail-closed read capability policy and audit context

## Unlocks

UI-02

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/production/main/SOP-AND-GATES.md`
- `docs/implementation/CONTRACTS.md`
- `docs/implementation/CHANGE-REQUEST-PRODUCTION-CONTROL-PLANE.md`
- `docs/implementation/CONTROL-PLANE-ROADMAP.md`
- `docs/superpowers/plans/2026-09-22-production-api-plan.md`
- `docs/superpowers/plans/2026-09-22-control-plane-program-plan.md`
- `docs/specs/20-testing-strategy.md`

## Current Context

Shared contracts, UI shell, and planned read models/capability policy are defined; Production application routes remain to be implemented after dependency sprints pass review.

## In Scope

Expose live Production read models, including real Indodax account balances, through a capability-protected HTTP API with no write authority.

Contract: FastAPI /api/v1/production endpoints delegate to ProductionReadService, require production.read, paginate stable lists and return common envelopes. Composition explicitly supplies the Production state namespace/root and server-side Production-owned read-only Indodax account source; no browser credentials, Research feed/state/provider, or writer adapter. App construction defaults to non-writing modes and never resolves IndodaxTradingVenue.

## Out of Scope

Changing live execution, provisioning/rotating/exposing credentials, order submission, withdrawal, venue writer access, ledger repair, Research feature implementation, Docker deployment and ASUS host changes. The existing Production-owned server credential/client authority may support read-only Indodax account reads; credentials stay server-side and are not managed by this API sprint.

## User / Actor Behavior

The operator sees only explicit backend state and safe blocked/unavailable outcomes. Production and Research identity remain separate.

## Functional Requirements

FR-23 in the admitted read-only scope.

- Every route requires read capability and serializes Decimal/UTC/provenance contracts
- Router/import graph cannot resolve the write venue or any POST order/withdraw/repair route
- Unavailable services return explicit safe state and outage responses

## Domain Rules / Invariants

Backend domain services own financial and operational truth. Unknown is distinct from zero. No UI state grants backend capability.

## Architecture / Design Contract

Keep Production, Research and System namespaces separate. Production routes do not proxy ASUS Research services or expose the Research market feed as Production truth. Any later browser event stream is a bounded, read-only backend observability transport, separate from Indodax WebSocket ownership.

The composition root must configure the exact Production state namespace/root and a Production-marked `VenueAccountProvider`; missing or Research-bound configuration fails closed. The injected read-only Indodax provider may use the existing Production-owned account credentials but has no order, cancel or withdrawal operations.

FastAPI /api/v1/production endpoints delegate to ProductionReadService, require production.read, paginate stable lists and return common envelopes. App construction defaults to non-writing modes and never resolves IndodaxTradingVenue.

## Planned Files / Artifacts

- src/indodax_lab/api/app.py
- src/indodax_lab/api/dependencies.py
- src/indodax_lab/api/routers/production.py
- tests/integration/lab/api/test_production_routes.py

## Interfaces & Contracts

FastAPI /api/v1/production endpoints delegate to ProductionReadService, require production.read, paginate stable lists and return common envelopes. App construction defaults to non-writing modes and never resolves IndodaxTradingVenue.

## Data / Persistence Impact

Read-only. No schema migration, new database, credential store or cross-host SQLite access. No shared SQLite WAL; the configured Production database root must be distinct from Research roots.

## API / External Contract Impact

Only the versioned read/API contract specified for this sprint. Account reads use the injected Production-owned read-only provider; no write-capable endpoint or direct exchange-client construction in the HTTP application.

## UI / UX Behavior

Backend only. No UI authority or UI-owned financial state.

## Implementation Steps

Inspect assigned paths and dependencies; write focused behavior tests; implement the smallest scoped change; run and record required checks; self-review and commit only owned files.

## Required Tests

- Every route requires read capability and serializes Decimal/UTC/provenance contracts
- Router/import graph cannot resolve the write venue or any POST order/withdraw/repair route
- Unavailable services return explicit safe state and outage responses
- Missing Production namespace/root/provider fails closed; Research paths/providers never satisfy Production reads
- Fresh Indodax account evidence is returned with source time/freshness and no credentials

## Failure / Edge Cases

- Every route requires read capability and serializes Decimal/UTC/provenance contracts
- Router/import graph cannot resolve the write venue or any POST order/withdraw/repair route
- Unavailable services return explicit safe state and outage responses
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

- **API-02-AC0**: Every route requires read capability and serializes Decimal/UTC/provenance contracts (test_api_02_0).
- **API-02-AC1**: Router/import graph cannot resolve the write venue or any POST order/withdraw/repair route (test_api_02_1).
- **API-02-AC2**: Unavailable services return explicit safe state and outage responses (test_api_02_2).

## Definition of Done

All acceptance criteria are demonstrated; exact SHA and commands/results are recorded; independent reviewer passes; no Critical/Important finding remains.

## Reviewer Checklist

- [ ] Every route requires read capability and serializes Decimal/UTC/provenance contracts
- [ ] Router/import graph cannot resolve the write venue or any POST order/withdraw/repair route
- [ ] Unavailable services return explicit safe state and outage responses
- [ ] Verify no unrelated paths or authority boundaries changed.

## Commit Guidance

Commit only paths owned by this sprint. Preserve dashboard.pen, design-prototype and unrelated user WIP.

## Handoff Requirements

Create docs/sprints/handoffs/API-02-HANDOFF.md with exact SHA, commands/results, review result and unresolved external gates.

## Ready-to-Run Implementation Prompt

Implement API-02 only. Expose live Production state, including fresh Indodax account portfolio evidence, through read-only routes without creating write authority; stop if any dependency is not DONE.
