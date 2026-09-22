# API, Production Main, Research Workbench, and Unified Dashboard Roadmap

Classification: TARGET PLANNING. The sprint manifest remains the only status/DAG authority. The units below are a required decomposition proposal; they become claimable only after a coordinated change request adds them to `docs/sprints/sprint-manifest.json` and creates the matching sprint files.

## Why this decomposition exists

The existing roadmap has strong domain and safety tasks but does not provide enough executable units for the API and dashboard program. `RW8-01` and `RW8-02` currently cover Research Workbench dashboard work; they do not cover the shared API contracts, Production Main read models, production command boundary, shared frontend shell, Production screens, or cross-context security tests.

The target is one control-plane product with two authority domains:

```text
One frontend shell
├── Production context → production services, production namespace, guarded controls
└── Research context   → research services, research namespace, evidence workflows
```

The contexts share navigation, request transport, status components, audit presentation, and visual language. They do not share credentials, persistence namespaces, write capabilities, or authority decisions.

## Current status of the feature families

| Family | Current reality | Official sprint authority | Next condition |
|---|---|---|---|
| Production domain | Core Python primitives exist; PM-01 review pending; PM-02–PM-06 planned | PM-01–PM-06 | Finish P0 safety tasks before guarded write controls |
| Research domain | RW0 done; RW1 review pending; registries/orchestration still incomplete | RW0–RW9 | Finish service dependencies before mutation API |
| Shared API contracts | Not implemented | No manifest node yet | Add `API-00` change-request node |
| Production API | Not implemented | No manifest node yet | Add `API-01`/`API-02` nodes |
| Research API | Not implemented | No manifest node yet | Add `API-03`/`API-04` nodes |
| Unified frontend shell | No web frontend in source tree; `DESIGN.md` is design input | RW8-01/02 are research-only | Add UI shell and production view nodes |
| Dashboard qualification | No browser/API boundary suite | No manifest node | Add security/isolation qualification node |

## Proposed sprint decomposition

These are planning IDs, not current `READY` tasks.

### API-00 — Shared API contracts and capability vocabulary

**Dependencies:** `RW0-01`.

**Deliverable:** Pydantic API envelope, stable errors, provenance, request context, idempotency key, decimal/UTC serialization, and capability names shared by both domains.

**Required tests:** malformed UTC, non-finite Decimal, unknown capability, stable error JSON, request ID propagation, and round-trip serialization.

**Files:** `src/indodax_lab/api/contracts/common.py`, `src/indodax_lab/api/capabilities.py`, `tests/unit/lab/api/test_common_contracts.py`.

**Unlocks:** `API-01`, `API-03`, shared frontend client.

### API-01 — Production read models

**Dependencies:** `API-00`, existing mode/OMS/ledger/reconciliation/risk/release services. PM-01 review is required before exposing authority-dependent status.

**Deliverable:** Service-derived `ProductionOverview`, mode, portfolio, positions, orders, fills, ledger summary, reconciliation, risk, release, and audit read models.

**Invariants:** No direct router-to-SQL; unavailable data remains unavailable; unknown metrics never become zero; every view carries `as_of`, source revision, and provenance.

**Files:** `src/indodax_lab/api/services/production_read.py`, `src/indodax_lab/api/contracts/production.py`, `tests/unit/lab/api/test_production_read_models.py`.

**Unlocks:** `API-02`, `UI-02`.

### API-02 — Production API boundary and read routes

**Dependencies:** `API-01`.

**Deliverable:** FastAPI app/dependencies and `/api/v1/production/*` read routes for health, overview, portfolio, positions, orders, fills, reconciliation, risk, releases, audit, and events.

**Forbidden:** Generic order submit, withdrawal, direct venue adapter resolution, model hot replacement, and direct ledger repair.

**Required tests:** schema responses, decimal strings, secret redaction, route import firewall, pagination, outage behavior, and default environment with no writer instantiated.

**Files:** `src/indodax_lab/api/app.py`, `src/indodax_lab/api/dependencies.py`, `src/indodax_lab/api/routers/production.py`, `tests/integration/lab/api/test_production_routes.py`.

**Unlocks:** `API-05`, `UI-01`, `UI-02`.

### API-03 — Research read models

**Dependencies:** `API-00`, `RW1-01`, `RW2-01`, `RW2-02`, `RW2-03`.

**Deliverable:** Dataset, strategy, model, pipeline, experiment, candidate, agent, tournament, Portfolio Shadow, artifact, and promotion-request read models.

**Invariants:** Immutable versions expose identity/hash/parent; lifecycle status is explicit; ranking never becomes qualification; tournament and Portfolio Shadow are separate types.

**Files:** `src/indodax_lab/api/services/research_read.py`, `src/indodax_lab/api/contracts/research.py`, `tests/unit/lab/api/test_research_read_models.py`.

**Unlocks:** `API-04`, `UI-03`.

### API-04 — Research API boundary and guarded mutations

**Dependencies:** `API-03`, `RW3-01`, `RW4-01`, `RW5-01`, `RW5-02`, `RW6-01`, `RW9-01`.

