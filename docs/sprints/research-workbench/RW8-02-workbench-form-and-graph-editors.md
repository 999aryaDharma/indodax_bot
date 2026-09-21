# RW8-02 — Workbench form and graph editors Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Synchronized form/visual editing of one backend-validated pipeline draft.

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

Recommended Branch: `feat/rw8-02-workbench-form-and-graph-editors`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Synchronized form/visual editing of one backend-validated pipeline draft.

## Why This Sprint Exists

Purpose: Workbench form and graph editors. Gap: Synchronized form/visual editing of one backend-validated pipeline draft.

## Depends On

- RW8-01 — Research read models and dashboard navigation
- RW2-03 — Typed declarative pipeline composer
- RW3-01 — Experiment lifecycle and backtest orchestration

## Unlocks

No mandatory dependent sprint.

## Required Reading

- `AGENTS.md`

- `docs/production/FROZEN-SYSTEMS.md`

- `docs/production/main/README.md`

- `docs/production/main/SOP-AND-GATES.md`

- `docs/production/research-workbench/DOMAIN-AND-LIFECYCLE.md`

- `docs/implementation/CONTRACTS.md`

- `docs/implementation/RUNTIME-PARITY.md`

- `docs/specs/20-testing-strategy.md`

## Current Context

No manifest-backed UI editor exists.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Bind form selectors to registry versions and dataset coverage

- Render typed DAG with accessible SVG node/edge editor from same state

- Surface node-specific server validation

- Handle revision conflict with explicit clone/reload, never silent overwrite

- Create experiment and display queued/running/terminal evidence

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW8-02-FR0:** Form→graph→form roundtrip has identical semantic digest.

1. **RW8-02-FR1:** Stale edit returns conflict and preserves saved draft.

2. **RW8-02-FR2:** Invalid cycle blocks experiment submission.

3. **RW8-02-FR3:** Clone completed experiment creates new identity.

4. **RW8-02-FR4:** Browser cannot add unknown executable component.

## Domain Rules / Invariants

POST /research/pipelines/drafts; PATCH /research/pipelines/drafts/{id} with expected_revision; POST /research/experiments; POST /research/experiments/{id}/run. Form and SVG graph use one PipelineManifest state; server validates every mutation.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. POST /research/pipelines/drafts; PATCH /research/pipelines/drafts/{id} with expected_revision; POST /research/experiments; POST /research/experiments/{id}/run. Form and SVG graph use one PipelineManifest state; server validates every mutation.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/web/research_api.py`

- `web/research/src/app.tsx`

Create:

- `web/research/src/workbench.tsx`

- `tests/integration/lab/test_workbench_drafts.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

POST /research/pipelines/drafts; PATCH /research/pipelines/drafts/{id} with expected_revision; POST /research/experiments; POST /research/experiments/{id}/run. Form and SVG graph use one PipelineManifest state; server validates every mutation.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Graph layout coordinates are UI metadata outside execution digest; no second execution engine.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

POST /research/pipelines/drafts; PATCH /research/pipelines/drafts/{id} with expected_revision; POST /research/experiments; POST /research/experiments/{id}/run. Form and SVG graph use one PipelineManifest state; server validates every mutation.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

Implement only the view/editor interfaces above; show provenance, failure reasons and unknown metrics.

## Implementation Steps

- [ ] Step 1: Bind form selectors to registry versions and dataset coverage.

- [ ] Step 2: Render typed DAG with accessible SVG node/edge editor from same state.

- [ ] Step 3: Surface node-specific server validation.

- [ ] Step 4: Handle revision conflict with explicit clone/reload, never silent overwrite.

- [ ] Step 5: Create experiment and display queued/running/terminal evidence.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/integration/lab/test_workbench_drafts.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/integration/lab/test_workbench_drafts.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW8-02-AC0 | `test_rw8_02_0` | Form→graph→form roundtrip has identical semantic digest |

| RW8-02-AC1 | `test_rw8_02_1` | Stale edit returns conflict and preserves saved draft |

| RW8-02-AC2 | `test_rw8_02_2` | Invalid cycle blocks experiment submission |

| RW8-02-AC3 | `test_rw8_02_3` | Clone completed experiment creates new identity |

| RW8-02-AC4 | `test_rw8_02_4` | Browser cannot add unknown executable component |

Focused command: `python -m pytest tests/integration/lab/test_workbench_drafts.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Stale edit returns conflict and preserves saved draft. Rejection preserves prior committed evidence and emits a specific reason.

- Invalid cycle blocks experiment submission. Rejection preserves prior committed evidence and emits a specific reason.

- Clone completed experiment creates new identity. Rejection preserves prior committed evidence and emits a specific reason.

- Browser cannot add unknown executable component. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW8-02 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Graph layout coordinates are UI metadata outside execution digest; no second execution engine.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW8-02-AC0** Form→graph→form roundtrip has identical semantic digest. Evidence: named test on exact committed SHA.

- [ ] **RW8-02-AC1** Stale edit returns conflict and preserves saved draft. Evidence: named test on exact committed SHA.

- [ ] **RW8-02-AC2** Invalid cycle blocks experiment submission. Evidence: named test on exact committed SHA.

- [ ] **RW8-02-AC3** Clone completed experiment creates new identity. Evidence: named test on exact committed SHA.

- [ ] **RW8-02-AC4** Browser cannot add unknown executable component. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw8-02-workbench-form-and-graph-editors` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw8-02): workbench form and graph editors`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW8-02-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW8-02

### OBJECTIVE

Synchronized form/visual editing of one backend-validated pipeline draft.

### ARCHITECTURAL CONTEXT

No manifest-backed UI editor exists. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/web/research_api.py`, `web/research/src/app.tsx`, `web/research/src/workbench.tsx`, `tests/integration/lab/test_workbench_drafts.py`

### TESTS

`python -m pytest tests/integration/lab/test_workbench_drafts.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW8-02-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.

