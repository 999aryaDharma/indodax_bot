# Production Control Plane and Research Workbench Program Plan

> **For agentic workers:** Read this program plan, then execute only the assigned child plan. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`; every implementation unit needs a focused test, an exact commit, and independent review.

**Goal:** Build one dashboard and API surface that keeps Production Main and Research Workbench separate in authority, persistence, routes, and permissions while reusing the repository's shared runtime contracts.

**Architecture:** Use a modular monolith first: one FastAPI application and one React/TypeScript/Vite frontend shell, with explicit `production` and `research` route namespaces. Backend services remain authoritative; API routers expose service-derived read models and guarded commands. Production write authority remains unavailable until the frozen production gates and PM/RP dependencies are complete.

**Tech Stack:** Existing Python/Pydantic/Decimal/SQLite domain code; FastAPI and Uvicorn for the API; pinned React/TypeScript/Vite with Cloudflare Kumo UI and locally hosted Vercel Geist Sans/Mono for the dashboard; Server-Sent Events for status streams; pytest and ruff for backend validation.

**Spec:** `docs/production/FROZEN-SYSTEMS.md`, `docs/production/main/*`, `docs/production/research-workbench/*`, `docs/implementation/RUNTIME-PARITY.md`, `docs/implementation/SYSTEM-DEPENDENCY-MAP.md`, and the three child plans in this directory.

## Current implementation reality

### Production Main — existing domain primitives

- Implemented or present: execution modes, durable mode store, manual approval store, reviewed authority gate, unified pipeline, OMS state machine, order router, Indodax read-only adapter, write-capable adapter, fill normalization/ingestion, durable ledger store, reconciliation engine, risk engine, portfolio constructor, release candidate packaging, backup/restore and service lifecycle utilities.
- PM-01 through PM-04 are DONE in the current manifest. PM-05 candidate-bound release provenance and PM-06 CI/security/release evidence remain PLANNED; RP-02 through RP-05 runtime parity remain incomplete.
- Missing: production API, stable API read models, authentication/authorization boundary, dashboard frontend, API audit projection, browser integration tests, and a production deployment contract.
- Safety status: the presence of `IndodaxTradingVenue` is not production qualification and does not authorize credentials, live writes, or activation.

### Research Workbench — existing domain primitives

- Implemented or present: RW0 immutable workbench contracts and RW1 dataset registry are DONE in the current manifest; backtest/data/model/feature modules, paper/shadow engine, release-candidate packaging, and historical research task artifacts exist.
- Later component/pipeline registry services, experiment orchestration, candidate packaging integration, tournament agents, Portfolio Shadow and QuantOps MCP remain in planned research sprints.
- Missing: research API, research read models, declarative pipeline editing API, dashboard Workbench, tournament views, and backend-to-UI provenance mapping.

### Shared dashboard reality

- `DESIGN.md` and `dashboard.pen` are design inputs, not backend contracts.
- API-00 shared contracts and UI-00 Kumo/Geist shell are implemented in the current workspace and awaiting independent review; production read models/routes and operational pages remain outstanding.
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
API-00 shared contracts
  ├── API-01 Production read models ─┐
  ├── API-03 fail-closed capability ├── API-02 Production read routes ── UI-02 Production views
  └── UI-00 Kumo/Geist shell ─ UI-01 capability context ─────────────────┘

Research APIs/UI remain a separate later dependency branch.
```

Do not start dashboard pages before the relevant read models and API schemas exist. Do not expose Research mutation endpoints before their underlying registry/orchestration services exist.

## Child plans

1. [Production API](2026-09-22-production-api-plan.md) — production read models, guarded operator commands, audit and capability policy.
2. [Research Workbench API](2026-09-22-research-workbench-api-plan.md) — datasets, registries, experiments, candidates, agents, tournament and Portfolio Shadow read/mutation boundaries.
3. [Unified Dashboard](2026-09-22-unified-dashboard-plan.md) — one shell with separate Production and Research contexts, route guards, status streams and screens.

## Delivery waves

### Wave A — shared contracts, Production read models and frontend foundation

API-00 and UI-00 can proceed in parallel on disjoint paths. After their independent PASS, API-01, API-03 and UI-01 can proceed according to the manifest DAG. Finish API-02 after API-01/API-03, then UI-02. These are read-only control-plane implementation sprints for the owner's live Production Main; Research/shadow state remains isolated. This plan does not authorize live execution changes or host deployment.

### Wave B — dashboard shell and operational read views

Complete UI-00/UI-01/UI-02 according to the manifest DAG. Use the design system Kumo components plus Geist Sans/Mono while matching `DESIGN.md`; use fixture-backed client checks only where the backend route is not yet available.

### Wave C — research service integration

Unlock only after RW1/RW2/RW3/RW4/RW5/RW6 service dependencies are DONE. Add Workbench, dataset, experiment, candidate, tournament, and Portfolio Shadow views with provenance and explicit qualification status.

### Wave D — guarded production commands

Unlock only after PM-01 through PM-06 and required RP tasks are DONE and independently reviewed. Add mode transitions, kill switch requests, manual approvals, reconciliation inspection, and release operations. Keep live write capability disabled in development and test environments.

### Wave E — qualification and release evidence

Run security, duplicate-command, stale-revision, restart, authorization, and forbidden-capability tests. The dashboard/API release is not production activation. Activation remains governed by the frozen G0–G7 gates.

## First implementer task

The first coding tasks are `API-00` and `UI-00` in the Production API and Unified Dashboard child plans. They have disjoint paths and no dependencies; each requires its own independent PASS before downstream nodes unlock.

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

## 2026-09-24 scope amendment

`docs/decisions/ADR-010-multi-strategy-production-and-guarded-controls.md` admits API-04/UI-03 for the exact commands in `docs/implementation/BOT-TRADE-PROGRAM.md`. Manifest owns dependencies and status; source inspection or this admission is not proof that the new commands exist.
