# Production Control Plane and Research Workbench Program Plan

> **For agentic workers:** Read this program plan, then execute only the assigned child plan. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`; every implementation unit needs a focused test, an exact commit, and independent review.

**Goal:** Build one dashboard and API surface that keeps Production Main and Research Workbench separate in authority, persistence, routes, and permissions while reusing the repository's shared runtime contracts.

**Architecture:** Use a modular monolith first: one FastAPI application and one React/TypeScript/Vite frontend shell, with explicit `production` and `research` route namespaces. Backend services remain authoritative; API routers expose service-derived read models and guarded commands. Production write authority remains unavailable until the frozen production gates and PM/RP dependencies are complete.

**Tech Stack:** Existing Python/Pydantic/Decimal/SQLite domain code; FastAPI and Uvicorn for the API; pinned React/TypeScript/Vite for the dashboard; Server-Sent Events for status streams; pytest and ruff for backend validation.

**Spec:** `docs/production/FROZEN-SYSTEMS.md`, `docs/production/main/*`, `docs/production/research-workbench/*`, `docs/implementation/RUNTIME-PARITY.md`, `docs/implementation/SYSTEM-DEPENDENCY-MAP.md`, and the three child plans in this directory.

## Current implementation reality

### Production Main — existing domain primitives

- Implemented or present: execution modes, durable mode store, manual approval store, authority gate implementation pending independent review, unified pipeline, OMS state machine, order router, Indodax read-only adapter, write-capable adapter, fill normalization/ingestion, durable ledger store, reconciliation engine, risk engine, portfolio constructor, release candidate packaging, backup/restore and service lifecycle utilities.
- Partial or blocked: PM-01 independent review; PM-02 atomic financial state; PM-03 recovery/operator governance; PM-04 venue parser/cancellation semantics; PM-05 candidate-bound release provenance; PM-06 CI/security/release evidence; RP-02 through RP-05 runtime parity.
- Missing: production API, stable API read models, authentication/authorization boundary, dashboard frontend, API audit projection, browser integration tests, and a production deployment contract.
- Safety status: the presence of `IndodaxTradingVenue` is not production qualification and does not authorize credentials, live writes, or activation.

### Research Workbench — existing domain primitives

- Implemented or present: RW0 immutable workbench contracts, RW1 dataset registry implementation awaiting independent review, backtest/data/model/feature modules, paper/shadow engine, release-candidate packaging, and many historical research task artifacts.
- Partial or blocked: RW1 review; component/pipeline registry services; experiment orchestration; candidate packaging integration; tournament agents; Portfolio Shadow; QuantOps MCP.
- Missing: research API, research read models, declarative pipeline editing API, dashboard Workbench, tournament views, and backend-to-UI provenance mapping.

### Shared dashboard reality

- `DESIGN.md` and `dashboard.pen` are design inputs, not backend contracts.
- No web API or frontend implementation exists in the current source tree.
- The dashboard must not read SQLite files directly or invent status. It consumes versioned Pydantic API schemas backed by domain services.

## Non-negotiable boundaries

- Production and Research use separate URL namespaces, service dependencies, persistence namespaces, and capability policies.
- Research endpoints never receive order-write or withdrawal credentials.
- Research cannot submit real orders, promote directly to live, bypass risk, mutate frozen candidates, or hot-replace a production model.
- Production write endpoints are disabled by default and remain blocked while required PM/RP gates are incomplete.
- UI actions are commands sent to backend authorities; the browser never owns financial truth, approval truth, OMS truth, ledger truth, or candidate identity.
- Tournament agents have isolated ledgers; Portfolio Shadow has intentionally shared capital; the API must expose these as different resource types.
- Every response carrying financial, candidate, dataset, experiment, or release state includes identity, `as_of`, status, and provenance.
- Every mutating command is idempotent, audited, authorization-checked, and rejected when the underlying authority is stale or unhealthy.

## Dependency order

```text
PM/RP prerequisite reviews
        ↓
Shared API schemas and error contract
        ↓
Production read models       Research read models
        ↓                              ↓
Production API boundary      Research API boundary
        ↓                              ↓
Unified dashboard shell and capability context
        ↓
Production views + Workbench views
        ↓
Guarded command endpoints and UI actions
        ↓
Integration/security/recovery qualification
```

Do not start dashboard pages before the relevant read models and API schemas exist. Do not expose Research mutation endpoints before their underlying registry/orchestration services exist.

## Child plans

1. [Production API](2026-09-22-production-api-plan.md) — production read models, guarded operator commands, audit and capability policy.
2. [Research Workbench API](2026-09-22-research-workbench-api-plan.md) — datasets, registries, experiments, candidates, agents, tournament and Portfolio Shadow read/mutation boundaries.
3. [Unified Dashboard](2026-09-22-unified-dashboard-plan.md) — one shell with separate Production and Research contexts, route guards, status streams and screens.

## Delivery waves

### Wave A — contracts and read-only API

Complete the first task of each child plan in dependency order. Deliver typed schemas, service-derived snapshots, health endpoints, and read-only routes. This wave is safe for paper/shadow environments and is the first implementer target.

### Wave B — dashboard shell and operational read views

Build the browser shell, environment switcher, authentication placeholder, route guards, Production Overview, Research navigation, and read-only status streams. Use fixture-backed API tests until services are ready.

### Wave C — research service integration

Unlock only after RW1/RW2/RW3/RW4/RW5/RW6 service dependencies are DONE. Add Workbench, dataset, experiment, candidate, tournament, and Portfolio Shadow views with provenance and explicit qualification status.

### Wave D — guarded production commands

Unlock only after PM-01 through PM-06 and required RP tasks are DONE and independently reviewed. Add mode transitions, kill switch requests, manual approvals, reconciliation inspection, and release operations. Keep live write capability disabled in development and test environments.

### Wave E — qualification and release evidence

Run security, duplicate-command, stale-revision, restart, authorization, and forbidden-capability tests. The dashboard/API release is not production activation. Activation remains governed by the frozen G0–G7 gates.

## First implementer task

The first coding task is `API-00` in the Production API child plan: create the shared API envelope, error, provenance, capability, and health schemas without adding a web framework route or changing domain behavior. It is small, reviewable, and unblocks both API branches.

## Cheap-model execution rules

1. Read `AGENTS.md`, this plan, the assigned child plan, the relevant frozen system documents, and only the listed source files.
2. Inspect `git status` and preserve `dashboard.pen`, `DESIGN.md`, and all unrelated WIP.
3. Implement one task only; do not redesign adjacent architecture.
4. Write the failing contract test first, then the smallest implementation, then focused and required regression tests.
5. Use fake services and temporary stores; never call public/private exchange endpoints from tests.
6. Record exact command, exit code, environment, and commit SHA in the handoff.
7. Stop at the task acceptance criteria. Do not add authentication vendors, message buses, microservices, GraphQL, websockets, or deployment automation unless a child task explicitly requires it.

## Review focus

- A Research request must be unable to resolve a production write capability or production credential.
- A stale or mismatched revision must make a command fail closed rather than return a success-shaped response.
- Duplicate command IDs and repeated browser retries must produce one effect.
- API responses must never confuse ranking with qualification or paper/shadow evidence with production authorization.
- Production and Research resources must not leak ledger, candidate, dataset, or persistence namespaces across boundaries.
