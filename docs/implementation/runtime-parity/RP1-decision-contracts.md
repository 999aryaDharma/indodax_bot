# RP1 — Decision contracts Implementation Plan

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

### RP-01 — Shared SignalIntent ownership with compatibility

Current: All three paths already import SignalIntent from backtest.events.

Deliverable: Neutral ownership needed before widening parity; preserve exact class behavior.

Dependencies: DOC-01, BASE-01. Complexity S; risk medium.

[Exact task and LUNA handoff](../../../docs/sprints/runtime-parity/RP-01-shared-signalintent-ownership-with-compatibility.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
