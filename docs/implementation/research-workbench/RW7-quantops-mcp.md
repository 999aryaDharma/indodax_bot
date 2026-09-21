# RW7 — QuantOps MCP Implementation Plan

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

### RW7-01 — Read-only QuantOps MCP boundary

Current: No tracked QuantOps server found; services are planned.

Deliverable: Allowlisted read-only discovery over existing typed service contracts.

Dependencies: RW1-01, RW2-03, RW4-01. Complexity M; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW7-01-read-only-quantops-mcp-boundary.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### RW7-02 — Audited QuantOps research mutations

Current: Mutation wrappers absent; service behavior must exist first.

Deliverable: Idempotent draft/job/agent control with append-only audit and promotion-request ceiling.

Dependencies: RW7-01, RW5-02, RW6-01, RW9-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW7-02-audited-quantops-research-mutations.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
