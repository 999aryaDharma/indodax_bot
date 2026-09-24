# API-04 — Guarded Production portfolio and lifecycle commands

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: production-main | Requirements: FR-23

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Planning only; claim only when manifest READY. No runtime acceptance yet.

## Goal

Guarded Production portfolio and lifecycle commands.

## Why This Sprint Exists

API-00 through API-03 are DONE read/control-plane foundations. Named command admission is new under ADR-010; reuse current auth and audit infrastructure without broadening read capabilities.

## Depends On

- PM-09 — Candidate exits and draining strategy replacement
- API-02 — Read-only Production API application and routes
- API-03 — Fail-closed read capability policy and audit context
- API-07 — Tailscale-authenticated Production read composition

## Unlocks

PM-06, UI-03

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/production/research-workbench/README.md`
- `docs/decisions/ADR-010-multi-strategy-production-and-guarded-controls.md`
- `docs/implementation/BOT-TRADE-PROGRAM.md`
- `docs/implementation/CONTRACTS.md`
- `docs/specs/20-testing-strategy.md`

- `docs/implementation/PRODUCTION-RISK-POLICY-V1.md`

## Current Context

API-00 through API-03 are DONE read/control-plane foundations. Named command admission is new under ADR-010; reuse current auth and audit infrastructure without broadening read capabilities.

## In Scope

Implement only the command routes and CommandReceipt contract named in BOT-TRADE-PROGRAM. Thin routes call adoption/allocation/lifecycle/control authorities; require production.control, request ID, reason, expected revision and exact proposal binding. Existing read APIs retain read-only behavior. Reuse the same proposal/decision flow for program dashboard defaults and validated drafts; candidate parameter edits use existing candidate/release authority. Expose adjusted peak, absolute drawdown allowance, floor and remaining distance through existing reviewed settings/results; server operating costs are excluded from the trading-return target. Use explicit new-risk-period purpose in existing proposal/decision flow; separate approval from resume and require incident review plus qualified release evidence.

- Research actor and read-only viewer cannot invoke Production commands.
- Stale revision or changed proposal rejects approval and requires a new proposal.
- Duplicate identical request returns same receipt and conflicting payload rejects.
- Command audit failure cannot acknowledge successful mutation.
- Resume revalidates recovery risk release and reconciliation gates.
- No route exposes order withdrawal or model reload authority.

- Existing proposal and decision flow exposes defaults drafts active revisions validation and impact; unset mandatory risk settings prevent activation without mutating active state.

- Agent parameter changes require new candidate evaluation and release; risk widening requires shared-capital evidence and no command hot-edits existing position exits.

- New-period approval is distinct from resume and binds exact state incident review release and risk policy; stale state rejects and identical retries create at most one period.

## Out of Scope

Live account access, credentials, orders, deployment, automatic promotion, unrelated refactors and changes to DONE evidence. Implement only the named service boundaries; DATA-07 does not own UI/API routers.

## User / Actor Behavior

The operator supplies versioned inputs through the named interface and receives durable evidence or an explicit blocked/rejected reason. Failed and superseded evidence remains inspectable.

## Functional Requirements

- **API-04-AC0** Research actor and read-only viewer cannot invoke Production commands.
- **API-04-AC1** Stale revision or changed proposal rejects approval and requires a new proposal.
- **API-04-AC2** Duplicate identical request returns same receipt and conflicting payload rejects.
- **API-04-AC3** Command audit failure cannot acknowledge successful mutation.
- **API-04-AC4** Resume revalidates recovery risk release and reconciliation gates.
- **API-04-AC5** No route exposes order withdrawal or model reload authority.

- **API-04-AC6** Existing proposal and decision flow exposes defaults drafts active revisions validation and impact; unset mandatory risk settings prevent activation without mutating active state.

- **API-04-AC7** Agent parameter changes require new candidate evaluation and release; risk widening requires shared-capital evidence and no command hot-edits existing position exits.

- **API-04-AC8** New-period approval is distinct from resume and binds exact state incident review release and risk policy; stale state rejects and identical retries create at most one period.

## Domain Rules / Invariants

BOT-TRADE-PROGRAM is normative for this task. Preserve Decimal accounting, UTC availability, immutable identity, no future information, exactly-once effects and separation of Research from Production authority.

## Architecture / Design Contract

Implement only the command routes and CommandReceipt contract named in BOT-TRADE-PROGRAM. Thin routes call adoption/allocation/lifecycle/control authorities; require production.control, request ID, reason, expected revision and exact proposal binding. Existing read APIs retain read-only behavior. Reuse the same proposal/decision flow for program dashboard defaults and validated drafts; candidate parameter edits use existing candidate/release authority. Expose adjusted peak, absolute drawdown allowance, floor and remaining distance through existing reviewed settings/results; server operating costs are excluded from the trading-return target. Use explicit new-risk-period purpose in existing proposal/decision flow; separate approval from resume and require incident review plus qualified release evidence.

## Planned Files / Artifacts

- `src/indodax_lab/api/routers/production_commands.py`
- `src/indodax_lab/api/contracts/production.py`
- `src/indodax_lab/api/dependencies.py`
- `src/indodax_lab/api/app.py`
- `src/indodax_lab/api/capabilities.py`
- `tests/integration/lab/api/test_production_commands.py`

Paths are owned implementation targets, not claims that new files already exist. Reuse the current equivalent and record actual paths in handoff.

## Interfaces & Contracts

Implement only the command routes and CommandReceipt contract named in BOT-TRADE-PROGRAM. Thin routes call adoption/allocation/lifecycle/control authorities; require production.control, request ID, reason, expected revision and exact proposal binding. Existing read APIs retain read-only behavior. Reuse the same proposal/decision flow for program dashboard defaults and validated drafts; candidate parameter edits use existing candidate/release authority. Expose adjusted peak, absolute drawdown allowance, floor and remaining distance through existing reviewed settings/results; server operating costs are excluded from the trading-return target. Use explicit new-risk-period purpose in existing proposal/decision flow; separate approval from resume and require incident review plus qualified release evidence.

Reuse ServiceError, ArtifactRef, existing API envelope and revision contracts. Unavailable values carry null plus reason; money is Decimal text on wire.

## Data / Persistence Impact

Commands are capability-gated and disabled in default development wiring; fake authorities only in tests. Old GET clients are unchanged. Receipts distinguish accepted proposal, applied state and blocked activation.

## API / External Contract Impact

Only the owning API task exposes routes. Local services use the program interfaces; unsupported input rejects explicitly. Existing historical artifact readers remain compatible; new version eligibility is explicit.

## UI / UX Behavior

Expose source revision, provenance, lifecycle, unavailable values and failure reasons. Never label a proposal as activated. DATA-07 service results are consumed by RW7/RW8; PM services are consumed by API-04/UI-03.

## Implementation Steps

1. Read dependency handoffs and trace existing callers/stores for the owned boundary.
2. Add the acceptance and negative tests below; demonstrate behavioral RED where practical.
3. Implement the smallest change using existing contracts/stores, with explicit schema compatibility.
4. Run focused checks and affected contract suites; record actual results.
5. Commit explicit owned paths and submit the exact SHA for independent review.

## Required Tests

Run `python -m pytest tests/integration/lab/api/test_production_commands.py -q` after implementation. Use fake transport and temporary state. Full suite is required when changing shared contracts/schemas.

- `test_api_04_0`: Research actor and read-only viewer cannot invoke Production commands.
- `test_api_04_1`: Stale revision or changed proposal rejects approval and requires a new proposal.
- `test_api_04_2`: Duplicate identical request returns same receipt and conflicting payload rejects.
- `test_api_04_3`: Command audit failure cannot acknowledge successful mutation.
- `test_api_04_4`: Resume revalidates recovery risk release and reconciliation gates.
- `test_api_04_5`: No route exposes order withdrawal or model reload authority.

- `test_api_04_6`: Existing proposal and decision flow exposes defaults drafts active revisions validation and impact; unset mandatory risk settings prevent activation without mutating active state.

- `test_api_04_7`: Agent parameter changes require new candidate evaluation and release; risk widening requires shared-capital evidence and no command hot-edits existing position exits.

- `test_api_04_8`: New-period approval is distinct from resume and binds exact state incident review release and risk policy; stale state rejects and identical retries create at most one period.

## Failure / Edge Cases

Exercise all acceptance negatives plus malformed/non-finite input, missing identity, stale revision, duplicate request, interrupted commit and recovery where applicable. Unknown never means zero or success.

## Security / Privacy / Safety

No arbitrary YAML code/import/pickle, path escape, secrets in logs or live DB test writes. Command access remains separate from read access. Research cannot resolve Production writer capability.

## Concurrency / Idempotency

Use single financial writer, revision checks and existing transaction boundary. Identical request ID and payload have one effect; conflicting payload rejects. No acknowledgement before durable commit.

## Performance Constraints

Bound requests, queue sizes and result pagination using existing policy owners; do not add a scheduler or presume ASUS capacity. Record workload dimensions for later OPS-01/QA-03 qualification.

## Observability

Correlate request, candidate, policy, strategy, pair and revision IDs; include reason codes and provenance. Do not log private account payloads.

## Migration / Backward Compatibility

Commands are capability-gated and disabled in default development wiring; fake authorities only in tests. Old GET clients are unchanged. Receipts distinguish accepted proposal, applied state and blocked activation.

## Rollback / Recovery

Revert only compatible code/configuration before activation. Preserve journal and immutable evidence; never erase committed fills, restore stale balances or re-enable entry by rollback. Reconciliation governs recovery.

## Acceptance Criteria

- [ ] **API-04-AC0** Research actor and read-only viewer cannot invoke Production commands. Evidence: `test_api_04_0` at exact committed SHA.
- [ ] **API-04-AC1** Stale revision or changed proposal rejects approval and requires a new proposal. Evidence: `test_api_04_1` at exact committed SHA.
- [ ] **API-04-AC2** Duplicate identical request returns same receipt and conflicting payload rejects. Evidence: `test_api_04_2` at exact committed SHA.
- [ ] **API-04-AC3** Command audit failure cannot acknowledge successful mutation. Evidence: `test_api_04_3` at exact committed SHA.
- [ ] **API-04-AC4** Resume revalidates recovery risk release and reconciliation gates. Evidence: `test_api_04_4` at exact committed SHA.
- [ ] **API-04-AC5** No route exposes order withdrawal or model reload authority. Evidence: `test_api_04_5` at exact committed SHA.

- [ ] **API-04-AC6** Existing proposal and decision flow exposes defaults drafts active revisions validation and impact; unset mandatory risk settings prevent activation without mutating active state. Evidence: `test_api_04_6` at exact committed SHA.

- [ ] **API-04-AC7** Agent parameter changes require new candidate evaluation and release; risk widening requires shared-capital evidence and no command hot-edits existing position exits. Evidence: `test_api_04_7` at exact committed SHA.

- [ ] **API-04-AC8** New-period approval is distinct from resume and binds exact state incident review release and risk policy; stale state rejects and identical retries create at most one period. Evidence: `test_api_04_8` at exact SHA; pending.

## Definition of Done

All task acceptance and affected checks pass, exact-SHA handoff exists, independent reviewer PASS, zero Critical/Important findings. Manifest coordinator alone marks DONE. Activation gates remain separate.

## Reviewer Checklist

Check every AC, actual caller integration, state ownership, failure/recovery and compatibility. Verify no secret/live effects. Preserve review-round count and report exact SHA.

## Commit Guidance

Work in current checkout unless isolation is needed. Stage explicit owned paths. Commit coherent passing slices using `feat(api-04): ...`; no merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/API-04-HANDOFF.md` with source/implementation SHA, actual paths, environment, commands/results, migration, review state and external gates.

## Ready-to-Run Implementation Prompt

Implement API-04 only when manifest READY and dependencies DONE. Read Required Reading and dependency handoffs; follow the interfaces, tests and owned scope above. Preserve user work and live system boundaries. Return a committed implementation plus handoff at REVIEW, not self-approved DONE.
