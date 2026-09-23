# UI-01 — Production and Research context navigation with capability boundary Implementation Plan

> For agentic workers: implement this sprint only. Keep live Production and isolated Research contexts visibly separate. Independent review is required before DONE.

**Goal:** Keep Production and Research route contexts distinct and reflect backend capability decisions safely.

**Architecture:** Shared shell labels current context and capability. Route namespaces remain /production/* and /research/*; the UI guard is presentation only and never substitutes for API authorization.

**Tech Stack:** React, TypeScript, Vite, Kumo UI 2.14.0, locally hosted Geist Sans/Mono.

**Spec:** DESIGN.md and CR-2026-09-23.

## Metadata

Status: READY

Priority: P1 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: feat/ui-01-production-control-plane

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: Planned implementation; dependencies and activation gates are separate.

## Goal

Keep Production and Research route contexts distinct and reflect backend capability decisions safely.

## Why This Sprint Exists

This sprint is part of the read-only Production MVP admitted by CR-2026-09-23 and supplies a separately reviewable dependency for later nodes.

## Depends On

- UI-00 — Kumo and Geist shell foundation with typed API client
- API-03 — Fail-closed read capability policy and audit context

## Unlocks

UI-02

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

The shared UI-00 shell is implemented and awaiting review. Context-aware navigation and server-derived capability boundaries are this sprint's scope.

## In Scope

Keep Production and Research route contexts distinct and reflect backend capability decisions safely.

Contract: Shared shell labels current context and capability. Route namespaces remain /production/* and /research/*; the UI guard is presentation only and never substitutes for API authorization.

## Out of Scope

Real-money activation, credentials, order submission, withdrawal, venue writer access, ledger repair, Research feature implementation, Docker deployment and ASUS host changes.

## User / Actor Behavior

The operator sees only explicit backend state and safe blocked/unavailable outcomes. Production and Research identity remain separate.

## Functional Requirements

FR-23 in the admitted read-only scope.

- Unknown/denied capability displays a blocked state and exposes no Production control affordance
- Changing route context cannot reuse a Production capability in Research or vice versa
- Navigation remains grouped and usable on desktop and smartphone

## Domain Rules / Invariants

Backend domain services own financial and operational truth. Unknown is distinct from zero. No UI state grants backend capability.

## Architecture / Design Contract

Show Production Main, Research Workbench and System as separate contexts and label status provenance. Never present the ASUS Research feed as Production market health. Any browser stream remains backend-owned observability only.

Shared shell labels current context and capability. Route namespaces remain /production/* and /research/*; the UI guard is presentation only and never substitutes for API authorization.

## Planned Files / Artifacts

- frontend/src/app/Shell.tsx
- frontend/src/app/ContextSwitcher.tsx
- frontend/src/app/CapabilityBoundary.tsx
- frontend/src/components/StatusStrip.tsx
- frontend/src/app/CapabilityBoundary.test.tsx

## Interfaces & Contracts

Shared shell labels current context and capability. Route namespaces remain /production/* and /research/*; the UI guard is presentation only and never substitutes for API authorization.

## Data / Persistence Impact

Read-only. No schema migration, new database, credential store or cross-host SQLite access.

## API / External Contract Impact

Only the versioned read/API contract specified for this sprint. No exchange network calls or write-capable endpoint.

## UI / UX Behavior

Use Kumo UI components plus local Geist Sans/Mono; match DESIGN.md tokens; desktop and smartphone only.

## Implementation Steps

Inspect assigned paths and dependencies; write focused behavior tests; implement the smallest scoped change; run and record required checks; self-review and commit only owned files.

## Required Tests

- Unknown/denied capability displays a blocked state and exposes no Production control affordance
- Changing route context cannot reuse a Production capability in Research or vice versa
- Navigation remains grouped and usable on desktop and smartphone

## Failure / Edge Cases

- Unknown/denied capability displays a blocked state and exposes no Production control affordance
- Changing route context cannot reuse a Production capability in Research or vice versa
- Navigation remains grouped and usable on desktop and smartphone
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

- **UI-01-AC0**: Unknown/denied capability displays a blocked state and exposes no Production control affordance (test_ui_01_0).
- **UI-01-AC1**: Changing route context cannot reuse a Production capability in Research or vice versa (test_ui_01_1).
- **UI-01-AC2**: Navigation remains grouped and usable on desktop and smartphone (test_ui_01_2).

## Definition of Done

All acceptance criteria are demonstrated; exact SHA and commands/results are recorded; independent reviewer passes; no Critical/Important finding remains.

## Reviewer Checklist

- [ ] Unknown/denied capability displays a blocked state and exposes no Production control affordance
- [ ] Changing route context cannot reuse a Production capability in Research or vice versa
- [ ] Navigation remains grouped and usable on desktop and smartphone
- [ ] Verify no unrelated paths or authority boundaries changed.

## Commit Guidance

Commit only paths owned by this sprint. Preserve dashboard.pen, design-prototype and unrelated user WIP.

## Handoff Requirements

Create docs/sprints/handoffs/UI-01-HANDOFF.md with exact SHA, commands/results, review result and unresolved external gates.

## Ready-to-Run Implementation Prompt

Implement UI-01 only. Keep live Production and isolated Research contexts visibly separate; stop if any dependency is not DONE.
