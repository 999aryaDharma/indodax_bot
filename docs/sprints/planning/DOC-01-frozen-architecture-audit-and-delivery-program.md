# DOC-01 — Frozen architecture audit and delivery program Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Recover evidence-backed status and publish complete RW/RP/PM tasks and one next LUNA unit.

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

Status: REVIEW

Priority: P0 | Type: planning | Domain: planning | Portfolio: CORE

Implementation Owner: ASTRA | Independent Reviewer: UNASSIGNED

Recommended Branch: `docs/architecture-runtime-plan`

Requirements: FR-17 | Legacy tasks: none

Risk level: high | Complexity: XL

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Recover evidence-backed status and publish complete RW/RP/PM tasks and one next LUNA unit.

## Why This Sprint Exists

Purpose: Frozen architecture audit and delivery program. Gap: Recover evidence-backed status and publish complete RW/RP/PM tasks and one next LUNA unit.

## Depends On

None. This capability can establish its own offline acceptance fixture.

## Unlocks

RP-01

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

Frozen specifications exist; manifest is internally truncated and runtime paths diverge.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Preserve corrupt manifest source digest and reconstruct records from sprint specs/handoffs
- Write source-indexed current state and every parity layer
- Publish task contracts, dependencies, ADRs, roadmaps and single next handoff
- Validate structure, negative mutations, coverage and links; commit and request independent review

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **DOC-01-FR0:** 92 legacy IDs retained and no unsupported DONE promotion.
1. **DOC-01-FR1:** Every new task resolves dependencies and required reading.
2. **DOC-01-FR2:** RP-01 is sole LUNA-NEXT and blocked until DOC-01 review passes.
3. **DOC-01-FR3:** src/tests/configs/deploy/model/result bytes unchanged.

## Domain Rules / Invariants

Input: tracked baseline SHA and frozen specs. Output: validated manifest, task specs, audit, ADRs and LUNA-NEXT; no product API.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. Input: tracked baseline SHA and frozen specs. Output: validated manifest, task specs, audit, ADRs and LUNA-NEXT; no product API.

## Planned Files / Artifacts

Modify:
- `docs/README.md`
- `docs/specs/00-master-product-technical-spec.md`
- `docs/sprints/sprint-manifest.json`
- `docs/quality/validate_planning.py`

Create:
- `docs/implementation/README.md`
- `docs/implementation/CURRENT-STATE.md`
- `docs/implementation/RUNTIME-PARITY.md`
- `docs/implementation/CONTRACTS.md`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text
Input: tracked baseline SHA and frozen specs. Output: validated manifest, task specs, audit, ADRs and LUNA-NEXT; no product API.
```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Documentation-only migration; retain corrupted source in Git and qualify old evidence.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

Input: tracked baseline SHA and frozen specs. Output: validated manifest, task specs, audit, ADRs and LUNA-NEXT; no product API.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Preserve corrupt manifest source digest and reconstruct records from sprint specs/handoffs.

- [ ] Step 2: Write source-indexed current state and every parity layer.

- [ ] Step 3: Publish task contracts, dependencies, ADRs, roadmaps and single next handoff.

- [ ] Step 4: Validate structure, negative mutations, coverage and links; commit and request independent review.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.
- [ ] Run `python docs/quality/validate_planning.py --self-test`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.
- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: planning validators.

| Acceptance | Planned test identity | Required assertion |
|---|---|---|
| DOC-01-AC0 | `test_doc_01_0` | 92 legacy IDs retained and no unsupported DONE promotion |
| DOC-01-AC1 | `test_doc_01_1` | Every new task resolves dependencies and required reading |
| DOC-01-AC2 | `test_doc_01_2` | RP-01 is sole LUNA-NEXT and blocked until DOC-01 review passes |
| DOC-01-AC3 | `test_doc_01_3` | src/tests/configs/deploy/model/result bytes unchanged |

Focused command: `python docs/quality/validate_planning.py --self-test`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Every new task resolves dependencies and required reading. Rejection preserves prior committed evidence and emits a specific reason.
- RP-01 is sole LUNA-NEXT and blocked until DOC-01 review passes. Rejection preserves prior committed evidence and emits a specific reason.
- src/tests/configs/deploy/model/result bytes unchanged. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. DOC-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Documentation-only migration; retain corrupted source in Git and qualify old evidence.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **DOC-01-AC0** 92 legacy IDs retained and no unsupported DONE promotion. Evidence: named test on exact committed SHA.
- [ ] **DOC-01-AC1** Every new task resolves dependencies and required reading. Evidence: named test on exact committed SHA.
- [ ] **DOC-01-AC2** RP-01 is sole LUNA-NEXT and blocked until DOC-01 review passes. Evidence: named test on exact committed SHA.
- [ ] **DOC-01-AC3** src/tests/configs/deploy/model/result bytes unchanged. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `docs/architecture-runtime-plan` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `docs(doc-01): publish audited architecture program`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/DOC-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

DOC-01

### OBJECTIVE

Recover evidence-backed status and publish complete RW/RP/PM tasks and one next LUNA unit.

### ARCHITECTURAL CONTEXT

Frozen specifications exist; manifest is internally truncated and runtime paths diverge. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`docs/README.md`, `docs/specs/00-master-product-technical-spec.md`, `docs/sprints/sprint-manifest.json`, `docs/quality/validate_planning.py`, `docs/implementation/README.md`, `docs/implementation/CURRENT-STATE.md`, `docs/implementation/RUNTIME-PARITY.md`, `docs/implementation/CONTRACTS.md`

### TESTS

`python docs/quality/validate_planning.py --self-test` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `DOC-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
