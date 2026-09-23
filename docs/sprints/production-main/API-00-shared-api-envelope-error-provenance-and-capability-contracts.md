# API-00 — Shared API envelope, error, provenance and capability contracts Implementation Plan

> For agentic workers: implement this sprint only. Preserve paper/shadow-only authority. Independent review is required before DONE.

**Goal:** Define stable typed contracts for safe Production and later Research API consumers.

**Architecture:** ApiEnvelope carries request_id, aware UTC as_of, source_revision, typed status (AVAILABLE, PARTIAL, UNAVAILABLE, EMPTY), data and provenance. ApiError uses stable code/message/retryable/details. Decimal serializes as a string. Capability vocabulary is typed and unknown names reject.

**Tech Stack:** Python 3.11+, existing Pydantic/Decimal services and FastAPI where scoped.

**Spec:** docs/implementation/CONTRACTS.md and CR-2026-09-23.

## Metadata

Status: IN_PROGRESS

Priority: P0 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: /root/api00_backend | Independent Reviewer: /root/prod_mvp_final_reviewer

Recommended Branch: feat/api-00-production-control-plane

Requirements: FR-23 | Legacy tasks: none

Risk level: medium | Complexity: L

Classification: Planned implementation; dependencies and activation gates are separate.

## Goal

Define stable typed contracts for safe Production and later Research API consumers.

## Why This Sprint Exists

This sprint is part of the read-only Production MVP admitted by CR-2026-09-23 and supplies a separately reviewable dependency for later nodes.

## Depends On

None. This capability can establish its own offline acceptance fixture.

## Unlocks

API-01, API-03

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

The shared API contracts are implemented in this workspace and awaiting independent review. This sprint adds contracts only; Production read models and routes remain later work.

## In Scope

Define stable typed contracts for safe Production and later Research API consumers.

Contract: ApiEnvelope carries request_id, aware UTC as_of, source_revision, typed status (AVAILABLE, PARTIAL, UNAVAILABLE, EMPTY), data and provenance. ApiError uses stable code/message/retryable/details. Decimal serializes as a string. Capability vocabulary is typed and unknown names reject.

## Out of Scope

Real-money activation, credentials, order submission, withdrawal, venue writer access, ledger repair, Research feature implementation, Docker deployment and ASUS host changes.

## User / Actor Behavior

The operator sees only explicit backend state and safe blocked/unavailable outcomes. Production and Research identity remain separate.

## Functional Requirements

FR-23 in the admitted read-only scope.

- Naive UTC timestamps reject and aware timestamps round-trip
- Non-finite Decimal rejects and finite Decimal serializes as a string
- Unknown capability, unsupported envelope status and malformed envelopes reject predictably

## Domain Rules / Invariants

Backend domain services own financial and operational truth. Unknown is distinct from zero. No UI state grants backend capability.

## Architecture / Design Contract

ApiEnvelope carries request_id, aware UTC as_of, source_revision, typed status (AVAILABLE, PARTIAL, UNAVAILABLE, EMPTY), data and provenance. ApiError uses stable code/message/retryable/details. Decimal serializes as a string. Capability vocabulary is typed and unknown names reject.

Production, Research and System identities stay namespaced. ASUS Research WebSocket feed state is never Production market authority; browser update transports, if admitted later, are distinct read-only observability channels and never exchange sockets.

## Planned Files / Artifacts

- src/indodax_lab/api/__init__.py
- src/indodax_lab/api/contracts/common.py
- src/indodax_lab/api/capabilities.py
- tests/unit/lab/api/test_common_contracts.py

## Interfaces & Contracts

ApiEnvelope carries request_id, aware UTC as_of, source_revision, typed status (AVAILABLE, PARTIAL, UNAVAILABLE, EMPTY), data and provenance. ApiError uses stable code/message/retryable/details. Decimal serializes as a string. Capability vocabulary is typed and unknown names reject.

## Data / Persistence Impact

Read-only. No schema migration, new database, credential store or cross-host SQLite access.

## API / External Contract Impact

Only the versioned read/API contract specified for this sprint. No exchange network calls or write-capable endpoint.

## UI / UX Behavior

Backend only. No UI authority or UI-owned financial state.

## Implementation Steps

Inspect assigned paths and dependencies; write focused behavior tests; implement the smallest scoped change; run and record required checks; self-review and commit only owned files.

## Required Tests

- Naive UTC timestamps reject and aware timestamps round-trip
- Non-finite Decimal rejects and finite Decimal serializes as a string
- Unknown capability, unsupported envelope status and malformed envelopes reject predictably

## Failure / Edge Cases

- Naive UTC timestamps reject and aware timestamps round-trip
- Non-finite Decimal rejects and finite Decimal serializes as a string
- Unknown capability, unsupported envelope status and malformed envelopes reject predictably
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

- **API-00-AC0**: Naive UTC timestamps reject and aware timestamps round-trip (test_api_00_0).
- **API-00-AC1**: Non-finite Decimal rejects and finite Decimal serializes as a string (test_api_00_1).
- **API-00-AC2**: Unknown capability, unsupported envelope status and malformed envelopes reject predictably (test_api_00_2).

## Definition of Done

All acceptance criteria are demonstrated; exact SHA and commands/results are recorded; independent reviewer passes; no Critical/Important finding remains.

## Reviewer Checklist

- [ ] Naive UTC timestamps reject and aware timestamps round-trip
- [ ] Non-finite Decimal rejects and finite Decimal serializes as a string
- [ ] Unknown capability, unsupported envelope status and malformed envelopes reject predictably
- [ ] Verify no unrelated paths or authority boundaries changed.

## Commit Guidance

Commit only paths owned by this sprint. Preserve dashboard.pen, design-prototype and unrelated user WIP.

## Handoff Requirements

Create docs/sprints/handoffs/API-00-HANDOFF.md with exact SHA, commands/results, review result and unresolved external gates.

## Ready-to-Run Implementation Prompt

Implement API-00 only. Read this sprint and listed dependencies. Preserve paper/shadow-only authority and stop if any dependency is not DONE.
