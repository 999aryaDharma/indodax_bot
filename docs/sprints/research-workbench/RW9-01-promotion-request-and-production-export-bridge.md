# RW9-01 — Promotion request and production export bridge Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Immutable export and governed request only; production owns release approval.

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

Recommended Branch: `feat/rw9-01-promotion-request-and-production-export-bridge`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: M

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Immutable export and governed request only; production owns release approval.

## Why This Sprint Exists

Purpose: Promotion request and production export bridge. Gap: Immutable export and governed request only; production owns release approval.

## Depends On

- RW4-01 — Immutable candidate packaging and lifecycle
- RW5-02 — Tournament cohorts leaderboard and qualification
- PM-05 — Candidate-bound release provenance

## Unlocks

RW7-02

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

Promotion counters/release utilities exist without complete bridge.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Validate candidate and historical/forward evidence refs

- Record idempotent append-only request

- Export candidate-compatible production release inputs

- Preserve production review decision as external evidence

- Expose only request API to MCP/UI

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW9-01-FR0:** Rank-one alone cannot qualify request evidence.

1. **RW9-01-FR1:** Request retry produces one record.

2. **RW9-01-FR2:** Missing 90-day/100-trade or unresolved incident evidence blocks qualified export.

3. **RW9-01-FR3:** Export digest mismatch rejected by production importer.

4. **RW9-01-FR4:** Request cannot transition mode or submit order.

## Domain Rules / Invariants

PromotionService.request(candidate_ref,evidence_refs,actor,reason,request_id)->PromotionRequest; export(request_id)->ExportArtifact. Production import verifies artifacts/gates independently; request has no deployed field.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. PromotionService.request(candidate_ref,evidence_refs,actor,reason,request_id)->PromotionRequest; export(request_id)->ExportArtifact. Production import verifies artifacts/gates independently; request has no deployed field.

## Planned Files / Artifacts

Modify:

None.

Create:

- `src/indodax_lab/evaluation/promotion_requests.py`

- `tests/security/test_promotion_request_boundary.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

PromotionService.request(candidate_ref,evidence_refs,actor,reason,request_id)->PromotionRequest; export(request_id)->ExportArtifact. Production import verifies artifacts/gates independently; request has no deployed field.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Existing research champion labels retained as historical; never translated to live deployment.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

PromotionService.request(candidate_ref,evidence_refs,actor,reason,request_id)->PromotionRequest; export(request_id)->ExportArtifact. Production import verifies artifacts/gates independently; request has no deployed field.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Validate candidate and historical/forward evidence refs.

- [ ] Step 2: Record idempotent append-only request.

- [ ] Step 3: Export candidate-compatible production release inputs.

- [ ] Step 4: Preserve production review decision as external evidence.

- [ ] Step 5: Expose only request API to MCP/UI.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/security/test_promotion_request_boundary.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/security/test_promotion_request_boundary.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW9-01-AC0 | `test_rw9_01_0` | Rank-one alone cannot qualify request evidence |

| RW9-01-AC1 | `test_rw9_01_1` | Request retry produces one record |

| RW9-01-AC2 | `test_rw9_01_2` | Missing 90-day/100-trade or unresolved incident evidence blocks qualified export |

| RW9-01-AC3 | `test_rw9_01_3` | Export digest mismatch rejected by production importer |

| RW9-01-AC4 | `test_rw9_01_4` | Request cannot transition mode or submit order |

Focused command: `python -m pytest tests/security/test_promotion_request_boundary.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Request retry produces one record. Rejection preserves prior committed evidence and emits a specific reason.

- Missing 90-day/100-trade or unresolved incident evidence blocks qualified export. Rejection preserves prior committed evidence and emits a specific reason.

- Export digest mismatch rejected by production importer. Rejection preserves prior committed evidence and emits a specific reason.

- Request cannot transition mode or submit order. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW9-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Existing research champion labels retained as historical; never translated to live deployment.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW9-01-AC0** Rank-one alone cannot qualify request evidence. Evidence: named test on exact committed SHA.

- [ ] **RW9-01-AC1** Request retry produces one record. Evidence: named test on exact committed SHA.

- [ ] **RW9-01-AC2** Missing 90-day/100-trade or unresolved incident evidence blocks qualified export. Evidence: named test on exact committed SHA.

- [ ] **RW9-01-AC3** Export digest mismatch rejected by production importer. Evidence: named test on exact committed SHA.

- [ ] **RW9-01-AC4** Request cannot transition mode or submit order. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw9-01-promotion-request-and-production-export-bridge` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw9-01): promotion request and production export bridge`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW9-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW9-01

### OBJECTIVE

Immutable export and governed request only; production owns release approval.

### ARCHITECTURAL CONTEXT

Promotion counters/release utilities exist without complete bridge. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/evaluation/promotion_requests.py`, `tests/security/test_promotion_request_boundary.py`

### TESTS

`python -m pytest tests/security/test_promotion_request_boundary.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW9-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
