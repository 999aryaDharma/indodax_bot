# RP3 — Portfolio and risk parity Implementation Plan

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

### RP-03 — Shared portfolio sizing and risk semantics

Current: PortfolioConstructor drops intent metadata and overwrites same-pair intents; risk caller semantics differ.

Deliverable: Deterministic allocation preserving lineage, costs, exits and order semantics.

Dependencies: RW0-01, SIM-02. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/runtime-parity/RP-03-shared-portfolio-sizing-and-risk-semantics.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
