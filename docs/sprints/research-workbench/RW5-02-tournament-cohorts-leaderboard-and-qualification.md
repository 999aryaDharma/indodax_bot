# RW5-02 — Tournament cohorts leaderboard and qualification Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Comparable live cohorts and evidence-based qualification distinct from rank.

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

Recommended Branch: `feat/rw5-02-tournament-cohorts-leaderboard-and-qualification`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Comparable live cohorts and evidence-based qualification distinct from rank.

## Why This Sprint Exists

Purpose: Tournament cohorts leaderboard and qualification. Gap: Comparable live cohorts and evidence-based qualification distinct from rank.

## Depends On

- RW5-01 — Isolated durable forward-shadow agents
- SHADOW-03 — Champion replacement gate

## Unlocks

RW7-02, RW8-01, RW9-01

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

Historical tournament and simple promotion counters exist.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Aggregate metrics from exact fills/trades and mark provenance

- Flag incompatible capital/coverage/policies

- Evaluate frozen 90-day AND 100-closed-trade gate with incident/restart identity evidence

- Append qualification decision without deployment authority

- Keep retired/failed challengers visible

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW5-02-FR0:** 89 days/100 trades and 90 days/99 trades both reject.

1. **RW5-02-FR1:** Rank one with unresolved incident is unqualified.

2. **RW5-02-FR2:** Candidate hash change invalidates accumulated qualification.

3. **RW5-02-FR3:** Missing marks produce unknown metrics rather than zero.

4. **RW5-02-FR4:** Qualification cannot call venue or release activation.

## Domain Rules / Invariants

TournamentService.create(cohort_manifest)->CohortRecord; leaderboard(cohort_id)->Leaderboard; compare(agent_ids)->ComparisonReport; qualify(agent_id,policy_ref)->QualificationDecision. CohortManifest binds agent IDs, capital/cost/feed/time-window comparability criteria.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. TournamentService.create(cohort_manifest)->CohortRecord; leaderboard(cohort_id)->Leaderboard; compare(agent_ids)->ComparisonReport; qualify(agent_id,policy_ref)->QualificationDecision. CohortManifest binds agent IDs, capital/cost/feed/time-window comparability criteria.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/evaluation/tournament.py`

- `src/indodax_lab/paper/promotion.py`

Create:

- `src/indodax_lab/paper/tournament_service.py`

- `tests/unit/lab/paper/test_tournament_qualification.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

TournamentService.create(cohort_manifest)->CohortRecord; leaderboard(cohort_id)->Leaderboard; compare(agent_ids)->ComparisonReport; qualify(agent_id,policy_ref)->QualificationDecision. CohortManifest binds agent IDs, capital/cost/feed/time-window comparability criteria.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Existing champion registry remains historical research terminology; no production deployment meaning.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

TournamentService.create(cohort_manifest)->CohortRecord; leaderboard(cohort_id)->Leaderboard; compare(agent_ids)->ComparisonReport; qualify(agent_id,policy_ref)->QualificationDecision. CohortManifest binds agent IDs, capital/cost/feed/time-window comparability criteria.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Aggregate metrics from exact fills/trades and mark provenance.

- [ ] Step 2: Flag incompatible capital/coverage/policies.

- [ ] Step 3: Evaluate frozen 90-day AND 100-closed-trade gate with incident/restart identity evidence.

- [ ] Step 4: Append qualification decision without deployment authority.

- [ ] Step 5: Keep retired/failed challengers visible.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/unit/lab/paper/test_tournament_qualification.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/unit/lab/paper/test_tournament_qualification.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW5-02-AC0 | `test_rw5_02_0` | 89 days/100 trades and 90 days/99 trades both reject |

| RW5-02-AC1 | `test_rw5_02_1` | Rank one with unresolved incident is unqualified |

| RW5-02-AC2 | `test_rw5_02_2` | Candidate hash change invalidates accumulated qualification |

| RW5-02-AC3 | `test_rw5_02_3` | Missing marks produce unknown metrics rather than zero |

| RW5-02-AC4 | `test_rw5_02_4` | Qualification cannot call venue or release activation |

Focused command: `python -m pytest tests/unit/lab/paper/test_tournament_qualification.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Rank one with unresolved incident is unqualified. Rejection preserves prior committed evidence and emits a specific reason.

- Candidate hash change invalidates accumulated qualification. Rejection preserves prior committed evidence and emits a specific reason.

- Missing marks produce unknown metrics rather than zero. Rejection preserves prior committed evidence and emits a specific reason.

- Qualification cannot call venue or release activation. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW5-02 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Existing champion registry remains historical research terminology; no production deployment meaning.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW5-02-AC0** 89 days/100 trades and 90 days/99 trades both reject. Evidence: named test on exact committed SHA.

- [ ] **RW5-02-AC1** Rank one with unresolved incident is unqualified. Evidence: named test on exact committed SHA.

- [ ] **RW5-02-AC2** Candidate hash change invalidates accumulated qualification. Evidence: named test on exact committed SHA.

- [ ] **RW5-02-AC3** Missing marks produce unknown metrics rather than zero. Evidence: named test on exact committed SHA.

- [ ] **RW5-02-AC4** Qualification cannot call venue or release activation. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw5-02-tournament-cohorts-leaderboard-and-qualification` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw5-02): tournament cohorts leaderboard and qualification`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW5-02-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW5-02

### OBJECTIVE

Comparable live cohorts and evidence-based qualification distinct from rank.

### ARCHITECTURAL CONTEXT

Historical tournament and simple promotion counters exist. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/evaluation/tournament.py`, `src/indodax_lab/paper/promotion.py`, `src/indodax_lab/paper/tournament_service.py`, `tests/unit/lab/paper/test_tournament_qualification.py`

### TESTS

`python -m pytest tests/unit/lab/paper/test_tournament_qualification.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW5-02-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
