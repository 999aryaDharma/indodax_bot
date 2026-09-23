# PM-04 — Venue parser cancellation and supported order semantics Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Verify actual internal type mapping, supported LIMIT/TIF and race/partial-fill behavior.

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

Priority: P0 | Type: integration | Domain: production-main | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/pm-04-venue-parser-cancellation-and-supported-order-semantics`

Requirements: FR-23 | Legacy tasks: none

Risk level: high | Complexity: M

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Verify actual internal type mapping, supported LIMIT/TIF and race/partial-fill behavior.

## Why This Sprint Exists

Purpose: Venue parser cancellation and supported order semantics. Gap: Verify actual internal type mapping, supported LIMIT/TIF and race/partial-fill behavior.

## Depends On

- PM-01 — Authoritative fail-closed pre-write gate
- PM-02 — Atomic financial execution state and recovery

## Unlocks

RP-05

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

Read/write parser reuse and inconclusive-cancel exception already present.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Build sanitized venue-shaped offline fixtures for quote/base quantity representations

- Validate parser object types and normalized totals through router

- Keep cancel UNKNOWN until conclusive order/fill evidence

- Reject unsupported semantics before transport

- Record externally unverified behavior as activation blocker, not fixture-proven venue fact

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **PM-04-FR0:** Original equals executed plus remaining in declared units.

1. **PM-04-FR1:** Cancel acknowledgement plus inconclusive lookup stays UNKNOWN.

2. **PM-04-FR2:** Fill/cancel race never invents zero fill.

3. **PM-04-FR3:** Unsupported order/TIF produces no HTTP call.

## Domain Rules / Invariants

TradingVenue existing submit/cancel/get methods remain; canonical VenueOrder fields require exact base quantity and executed/remaining consistency. Production supported order policy is explicit LIMIT plus externally verified TIF; no fallback to venue defaults.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. TradingVenue existing submit/cancel/get methods remain; canonical VenueOrder fields require exact base quantity and executed/remaining consistency. Production supported order policy is explicit LIMIT plus externally verified TIF; no fallback to venue defaults.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/execution/indodax_readonly.py`

- `src/indodax_lab/execution/indodax_trading.py`

- `src/indodax_lab/execution/order_router.py`

Create:

- `tests/unit/lab/execution/test_venue_semantics_contract.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

TradingVenue existing submit/cancel/get methods remain; canonical VenueOrder fields require exact base quantity and executed/remaining consistency. Production supported order policy is explicit LIMIT plus externally verified TIF; no fallback to venue defaults.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Parser refactor only where tests demonstrate remaining defect; retain known-good fixtures and no blind submit retry.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

TradingVenue existing submit/cancel/get methods remain; canonical VenueOrder fields require exact base quantity and executed/remaining consistency. Production supported order policy is explicit LIMIT plus externally verified TIF; no fallback to venue defaults.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Build sanitized venue-shaped offline fixtures for quote/base quantity representations.

- [ ] Step 2: Validate parser object types and normalized totals through router.

- [ ] Step 3: Keep cancel UNKNOWN until conclusive order/fill evidence.

- [ ] Step 4: Reject unsupported semantics before transport.

- [ ] Step 5: Record externally unverified behavior as activation blocker, not fixture-proven venue fact.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/unit/lab/execution/test_venue_semantics_contract.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/unit/lab/execution/test_venue_semantics_contract.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| PM-04-AC0 | `test_pm_04_0` | Original equals executed plus remaining in declared units |

| PM-04-AC1 | `test_pm_04_1` | Cancel acknowledgement plus inconclusive lookup stays UNKNOWN |

| PM-04-AC2 | `test_pm_04_2` | Fill/cancel race never invents zero fill |

| PM-04-AC3 | `test_pm_04_3` | Unsupported order/TIF produces no HTTP call |

Focused command: `python -m pytest tests/unit/lab/execution/test_venue_semantics_contract.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Cancel acknowledgement plus inconclusive lookup stays UNKNOWN. Rejection preserves prior committed evidence and emits a specific reason.

- Fill/cancel race never invents zero fill. Rejection preserves prior committed evidence and emits a specific reason.

- Unsupported order/TIF produces no HTTP call. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. PM-04 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Parser refactor only where tests demonstrate remaining defect; retain known-good fixtures and no blind submit retry.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **PM-04-AC0** Original equals executed plus remaining in declared units. Evidence: named test on exact committed SHA.

- [ ] **PM-04-AC1** Cancel acknowledgement plus inconclusive lookup stays UNKNOWN. Evidence: named test on exact committed SHA.

- [ ] **PM-04-AC2** Fill/cancel race never invents zero fill. Evidence: named test on exact committed SHA.

- [ ] **PM-04-AC3** Unsupported order/TIF produces no HTTP call. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/pm-04-venue-parser-cancellation-and-supported-order-semantics` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(pm-04): venue parser cancellation and supported order semantics`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-04-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

PM-04

### OBJECTIVE

Verify actual internal type mapping, supported LIMIT/TIF and race/partial-fill behavior.

### ARCHITECTURAL CONTEXT

Read/write parser reuse and inconclusive-cancel exception already present. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/execution/indodax_readonly.py`, `src/indodax_lab/execution/indodax_trading.py`, `src/indodax_lab/execution/order_router.py`, `tests/unit/lab/execution/test_venue_semantics_contract.py`

### TESTS

`python -m pytest tests/unit/lab/execution/test_venue_semantics_contract.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `PM-04-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
