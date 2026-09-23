# Production Main API Implementation Plan

> **For agentic workers:** Implement one task at a time. Do not enable live trading, add credentials, or expose a direct venue write route. Independent review is required for every task.

**Goal:** Expose Production Main state and guarded operator controls through a typed API without moving authority out of the existing control, OMS, ledger, risk, reconciliation, and release services.

**Architecture:** FastAPI routers are thin adapters. Domain services remain authoritative. Read routes use immutable service snapshots; command routes call existing authorities and return command receipts. `/api/v1/production/*` is isolated from `/api/v1/research/*` by dependency injection and capability policy.

**Tech Stack:** Python 3.11+, Pydantic, existing Decimal/SQLite services, FastAPI, Uvicorn, pytest, ruff.

**Spec:** Frozen Production Main documents, `docs/implementation/CONTRACTS.md`, `docs/implementation/RUNTIME-PARITY.md`, PM-01–PM-06, and `2026-09-22-control-plane-program-plan.md`.

## Global constraints

- Development and test defaults are `DISABLED`, `RECOVERY`, `READ_ONLY`, or `SHADOW`.
- No endpoint accepts or stores exchange API keys in request bodies, browser storage, logs, or fixtures.
- No endpoint calls `IndodaxTradingVenue` directly from a router.
- No endpoint reports production `READY` merely because a service is reachable.
- Financial values serialize as decimal strings, never binary floats.
- Responses include `request_id`, `as_of`, `source_revision`, and explicit status.
- Command endpoints require idempotency keys and produce durable audit records.

## Existing services to reuse

- `src/indodax_lab/control/mode.py`
- `src/indodax_lab/control/approval.py`
- `src/indodax_lab/control/authority.py`
- `src/indodax_lab/control/pipeline.py`
- `src/indodax_lab/execution/oms.py`
- `src/indodax_lab/execution/oms_store.py`
- `src/indodax_lab/execution/ledger_store.py`
- `src/indodax_lab/execution/reconciliation.py`
- `src/indodax_lab/execution/reconciliation_store.py`
- `src/indodax_lab/risk/engine.py`
- `src/indodax_lab/portfolio/constructor.py`
- `src/indodax_lab/verification/release.py`

## API resource boundary

```text
GET  /api/v1/production/health
GET  /api/v1/production/overview
GET  /api/v1/production/mode
GET  /api/v1/production/portfolio
GET  /api/v1/production/positions
GET  /api/v1/production/orders
GET  /api/v1/production/fills
GET  /api/v1/production/ledger/summary
GET  /api/v1/production/reconciliation/latest
GET  /api/v1/production/risk
GET  /api/v1/production/releases/current
GET  /api/v1/production/audit
GET  /api/v1/production/events

POST /api/v1/production/commands/mode-transition
POST /api/v1/production/commands/kill-switch
POST /api/v1/production/commands/approval/{proposal_id}/decide
POST /api/v1/production/commands/reconciliation/run
```

There is deliberately no generic `POST /orders`, `POST /withdraw`, `POST /promote-live`, or `POST /model-reload` route. Order submission remains inside the reviewed pipeline and authority gate.

## Tasks

### API-00 — Shared envelope, error, provenance, and capability contracts

**Files:** Create `src/indodax_lab/api/__init__.py`, `src/indodax_lab/api/contracts/common.py`, `src/indodax_lab/api/capabilities.py`; test `tests/unit/lab/api/test_common_contracts.py`.

**Produces:** `ApiEnvelope[T]`, `ApiError`, `Provenance`, `Capability`, `RequestContext`, `IdempotencyKey`.

Required behavior:

- `ApiEnvelope` carries `request_id`, `as_of`, `source_revision`, `status`, `data`, and `provenance`.
- `ApiError` carries stable `code`, human-safe `message`, `retryable`, and optional `details`.
- Decimal fields use string serialization.
- UTC timestamps reject naive values.
- Capabilities include `production.read`, `production.control`, `production.write`, `research.read`, and `research.mutate`; the development default denies `production.write`.
- Tests cover malformed timestamps, non-finite Decimal, unknown capabilities, and serialization round trips.

### API-01 — Production read-model service

**Files:** Create `src/indodax_lab/api/services/production_read.py`, `src/indodax_lab/api/contracts/production.py`; test `tests/unit/lab/api/test_production_read_models.py`.

**Consumes:** Existing mode store, OMS store, ledger store, reconciliation store, risk engine, release manager.

