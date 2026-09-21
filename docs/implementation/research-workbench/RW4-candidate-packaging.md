# RW4 — Candidate packaging Implementation Plan

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

### RW4-01 — Immutable candidate packaging and lifecycle

Current: Model/release bundles and candidate IDs exist; no full immutable research package.

Deliverable: Verified configuration plus evidence binding and append-only candidate lifecycle.

Dependencies: RW3-01, ML-04. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW4-01-immutable-candidate-packaging-and-lifecycle.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
