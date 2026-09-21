# P1 — Governance and release Implementation Plan

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

### PM-03 — Recovery mode and durable operator risk governance

Current: Optional mode/kill/throttle persistence and reset health defaults permit weak paths.

Deliverable: Every boot enters RECOVERY; fail-closed durable mode/risk/approval authority.

Dependencies: PM-01, PM-02. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/production-main/PM-03-recovery-mode-and-durable-operator-risk-governance.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.

### PM-05 — Candidate-bound release provenance

Current: ReleaseBundle hashes fields but candidate identities optional; digest is not signature.

Deliverable: Complete release manifest and fail-closed verification with explicit authenticity policy.

Dependencies: RW4-01, PM-03. Complexity L; risk high.

[Exact task and LUNA handoff](../../../docs/sprints/production-main/PM-05-candidate-bound-release-provenance.md). Contains files, schema, interfaces, lifecycle, failure cases, tests and migration.
