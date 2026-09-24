# RW1-01 — Reusable immutable dataset registry Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Range-aware reusable versions, atomic catalog publication and explicit quality lineage.

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

Status: DONE

Priority: P1 | Type: integration | Domain: research-workbench | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/rw1-01-reusable-immutable-dataset-registry`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Range-aware reusable versions, atomic catalog publication and explicit quality lineage.

## Why This Sprint Exists

Purpose: Reusable immutable dataset registry. Gap: Range-aware reusable versions, atomic catalog publication and explicit quality lineage.

## Depends On

- RW0-01 — Immutable Workbench domain manifests
- DATA-06 — Provider-derived reproducible snapshot

## Unlocks

RW3-01, RW7-01, DATA-07

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

Backfill/snapshot/quality/publication and inventory exist; aggregate identity contains root paths.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Build temp-root cached-range and immutable-version fixtures

- Reuse candle backfill/snapshot publication for missing intervals only

- Validate ordering, gaps, duplicates, schema and bytes before registry visibility

- Publish manifest/catalog using exclusive atomic operation

- Add CLI lookup/create/extend/validate with structured status

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW1-01-FR0:** Covered request performs zero provider fetches.

1. **RW1-01-FR1:** Extension fetches only uncovered intervals and preserves v1 bytes.

2. **RW1-01-FR2:** Zero bars or broken partition hash cannot be experiment-ready.

3. **RW1-01-FR3:** Concurrent same-version changed publication rejects.

4. **RW1-01-FR4:** Crash before catalog commit leaves no visible successful dataset.

## Domain Rules / Invariants

DatasetRegistry.find(venue,pair,timeframe,start,end)->tuple[ArtifactRef,...]; create(request)->DatasetManifest; extend(parent,request)->DatasetManifest; get(ref)->DatasetManifest; validate(ref)->QualityReport. DatasetRequest and QualityReport use dataset fields in CONTRACTS.md.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. DatasetRegistry.find(venue,pair,timeframe,start,end)->tuple[ArtifactRef,...]; create(request)->DatasetManifest; extend(parent,request)->DatasetManifest; get(ref)->DatasetManifest; validate(ref)->QualityReport. DatasetRequest and QualityReport use dataset fields in CONTRACTS.md.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/cli/dataset_registry.py`

- `src/indodax_lab/cli/dataset_inventory.py`

Create:

- `src/indodax_lab/data/dataset_registry.py`

- `tests/integration/lab/test_dataset_registry_versions.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

DatasetRegistry.find(venue,pair,timeframe,start,end)->tuple[ArtifactRef,...]; create(request)->DatasetManifest; extend(parent,request)->DatasetManifest; get(ref)->DatasetManifest; validate(ref)->QualityReport. DatasetRequest and QualityReport use dataset fields in CONTRACTS.md.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Import legacy snapshots by verified partition bytes; preserve root paths as location metadata outside identity. Do not alter raw bytes.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

DatasetRegistry.find(venue,pair,timeframe,start,end)->tuple[ArtifactRef,...]; create(request)->DatasetManifest; extend(parent,request)->DatasetManifest; get(ref)->DatasetManifest; validate(ref)->QualityReport. DatasetRequest and QualityReport use dataset fields in CONTRACTS.md.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Build temp-root cached-range and immutable-version fixtures.

- [ ] Step 2: Reuse candle backfill/snapshot publication for missing intervals only.

- [ ] Step 3: Validate ordering, gaps, duplicates, schema and bytes before registry visibility.

- [ ] Step 4: Publish manifest/catalog using exclusive atomic operation.

- [ ] Step 5: Add CLI lookup/create/extend/validate with structured status.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/integration/lab/test_dataset_registry_versions.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/integration/lab/test_dataset_registry_versions.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW1-01-AC0 | `test_rw1_01_0` | Covered request performs zero provider fetches |

| RW1-01-AC1 | `test_rw1_01_1` | Extension fetches only uncovered intervals and preserves v1 bytes |

| RW1-01-AC2 | `test_rw1_01_2` | Zero bars or broken partition hash cannot be experiment-ready |

| RW1-01-AC3 | `test_rw1_01_3` | Concurrent same-version changed publication rejects |

| RW1-01-AC4 | `test_rw1_01_4` | Crash before catalog commit leaves no visible successful dataset |

Focused command: `python -m pytest tests/integration/lab/test_dataset_registry_versions.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Extension fetches only uncovered intervals and preserves v1 bytes. Rejection preserves prior committed evidence and emits a specific reason.

- Zero bars or broken partition hash cannot be experiment-ready. Rejection preserves prior committed evidence and emits a specific reason.

- Concurrent same-version changed publication rejects. Rejection preserves prior committed evidence and emits a specific reason.

- Crash before catalog commit leaves no visible successful dataset. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW1-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Import legacy snapshots by verified partition bytes; preserve root paths as location metadata outside identity. Do not alter raw bytes.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW1-01-AC0** Covered request performs zero provider fetches. Evidence: named test on exact committed SHA.

- [ ] **RW1-01-AC1** Extension fetches only uncovered intervals and preserves v1 bytes. Evidence: named test on exact committed SHA.

- [ ] **RW1-01-AC2** Zero bars or broken partition hash cannot be experiment-ready. Evidence: named test on exact committed SHA.

- [ ] **RW1-01-AC3** Concurrent same-version changed publication rejects. Evidence: named test on exact committed SHA.

- [ ] **RW1-01-AC4** Crash before catalog commit leaves no visible successful dataset. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw1-01-reusable-immutable-dataset-registry` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw1-01): reusable immutable dataset registry`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW1-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW1-01

### OBJECTIVE

Range-aware reusable versions, atomic catalog publication and explicit quality lineage.

### ARCHITECTURAL CONTEXT

Backfill/snapshot/quality/publication and inventory exist; aggregate identity contains root paths. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/cli/dataset_registry.py`, `src/indodax_lab/cli/dataset_inventory.py`, `src/indodax_lab/data/dataset_registry.py`, `tests/integration/lab/test_dataset_registry_versions.py`

### TESTS

`python -m pytest tests/integration/lab/test_dataset_registry_versions.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW1-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
