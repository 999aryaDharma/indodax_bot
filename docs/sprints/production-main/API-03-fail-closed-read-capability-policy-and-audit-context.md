# API-03 — Fail-closed read capability policy and audit context Implementation Plan

> For agentic workers: implement this sprint only. Protect access to the existing live Production read surface; do not grant write authority. Independent review is required before DONE.

**Goal:** Require explicit request identity and production.read capability before serving sensitive operational data.

**Architecture:** RequestContext binds request ID, principal, capability and timestamp. Missing/anonymous identity receives a stable denial; development/test actors are injected explicitly. This sprint grants no Production writes or Research mutations.

**Tech Stack:** Python 3.11+, existing Pydantic/Decimal services and FastAPI where scoped.

**Spec:** docs/implementation/CONTRACTS.md and CR-2026-09-23.

## Metadata

Status: READY

Priority: P0 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: feat/api-03-production-control-plane

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: Planned implementation; dependencies and activation gates are separate.

## Goal

Require explicit request identity and production.read capability before serving sensitive operational data.

## Why This Sprint Exists

This sprint is part of the read-only Production MVP admitted by CR-2026-09-23 and supplies a separately reviewable dependency for later nodes.

## Depends On

- API-00 — Shared API envelope, error, provenance and capability contracts

## Unlocks

API-02, UI-01

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

Shared API contracts and UI shell are present in this workspace; production server capability enforcement and audit context remain unimplemented.

## In Scope

Require explicit request identity and production.read capability before serving sensitive operational data.

Contract: RequestContext binds request ID, principal, capability and timestamp. Missing/anonymous identity receives a stable denial; development/test actors are injected explicitly. This sprint grants no Production writes or Research mutations.

## Out of Scope

Real-money activation, credentials, order submission, withdrawal, venue writer access, ledger repair, Research feature implementation, Docker deployment and ASUS host changes.

## User / Actor Behavior

The operator sees only explicit backend state and safe blocked/unavailable outcomes. Production and Research identity remain separate.

## Functional Requirements

FR-23 in the admitted read-only scope.

- Missing principal/capability is denied without resolving production services
- Research capability never satisfies production.read
- Each allow/deny decision records request ID, actor class, capability and reason without secrets

## Domain Rules / Invariants

Backend domain services own financial and operational truth. Unknown is distinct from zero. No UI state grants backend capability.

## Architecture / Design Contract

RequestContext binds request ID, principal, capability and timestamp. Missing/anonymous identity receives a stable denial; development/test actors are injected explicitly. This sprint grants no Production writes or Research mutations.

## Planned Files / Artifacts

- src/indodax_lab/api/auth.py
- src/indodax_lab/api/audit.py
- src/indodax_lab/api/dependencies.py
- tests/unit/lab/api/test_capability_policy.py
- tests/integration/lab/api/test_api_audit.py

## Interfaces & Contracts

RequestContext binds request ID, principal, capability and timestamp. Missing/anonymous identity receives a stable denial; development/test actors are injected explicitly. This sprint grants no Production writes or Research mutations.

## Data / Persistence Impact

Read-only. No schema migration, new database, credential store or cross-host SQLite access.

## API / External Contract Impact

Only the versioned read/API contract specified for this sprint. No exchange network calls or write-capable endpoint.

## UI / UX Behavior

Backend only. No UI authority or UI-owned financial state.

## Implementation Steps

Inspect assigned paths and dependencies; write focused behavior tests; implement the smallest scoped change; run and record required checks; self-review and commit only owned files.

## Required Tests

- Missing principal/capability is denied without resolving production services
- Research capability never satisfies production.read
- Each allow/deny decision records request ID, actor class, capability and reason without secrets

## Failure / Edge Cases

- Missing principal/capability is denied without resolving production services
- Research capability never satisfies production.read
- Each allow/deny decision records request ID, actor class, capability and reason without secrets
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

- **API-03-AC0**: Missing principal/capability is denied without resolving production services (test_api_03_0).
- **API-03-AC1**: Research capability never satisfies production.read (test_api_03_1).
- **API-03-AC2**: Each allow/deny decision records request ID, actor class, capability and reason without secrets (test_api_03_2).

## Definition of Done

All acceptance criteria are demonstrated; exact SHA and commands/results are recorded; independent reviewer passes; no Critical/Important finding remains.

## Reviewer Checklist

- [ ] Missing principal/capability is denied without resolving production services
- [ ] Research capability never satisfies production.read
- [ ] Each allow/deny decision records request ID, actor class, capability and reason without secrets
- [ ] Verify no unrelated paths or authority boundaries changed.

## Commit Guidance

Commit only paths owned by this sprint. Preserve dashboard.pen, design-prototype and unrelated user WIP.

## Handoff Requirements

Create docs/sprints/handoffs/API-03-HANDOFF.md with exact SHA, commands/results, review result and unresolved external gates.

## Ready-to-Run Implementation Prompt

Implement API-03 only. Protect the live Production read surface without granting write authority; stop if any dependency is not DONE.
