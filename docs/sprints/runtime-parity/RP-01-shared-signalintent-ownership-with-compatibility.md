# RP-01 — Shared SignalIntent ownership with compatibility Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Neutral ownership needed before widening parity; preserve exact class behavior.

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

Status: BLOCKED

Priority: P0 | Type: integration | Domain: runtime-parity | Portfolio: CORE

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Recommended Branch: `feat/rp-01-shared-signalintent-ownership-with-compatibility`

Requirements: FR-20 | Legacy tasks: none

Risk level: medium | Complexity: S

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Neutral ownership needed before widening parity; preserve exact class behavior.

## Why This Sprint Exists

Purpose: Shared SignalIntent ownership with compatibility. Gap: Neutral ownership needed before widening parity; preserve exact class behavior.

## Depends On

- DOC-01 — Frozen architecture audit and delivery program
- BASE-01 — Offline verification harness

## Unlocks

RW0-01

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

All three paths already import SignalIntent from backtest.events.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Add AST ownership assertion that fails on current class location without import failure

- Add golden serialization and invalid Decimal/UTC characterization

- Move class with required imports and local UTC helper, re-export old path

- Replace SignalIntent imports in canonical consumers, preserving other imports

- Run contract/architecture and full suite; submit exact SHA

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RP-01-FR0:** Only contracts/decision.py defines SignalIntent.

1. **RP-01-FR1:** Old and new import paths refer to the same class object.

2. **RP-01-FR2:** Golden BUY/SELL serialization including IOC/TAKER defaults is identical.

3. **RP-01-FR3:** Nonfinite or zero quantity and naive decision timestamp reject identically.

## Domain Rules / Invariants

SignalIntent is moved unchanged to indodax_lab.contracts.decision; backtest.events.SignalIntent is an identical class alias. Existing fields, validators, Decimal/UTC behavior and defaults are unchanged.

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. SignalIntent is moved unchanged to indodax_lab.contracts.decision; backtest.events.SignalIntent is an identical class alias. Existing fields, validators, Decimal/UTC behavior and defaults are unchanged.

## Planned Files / Artifacts

Modify:

- `src/indodax_lab/backtest/events.py`

- `src/indodax_lab/strategies/base.py`

- `src/indodax_lab/strategies/registry.py`

Create:

- `src/indodax_lab/contracts/decision.py`

- `tests/architecture/test_decision_contract_ownership.py`

- `tests/unit/lab/test_decision_contract_compatibility.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

SignalIntent is moved unchanged to indodax_lab.contracts.decision; backtest.events.SignalIntent is an identical class alias. Existing fields, validators, Decimal/UTC behavior and defaults are unchanged.

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

Legacy import remains supported; no schema/version/default change. Additional consumer edits are limited to SignalIntent import statements enumerated by rg.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

SignalIntent is moved unchanged to indodax_lab.contracts.decision; backtest.events.SignalIntent is an identical class alias. Existing fields, validators, Decimal/UTC behavior and defaults are unchanged.

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Add AST ownership assertion that fails on current class location without import failure.

- [ ] Step 2: Add golden serialization and invalid Decimal/UTC characterization.

- [ ] Step 3: Move class with required imports and local UTC helper, re-export old path.

- [ ] Step 4: Replace SignalIntent imports in canonical consumers, preserving other imports.

- [ ] Step 5: Run contract/architecture and full suite; submit exact SHA.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/architecture/test_decision_contract_ownership.py tests/unit/lab/test_decision_contract_compatibility.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/architecture/test_decision_contract_ownership.py`, `tests/unit/lab/test_decision_contract_compatibility.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RP-01-AC0 | `test_rp_01_0` | Only contracts/decision.py defines SignalIntent |

| RP-01-AC1 | `test_rp_01_1` | Old and new import paths refer to the same class object |

| RP-01-AC2 | `test_rp_01_2` | Golden BUY/SELL serialization including IOC/TAKER defaults is identical |

| RP-01-AC3 | `test_rp_01_3` | Nonfinite or zero quantity and naive decision timestamp reject identically |

Focused command: `python -m pytest tests/architecture/test_decision_contract_ownership.py tests/unit/lab/test_decision_contract_compatibility.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Old and new import paths refer to the same class object. Rejection preserves prior committed evidence and emits a specific reason.

- Golden BUY/SELL serialization including IOC/TAKER defaults is identical. Rejection preserves prior committed evidence and emits a specific reason.

- Nonfinite or zero quantity and naive decision timestamp reject identically. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RP-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

Legacy import remains supported; no schema/version/default change. Additional consumer edits are limited to SignalIntent import statements enumerated by rg.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RP-01-AC0** Only contracts/decision.py defines SignalIntent. Evidence: named test on exact committed SHA.

- [ ] **RP-01-AC1** Old and new import paths refer to the same class object. Evidence: named test on exact committed SHA.

- [ ] **RP-01-AC2** Golden BUY/SELL serialization including IOC/TAKER defaults is identical. Evidence: named test on exact committed SHA.

- [ ] **RP-01-AC3** Nonfinite or zero quantity and naive decision timestamp reject identically. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rp-01-shared-signalintent-ownership-with-compatibility` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rp-01): shared signalintent ownership with compatibility`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RP-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RP-01

### OBJECTIVE

Neutral ownership needed before widening parity; preserve exact class behavior.

### ARCHITECTURAL CONTEXT

All three paths already import SignalIntent from backtest.events. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/backtest/events.py`, `src/indodax_lab/strategies/base.py`, `src/indodax_lab/strategies/registry.py`, `src/indodax_lab/contracts/decision.py`, `tests/architecture/test_decision_contract_ownership.py`, `tests/unit/lab/test_decision_contract_compatibility.py`

### TESTS

`python -m pytest tests/architecture/test_decision_contract_ownership.py tests/unit/lab/test_decision_contract_compatibility.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RP-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
