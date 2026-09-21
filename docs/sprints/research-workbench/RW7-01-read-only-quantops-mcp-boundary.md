# RW7-01 — Read-only QuantOps MCP boundary Implementation Plan

> **For agentic workers:** LUNA uses superpowers:executing-plans task-by-task; independent reviewer is required.

**Goal:** Allowlisted read-only discovery over existing typed service contracts.

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

Recommended Branch: `feat/rw7-01-read-only-quantops-mcp-boundary`

Requirements: FR-19 | Legacy tasks: none

Risk level: high | Complexity: M

Classification: PLANNED implementation; current-state statements are audit facts. External gates are separate from READY.

## Goal

Allowlisted read-only discovery over existing typed service contracts.

## Why This Sprint Exists

Purpose: Read-only QuantOps MCP boundary. Gap: Allowlisted read-only discovery over existing typed service contracts.

## Depends On

- RW1-01 — Reusable immutable dataset registry
- RW2-03 — Typed declarative pipeline composer
- RW4-01 — Immutable candidate packaging and lifecycle

## Unlocks

RW7-02

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

No tracked QuantOps server found; services are planned.

Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Inspect exact dependency handoffs before claim; REVIEW is not DONE.

## In Scope

- Declare explicit tool allowlist and typed request schemas

- Resolve public research service capabilities only

- Reject unknown tools and arbitrary paths/SQL/code

- Emit redacted request/outcome audit

- Test forbidden production names and transitive dependency boundary

## Out of Scope

Other task implementations; live orders/credentials; runtime DB tests; changing frozen gates; retroactive qualification of old evidence. LUNA must stop if an interface requires an unrecorded architectural redesign.

## User / Actor Behavior

Research/operator consumer invokes the declared interface on verified inputs. It receives the typed result or a specific rejection/blocked outcome. No implicit promotion or invented evidence.

## Functional Requirements

0. **RW7-01-FR0:** Read tool returns registry truth without mutation.

1. **RW7-01-FR1:** Unknown submit_real_order/withdraw/direct_promote_live rejects.

2. **RW7-01-FR2:** Traversal or embedded executable payload treated as data and rejected by schema.

3. **RW7-01-FR3:** Missing service gives unavailable error, never synthetic success.

## Domain Rules / Invariants

Tools list_pairs/find_dataset/list_datasets/get_dataset/list_strategies/get_strategy/list_models/get_model/get_pipeline/get_backtest_status/get_backtest_result/compare_experiments map to service methods. Responses contain schema_version, request_id, data or error(code,message).

Decimal accounting, UTC availability, immutable identities, exactly-once effects and separate execution authority follow CONTRACTS.md/ADR-002. Simulator assumptions cannot redefine accounting.

## Architecture / Design Contract

Reuse existing primitives named under Current Context. New files own only the declared service/contract. Tools list_pairs/find_dataset/list_datasets/get_dataset/list_strategies/get_strategy/list_models/get_model/get_pipeline/get_backtest_status/get_backtest_result/compare_experiments map to service methods. Responses contain schema_version, request_id, data or error(code,message).

## Planned Files / Artifacts

Modify:

None.

Create:

- `src/indodax_lab/mcp/server.py`

- `src/indodax_lab/mcp/read_tools.py`

- `tests/security/test_quantops_boundary.py`

Actual import-only consumer changes for RP-01 are enumerated in its focused handoff; no arbitrary adjacent refactor.

## Interfaces & Contracts

Consumes: verified dependency artifacts/contracts and policy versions described above.

Produces:

```text

Tools list_pairs/find_dataset/list_datasets/get_dataset/list_strategies/get_strategy/list_models/get_model/get_pipeline/get_backtest_status/get_backtest_result/compare_experiments map to service methods. Responses contain schema_version, request_id, data or error(code,message).

```

Field definitions, error semantics and lifecycle transitions are normative in docs/implementation/CONTRACTS.md. Existing API changes require compatibility adapter described below.

## Data / Persistence Impact

MCP package/runtime dependency pinned during implementation via reviewed dependency change; no production credentials or transport adapter.

Schema: use the named manifest/state/result model; append-only identity and lifecycle rules in CONTRACTS.md. Read-only tasks create no product persistence. Stateful tasks use a temp namespace in tests.

## API / External Contract Impact

Tools list_pairs/find_dataset/list_datasets/get_dataset/list_strategies/get_strategy/list_models/get_model/get_pipeline/get_backtest_status/get_backtest_result/compare_experiments map to service methods. Responses contain schema_version, request_id, data or error(code,message).

No new production write authority. Provider facts are not asserted by offline fixtures.

## UI / UX Behavior

No graphical UI work in this task; expose structured results/reason codes to later adapters.

## Implementation Steps

- [ ] Step 1: Declare explicit tool allowlist and typed request schemas.

- [ ] Step 2: Resolve public research service capabilities only.

- [ ] Step 3: Reject unknown tools and arbitrary paths/SQL/code.

- [ ] Step 4: Emit redacted request/outcome audit.

- [ ] Step 5: Test forbidden production names and transitive dependency boundary.

- [ ] For every acceptance row below, first write its named behavioral assertion using fake clocks/transports and temporary storage; observe wrong-behavior RED, implement its owner code, then GREEN. Missing dependency/import alone is not RED.

- [ ] Run `python -m pytest tests/security/test_quantops_boundary.py -q`; expected all named behaviors pass. Shared contract/accounting/recovery changes additionally run `python -m pytest -q` with required dependencies; required skips block acceptance.

- [ ] Run `git diff --check`, record exact environment/command/exit/SHA, commit scoped files, and submit independent review.

## Required Tests

Planned test paths: `tests/security/test_quantops_boundary.py`.

