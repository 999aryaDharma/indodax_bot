# RP4 — Runtime environment adapters Implementation Plan

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

### RP-04 — Canonical feed and environment runtime adapters

Current: MarketGateway and fake venue exist; shadow polls per engine and bypasses OMS.

Deliverable: One production-shaped core with simulated adapters and credential-free research wiring.

Dependencies: RP-02, RP-03, PM-02. Complexity XL; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/runtime-parity/RP-04-canonical-feed-and-environment-runtime-adapters.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
