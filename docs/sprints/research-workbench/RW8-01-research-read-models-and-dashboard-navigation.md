# RW8-01 — Research read models and dashboard navigation Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Service-derived views with provenance and explicit qualification state.

**Architecture:** Shared runtime contracts with environment-specific adapters; reuse existing source primitives.

**Tech Stack:** Python 3.11+, Pydantic, Decimal, SQLite; existing optional research environments. UI tasks additionally use pinned React/TypeScript/Vite and FastAPI.

**Spec:** `docs/implementation/CONTRACTS.md` and frozen Required Reading.

## Global Constraints

No real execution/credentials; no main/merge/push/deploy; immutable candidates/datasets; >=90 days AND >=100 closed forward trades; single writer; no shared SQLite WAL across hosts.

## Review Focus

- Corrupt/mismatched identity cannot authorize downstream use.

- Missing evidence must not become a numeric success/default.

- Duplicate request/event cannot duplicate effect.

- Interrupted state publication cannot acknowledge completion.

- Research path cannot gain real write authority.

Apply these to the task-owned boundaries; test rows below pin concrete relevant cases.

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: research-workbench | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/rw8-01-research-read-models-and-dashboard-navigation`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Service-derived views with provenance and explicit qualification state.

## Why This Sprint Exists

Purpose: Research read models and dashboard navigation. Gap: Service-derived views with provenance and explicit qualification state.

## Depends On

- RW5-02 — Tournament cohorts leaderboard and qualification
- RW6-01 — Separate shared-capital Portfolio Shadow

## Unlocks

RW8-02

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/production/main/SOP-AND-GATES.md`
- `docs/production/research-workbench/DOMAIN-AND-LIFECYCLE.md`
- `docs/implementation/CONTRACTS.md`
- `docs/implementation/RUNTIME-PARITY.md`
- `docs/specs/20-testing-strategy.md`
- `docs/decisions/ADR-010-multi-strategy-production-and-guarded-controls.md`
- `docs/implementation/BOT-TRADE-PROGRAM.md`

## Current Context

Console dashboard and design artifact exist; Workbench web app absent.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

Owner-approved 2026-09-24 amendment: implement this sprint's behavior in `docs/implementation/BOT-TRADE-PROGRAM.md`; prior requirements remain mandatory.

- Implement read DTOs from services, not UI-owned state

- Create research navigation and provenance-rich detail/compare views

- Show missing metrics as unavailable and rank separate from qualification

- Add accessible tabular/keyboard navigation and artifact downloads

- Keep production controls outside this API

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW8-01-FR0:** View values reconcile with authoritative store.

1. **RW8-01-FR1:** Unknown metric never displayed as zero.

2. **RW8-01-FR2:** Agent detail shows isolated namespace and candidate digest.

3. **RW8-01-FR3:** Pagination stable under new records.

4. **RW8-01-FR4:** Read API cannot mutate or return private credentials.

## Domain Rules / Invariants

GET /research/{datasets,strategies,models,pipelines,experiments,backtests,candidates,tournament,agents,portfolio-shadow}; GET collection/{id}. DTOs expose immutable refs, lifecycle, metrics validity and incident/qualification reasons; cursor pagination with stable ID ordering.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. GET /research/{datasets,strategies,models,pipelines,experiments,backtests,candidates,tournament,agents,portfolio-shadow}; GET collection/{id}. DTOs expose immutable refs, lifecycle, metrics validity and incident/qualification reasons; cursor pagination with stable ID ordering.

## Planned Files / Artifacts

Modify:

None.

Create:

- `src/indodax_lab/web/research_api.py`

- `web/research/src/app.tsx`

- `tests/integration/lab/test_research_read_api.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

GET /research/{datasets,strategies,models,pipelines,experiments,backtests,candidates,tournament,agents,portfolio-shadow}; GET collection/{id}. DTOs expose immutable refs, lifecycle, metrics validity and incident/qualification reasons; cursor pagination with stable ID ordering.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Frontend dependency/framework selection is constrained to React+TypeScript/Vite; backend local FastAPI read adapter; additions require pinned dependencies and no public deployment.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

GET /research/{datasets,strategies,models,pipelines,experiments,backtests,candidates,tournament,agents,portfolio-shadow}; GET collection/{id}. DTOs expose immutable refs, lifecycle, metrics validity and incident/qualification reasons; cursor pagination with stable ID ordering.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

Implement only the view/editor interfaces above; show provenance, failure reasons and unknown metrics.

## Implementation Steps

- [ ] Step 1: Implement read DTOs from services, not UI-owned state.

- [ ] Step 2: Create research navigation and provenance-rich detail/compare views.

- [ ] Step 3: Show missing metrics as unavailable and rank separate from qualification.

- [ ] Step 4: Add accessible tabular/keyboard navigation and artifact downloads.

- [ ] Step 5: Keep production controls outside this API.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/integration/lab/test_research_read_api.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/integration/lab/test_research_read_api.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW8-01-AC0 | `test_rw8_01_0` | View values reconcile with authoritative store |

| RW8-01-AC1 | `test_rw8_01_1` | Unknown metric never displayed as zero |

| RW8-01-AC2 | `test_rw8_01_2` | Agent detail shows isolated namespace and candidate digest |

| RW8-01-AC3 | `test_rw8_01_3` | Pagination stable under new records |

| RW8-01-AC4 | `test_rw8_01_4` | Read API cannot mutate or return private credentials |

Focused command: `python -m pytest tests/integration/lab/test_research_read_api.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Unknown metric never displayed as zero. Rejection preserves prior committed evidence and emits a specific reason.

- Agent detail shows isolated namespace and candidate digest. Rejection preserves prior committed evidence and emits a specific reason.

- Pagination stable under new records. Rejection preserves prior committed evidence and emits a specific reason.

- Read API cannot mutate or return private credentials. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW8-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Frontend dependency/framework selection is constrained to React+TypeScript/Vite; backend local FastAPI read adapter; additions require pinned dependencies and no public deployment.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW8-01-AC5** Display requested versus actual coverage per-pair results and Top 10 exclusions without zero defaults. Evidence: `test_rw8_01_program_5` at exact implementation SHA.

- [ ] **RW8-01-AC0** View values reconcile with authoritative store. Evidence: named test on exact committed SHA.

- [ ] **RW8-01-AC1** Unknown metric never displayed as zero. Evidence: named test on exact committed SHA.

- [ ] **RW8-01-AC2** Agent detail shows isolated namespace and candidate digest. Evidence: named test on exact committed SHA.

- [ ] **RW8-01-AC3** Pagination stable under new records. Evidence: named test on exact committed SHA.

- [ ] **RW8-01-AC4** Read API cannot mutate or return private credentials. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw8-01-research-read-models-and-dashboard-navigation` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw8-01): research read models and dashboard navigation`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW8-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW8-01

### OBJECTIVE

Service-derived views with provenance and explicit qualification state.

### ARCHITECTURAL CONTEXT

Console dashboard and design artifact exist; Workbench web app absent. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/web/research_api.py`, `web/research/src/app.tsx`, `tests/integration/lab/test_research_read_api.py`

### TESTS

`python -m pytest tests/integration/lab/test_research_read_api.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW8-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
