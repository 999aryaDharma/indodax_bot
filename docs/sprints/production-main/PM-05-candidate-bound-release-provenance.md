# PM-05 — Candidate-bound release provenance Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Complete release manifest and fail-closed verification with explicit authenticity policy.

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

Recommended Branch: `feat/pm-05-candidate-bound-release-provenance`

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Complete release manifest and fail-closed verification with explicit authenticity policy.

## Why This Sprint Exists

Purpose: Candidate-bound release provenance. Gap: Complete release manifest and fail-closed verification with explicit authenticity policy.

## Depends On

- RW4-01 — Immutable candidate packaging and lifecycle
- PM-03 — Recovery mode and durable operator risk governance

## Unlocks

PM-06, RW9-01

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

ReleaseBundle hashes fields but candidate identities optional; digest is not signature.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Require all production identity fields while retaining legacy bundle type

- Verify referenced bytes and environment before release selection

- Package immutable manifest instead of printing READY

- Define detached signature verification capability with offline trust roots, no keys added here

- Refuse activation eligibility without independent gate evidence

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **PM-05-FR0:** Missing/mismatched policy/model/schema identity rejects.

1. **PM-05-FR1:** Same filename with changed bytes fails.

2. **PM-05-FR2:** Digest-only legacy bundle cannot claim authenticity.

3. **PM-05-FR3:** Dirty source/unknown dependency identity cannot produce eligible release.

4. **PM-05-FR4:** Research request cannot mark deployed.

## Domain Rules / Invariants

ProductionReleaseManifest requires candidate/models/features/pipeline/risk/cost/execution/Git/dependency/environment digests plus qualification refs. verify_release(manifest,artifacts,trust_policy)->VerifiedRelease; local SHA checksum must never be described as signature.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. ProductionReleaseManifest requires candidate/models/features/pipeline/risk/cost/execution/Git/dependency/environment digests plus qualification refs. verify_release(manifest,artifacts,trust_policy)->VerifiedRelease; local SHA checksum must never be described as signature.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/verification/release_bundle.py`

- `src/indodax_lab/verification/release.py`

- `deploy/release-lab.sh`

Create:

- `tests/unit/lab/verification/test_release_provenance.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

ProductionReleaseManifest requires candidate/models/features/pipeline/risk/cost/execution/Git/dependency/environment digests plus qualification refs. verify_release(manifest,artifacts,trust_policy)->VerifiedRelease; local SHA checksum must never be described as signature.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Legacy content-integrity bundles remain readable evidence; explicit new release schema for production.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

ProductionReleaseManifest requires candidate/models/features/pipeline/risk/cost/execution/Git/dependency/environment digests plus qualification refs. verify_release(manifest,artifacts,trust_policy)->VerifiedRelease; local SHA checksum must never be described as signature.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Require all production identity fields while retaining legacy bundle type.

- [ ] Step 2: Verify referenced bytes and environment before release selection.

- [ ] Step 3: Package immutable manifest instead of printing READY.

- [ ] Step 4: Define detached signature verification capability with offline trust roots, no keys added here.

- [ ] Step 5: Refuse activation eligibility without independent gate evidence.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/unit/lab/verification/test_release_provenance.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/unit/lab/verification/test_release_provenance.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| PM-05-AC0 | `test_pm_05_0` | Missing/mismatched policy/model/schema identity rejects |

| PM-05-AC1 | `test_pm_05_1` | Same filename with changed bytes fails |

| PM-05-AC2 | `test_pm_05_2` | Digest-only legacy bundle cannot claim authenticity |

| PM-05-AC3 | `test_pm_05_3` | Dirty source/unknown dependency identity cannot produce eligible release |

| PM-05-AC4 | `test_pm_05_4` | Research request cannot mark deployed |

Focused command: `python -m pytest tests/unit/lab/verification/test_release_provenance.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Same filename with changed bytes fails. Rejection preserves prior committed evidence and emits a specific reason.

- Digest-only legacy bundle cannot claim authenticity. Rejection preserves prior committed evidence and emits a specific reason.

- Dirty source/unknown dependency identity cannot produce eligible release. Rejection preserves prior committed evidence and emits a specific reason.

- Research request cannot mark deployed. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. PM-05 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Legacy content-integrity bundles remain readable evidence; explicit new release schema for production.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **PM-05-AC0** Missing/mismatched policy/model/schema identity rejects. Evidence: named test on exact committed SHA.

- [ ] **PM-05-AC1** Same filename with changed bytes fails. Evidence: named test on exact committed SHA.

- [ ] **PM-05-AC2** Digest-only legacy bundle cannot claim authenticity. Evidence: named test on exact committed SHA.

- [ ] **PM-05-AC3** Dirty source/unknown dependency identity cannot produce eligible release. Evidence: named test on exact committed SHA.

- [ ] **PM-05-AC4** Research request cannot mark deployed. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/pm-05-candidate-bound-release-provenance` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(pm-05): candidate-bound release provenance`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-05-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

PM-05

### OBJECTIVE

Complete release manifest and fail-closed verification with explicit authenticity policy.

### ARCHITECTURAL CONTEXT

ReleaseBundle hashes fields but candidate identities optional; digest is not signature. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/verification/release_bundle.py`, `src/indodax_lab/verification/release.py`, `deploy/release-lab.sh`, `tests/unit/lab/verification/test_release_provenance.py`

### TESTS

`python -m pytest tests/unit/lab/verification/test_release_provenance.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `PM-05-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
