# RP-02 — Shared candidate feature and exit evaluation Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** One verified evaluator independent of venue, training and ambient clock.

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

Recommended Branch: `feat/rp-02-shared-candidate-feature-and-exit-evaluation`

Requirements: FR-20 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

One verified evaluator independent of venue, training and ambient clock.

## Why This Sprint Exists

Purpose: Shared candidate feature and exit evaluation. Gap: One verified evaluator independent of venue, training and ambient clock.

## Depends On

- RW2-03 — Typed declarative pipeline composer
- FEAT-02 — Golden technical and liquidity transforms

## Unlocks

RP-04

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

Feature registry and registered TA implementations coexist with custom shadow feature/TA/exit code.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Construct offline fixture manifests from RW0 contracts; packaging service is not prerequisite

- Resolve feature and registered pipeline nodes once by digest

- Evaluate with causal availability and immutable inference transforms

- Implement exit state per versioned policy; stop-first on ambiguous OHLCV evidence

- Emit content-derived intent IDs and persistible feature/exit state

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RP-02-FR0:** Same candidate/event/state gives identical intent bytes.

1. **RP-02-FR1:** Future-row perturbation leaves past decisions unchanged.

2. **RP-02-FR2:** Feature/model mismatch rejects before decision.

3. **RP-02-FR3:** C02 trailing/breakeven advances once per new closed bar.

4. **RP-02-FR4:** Missing M02/D04 declared artifact cannot silently degrade to TA-only.

## Domain Rules / Invariants

CandidateRuntime.evaluate(event:CanonicalMarketEvent,state:RuntimeState)->tuple[SignalIntent,...]; CandidateRuntime.load(manifest:CandidateManifest,artifact_resolver)->CandidateRuntime. RuntimeState and event fields are fixed in CONTRACTS.md.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. CandidateRuntime.evaluate(event:CanonicalMarketEvent,state:RuntimeState)->tuple[SignalIntent,...]; CandidateRuntime.load(manifest:CandidateManifest,artifact_resolver)->CandidateRuntime. RuntimeState and event fields are fixed in CONTRACTS.md.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/backtest/feature_replay.py`

Create:

- `src/indodax_lab/runtime/candidate.py`

- `src/indodax_lab/runtime/exits.py`

- `tests/unit/lab/runtime/test_candidate_runtime.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

CandidateRuntime.evaluate(event:CanonicalMarketEvent,state:RuntimeState)->tuple[SignalIntent,...]; CandidateRuntime.load(manifest:CandidateManifest,artifact_resolver)->CandidateRuntime. RuntimeState and event fields are fixed in CONTRACTS.md.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Old shadow parameters/exits remain an archived policy version; new semantics require new candidate, never re-label existing evidence.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

CandidateRuntime.evaluate(event:CanonicalMarketEvent,state:RuntimeState)->tuple[SignalIntent,...]; CandidateRuntime.load(manifest:CandidateManifest,artifact_resolver)->CandidateRuntime. RuntimeState and event fields are fixed in CONTRACTS.md.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Construct offline fixture manifests from RW0 contracts; packaging service is not prerequisite.

- [ ] Step 2: Resolve feature and registered pipeline nodes once by digest.

- [ ] Step 3: Evaluate with causal availability and immutable inference transforms.

- [ ] Step 4: Implement exit state per versioned policy; stop-first on ambiguous OHLCV evidence.

- [ ] Step 5: Emit content-derived intent IDs and persistible feature/exit state.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/unit/lab/runtime/test_candidate_runtime.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/unit/lab/runtime/test_candidate_runtime.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RP-02-AC0 | `test_rp_02_0` | Same candidate/event/state gives identical intent bytes |

| RP-02-AC1 | `test_rp_02_1` | Future-row perturbation leaves past decisions unchanged |

| RP-02-AC2 | `test_rp_02_2` | Feature/model mismatch rejects before decision |

| RP-02-AC3 | `test_rp_02_3` | C02 trailing/breakeven advances once per new closed bar |

| RP-02-AC4 | `test_rp_02_4` | Missing M02/D04 declared artifact cannot silently degrade to TA-only |

Focused command: `python -m pytest tests/unit/lab/runtime/test_candidate_runtime.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Future-row perturbation leaves past decisions unchanged. Rejection preserves prior committed evidence and emits a specific reason.

- Feature/model mismatch rejects before decision. Rejection preserves prior committed evidence and emits a specific reason.

- C02 trailing/breakeven advances once per new closed bar. Rejection preserves prior committed evidence and emits a specific reason.

- Missing M02/D04 declared artifact cannot silently degrade to TA-only. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RP-02 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Old shadow parameters/exits remain an archived policy version; new semantics require new candidate, never re-label existing evidence.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RP-02-AC0** Same candidate/event/state gives identical intent bytes. Evidence: named test on exact committed SHA.

- [ ] **RP-02-AC1** Future-row perturbation leaves past decisions unchanged. Evidence: named test on exact committed SHA.

- [ ] **RP-02-AC2** Feature/model mismatch rejects before decision. Evidence: named test on exact committed SHA.

- [ ] **RP-02-AC3** C02 trailing/breakeven advances once per new closed bar. Evidence: named test on exact committed SHA.

- [ ] **RP-02-AC4** Missing M02/D04 declared artifact cannot silently degrade to TA-only. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rp-02-shared-candidate-feature-and-exit-evaluation` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rp-02): shared candidate feature and exit evaluation`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RP-02-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RP-02

### OBJECTIVE

One verified evaluator independent of venue, training and ambient clock.

### ARCHITECTURAL CONTEXT

Feature registry and registered TA implementations coexist with custom shadow feature/TA/exit code. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/backtest/feature_replay.py`, `src/indodax_lab/runtime/candidate.py`, `src/indodax_lab/runtime/exits.py`, `tests/unit/lab/runtime/test_candidate_runtime.py`

### TESTS

`python -m pytest tests/unit/lab/runtime/test_candidate_runtime.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RP-02-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.

