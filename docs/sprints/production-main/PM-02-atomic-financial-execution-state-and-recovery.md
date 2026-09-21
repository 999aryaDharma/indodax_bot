# PM-02 — Atomic financial execution state and recovery Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** One authoritative transaction and verified restart across all financial effects.

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

Recommended Branch: `feat/pm-02-atomic-financial-execution-state-and-recovery`

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: XL

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

One authoritative transaction and verified restart across all financial effects.

## Why This Sprint Exists

Purpose: Atomic financial execution state and recovery. Gap: One authoritative transaction and verified restart across all financial effects.

## Depends On

- RW0-01 — Immutable Workbench domain manifests
- LED-01 — Balanced research postings

## Unlocks

PM-03, PM-04, RP-04

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

Ledger store exists but ingester/OMS/fill-ID application are separate mutations.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Inject failure before/after each existing mutation boundary

- Consolidate journal/OMS/applied identity/audit in one local SQLite transaction

- Validate duplicate content, matching order, quantity and revision before commit

- Publish memory only after commit and verify snapshot/journal linkage on restore

- Add read-only-source migration with ambiguity rejection

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **PM-02-FR0:** Crash at each boundary yields either zero or one complete effect after restart.

1. **PM-02-FR1:** Duplicate replay cannot double OMS quantity or fees.

2. **PM-02-FR2:** Conflicting duplicate/overfill/unmatched fill halts without partial posting.

3. **PM-02-FR3:** Late fill after cancellation updates cumulative evidence once.

4. **PM-02-FR4:** Corrupt snapshot/journal linkage blocks restore.

## Domain Rules / Invariants

ExecutionStateStore.apply_fill(fill:Fill,expected_revision:int)->FillCommitResult; restore()->ExecutionSnapshot; migrate_readonly(source_paths,target_namespace)->MigrationReport. Contracts and late-fill policy are in ADR-007 and CONTRACTS.md.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. ExecutionStateStore.apply_fill(fill:Fill,expected_revision:int)->FillCommitResult; restore()->ExecutionSnapshot; migrate_readonly(source_paths,target_namespace)->MigrationReport. Contracts and late-fill policy are in ADR-007 and CONTRACTS.md.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/execution/fill_ingestion.py`

- `src/indodax_lab/execution/oms_store.py`

- `src/indodax_lab/execution/ledger_store.py`

Create:

- `src/indodax_lab/execution/state_store.py`

- `tests/integration/lab/test_execution_transaction_recovery.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Own ExecutionStateStore.prepare_event, commit_decision, claim_submission, record_submission, acknowledge_event, apply_fill and recover APIs exactly as CONTRACTS.md event protocol. Store inbox/outbox plus feature/exit/risk/reservations/cursor state atomically by phase.

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

ExecutionStateStore.apply_fill(fill:Fill,expected_revision:int)->FillCommitResult; restore()->ExecutionSnapshot; migrate_readonly(source_paths,target_namespace)->MigrationReport. Contracts and late-fill policy are in ADR-007 and CONTRACTS.md.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Offline copy to new schema/namespace; preserve source DB and reconcile before selecting new store. Never migrate active runtime DB during tests.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

ExecutionStateStore.apply_fill(fill:Fill,expected_revision:int)->FillCommitResult; restore()->ExecutionSnapshot; migrate_readonly(source_paths,target_namespace)->MigrationReport. Contracts and late-fill policy are in ADR-007 and CONTRACTS.md.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Inject failure before/after each existing mutation boundary.

- [ ] Step 2: Consolidate journal/OMS/applied identity/audit in one local SQLite transaction.

- [ ] Step 3: Validate duplicate content, matching order, quantity and revision before commit.

- [ ] Step 4: Publish memory only after commit and verify snapshot/journal linkage on restore.

- [ ] Step 5: Add read-only-source migration with ambiguity rejection.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/integration/lab/test_execution_transaction_recovery.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

`test_pm_02_bootstrap_recovery`: No-intent event crash and partial two-order submission recover once without cursor loss or blind resubmission. Use the event phases/bootstrap sequence in CONTRACTS.md as the independently specified expected result.

Planned test paths: `tests/integration/lab/test_execution_transaction_recovery.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| PM-02-AC0 | `test_pm_02_0` | Crash at each boundary yields either zero or one complete effect after restart |

| PM-02-AC1 | `test_pm_02_1` | Duplicate replay cannot double OMS quantity or fees |

| PM-02-AC2 | `test_pm_02_2` | Conflicting duplicate/overfill/unmatched fill halts without partial posting |

| PM-02-AC3 | `test_pm_02_3` | Late fill after cancellation updates cumulative evidence once |

| PM-02-AC4 | `test_pm_02_4` | Corrupt snapshot/journal linkage blocks restore |

Focused command: `python -m pytest tests/integration/lab/test_execution_transaction_recovery.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Duplicate replay cannot double OMS quantity or fees. Rejection preserves prior committed evidence and emits a specific reason.

- Conflicting duplicate/overfill/unmatched fill halts without partial posting. Rejection preserves prior committed evidence and emits a specific reason.

- Late fill after cancellation updates cumulative evidence once. Rejection preserves prior committed evidence and emits a specific reason.

- Corrupt snapshot/journal linkage blocks restore. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. PM-02 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Offline copy to new schema/namespace; preserve source DB and reconcile before selecting new store. Never migrate active runtime DB during tests.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **PM-02-AC5** No-intent event crash and partial two-order submission recover once without cursor loss or blind resubmission. Evidence: `test_pm_02_bootstrap_recovery` through public interfaces.
- [ ] **PM-02-AC0** Crash at each boundary yields either zero or one complete effect after restart. Evidence: named test on exact committed SHA.

- [ ] **PM-02-AC1** Duplicate replay cannot double OMS quantity or fees. Evidence: named test on exact committed SHA.

- [ ] **PM-02-AC2** Conflicting duplicate/overfill/unmatched fill halts without partial posting. Evidence: named test on exact committed SHA.

- [ ] **PM-02-AC3** Late fill after cancellation updates cumulative evidence once. Evidence: named test on exact committed SHA.

- [ ] **PM-02-AC4** Corrupt snapshot/journal linkage blocks restore. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/pm-02-atomic-financial-execution-state-and-recovery` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(pm-02): atomic financial execution state and recovery`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-02-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

PM-02

### OBJECTIVE

One authoritative transaction and verified restart across all financial effects.

### ARCHITECTURAL CONTEXT

Ledger store exists but ingester/OMS/fill-ID application are separate mutations. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/execution/fill_ingestion.py`, `src/indodax_lab/execution/oms_store.py`, `src/indodax_lab/execution/ledger_store.py`, `src/indodax_lab/execution/state_store.py`, `tests/integration/lab/test_execution_transaction_recovery.py`

### TESTS

`python -m pytest tests/integration/lab/test_execution_transaction_recovery.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `PM-02-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