**Produces:** `ProductionOverview`, `ProductionModeView`, `PortfolioView`, `RiskView`, `ReconciliationView`, `ReleaseView` and `ProductionReadService.snapshot()`.

Rules:

- Read models are assembled from service interfaces, never direct SQL in the router.
- Missing data returns explicit `UNAVAILABLE`/`BLOCKED`, never zero defaults.
- Overview exposes mode, venue health, market health, reconciliation, unknown orders, risk state, release identity, and last audit event.
- Production financial truth is labeled authoritative only when source revision and reconciliation status are healthy.
- Tests use fake stores and verify stale/missing/unknown conditions.

### API-02 — FastAPI application and read-only Production routes

**Dependencies:** API-01 and API-03 DONE and independently reviewed.

**Files:** Create `src/indodax_lab/api/app.py`, `src/indodax_lab/api/dependencies.py`, `src/indodax_lab/api/routers/production.py`; test `tests/integration/lab/api/test_production_routes.py`.

Endpoints:

- `GET /health` returns process health only.
- `GET /overview`, `/mode`, `/portfolio`, `/positions`, `/orders`, `/fills`, `/ledger/summary`, `/reconciliation/latest`, `/risk`, `/releases/current`, `/audit` return typed envelopes.
- No route imports the write-capable venue adapter.
- Route tests assert JSON schema, decimal strings, UTC, provenance, and no secret leakage.

### API-03 — Capability policy and audit middleware

**Dependencies:** API-00 DONE.

**Files:** Modify `src/indodax_lab/api/dependencies.py`; create `src/indodax_lab/api/auth.py`, `src/indodax_lab/api/audit.py`; test `tests/unit/lab/api/test_capability_policy.py` and `tests/integration/lab/api/test_api_audit.py`.

Required behavior:

- Development mode uses explicit local operator identity supplied by test dependency injection, never an implicit production user.
- Every request receives a request ID.
- Every request/command attempt records actor or explicit anonymous identity, capability, resource, decision, reason code, source revision, request ID, and timestamp. Missing Production identity fails closed; do not add an implicit local Production operator.
- Missing capability returns `403`; stale/unhealthy authority returns `409` or `423` with stable error code.
- Research capability cannot satisfy production capability checks.

### API-04 — Guarded mode, kill-switch, approval, and reconciliation commands

**Dependencies:** PM-01, PM-02, PM-03 and PM-04 DONE and independently reviewed; API-02 DONE. API-04 is outside the read-only MVP.

**Files:** Modify `src/indodax_lab/api/routers/production.py`; create `src/indodax_lab/api/contracts/commands.py`; test `tests/integration/lab/api/test_production_commands.py`.

Commands:

- Mode transition calls `DurableModeStore` and validates legal transitions.
- Kill-switch activation is idempotent and always allowed for an authorized production operator; reset requires current reconciliation, risk, and approval evidence.
- Approval decision calls `ManualApprovalStore` and forces fresh authority re-risk before execution.
- Reconciliation run is a diagnostic command and cannot repair ledger or venue state automatically.
- In tests and development, any command that would submit a real venue order returns `PRODUCTION_WRITE_DISABLED` before adapter resolution.

### API-05 — Operational event stream

**Dependencies:** API-01 and API-02.

**Files:** Create `src/indodax_lab/api/events.py`, add `GET /api/v1/production/events`; test `tests/integration/lab/api/test_production_events.py`.

Use Server-Sent Events with bounded replay by event ID. Emit mode changes, reconciliation status, unknown-order count, risk halt, approval decisions, release changes, and audit events. A dropped client reconnects from the last event ID or receives an explicit `REPLAY_UNAVAILABLE` response. Do not stream secrets or raw credentials.

### API-06 — Production API qualification

**Dependencies:** API-00 through API-05, PM-02, PM-05, PM-06, RP-04, RP-05.

**Files:** Create `tests/qualification/api/test_production_api_boundary.py`; update production API handoff documentation.

Test matrix:

- Research capability cannot call production command routes.
- Repeated idempotency key has one effect.
- Stale revision rejects command.
- Unknown OMS order blocks exposure-increasing command.
- Restart restores read-model source revisions and audit continuity.
- No production route imports or instantiates write venue in default environment.

## Definition of done

- Read-only production API routes pass schema, provenance, and secret-redaction tests.
- Guarded commands are unreachable until their PM/RP dependencies are DONE.
- API has no generic order-write or withdrawal endpoint.
- Exact source SHA, test exits, environment, and unresolved external gates are recorded in `docs/sprints/handoffs/API-PRODUCTION-HANDOFF.md`.
