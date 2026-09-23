# API-01 — Production service-derived read models Implementation Plan

> For agentic workers: implement this sprint only. Read authoritative live Production state without creating write authority. Independent review is required before DONE.

**Goal:** Expose immutable Production read snapshots assembled from authoritative live Production services, including fresh Indodax account balances and separately attributed Production-managed portfolio state.

**Architecture:** ProductionReadService.snapshot returns typed overview/mode/live Indodax account portfolio/managed positions/orders/fills/reconciliation/risk/release/audit views with UTC as_of, source_revision and provenance. Live account evidence comes through an injected Production-owned read-only provider backed by the existing Indodax account reader. Missing/stale sources remain UNAVAILABLE or UNKNOWN, never numeric zero.

**Tech Stack:** Python 3.11+, existing Pydantic/Decimal services and FastAPI where scoped.

**Spec:** docs/implementation/CONTRACTS.md and CR-2026-09-23.

## Metadata

Status: READY

Priority: P0 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: feat/api-01-production-control-plane

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: Planned implementation; dependencies and activation gates are separate.

## Goal

Expose immutable Production read snapshots assembled from authoritative live Production services, including fresh Indodax account balances and separately attributed Production-managed portfolio state.

## Why This Sprint Exists

This sprint is part of the read-only Production MVP admitted by CR-2026-09-23 and supplies a separately reviewable dependency for later nodes.

## Depends On

- API-00 — Shared API envelope, error, provenance and capability contracts
- PM-01 — Authoritative fail-closed pre-write gate
- PM-02 — Atomic financial execution state and recovery
- PM-03 — Recovery mode and durable operator risk governance
- PM-04 — Venue parser cancellation and supported order semantics

## Unlocks

API-02

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

API-00 contracts and the UI-00 frontend shell are present in this workspace; Production service-derived read models remain to be implemented after dependencies pass review.

## In Scope

Expose immutable Production read snapshots assembled from authoritative domain services.

Contract: ProductionReadService.snapshot returns typed overview/mode/live Indodax account portfolio/managed positions/orders/fills/reconciliation/risk/release/audit views with UTC as_of, source_revision and provenance. The account reader is injected by Production, read-only, and carries the exchange timestamp and measured freshness. Missing/stale sources remain UNAVAILABLE or UNKNOWN, never numeric zero.

## Out of Scope

Changing live activation, provisioning/changing credentials, order submission, withdrawal, venue writer access, ledger repair, Research feature implementation, Docker deployment and ASUS host changes. Existing Production-owned server credentials may be used only behind the injected read-only Indodax account provider; API/UI never receive them.

## User / Actor Behavior

The operator sees only explicit backend state and safe blocked/unavailable outcomes. Production and Research identity remain separate.

## Functional Requirements

FR-23 in the admitted read-only scope.

- Indodax account balances are read only through an injected Production-owned reader and carry the exchange timestamp/freshness
- Missing/stale Indodax account evidence is explicit and never becomes zero
- Research and shadow account/portfolio providers cannot satisfy Production account reads
- Execution state must be bound to an explicitly configured Production namespace and resolved Production database root; a matching namespace in a Research database is not sufficient
- Unknown managed positions/risk/reconciliation stay explicit and never become zero
- Read snapshots expose source revision and UTC as_of for every authority-backed resource
- PM-05 release evidence remains UNAVAILABLE until authoritative verified evidence exists

## Domain Rules / Invariants

Backend domain services own financial and operational truth. Unknown is distinct from zero. No UI state grants backend capability.

## Architecture / Design Contract

Production read models come only from Production-owned services and their own independently verified market/account/release authority. The Indodax account reader is read-only, injected by the Production runtime, and must declare its Production account authority; it must not load credentials or create a venue client in the API service. Carry the Indodax server timestamp and measured age into the read model. Execution state is bound to an explicitly configured Production namespace and database root. Never proxy ASUS Research Runtime feed health, account balances, database or shadow wallet as Production truth. Unknown or stale evidence remains explicit.

ProductionReadService.snapshot returns typed overview/mode/live Indodax account portfolio/managed positions/orders/fills/reconciliation/risk/release/audit views with UTC as_of, source_revision and provenance. Missing/stale sources remain UNAVAILABLE or UNKNOWN, never numeric zero.

## Planned Files / Artifacts

- src/indodax_lab/api/services/production_read.py
- src/indodax_lab/api/contracts/production.py
- tests/unit/lab/api/test_production_read_models.py

## Interfaces & Contracts

ProductionReadService.snapshot returns typed overview/mode/portfolio/positions/orders/fills/reconciliation/risk/release/audit views with UTC as_of, source_revision and provenance. Missing/stale sources remain UNAVAILABLE or UNKNOWN, never numeric zero.

## Data / Persistence Impact

Read-only. No schema migration, new database, credential store or cross-host SQLite access.

## API / External Contract Impact

Only the versioned read/API contract specified for this sprint. The injected Production account reader may use the existing adapter for read-only Indodax account reads; no order, cancel or withdrawal call is allowed. Tests use fakes and never contact Indodax.

## UI / UX Behavior

Backend only. No UI authority or UI-owned financial state.

## Implementation Steps

Inspect assigned paths and dependencies; write focused behavior tests; implement the smallest scoped change; run and record required checks; self-review and commit only owned files.

## Required Tests

- Indodax account balances expose the venue server timestamp and freshness
- Missing/stale Indodax account evidence stays explicit and never becomes zero
- Research/shadow account providers cannot be used by Production
- A Research database cannot satisfy Production execution state even when a namespace string matches
- Unknown managed positions/risk/reconciliation stay explicit and never become zero
- Read snapshots expose source revision and UTC as_of for every authority-backed resource
- PM-05 release evidence remains UNAVAILABLE until authoritative verified evidence exists

## Failure / Edge Cases

- Unknown positions/risk/reconciliation stay explicit and never become zero
- Read snapshots expose source revision and UTC as_of for every authority-backed resource
- PM-05 release evidence remains UNAVAILABLE until authoritative verified evidence exists
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

- **API-01-AC0**: Unknown positions/risk/reconciliation stay explicit and never become zero (test_api_01_0).
- **API-01-AC1**: Read snapshots expose source revision and UTC as_of for every authority-backed resource (test_api_01_1).
- **API-01-AC2**: PM-05 release evidence remains UNAVAILABLE until authoritative verified evidence exists (test_api_01_2).

## Definition of Done

All acceptance criteria are demonstrated; exact SHA and commands/results are recorded; independent reviewer passes; no Critical/Important finding remains.

## Reviewer Checklist

- [ ] Unknown positions/risk/reconciliation stay explicit and never become zero
- [ ] Research account provider and Research database are rejected by Production readers
- [ ] Read snapshots expose source revision and UTC as_of for every authority-backed resource
- [ ] PM-05 release evidence remains UNAVAILABLE until authoritative verified evidence exists
- [ ] Verify no unrelated paths or authority boundaries changed.

## Commit Guidance

Commit only paths owned by this sprint. Preserve dashboard.pen, design-prototype and unrelated user WIP.

## Handoff Requirements

Create docs/sprints/handoffs/API-01-HANDOFF.md with exact SHA, commands/results, review result and unresolved external gates.

## Ready-to-Run Implementation Prompt

Implement API-01 only. Read authoritative live Production state without creating write authority; stop if any dependency is not DONE.
