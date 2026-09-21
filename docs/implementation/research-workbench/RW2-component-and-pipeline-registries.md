# RW2 — Component and pipeline registries Implementation Plan

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

### RW2-01 — Durable versioned strategy registry

Current: StrategyRegistry is in-memory; built-in strategies and YAML specifications already work.

Deliverable: Draft revisions, stable code identity and published component discovery.

Dependencies: RW0-01, STRAT-01. Complexity M; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW2-01-durable-versioned-strategy-registry.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### RW2-02 — Model registry and offline training services

Current: M01 portable bundles, M02/optional DL trainers and raw artifact files exist.

Deliverable: One model identity/loader contract and immutable training/evaluation evidence.

Dependencies: RW0-01, ML-04, JOB-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW2-02-model-registry-and-offline-training-services.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### RW2-03 — Typed declarative pipeline composer

Current: Callbacks and pair branches compose strategies ad hoc.

Deliverable: One validated graph for TA-only and hybrid compositions.

Dependencies: RW2-01, RW2-02. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/research-workbench/RW2-03-typed-declarative-pipeline-composer.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
