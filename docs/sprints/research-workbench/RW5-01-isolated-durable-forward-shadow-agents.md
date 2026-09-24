# RW5-01 — Isolated durable forward-shadow agents Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Candidate-bound isolated agent state and restart-safe lifecycle.

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

Recommended Branch: `feat/rw5-01-isolated-durable-forward-shadow-agents`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Candidate-bound isolated agent state and restart-safe lifecycle.

## Why This Sprint Exists

Purpose: Isolated durable forward-shadow agents. Gap: Candidate-bound isolated agent state and restart-safe lifecycle.

## Depends On

- RW4-01 — Immutable candidate packaging and lifecycle
- RP-05 — Runtime parity qualification fixtures

## Unlocks

RW5-02, RW6-01, PM-06

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
- `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`

## Current Context

LiveShadowEngine is one shared portfolio with checkpoints.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

2026-09-24 capacity extension: follow `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`; additional cases remain unverified, including for REVIEW tasks.

Owner-approved 2026-09-24 amendment: implement this sprint's behavior in `docs/implementation/BOT-TRADE-PROGRAM.md`; prior requirements remain mandatory.

- Allocate exclusive namespace per agent and immutable starting cash

- Subscribe to canonical feed; use shared runtime kernel

- Persist lifecycle/feature/exit/risk/OMS/ledger/cursor recovery state

- Implement pause/halt/recover/resume with coverage evidence

- Add read-only agent query and fake-feed CLI integration

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW5-01-FR0:** Agent A trade cannot change B cash/positions/risk/cursor.

1. **RW5-01-FR1:** Namespace collision or candidate replacement rejects.

2. **RW5-01-FR2:** Restart restores exactly with duplicate event no-op.

3. **RW5-01-FR3:** Corrupt A halts A without corrupting B.

4. **RW5-01-FR4:** Retire preserves all evidence.

## Domain Rules / Invariants

AgentFactory.register(manifest)->AgentRecord; start(id)->AgentRecord; pause(id)->AgentRecord; retire(id)->AgentRecord; recover(id)->RecoveryReport; get(id)->AgentRecord. AgentRecord includes manifest ref, lifecycle, cursor, incident refs and state-store namespace.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. AgentFactory.register(manifest)->AgentRecord; start(id)->AgentRecord; pause(id)->AgentRecord; retire(id)->AgentRecord; recover(id)->RecoveryReport; get(id)->AgentRecord. AgentRecord includes manifest ref, lifecycle, cursor, incident refs and state-store namespace.

## Planned Files / Artifacts

Modify:

None.

Create:

- `src/indodax_lab/paper/agents.py`

- `src/indodax_lab/cli/shadow.py`

- `tests/integration/lab/test_agent_isolation.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

AgentFactory.register(manifest)->AgentRecord; start(id)->AgentRecord; pause(id)->AgentRecord; retire(id)->AgentRecord; recover(id)->RecoveryReport; get(id)->AgentRecord. AgentRecord includes manifest ref, lifecycle, cursor, incident refs and state-store namespace.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Do not reset legacy wallet to become a tournament; create new agent identity and archive old shared run.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

AgentFactory.register(manifest)->AgentRecord; start(id)->AgentRecord; pause(id)->AgentRecord; retire(id)->AgentRecord; recover(id)->RecoveryReport; get(id)->AgentRecord. AgentRecord includes manifest ref, lifecycle, cursor, incident refs and state-store namespace.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Allocate exclusive namespace per agent and immutable starting cash.

- [ ] Step 2: Subscribe to canonical feed; use shared runtime kernel.

- [ ] Step 3: Persist lifecycle/feature/exit/risk/OMS/ledger/cursor recovery state.

- [ ] Step 4: Implement pause/halt/recover/resume with coverage evidence.

- [ ] Step 5: Add read-only agent query and fake-feed CLI integration.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/integration/lab/test_agent_isolation.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/integration/lab/test_agent_isolation.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW5-01-AC0 | `test_rw5_01_0` | Agent A trade cannot change B cash/positions/risk/cursor |

| RW5-01-AC1 | `test_rw5_01_1` | Namespace collision or candidate replacement rejects |

| RW5-01-AC2 | `test_rw5_01_2` | Restart restores exactly with duplicate event no-op |

| RW5-01-AC3 | `test_rw5_01_3` | Corrupt A halts A without corrupting B |

| RW5-01-AC4 | `test_rw5_01_4` | Retire preserves all evidence |

Focused command: `python -m pytest tests/integration/lab/test_agent_isolation.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Namespace collision or candidate replacement rejects. Rejection preserves prior committed evidence and emits a specific reason.

- Restart restores exactly with duplicate event no-op. Rejection preserves prior committed evidence and emits a specific reason.

- Corrupt A halts A without corrupting B. Rejection preserves prior committed evidence and emits a specific reason.

- Retire preserves all evidence. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW5-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Do not reset legacy wallet to become a tournament; create new agent identity and archive old shared run.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW5-01-AC6** Agent admission reserves measured incremental resources and slow consumer pause preserves other agents. Evidence: `test_rw5_01_capacity_6` plus applicable measured host artifact; not established by historical tests.

- [ ] **RW5-01-AC5** Realtime agents preserve isolated wallets and candidate-bound exits across partial fill and restart. Evidence: `test_rw5_01_program_5` at exact implementation SHA.

- [ ] **RW5-01-AC0** Agent A trade cannot change B cash/positions/risk/cursor. Evidence: named test on exact committed SHA.

- [ ] **RW5-01-AC1** Namespace collision or candidate replacement rejects. Evidence: named test on exact committed SHA.

- [ ] **RW5-01-AC2** Restart restores exactly with duplicate event no-op. Evidence: named test on exact committed SHA.

- [ ] **RW5-01-AC3** Corrupt A halts A without corrupting B. Evidence: named test on exact committed SHA.

- [ ] **RW5-01-AC4** Retire preserves all evidence. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw5-01-isolated-durable-forward-shadow-agents` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw5-01): isolated durable forward-shadow agents`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW5-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW5-01

### OBJECTIVE

Candidate-bound isolated agent state and restart-safe lifecycle.

### ARCHITECTURAL CONTEXT

LiveShadowEngine is one shared portfolio with checkpoints. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/paper/agents.py`, `src/indodax_lab/cli/shadow.py`, `tests/integration/lab/test_agent_isolation.py`

### TESTS

`python -m pytest tests/integration/lab/test_agent_isolation.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW5-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
