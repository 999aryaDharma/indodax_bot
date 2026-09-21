# RW6 — Portfolio Shadow Implementation Plan

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

### RW6-01 — Separate shared-capital Portfolio Shadow

Current: SharedCapitalLedger allocates cash outside common financial runtime.

Deliverable: Intentional multi-candidate capital sharing through one common ledger/risk authority.

Dependencies: RW5-01, RP-03. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW6-01-separate-shared-capital-portfolio-shadow.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
