# RW3 — Experiment and backtest orchestration Implementation Plan

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

### RW3-01 — Experiment lifecycle and backtest orchestration

Current: Run registry, replay engine and leased queue exist independently.

Deliverable: Immutable experiment revisions with durable run/cancel/finalization and comparable results.

Dependencies: RW1-01, RW2-03, RP-04, EVAL-01, JOB-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW3-01-experiment-lifecycle-and-backtest-orchestration.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
