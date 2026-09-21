# RW5 — Tournament runtime Implementation Plan

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

### RW5-01 — Isolated durable forward-shadow agents

Current: LiveShadowEngine is one shared portfolio with checkpoints.

Deliverable: Candidate-bound isolated agent state and restart-safe lifecycle.

Dependencies: RW4-01, RP-05. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW5-01-isolated-durable-forward-shadow-agents.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### RW5-02 — Tournament cohorts leaderboard and qualification

Current: Historical tournament and simple promotion counters exist.

Deliverable: Comparable live cohorts and evidence-based qualification distinct from rank.

Dependencies: RW5-01, SHADOW-03. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW5-02-tournament-cohorts-leaderboard-and-qualification.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
