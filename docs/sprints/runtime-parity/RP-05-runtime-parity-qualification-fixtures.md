# RP-05 — Runtime parity qualification fixtures Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Evidence of shared decisions, risk, OMS and accounting before tournament qualification.

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

Priority: P0 | Type: integration | Domain: runtime-parity | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/rp-05-runtime-parity-qualification-fixtures`

Requirements: FR-20 | Legacy tasks: none

Risk level: high | Complexity: M

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Evidence of shared decisions, risk, OMS and accounting before tournament qualification.

## Why This Sprint Exists

Purpose: Runtime parity qualification fixtures. Gap: Evidence of shared decisions, risk, OMS and accounting before tournament qualification.

## Depends On

- RP-04 — Canonical feed and environment runtime adapters
- PM-04 — Venue parser cancellation and supported order semantics

## Unlocks

RW5-01

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

Unit suites prove individual components; no cross-environment parity suite.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Replay common canonical sequence into historical/shadow/production-shaped fake compositions

- Compare exact pre-venue IDs and Decimal semantics

- Enumerate justified fill/timing differences without hiding decision drift

- Run duplicate/restart/halt failure matrix

- Emit immutable test evidence manifest tied to code SHA

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RP-05-FR0:** Candidate intent IDs/content match before venue boundary.

1. **RP-05-FR1:** Same risk state gives same quantity/reason.

2. **RP-05-FR2:** Same normalized fills produce identical journal totals.

3. **RP-05-FR3:** Clock/fill differences cannot mask order-semantic divergence.

4. **RP-05-FR4:** Research transitive imports expose no real writer.

## Domain Rules / Invariants

ParityTrace: candidate/event/state/policy digests, ordered intents, risk decisions, OMS transitions and ledger postings. compare_traces(left,right)->tuple[Divergence,...], ignoring only explicitly adapter-specific execution outcomes.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. ParityTrace: candidate/event/state/policy digests, ordered intents, risk decisions, OMS transitions and ledger postings. compare_traces(left,right)->tuple[Divergence,...], ignoring only explicitly adapter-specific execution outcomes.

## Planned Files / Artifacts

Modify:

None.

Create:

- `tests/integration/lab/test_runtime_parity.py`

- `tests/architecture/test_research_write_firewall.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

ParityTrace: candidate/event/state/policy digests, ordered intents, risk decisions, OMS transitions and ledger postings. compare_traces(left,right)->tuple[Divergence,...], ignoring only explicitly adapter-specific execution outcomes.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

No old shadow performance becomes qualification evidence; this suite is offline parity proof only.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

ParityTrace: candidate/event/state/policy digests, ordered intents, risk decisions, OMS transitions and ledger postings. compare_traces(left,right)->tuple[Divergence,...], ignoring only explicitly adapter-specific execution outcomes.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Replay common canonical sequence into historical/shadow/production-shaped fake compositions.

- [ ] Step 2: Compare exact pre-venue IDs and Decimal semantics.

- [ ] Step 3: Enumerate justified fill/timing differences without hiding decision drift.

- [ ] Step 4: Run duplicate/restart/halt failure matrix.

- [ ] Step 5: Emit immutable test evidence manifest tied to code SHA.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/integration/lab/test_runtime_parity.py tests/architecture/test_research_write_firewall.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/integration/lab/test_runtime_parity.py`, `tests/architecture/test_research_write_firewall.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RP-05-AC0 | `test_rp_05_0` | Candidate intent IDs/content match before venue boundary |

| RP-05-AC1 | `test_rp_05_1` | Same risk state gives same quantity/reason |

| RP-05-AC2 | `test_rp_05_2` | Same normalized fills produce identical journal totals |

| RP-05-AC3 | `test_rp_05_3` | Clock/fill differences cannot mask order-semantic divergence |

| RP-05-AC4 | `test_rp_05_4` | Research transitive imports expose no real writer |

Focused command: `python -m pytest tests/integration/lab/test_runtime_parity.py tests/architecture/test_research_write_firewall.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Same risk state gives same quantity/reason. Rejection preserves prior committed evidence and emits a specific reason.

- Same normalized fills produce identical journal totals. Rejection preserves prior committed evidence and emits a specific reason.

- Clock/fill differences cannot mask order-semantic divergence. Rejection preserves prior committed evidence and emits a specific reason.

- Research transitive imports expose no real writer. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RP-05 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

No old shadow performance becomes qualification evidence; this suite is offline parity proof only.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RP-05-AC0** Candidate intent IDs/content match before venue boundary. Evidence: named test on exact committed SHA.

- [ ] **RP-05-AC1** Same risk state gives same quantity/reason. Evidence: named test on exact committed SHA.

- [ ] **RP-05-AC2** Same normalized fills produce identical journal totals. Evidence: named test on exact committed SHA.

- [ ] **RP-05-AC3** Clock/fill differences cannot mask order-semantic divergence. Evidence: named test on exact committed SHA.

- [ ] **RP-05-AC4** Research transitive imports expose no real writer. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rp-05-runtime-parity-qualification-fixtures` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rp-05): runtime parity qualification fixtures`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RP-05-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RP-05

### OBJECTIVE

Evidence of shared decisions, risk, OMS and accounting before tournament qualification.

### ARCHITECTURAL CONTEXT

Unit suites prove individual components; no cross-environment parity suite. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`tests/integration/lab/test_runtime_parity.py`, `tests/architecture/test_research_write_firewall.py`

### TESTS

`python -m pytest tests/integration/lab/test_runtime_parity.py tests/architecture/test_research_write_firewall.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RP-05-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.

