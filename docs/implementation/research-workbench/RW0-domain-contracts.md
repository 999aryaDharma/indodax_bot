# RW0 — Domain contracts Implementation Plan

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

### RW0-01 — Immutable Workbench domain manifests

Current: Typed market contracts and separate model/run records exist; aggregate domain identity is absent.

Deliverable: Deep immutable portable identities and state-machine contracts.

Dependencies: RP-01, DATA-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW0-01-immutable-workbench-domain-manifests.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
