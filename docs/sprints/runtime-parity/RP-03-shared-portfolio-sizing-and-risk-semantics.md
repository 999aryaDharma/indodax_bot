# RP-03 — Shared portfolio sizing and risk semantics Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Deterministic allocation preserving lineage, costs, exits and order semantics.

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

Priority: P0 | Type: integration | Domain: runtime-parity | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/rp-03-shared-portfolio-sizing-and-risk-semantics`

Requirements: FR-20 | Legacy tasks: none

Risk level: high | Complexity: L

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Deterministic allocation preserving lineage, costs, exits and order semantics.

## Why This Sprint Exists

Purpose: Shared portfolio sizing and risk semantics. Gap: Deterministic allocation preserving lineage, costs, exits and order semantics.

## Depends On

- RW0-01 — Immutable Workbench domain manifests
- SIM-02 — Portfolio risk and circuit breakers

## Unlocks

RP-04, RW6-01, PM-08

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

PortfolioConstructor drops intent metadata and overwrites same-pair intents; risk caller semantics differ.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

Owner-approved 2026-09-24 amendment: implement this sprint's behavior in `docs/implementation/BOT-TRADE-PROGRAM.md`; prior requirements remain mandatory.

- Characterize existing risk quantities/cost rounding

- Carry source IDs and role/TIF/stop/TP through portfolio transforms

- Reject same-pair conflict unless explicit shared allocation policy supplies deterministic arbitration

- Centralize fee-aware sizing/reservations and risk observation

- Version changed semantics and adapt existing step caller

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RP-03-FR0:** Two same-pair opposing intents never silently last-win.

1. **RP-03-FR1:** Limit/TIF/role/exit lineage survives construction.

2. **RP-03-FR2:** Same state/intent/cost yields exact same approved quantity in each runtime.

3. **RP-03-FR3:** Pending exposure and fees cannot be spent twice.

## Domain Rules / Invariants

PortfolioConstructor.construct_orders(intents,state,allocation_policy)->tuple[SignalIntent,...]; RiskEngine.assess_intent retains existing result type with explicit cost/precision parameters. PortfolioState supplies Decimal cash, positions, marks, reservations and revision.

For guarded proposal execution, the authoritative `ExecutionSnapshot` records pending
cash reservations by OMS order ID. The authority gate may release only the exact
approved order's reserve for its recheck; other reservations remain deducted. A
missing or mismatched reservation remains fail-closed.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. PortfolioConstructor.construct_orders(intents,state,allocation_policy)->tuple[SignalIntent,...]; RiskEngine.assess_intent retains existing result type with explicit cost/precision parameters. PortfolioState supplies Decimal cash, positions, marks, reservations and revision.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/portfolio/constructor.py`

- `src/indodax_lab/risk/engine.py`

- `src/indodax_lab/backtest/risk.py`

Create:

- `tests/unit/lab/portfolio/test_intent_semantics.py`

- `tests/unit/lab/risk/test_risk_parity.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

PortfolioConstructor.construct_orders(intents,state,allocation_policy)->tuple[SignalIntent,...]; RiskEngine.assess_intent retains existing result type with explicit cost/precision parameters. PortfolioState supplies Decimal cash, positions, marks, reservations and revision.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Keep old generate_rebalance_intents wrapper for historical callers; qualification uses versioned new interface. Never alter historical result PnL.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

PortfolioConstructor.construct_orders(intents,state,allocation_policy)->tuple[SignalIntent,...]; RiskEngine.assess_intent retains existing result type with explicit cost/precision parameters. PortfolioState supplies Decimal cash, positions, marks, reservations and revision.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Characterize existing risk quantities/cost rounding.

- [ ] Step 2: Carry source IDs and role/TIF/stop/TP through portfolio transforms.

- [ ] Step 3: Reject same-pair conflict unless explicit shared allocation policy supplies deterministic arbitration.

- [ ] Step 4: Centralize fee-aware sizing/reservations and risk observation.

- [ ] Step 5: Version changed semantics and adapt existing step caller.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/unit/lab/portfolio/test_intent_semantics.py tests/unit/lab/risk/test_risk_parity.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/unit/lab/portfolio/test_intent_semantics.py`, `tests/unit/lab/risk/test_risk_parity.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RP-03-AC0 | `test_rp_03_0` | Two same-pair opposing intents never silently last-win |

| RP-03-AC1 | `test_rp_03_1` | Limit/TIF/role/exit lineage survives construction |

| RP-03-AC2 | `test_rp_03_2` | Same state/intent/cost yields exact same approved quantity in each runtime |

| RP-03-AC3 | `test_rp_03_3` | Pending exposure and fees cannot be spent twice |

Focused command: `python -m pytest tests/unit/lab/portfolio/test_intent_semantics.py tests/unit/lab/risk/test_risk_parity.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Limit/TIF/role/exit lineage survives construction. Rejection preserves prior committed evidence and emits a specific reason.

- Same state/intent/cost yields exact same approved quantity in each runtime. Rejection preserves prior committed evidence and emits a specific reason.

- Pending exposure and fees cannot be spent twice. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RP-03 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Keep old generate_rebalance_intents wrapper for historical callers; qualification uses versioned new interface. Never alter historical result PnL.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RP-03-AC4** Expose risk sizing inputs for strategy ownership stop distance and pending reservations without duplicate cash authority. Evidence: `test_rp_03_program_4` at exact implementation SHA.

- [ ] **RP-03-AC0** Two same-pair opposing intents never silently last-win. Evidence: named test on exact committed SHA.

- [ ] **RP-03-AC1** Limit/TIF/role/exit lineage survives construction. Evidence: named test on exact committed SHA.

- [ ] **RP-03-AC2** Same state/intent/cost yields exact same approved quantity in each runtime. Evidence: named test on exact committed SHA.

- [ ] **RP-03-AC3** Pending exposure and fees cannot be spent twice. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rp-03-shared-portfolio-sizing-and-risk-semantics` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rp-03): shared portfolio sizing and risk semantics`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RP-03-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RP-03

### OBJECTIVE

Deterministic allocation preserving lineage, costs, exits and order semantics.

### ARCHITECTURAL CONTEXT

PortfolioConstructor drops intent metadata and overwrites same-pair intents; risk caller semantics differ. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/portfolio/constructor.py`, `src/indodax_lab/risk/engine.py`, `src/indodax_lab/backtest/risk.py`, `tests/unit/lab/portfolio/test_intent_semantics.py`, `tests/unit/lab/risk/test_risk_parity.py`

### TESTS

`python -m pytest tests/unit/lab/portfolio/test_intent_semantics.py tests/unit/lab/risk/test_risk_parity.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RP-03-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
