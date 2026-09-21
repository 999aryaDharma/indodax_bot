# PM-01 — Authoritative fail-closed pre-write gate Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** All real writes need trusted current scoped evidence and exact approval re-risk.

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

Priority: P0 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/pm-01-authoritative-fail-closed-pre-write-gate`

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

All real writes need trusted current scoped evidence and exact approval re-risk.

## Why This Sprint Exists

Purpose: Authoritative fail-closed pre-write gate. Gap: All real writes need trusted current scoped evidence and exact approval re-risk.

## Depends On

- RW0-01 — Immutable Workbench domain manifests

## Unlocks

PM-03, PM-04

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

Pipeline conditionally checks reconciliation; manual execution defaults missing capital.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Reject absent, future, stale, unhealthy or wrong-scope evidence before adapter call

- Remove invented equity/cash and require authoritative snapshot

- Re-risk exact approved order with current state and reject changed quantity requiring new approval

- Enforce permit at real writer boundary including cancel authority

- Make stale revision/expired permit fail closed immediately before submission

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **PM-01-FR0:** No report or portfolio snapshot means zero venue writes.

1. **PM-01-FR1:** Wrong scope or future timestamp cannot pass freshness.

2. **PM-01-FR2:** Changed cash/positions/price after approval requires fresh rejection/reapproval.

3. **PM-01-FR3:** Unknown orders block new exposure.

4. **PM-01-FR4:** Direct real-writer call without valid permit fails.

## Domain Rules / Invariants

AuthorityGate.authorize(order,execution_snapshot,release_ref,approval,now)->WritePermit; ExecutionSnapshot has ledger/OMS/risk revisions, cash/positions/equity, market/clock health, reconciliation scope/time and unknown count. WritePermit is bound to order/candidate/snapshot digest and single-use submission.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. AuthorityGate.authorize(order,execution_snapshot,release_ref,approval,now)->WritePermit; ExecutionSnapshot has ledger/OMS/risk revisions, cash/positions/equity, market/clock health, reconciliation scope/time and unknown count. WritePermit is bound to order/candidate/snapshot digest and single-use submission.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/control/pipeline.py`

- `src/indodax_lab/control/approval.py`

- `src/indodax_lab/execution/order_router.py`

Create:

- `src/indodax_lab/control/authority.py`

- `tests/unit/lab/control/test_authority_gate.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

AuthorityGate.authorize(order,execution_snapshot,release_ref,approval,now)->WritePermit; ExecutionSnapshot has ledger/OMS/risk revisions, cash/positions/equity, market/clock health, reconciliation scope/time and unknown count. WritePermit is bound to order/candidate/snapshot digest and single-use submission.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Existing fake/shadow construction uses simulation permission, never a production permit. No real transport in tests.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

AuthorityGate.authorize(order,execution_snapshot,release_ref,approval,now)->WritePermit; ExecutionSnapshot has ledger/OMS/risk revisions, cash/positions/equity, market/clock health, reconciliation scope/time and unknown count. WritePermit is bound to order/candidate/snapshot digest and single-use submission.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Reject absent, future, stale, unhealthy or wrong-scope evidence before adapter call.

- [ ] Step 2: Remove invented equity/cash and require authoritative snapshot.

- [ ] Step 3: Re-risk exact approved order with current state and reject changed quantity requiring new approval.

- [ ] Step 4: Enforce permit at real writer boundary including cancel authority.

- [ ] Step 5: Make stale revision/expired permit fail closed immediately before submission.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/unit/lab/control/test_authority_gate.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/unit/lab/control/test_authority_gate.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| PM-01-AC0 | `test_pm_01_0` | No report or portfolio snapshot means zero venue writes |

| PM-01-AC1 | `test_pm_01_1` | Wrong scope or future timestamp cannot pass freshness |

| PM-01-AC2 | `test_pm_01_2` | Changed cash/positions/price after approval requires fresh rejection/reapproval |

| PM-01-AC3 | `test_pm_01_3` | Unknown orders block new exposure |

| PM-01-AC4 | `test_pm_01_4` | Direct real-writer call without valid permit fails |

Focused command: `python -m pytest tests/unit/lab/control/test_authority_gate.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Wrong scope or future timestamp cannot pass freshness. Rejection preserves prior committed evidence and emits a specific reason.

- Changed cash/positions/price after approval requires fresh rejection/reapproval. Rejection preserves prior committed evidence and emits a specific reason.

- Unknown orders block new exposure. Rejection preserves prior committed evidence and emits a specific reason.

- Direct real-writer call without valid permit fails. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. PM-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Existing fake/shadow construction uses simulation permission, never a production permit. No real transport in tests.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **PM-01-AC0** No report or portfolio snapshot means zero venue writes. Evidence: named test on exact committed SHA.

- [ ] **PM-01-AC1** Wrong scope or future timestamp cannot pass freshness. Evidence: named test on exact committed SHA.

- [ ] **PM-01-AC2** Changed cash/positions/price after approval requires fresh rejection/reapproval. Evidence: named test on exact committed SHA.

- [ ] **PM-01-AC3** Unknown orders block new exposure. Evidence: named test on exact committed SHA.

- [ ] **PM-01-AC4** Direct real-writer call without valid permit fails. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/pm-01-authoritative-fail-closed-pre-write-gate` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(pm-01): authoritative fail-closed pre-write gate`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

PM-01

### OBJECTIVE

All real writes need trusted current scoped evidence and exact approval re-risk.

### ARCHITECTURAL CONTEXT

Pipeline conditionally checks reconciliation; manual execution defaults missing capital. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/control/pipeline.py`, `src/indodax_lab/control/approval.py`, `src/indodax_lab/execution/order_router.py`, `src/indodax_lab/control/authority.py`, `tests/unit/lab/control/test_authority_gate.py`

### TESTS

`python -m pytest tests/unit/lab/control/test_authority_gate.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `PM-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.

