# RW1 — Dataset registry Implementation Plan

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

### RW1-01 — Reusable immutable dataset registry

Current: Backfill/snapshot/quality/publication and inventory exist; aggregate identity contains root paths.

Deliverable: Range-aware reusable versions, atomic catalog publication and explicit quality lineage.

Dependencies: RW0-01, DATA-06. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW1-01-reusable-immutable-dataset-registry.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