| Acceptance | Planned test identity | Required assertion |

|---|---|---|

| RW7-01-AC0 | `test_rw7_01_0` | Read tool returns registry truth without mutation |

| RW7-01-AC1 | `test_rw7_01_1` | Unknown submit_real_order/withdraw/direct_promote_live rejects |

| RW7-01-AC2 | `test_rw7_01_2` | Traversal or embedded executable payload treated as data and rejected by schema |

| RW7-01-AC3 | `test_rw7_01_3` | Missing service gives unavailable error, never synthetic success |

Focused command: `python -m pytest tests/security/test_quantops_boundary.py -q`. Tests must exercise the public service boundary, not only fabricated ID equality. No real network/Telegram/DB.

## Failure / Edge Cases

- Unknown submit_real_order/withdraw/direct_promote_live rejects. Rejection preserves prior committed evidence and emits a specific reason.

- Traversal or embedded executable payload treated as data and rejected by schema. Rejection preserves prior committed evidence and emits a specific reason.

- Missing service gives unavailable error, never synthetic success. Rejection preserves prior committed evidence and emits a specific reason.

Interrupted publication remains incomplete; stale worker/version cannot finalize it. Pure contract tasks reject invalid values before producing output.

## Security / Privacy / Safety

No trade/withdraw credentials, arbitrary pickle/callable imports, secret logging, production DB mutation or gate bypass. Live venue class is unavailable from research runtime/control-plane wiring. All filesystem artifact resolution stays inside configured roots.

## Concurrency / Idempotency

Published identity is no-clobber; duplicate identical request/event has no additional semantic effect; conflicting bytes under same identity reject. Stateful stores enforce revision/lease fencing and one authoritative writer. Pure transforms have no ambient mutable state.

## Performance Constraints

Bound batches/queues and report workload dimensions; no invented host throughput or GPU capacity. Existing ADR-003 research budgets remain. Optional ML/DL environments load only for declared nodes; no collector heavy-import dependency.

## Observability

Emit task/service reason codes with candidate/artifact/event/request IDs, namespace and policy/schema versions. RW7-01 acceptance evidence records exact code SHA and command exit. Log durations outside semantic hashes; never private payloads.

## Migration / Backward Compatibility

MCP package/runtime dependency pinned during implementation via reviewed dependency change; no production credentials or transport adapter.

## Rollback / Recovery

Select prior compatible code/artifact before activation; preserve failed/new evidence. Never overwrite immutable versions or erase committed financial history. For stateful migration use read-only source plus separately validated new namespace; reject ambiguity.

## Acceptance Criteria

- [ ] **RW7-01-AC0** Read tool returns registry truth without mutation. Evidence: named test on exact committed SHA.

- [ ] **RW7-01-AC1** Unknown submit_real_order/withdraw/direct_promote_live rejects. Evidence: named test on exact committed SHA.

- [ ] **RW7-01-AC2** Traversal or embedded executable payload treated as data and rejected by schema. Evidence: named test on exact committed SHA.

- [ ] **RW7-01-AC3** Missing service gives unavailable error, never synthetic success. Evidence: named test on exact committed SHA.

## Definition of Done

All acceptance tests and affected/full-suite gates pass without hidden required skips; exact SHA handoff; migration/rollback proven; self-review plus independent spec/quality PASS; no Critical/Important findings. Coordinator alone updates DONE and projections. External activation remains separately gated.

## Reviewer Checklist

Independently run required acceptance/negative cases; verify units/availability/identity; attempt crash/duplicate/stale-state boundaries where applicable; inspect actual caller wiring; confirm no adjacent scope/gate weakening; report Critical/Important/Minor and exact SHA. Maximum five rounds, preserved across reviewers.

## Commit Guidance

Use `feat/rw7-01-read-only-quantops-mcp-boundary` in an isolated worktree. Stage only listed/recorded scoped files; no broad staging. Commit message: `feat(rw7-01): read-only quantops mcp boundary`. No merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/RW7-01-HANDOFF.md`: owner/reviewer, base/code/evidence SHAs, actual paths, acceptance command/results, migration, deviations and pending external gates. Preserve review rounds. Completion does not follow automatically from a passing local unit test.

## Ready-to-Run Implementation Prompt

### TASK ID

RW7-01

### OBJECTIVE

Allowlisted read-only discovery over existing typed service contracts.

### ARCHITECTURAL CONTEXT

No tracked QuantOps server found; services are planned. Shared-runtime/frozen authority contracts apply.

### ALLOWED SCOPE

Only In Scope and declared files; exact interfaces above.

### DO NOT TOUCH

Other tasks, main, credentials, real DBs, historical evidence, frozen gates.

### PRECONDITIONS

Manifest READY, all dependencies DONE, one owner/worktree and independent reviewer, external gates checked.

### IMPLEMENTATION STEPS

Execute checkbox steps above in order with behavioral RED/GREEN and compatibility verification.

### FILES

`src/indodax_lab/mcp/server.py`, `src/indodax_lab/mcp/read_tools.py`, `tests/security/test_quantops_boundary.py`

### TESTS

`python -m pytest tests/security/test_quantops_boundary.py -q` and full-suite gate when required. Every AC above is mandatory.

### ACCEPTANCE CHECKS

All AC rows, no forbidden side effects, exact interface/schema and dependency consumption.

### EXPECTED OUTPUT

Scoped committed implementation and `RW7-01-HANDOFF.md`, submitted at REVIEW, not self-approved DONE.

### STOP CONDITIONS

Dependency not DONE; missing review owner; identity/schema conflict; real credential requirement; required environment unavailable; failed migration or need to widen scope. Preserve evidence and mark blocker, never redesign silently.
