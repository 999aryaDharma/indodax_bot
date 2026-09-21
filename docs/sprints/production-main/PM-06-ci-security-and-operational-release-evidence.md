# PM-06 — CI security and operational release evidence Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Reproducible environment, security evidence and executable service/recovery drills.

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

Recommended Branch: `feat/pm-06-ci-security-and-operational-release-evidence`

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Reproducible environment, security evidence and executable service/recovery drills.

## Why This Sprint Exists

Purpose: CI security and operational release evidence. Gap: Reproducible environment, security evidence and executable service/recovery drills.

## Depends On

- PM-05 — Candidate-bound release provenance
- RW5-01 — Isolated durable forward-shadow agents

## Unlocks

No mandatory dependent sprint.

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

CI tests/lints subsets; service templates and deployment workflow are not governed release proof.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Pin compatible dependency lock and emit SBOM/security/history-scan evidence

- Expand strict checks to all canonical production/core modules

- Verify service entrypoints and graceful durable shutdown using fake adapters

- Document single-writer restore/network/clock/disk failure drills

- Replace deployment assumptions in runbook with governed artifact selection; do not deploy

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **PM-06-FR0:** Missing CLI entrypoint fails offline check.

1. **PM-06-FR1:** Secret/history/CVE finding prevents eligible release.

2. **PM-06-FR2:** Required skipped test cannot become PASS.

3. **PM-06-FR3:** Backup restore verifies hashes and exact financial revision.

4. **PM-06-FR4:** No workflow execution or host benchmark is claimed from local fixtures.

## Domain Rules / Invariants

ReleaseEvidence records source SHA, lock/SBOM/security scan digests, command exits, target-host measurements, backup/restore RPO/RTO and gate states. CI validates service entrypoints offline; operational drills require separate authorized host.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. ReleaseEvidence records source SHA, lock/SBOM/security scan digests, command exits, target-host measurements, backup/restore RPO/RTO and gate states. CI validates service entrypoints offline; operational drills require separate authorized host.

## Planned Files / Artifacts

Modify:

- `.github/workflows/ci.yml`

- `deploy/lab-shadow.service`

- `deploy/lab-worker.service`

- `deploy/release-lab.sh`

Create:

- `docs/quality/production-release-evidence.md`

- `tests/integration/lab/test_service_entrypoints.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

ReleaseEvidence records source SHA, lock/SBOM/security scan digests, command exits, target-host measurements, backup/restore RPO/RTO and gate states. CI validates service entrypoints offline; operational drills require separate authorized host.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Legacy main deploy workflow remains explicitly unqualified until separately reviewed replacement; no workflow dispatch in this task.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

ReleaseEvidence records source SHA, lock/SBOM/security scan digests, command exits, target-host measurements, backup/restore RPO/RTO and gate states. CI validates service entrypoints offline; operational drills require separate authorized host.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Pin compatible dependency lock and emit SBOM/security/history-scan evidence.

- [ ] Step 2: Expand strict checks to all canonical production/core modules.

- [ ] Step 3: Verify service entrypoints and graceful durable shutdown using fake adapters.

- [ ] Step 4: Document single-writer restore/network/clock/disk failure drills.

- [ ] Step 5: Replace deployment assumptions in runbook with governed artifact selection; do not deploy.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/integration/lab/test_service_entrypoints.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/integration/lab/test_service_entrypoints.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| PM-06-AC0 | `test_pm_06_0` | Missing CLI entrypoint fails offline check |

| PM-06-AC1 | `test_pm_06_1` | Secret/history/CVE finding prevents eligible release |

| PM-06-AC2 | `test_pm_06_2` | Required skipped test cannot become PASS |

| PM-06-AC3 | `test_pm_06_3` | Backup restore verifies hashes and exact financial revision |

| PM-06-AC4 | `test_pm_06_4` | No workflow execution or host benchmark is claimed from local fixtures |

Focused command: `python -m pytest tests/integration/lab/test_service_entrypoints.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Secret/history/CVE finding prevents eligible release. Rejection preserves prior committed evidence and emits a specific reason.

- Required skipped test cannot become PASS. Rejection preserves prior committed evidence and emits a specific reason.

- Backup restore verifies hashes and exact financial revision. Rejection preserves prior committed evidence and emits a specific reason.

- No workflow execution or host benchmark is claimed from local fixtures. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. PM-06 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Legacy main deploy workflow remains explicitly unqualified until separately reviewed replacement; no workflow dispatch in this task.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **PM-06-AC0** Missing CLI entrypoint fails offline check. Evidence: named test on exact committed SHA.

- [ ] **PM-06-AC1** Secret/history/CVE finding prevents eligible release. Evidence: named test on exact committed SHA.

- [ ] **PM-06-AC2** Required skipped test cannot become PASS. Evidence: named test on exact committed SHA.

- [ ] **PM-06-AC3** Backup restore verifies hashes and exact financial revision. Evidence: named test on exact committed SHA.

- [ ] **PM-06-AC4** No workflow execution or host benchmark is claimed from local fixtures. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/pm-06-ci-security-and-operational-release-evidence` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(pm-06): ci security and operational release evidence`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-06-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

PM-06

### OBJECTIVE

Reproducible environment, security evidence and executable service/recovery drills.

### ARCHITECTURAL CONTEXT

CI tests/lints subsets; service templates and deployment workflow are not governed release proof. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`.github/workflows/ci.yml`, `deploy/lab-shadow.service`, `deploy/lab-worker.service`, `deploy/release-lab.sh`, `docs/quality/production-release-evidence.md`, `tests/integration/lab/test_service_entrypoints.py`

### TESTS

`python -m pytest tests/integration/lab/test_service_entrypoints.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `PM-06-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
