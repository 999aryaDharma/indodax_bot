# RP2 — Candidate and feature runtime Implementation Plan

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

### RP-02 — Shared candidate feature and exit evaluation

Current: Feature registry and registered TA implementations coexist with custom shadow feature/TA/exit code.

Deliverable: One verified evaluator independent of venue, training and ambient clock.

Dependencies: RW2-03, FEAT-02. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/runtime-parity/RP-02-shared-candidate-feature-and-exit-evaluation.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
