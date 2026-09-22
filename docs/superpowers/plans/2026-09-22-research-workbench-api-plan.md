# Research Workbench API Implementation Plan

> **For agentic workers:** Implement only after the underlying RW service dependency is DONE. A router must not invent a registry or mutate a database directly.

**Goal:** Expose Research Workbench datasets, components, pipelines, experiments, candidates, agents, tournaments, Portfolio Shadow, and promotion requests through a capability-isolated API.

**Architecture:** Research routes are read-first adapters over immutable registries and orchestration services. Every mutation creates a new version, draft, clone, experiment, candidate, or promotion request. The API never exposes production write authority.

**Tech Stack:** Python 3.11+, Pydantic, existing research services, FastAPI, pytest, ruff.

**Spec:** Frozen Research Workbench documents, RW0–RW9 plans, `docs/implementation/RUNTIME-PARITY.md`, and `2026-09-22-control-plane-program-plan.md`.

## API resource boundary

```text
GET  /api/v1/research/health
GET  /api/v1/research/datasets
GET  /api/v1/research/strategies
GET  /api/v1/research/models
GET  /api/v1/research/pipelines
GET  /api/v1/research/experiments
GET  /api/v1/research/backtests/{experiment_id}
GET  /api/v1/research/candidates
GET  /api/v1/research/agents
GET  /api/v1/research/tournaments
GET  /api/v1/research/portfolio-shadows
GET  /api/v1/research/leaderboard
GET  /api/v1/research/artifacts/{artifact_id}
GET  /api/v1/research/audit

POST /api/v1/research/datasets
POST /api/v1/research/experiments
POST /api/v1/research/experiments/{id}/clone
POST /api/v1/research/experiments/{id}/run
POST /api/v1/research/candidates
POST /api/v1/research/shadow-agents
POST /api/v1/research/promotion-requests
```

Forbidden routes include `submit_real_order`, `withdraw`, `direct_promote_live`, `bypass_risk`, `bypass_production_gate`, and `hot_replace_production_model`.

## Tasks

### RW-API-00 — Research API contracts and forbidden capability boundary

**Files:** Create `src/indodax_lab/api/contracts/research.py`, `src/indodax_lab/api/routers/research.py`, `src/indodax_lab/api/research_policy.py`; test `tests/unit/lab/api/test_research_policy.py`.

Define typed views for dataset identity, component identity, pipeline manifest, experiment lifecycle, candidate evidence, agent lifecycle, tournament metrics, Portfolio Shadow, and promotion request. Every view includes immutable identity, lifecycle state, provenance, and qualification state. Tests prove forbidden capability names cannot be registered or routed.

### RW-API-01 — Dataset and component read models

**Dependencies:** RW0-01 DONE; RW1-01 independently reviewed; RW2-01/RW2-02/RW2-03 for component resources.

**Files:** Create `src/indodax_lab/api/services/research_read.py`; test `tests/unit/lab/api/test_research_read_models.py`.

Expose dataset versions, quality reports, parent/extension links, strategy/model versions, pipeline manifests, schema identity, content hashes, and status. A completed dataset/config cannot be edited; mutation returns a new version or draft.

### RW-API-02 — Experiment, backtest, and artifact routes

**Dependencies:** RW3-01 and existing backtest services.

**Files:** Modify `src/indodax_lab/api/routers/research.py`; create `tests/integration/lab/api/test_experiment_routes.py`.

Implement create draft, validate, queue, run, cancel, status, result, compare, and clone. Completed and failed experiments remain immutable. Results include cost policy, seed, environment identity, Git SHA, dataset/pipeline IDs, artifact IDs, and explicit failure reason.

### RW-API-03 — Candidate and shadow-agent routes

**Dependencies:** RW4-01 and RW5-01.

**Files:** Modify `src/indodax_lab/api/routers/research.py`; create `tests/integration/lab/api/test_candidate_agent_routes.py`.

Candidate creation binds strategy, model hashes, pipeline graph, feature schema, dataset evidence, risk/execution assumptions, Git SHA, and evaluation evidence. Agent registration creates isolated namespace, virtual balance, ledger, positions, risk state, checkpoint, and lifecycle. No agent shares another agent's ledger.

### RW-API-04 — Tournament and Portfolio Shadow routes

**Dependencies:** RW5-02 and RW6-01.

**Files:** Create `src/indodax_lab/api/services/tournament_read.py`; modify router; test `tests/integration/lab/api/test_tournament_isolation_routes.py`.

Expose agent metrics, leaderboard, cohorts, qualification state, and comparisons. Expose Portfolio Shadow separately with shared capital and allocator state. API tests verify Agent A trade cannot change Agent B and that Portfolio Shadow is not reported as a tournament agent.

### RW-API-05 — Promotion request boundary

**Dependencies:** RW9-01 and PM-05.

**Files:** Create `src/indodax_lab/api/services/promotion.py`; modify router; test `tests/integration/lab/api/test_promotion_requests.py`.

`POST /promotion-requests` creates an auditable request only. It must not deploy, enable, or mutate production. The response includes missing gates, forward age, closed trade count, evidence IDs, candidate identity, and reviewer state.

### RW-API-06 — Research API qualification

**Dependencies:** RW-API-00 through RW-API-05.

**Files:** Create `tests/qualification/api/test_research_api_boundary.py`.

Test immutable dataset versions, completed experiment immutability, clone semantics, agent isolation, Portfolio Shadow separation, forbidden capability rejection, no production credentials, and provenance preservation across serialization.

## Definition of done

- Read and mutation endpoints exist only for services whose sprint dependencies are DONE.
- Every completed artifact is immutable and addressable by identity/hash.
- Promotion requests never become live deployment commands.
- Research API cannot import or instantiate production write adapters.
- Handoff records exact endpoint schemas, focused tests, full regression, and unresolved service dependencies.
