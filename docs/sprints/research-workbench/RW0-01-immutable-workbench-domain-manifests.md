# RW0-01 — Immutable Workbench domain manifests Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Deep immutable portable identities and state-machine contracts.

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

Priority: P0 | Type: integration | Domain: research-workbench | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/rw0-01-immutable-workbench-domain-manifests`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Deep immutable portable identities and state-machine contracts.

## Why This Sprint Exists

Purpose: Immutable Workbench domain manifests. Gap: Deep immutable portable identities and state-machine contracts.

## Depends On

- RP-01 — Shared SignalIntent ownership with compatibility
- DATA-01 — Canonical market contracts

## Unlocks

RW1-01, RW2-01, RW2-02, RP-03, PM-01, PM-02

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

Typed market contracts and separate model/run records exist; aggregate domain identity is absent.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Implement table-driven identity/UTC/Decimal/extra-field tests

- Define deeply immutable manifests and typed references

- Separate semantic payload from audit envelope

- Define allowed lifecycle events without adding persistence

- Pin serialization vectors and document adapters to existing records

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW0-01-FR0:** Key reordering gives same digest; local-root relocation cannot affect it.

1. **RW0-01-FR1:** Nested mutation cannot change published manifest.

2. **RW0-01-FR2:** Changed risk/model/feature/seed changes identity.

3. **RW0-01-FR3:** Extra fields, naive time, NaN and invalid hash reject.

4. **RW0-01-FR4:** Terminal experiment configuration cannot be edited.

## Domain Rules / Invariants

ArtifactRef; DatasetManifest; StrategyManifest; ModelManifest; PipelineManifest; ExperimentManifest; CandidateManifest; AgentManifest; canonical_bytes(manifest)->bytes; manifest_digest(manifest)->str. Fields and lifecycle edges are fixed in CONTRACTS.md.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. ArtifactRef; DatasetManifest; StrategyManifest; ModelManifest; PipelineManifest; ExperimentManifest; CandidateManifest; AgentManifest; canonical_bytes(manifest)->bytes; manifest_digest(manifest)->str. Fields and lifecycle edges are fixed in CONTRACTS.md.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/contracts/__init__.py`

Create:

- `src/indodax_lab/contracts/workbench.py`

- `src/indodax_lab/contracts/identity.py`

- `tests/unit/lab/test_workbench_contracts.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

ArtifactRef; DatasetManifest; StrategyManifest; ModelManifest; PipelineManifest; ExperimentManifest; CandidateManifest; AgentManifest; canonical_bytes(manifest)->bytes; manifest_digest(manifest)->str. Fields and lifecycle edges are fixed in CONTRACTS.md.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Add version 1 manifests; existing artifacts stay legacy and require explicit verified import, never guessed lineage.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

ArtifactRef; DatasetManifest; StrategyManifest; ModelManifest; PipelineManifest; ExperimentManifest; CandidateManifest; AgentManifest; canonical_bytes(manifest)->bytes; manifest_digest(manifest)->str. Fields and lifecycle edges are fixed in CONTRACTS.md.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Implement table-driven identity/UTC/Decimal/extra-field tests.

- [ ] Step 2: Define deeply immutable manifests and typed references.

- [ ] Step 3: Separate semantic payload from audit envelope.

- [ ] Step 4: Define allowed lifecycle events without adding persistence.

- [ ] Step 5: Pin serialization vectors and document adapters to existing records.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/unit/lab/test_workbench_contracts.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/unit/lab/test_workbench_contracts.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW0-01-AC0 | `test_rw0_01_0` | Key reordering gives same digest; local-root relocation cannot affect it |

| RW0-01-AC1 | `test_rw0_01_1` | Nested mutation cannot change published manifest |

| RW0-01-AC2 | `test_rw0_01_2` | Changed risk/model/feature/seed changes identity |

| RW0-01-AC3 | `test_rw0_01_3` | Extra fields, naive time, NaN and invalid hash reject |

| RW0-01-AC4 | `test_rw0_01_4` | Terminal experiment configuration cannot be edited |

Focused command: `python -m pytest tests/unit/lab/test_workbench_contracts.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Nested mutation cannot change published manifest. Rejection preserves prior committed evidence and emits a specific reason.

- Changed risk/model/feature/seed changes identity. Rejection preserves prior committed evidence and emits a specific reason.

- Extra fields, naive time, NaN and invalid hash reject. Rejection preserves prior committed evidence and emits a specific reason.

- Terminal experiment configuration cannot be edited. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW0-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Add version 1 manifests; existing artifacts stay legacy and require explicit verified import, never guessed lineage.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW0-01-AC0** Key reordering gives same digest; local-root relocation cannot affect it. Evidence: named test on exact committed SHA.

- [ ] **RW0-01-AC1** Nested mutation cannot change published manifest. Evidence: named test on exact committed SHA.

- [ ] **RW0-01-AC2** Changed risk/model/feature/seed changes identity. Evidence: named test on exact committed SHA.

- [ ] **RW0-01-AC3** Extra fields, naive time, NaN and invalid hash reject. Evidence: named test on exact committed SHA.

- [ ] **RW0-01-AC4** Terminal experiment configuration cannot be edited. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw0-01-immutable-workbench-domain-manifests` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw0-01): immutable workbench domain manifests`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW0-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW0-01

### OBJECTIVE

Deep immutable portable identities and state-machine contracts.

### ARCHITECTURAL CONTEXT

Typed market contracts and separate model/run records exist; aggregate domain identity is absent. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/contracts/__init__.py`, `src/indodax_lab/contracts/workbench.py`, `src/indodax_lab/contracts/identity.py`, `tests/unit/lab/test_workbench_contracts.py`

### TESTS

`python -m pytest tests/unit/lab/test_workbench_contracts.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW0-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.