**Deliverable:** `/api/v1/research/*` routes for immutable registry reads, draft/clone operations, experiment lifecycle, candidate creation, agent registration, tournament controls, Portfolio Shadow, and promotion requests.

**Forbidden:** `submit_real_order`, `withdraw`, `direct_promote_live`, `bypass_risk`, `bypass_production_gate`, and `hot_replace_production_model`.

**Required tests:** completed experiment immutability, clone identity, dataset version immutability, agent isolation, Portfolio Shadow separation, forbidden capability rejection, and no import path to production writer.

**Files:** `src/indodax_lab/api/routers/research.py`, `src/indodax_lab/api/research_policy.py`, `tests/integration/lab/api/test_research_routes.py`.

**Unlocks:** `UI-01`, `UI-03`, `API-06`.

### API-05 — Guarded Production commands

**Dependencies:** `PM-01`, `PM-02`, `PM-03`, `PM-04`, `API-02` all independently reviewed.

**Deliverable:** Explicit commands for legal mode transitions, kill-switch activation/reset, manual approval decision, and reconciliation run. Every command is authority-checked, audited, idempotent, and disabled in development/test for live writes.

**Files:** `src/indodax_lab/api/contracts/commands.py`, `src/indodax_lab/api/routers/production_commands.py`, `tests/integration/lab/api/test_production_commands.py`.

**Unlocks:** `UI-04`.

### API-06 — Cross-context API security qualification

**Dependencies:** `API-02`, `API-04`, `API-05`, `RP-05`, `PM-06`.

**Deliverable:** One qualification suite proving that Research cannot reach Production authority, stale revisions reject, duplicate commands produce one effect, and browser retries do not duplicate effects.

**Files:** `tests/qualification/api/test_control_plane_firewall.py`, `docs/sprints/handoffs/API-QUALIFICATION-HANDOFF.md`.

### UI-01 — Shared dashboard shell and capability context

**Dependencies:** `API-00`, `API-02`, `API-04`.

**Deliverable:** React/TypeScript/Vite shell, typed client, `/production/*` and `/research/*` route namespaces, environment switcher, capability guard, global status strip, error/loading/blocked states.

**Files:** `frontend/src/app/*`, `frontend/src/api/*`, `frontend/src/components/StatusStrip.tsx`, `frontend/src/app/CapabilityBoundary.tsx`.

### UI-02 — Production operational dashboard

**Dependencies:** `UI-01`, `API-02`.

**Deliverable:** Production Overview, Portfolio, Positions, Orders, Reconciliation, Risk, Releases, Audit, and read-only Approval pages.

**Required states:** healthy, stale market, RECOVERY, HALTED, reconciliation mismatch, unknown OMS, unavailable risk authority, unavailable release evidence.

### UI-03 — Research Workbench dashboard

**Dependencies:** `UI-01`, `API-04`, existing `RW8-01`/`RW8-02` scope.

**Deliverable:** Dataset, Strategy, Model, Pipeline, Experiment, Backtest, Candidate, Tournament, Portfolio Shadow, and Promotion Request views.

**Required behavior:** completed experiments cannot be edited; clone creates new identity; rank and qualification are separate; agent ledger isolation is visible.

### UI-04 — Guarded command workflows

**Dependencies:** `API-05`, `UI-02`.

**Deliverable:** Mode transition, kill switch, approval decision, and reconciliation command flows with revision, actor, reason, expiry, idempotency, and backend result visible.

**Forbidden:** generic order form, credential prompt, automatic balance correction, direct promotion, or live model replacement.

### UI-05 — Browser and dashboard qualification

**Dependencies:** `UI-02`, `UI-03`, `UI-04`, `API-06`.

**Deliverable:** Browser tests for route isolation, Research/Production capability separation, stale command, duplicate click, completed experiment immutability, Tournament versus Portfolio Shadow semantics, SSE reconnect, and permission denial.

## Proposed dependency graph

```text
RW0-01
  ↓
API-00 ───────────────┐
  ↓                    │
API-01 → API-02 ──────┼→ UI-01 → UI-02 → UI-04 → UI-05
  ↓                    │     ↘ UI-03 ────────↗
API-03 → API-04 ──────┘
             ↓
          API-06

PM-01 → PM-02 → PM-03/PM-04 → PM-05 → PM-06
                 └──────────────→ API-05
```

## Required manifest change before implementation

The coordinator must add the proposed nodes to `docs/sprints/sprint-manifest.json`, create one canonical sprint file per node under an approved domain folder, update `00-sprint-index.md`, `01-dependency-graph.md`, `02-execution-waves.md`, `FEATURE-MAP.md`, and requirements traceability, then run `python docs/quality/validate_planning.py --self-test`.

Until that change is complete:

- these IDs are not `READY`;
- no implementer may claim them through the sprint queue;
- `RW8-01` and `RW8-02` remain the only official dashboard nodes;
- the existing PM/RW/RP dependencies retain priority.

## Cheap-model handoff rule

Give the implementer exactly one ID, its sprint file, this roadmap, the required-reading list, and the affected source paths. The implementer must not choose a different API framework, add a database, split into microservices, or combine Production and Research routes. If the required dependency is not `DONE`, stop with `BLOCKED` and report the exact manifest status.
