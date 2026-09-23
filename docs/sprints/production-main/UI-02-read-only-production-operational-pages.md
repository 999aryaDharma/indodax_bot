# UI-02 — Read-only Production operational pages Implementation Plan

> For agentic workers: implement this sprint only. Show authoritative live Production state, including live Indodax account portfolio evidence, through read-only pages. Independent review is required before DONE.

**Goal:** Render operational truth, authoritative state and failure context through read-only Production pages.

**Architecture:** Overview, Portfolio, Positions, Orders, Reconciliation, Risk, Releases and Audit pages consume typed API data only. No write, repair or promotion controls appear.

**Tech Stack:** React, TypeScript, Vite, Kumo UI 2.14.0, locally hosted Geist Sans/Mono.

**Spec:** DESIGN.md and CR-2026-09-23.

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: feat/ui-02-production-control-plane

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: Planned implementation; dependencies and activation gates are separate.

## Goal

Render operational truth, authoritative state and failure context through read-only Production pages.

## Why This Sprint Exists

This sprint is part of the read-only Production MVP admitted by CR-2026-09-23 and supplies a separately reviewable dependency for later nodes.

## Depends On

- UI-01 — Production and Research context navigation with capability boundary
- API-02 — Read-only Production API application and routes

## Unlocks

No mandatory dependent sprint.

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

The UI shell and planned Production API/read models are defined; operational Production pages remain to be implemented after API/UI dependency sprints pass review.

## In Scope

Render operational truth, authoritative state and failure context through read-only Production pages.

Contract: Overview, Portfolio, Positions, Orders, Reconciliation, Risk, Releases and Audit pages consume typed API data only. No write, repair or promotion controls appear.

## Out of Scope

Real-money activation, credentials, order submission, withdrawal, venue writer access, ledger repair, Research feature implementation, Docker deployment and ASUS host changes.

## User / Actor Behavior

The operator sees only explicit backend state and safe blocked/unavailable outcomes. Production and Research identity remain separate.

## Functional Requirements

FR-23 in the admitted read-only scope.

- HALTED/RECOVERY/UNKNOWN/mismatch/stale/unavailable remain prominent and text-labeled
- Tables align numeric values and expose provenance without rendering unknown metrics as zero
- Pages remain legible at desktop and smartphone widths with semantic order preserved

## Domain Rules / Invariants

Backend domain services own financial and operational truth. Unknown is distinct from zero. No UI state grants backend capability.

## Architecture / Design Contract

Production pages show Production-owned market health, release and financial state. Do not proxy ASUS Research feed freshness or shadow status into Production. If an authority source is missing, show UNAVAILABLE; do not substitute Research data.

Overview, Portfolio, Positions, Orders, Reconciliation, Risk, Releases and Audit pages consume typed API data only. No write, repair or promotion controls appear.

## Planned Files / Artifacts

- frontend/src/features/production/OverviewPage.tsx
- frontend/src/features/production/PortfolioPage.tsx
- frontend/src/features/production/PositionsPage.tsx
- frontend/src/features/production/OrdersPage.tsx
- frontend/src/features/production/ReconciliationPage.tsx
- frontend/src/features/production/RiskPage.tsx
- frontend/src/features/production/ReleasesPage.tsx
- frontend/src/features/production/AuditPage.tsx

## Interfaces & Contracts

Overview, Portfolio, Positions, Orders, Reconciliation, Risk, Releases and Audit pages consume typed API data only. No write, repair or promotion controls appear.

## Data / Persistence Impact

Read-only. No schema migration, new database, credential store or cross-host SQLite access.

## API / External Contract Impact

Only the versioned read/API contract specified for this sprint. No exchange network calls or write-capable endpoint.

## UI / UX Behavior

Use Kumo UI components plus local Geist Sans/Mono; match DESIGN.md tokens; desktop and smartphone only.

## Implementation Steps

Inspect assigned paths and dependencies; write focused behavior tests; implement the smallest scoped change; run and record required checks; self-review and commit only owned files.

## Required Tests

- HALTED/RECOVERY/UNKNOWN/mismatch/stale/unavailable remain prominent and text-labeled
- Tables align numeric values and expose provenance without rendering unknown metrics as zero
- Pages remain legible at desktop and smartphone widths with semantic order preserved

## Failure / Edge Cases

- HALTED/RECOVERY/UNKNOWN/mismatch/stale/unavailable remain prominent and text-labeled
- Tables align numeric values and expose provenance without rendering unknown metrics as zero
- Pages remain legible at desktop and smartphone widths with semantic order preserved
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

- **UI-02-AC0**: HALTED/RECOVERY/UNKNOWN/mismatch/stale/unavailable remain prominent and text-labeled (test_ui_02_0).
- **UI-02-AC1**: Tables align numeric values and expose provenance without rendering unknown metrics as zero (test_ui_02_1).
- **UI-02-AC2**: Pages remain legible at desktop and smartphone widths with semantic order preserved (test_ui_02_2).

## Definition of Done

All acceptance criteria are demonstrated; exact SHA and commands/results are recorded; independent reviewer passes; no Critical/Important finding remains.

## Reviewer Checklist

- [ ] HALTED/RECOVERY/UNKNOWN/mismatch/stale/unavailable remain prominent and text-labeled
- [ ] Tables align numeric values and expose provenance without rendering unknown metrics as zero
- [ ] Pages remain legible at desktop and smartphone widths with semantic order preserved
- [ ] Verify no unrelated paths or authority boundaries changed.

## Commit Guidance

Commit only paths owned by this sprint. Preserve dashboard.pen, design-prototype and unrelated user WIP.

## Handoff Requirements

Create docs/sprints/handoffs/UI-02-HANDOFF.md with exact SHA, commands/results, review result and unresolved external gates.

## Ready-to-Run Implementation Prompt

Implement UI-02 only. Show authoritative live Production state, including live Indodax account portfolio evidence, through read-only pages; stop if any dependency is not DONE.
