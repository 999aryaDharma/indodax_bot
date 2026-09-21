# P0 — Financial safety Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans for one READY task; independent final review required.

**Goal:** Deliver the capabilities below without duplicating existing runtime primitives.

**Architecture:** Frozen two-system boundary, one shared runtime kernel with isolated adapters and namespaces.

**Tech Stack:** Existing Python/Pydantic/Decimal/SQLite research stack; pinned UI adapters only in RW8.

**Spec:** [Domain contracts](../CONTRACTS.md), [parity](../RUNTIME-PARITY.md), frozen system documents.

## Global Constraints

No live activation or credentials; immutable artifacts; manifest is status authority; no UI/MCP before services.

## Review Focus

Missing identity, duplicate effects, interrupted publication, stale revisions and execution-capability leakage must fail closed at the owning task boundary.

## Tasks

### PM-01 — Authoritative fail-closed pre-write gate

Current: Pipeline conditionally checks reconciliation; manual execution defaults missing capital.

Deliverable: All real writes need trusted current scoped evidence and exact approval re-risk.

Dependencies: RW0-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/production-main/PM-01-authoritative-fail-closed-pre-write-gate.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### PM-02 — Atomic financial execution state and recovery

Current: Ledger store exists but ingester/OMS/fill-ID application are separate mutations.

Deliverable: One authoritative transaction and verified restart across all financial effects.

Dependencies: RW0-01, LED-01. Complexity XL; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/production-main/PM-02-atomic-financial-execution-state-and-recovery.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### PM-04 — Venue parser cancellation and supported order semantics

Current: Read/write parser reuse and inconclusive-cancel exception already present.

Deliverable: Verify actual internal type mapping, supported LIMIT/TIF and race/partial-fill behavior.

Dependencies: PM-01, PM-02. Complexity M; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/production-main/PM-04-venue-parser-cancellation-and-supported-order-semantics.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
