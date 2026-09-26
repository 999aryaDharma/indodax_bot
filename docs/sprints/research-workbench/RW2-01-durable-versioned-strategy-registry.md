# RW2-01 — Durable versioned strategy registry Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Draft revisions, stable code identity and published component discovery.

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

Status: READY

Priority: P1 | Type: integration | Domain: research-workbench | Portfolio: CORE

Implementation Owner: Codex | Independent Reviewer: /root/docs_review

Recommended Branch: `feat/rw2-01-durable-versioned-strategy-registry`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: M

Classification: Code committed at `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c`; review state remains governed by the sprint manifest and handoff. External gates remain separate from code acceptance.

## Goal

Draft revisions, stable code identity and published component discovery.

## Why This Sprint Exists

Purpose: Durable versioned strategy registry. Gap: Draft revisions, stable code identity and published component discovery.

## Depends On

- RW0-01 — Immutable Workbench domain manifests
- STRAT-01 — Declarative strategy protocol

## Unlocks

RW2-03

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

## Current Context

StrategyRegistry is in-memory; built-in strategies and YAML specifications already work.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

Owner-approved 2026-09-24 amendment: implement this sprint's behavior in `docs/implementation/BOT-TRADE-PROGRAM.md`; prior requirements remain mandatory.

- Wrap existing built-in registry through allowlisted strategy IDs

- Store draft revisions with compare-and-swap

- Hash versioned source/artifact bytes instead of callable repr

- Publish immutable parameters and feature/exit contracts

- Register C07/C02 seed manifests without hard-coded pair dispatch

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW2-01-FR0:** Published same-version parameter/logic change rejects.

1. **RW2-01-FR1:** Stale draft revision cannot overwrite edit.

2. **RW2-01-FR2:** Unknown import/module path rejects.

3. **RW2-01-FR3:** Clone preserves parent and leaves original intact.

## Domain Rules / Invariants

StrategyService.create_draft(manifest)->DraftRef; update_draft(id,expected_revision,parameters)->DraftRef; publish(id,expected_revision)->ArtifactRef; clone(ref)->DraftRef; get(ref)->StrategyManifest. DraftRef has id, revision and digest.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. StrategyService.create_draft(manifest)->DraftRef; update_draft(id,expected_revision,parameters)->DraftRef; publish(id,expected_revision)->ArtifactRef; clone(ref)->DraftRef; get(ref)->StrategyManifest. DraftRef has id, revision and digest.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/strategies/registry.py`

- `src/indodax_lab/strategies/base.py`

- `src/indodax_lab/strategies/__init__.py`

Create:

- `src/indodax_lab/strategies/store.py`

- `tests/unit/lab/strategies/test_versioned_registry.py`

- `configs/strategies/seeds.yaml`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

StrategyService.create_draft(manifest)->DraftRef; update_draft(id,expected_revision,parameters)->DraftRef; publish(id,expected_revision)->ArtifactRef; clone(ref)->DraftRef; get(ref)->StrategyManifest. DraftRef has id, revision and digest.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Existing register/get APIs remain; durable catalog adds explicit import records and leaves old experiment references unchanged.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

StrategyService.create_draft(manifest)->DraftRef; update_draft(id,expected_revision,parameters)->DraftRef; publish(id,expected_revision)->ArtifactRef; clone(ref)->DraftRef; get(ref)->StrategyManifest. DraftRef has id, revision and digest.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [x] Step 1: Wrap existing built-in registry through allowlisted strategy IDs.

- [x] Step 2: Store draft revisions with compare-and-swap.

- [x] Step 3: Hash versioned source/artifact bytes instead of callable repr.

- [x] Step 4: Publish immutable parameters and feature/exit contracts.

- [x] Step 5: Register C07/C02 seed manifests without hard-coded pair dispatch.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [x] Run focused versioned-registry tests and the whole strategy suite; the full repository suite also passed on the implementation SHA. Platform-specific skips are recorded in the handoff.

- [x] Run Ruff and `git diff --check`, record exact environment/commands/exit/SHA, and commit the scoped implementation. Independent review is pending.

## Required Tests

Planned test paths: `tests/unit/lab/strategies/test_versioned_registry.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW2-01-AC0 | `test_rw2_01_0_published_same_version_change_rejects`, `test_rw2_01_0_published_same_version_source_change_rejects`, `test_same_version_specification_metadata_change_rejects` | Published same-version parameter, source and specification changes reject |

| RW2-01-AC1 | `test_rw2_01_1_stale_draft_revision_cannot_overwrite_edit`, `test_rw2_01_1_revision_cas_holds_across_service_connections` | Stale draft revision cannot overwrite edit, including across store connections |

| RW2-01-AC2 | `test_rw2_01_2_unknown_source_and_executable_yaml_reject`, `test_registry_builtin_registration_uses_allowlist` | Unknown implementation and executable YAML fields reject without importing user paths |

| RW2-01-AC3 | `test_rw2_01_3_clone_preserves_parent_and_source` | Clone preserves parent, gets a distinct opaque version and leaves original intact |

| RW2-01-AC4 | `test_rw2_01_program_4_component_metadata_yaml_and_durable_reload`, `test_seed_manifests_bind_selected_pairs_without_pair_dispatch`, `test_seed_manifest_preserves_yaml_strategy_and_risk_defaults` | Versioned schemas/metadata and declarative C07/C02 seeds are available without executable expressions |

Focused command: `python -m pytest tests/unit/lab/strategies/test_versioned_registry.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Stale draft revision cannot overwrite edit. Rejection preserves prior committed evidence and emits a specific reason.

- Unknown import/module path rejects. Rejection preserves prior committed evidence and emits a specific reason.

- Clone preserves parent and leaves original intact. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW2-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Existing register/get APIs remain; durable catalog adds explicit import records and leaves old experiment references unchanged.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [x] **RW2-01-AC4** Expose versioned parameter schemas and component metadata to form/YAML/MCP without executable user expressions. Evidence: `test_rw2_01_program_4_component_metadata_yaml_and_durable_reload` at code SHA `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c`.

- [x] **RW2-01-AC0** Published same-version parameter/logic change rejects. Evidence: mapped parameter/source/full-spec tests on code SHA `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c`.

- [x] **RW2-01-AC1** Stale draft revision cannot overwrite edit. Evidence: same-service and two-connection CAS tests on code SHA `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c`.

- [x] **RW2-01-AC2** Unknown import/module path rejects. Evidence: allowlist and safe YAML tests on code SHA `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c`.

- [x] **RW2-01-AC3** Clone preserves parent and leaves original intact. Evidence: parent-ref, version separation and immutable-original test on code SHA `ab8fff6b2a7a64dbc84388f03f2b90bf05e4691c`.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw2-01-durable-versioned-strategy-registry` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw2-01): durable versioned strategy registry`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW2-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW2-01

### OBJECTIVE

Draft revisions, stable code identity and published component discovery.

### ARCHITECTURAL CONTEXT

StrategyRegistry is in-memory; built-in strategies and YAML specifications already work. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/strategies/registry.py`, `src/indodax_lab/strategies/base.py`, `src/indodax_lab/strategies/store.py`, `tests/unit/lab/strategies/test_versioned_registry.py`

### TESTS

`python -m pytest tests/unit/lab/strategies/test_versioned_registry.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW2-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
