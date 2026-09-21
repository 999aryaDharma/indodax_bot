# RW9 — Production bridge Implementation Plan

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

### RW9-01 — Promotion request and production export bridge

Current: Promotion counters/release utilities exist without complete bridge.

Deliverable: Immutable export and governed request only; production owns release approval.

Dependencies: RW4-01, RW5-02, PM-05. Complexity M; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW9-01-promotion-request-and-production-export-bridge.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
