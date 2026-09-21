# P2 — Operational release evidence Implementation Plan

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

### PM-06 — CI security and operational release evidence

Current: CI tests/lints subsets; service templates and deployment workflow are not governed release proof.

Deliverable: Reproducible environment, security evidence and executable service/recovery drills.

Dependencies: PM-05, RW5-01. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/production-main/PM-06-ci-security-and-operational-release-evidence.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
