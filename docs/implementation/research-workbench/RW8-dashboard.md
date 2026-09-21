# RW8 — Dashboard Implementation Plan

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

### RW8-01 — Research read models and dashboard navigation

Current: Console dashboard and design artifact exist; Workbench web app absent.

Deliverable: Service-derived views with provenance and explicit qualification state.

Dependencies: RW5-02, RW6-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW8-01-research-read-models-and-dashboard-navigation.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### RW8-02 — Workbench form and graph editors

Current: No manifest-backed UI editor exists.

Deliverable: Synchronized form/visual editing of one backend-validated pipeline draft.

Dependencies: RW8-01, RW2-03, RW3-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW8-02-workbench-form-and-graph-editors.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
