# PM-07 — Reviewed account portfolio adoption

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: production-main | Requirements: FR-23

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Planning only; claim only when manifest READY. No runtime acceptance yet.

## Goal

Reviewed account portfolio adoption.

## Why This Sprint Exists

Production already owns venue account truth and durable financial state; this task adds reviewed strategy ownership, not a second ledger.

## Depends On

- PM-02 — Atomic financial execution state and recovery
- PM-03 — Recovery mode and durable operator risk governance
- PM-04 — Venue parser cancellation and supported order semantics
- PM-05 — Candidate-bound release provenance

## Unlocks

PM-08

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/production/research-workbench/README.md`
- `docs/decisions/ADR-010-multi-strategy-production-and-guarded-controls.md`
- `docs/implementation/BOT-TRADE-PROGRAM.md`
- `docs/implementation/CONTRACTS.md`
- `docs/specs/20-testing-strategy.md`

## Current Context

Production already owns venue account truth and durable financial state; this task adds reviewed strategy ownership, not a second ledger.

## In Scope

propose_adoption(snapshot_ref, assignments) and approve_adoption(proposal_id, expected_revision, actor, reason, request_id) return a durable AdoptionRecord with release/owner refs, quantity, cost-basis validity and reconciliation evidence. Reuse financial transaction/revision ownership from PM-02.

- Stale snapshot or unresolved existing order prevents adoption.
- Unknown cost basis stays unknown while post-adoption baseline is separately attributed.
- Unadopted assets affect exposure but cannot be sold by a strategy.
- Unexplained external account change blocks new entry until reviewed reconciliation.
- Duplicate adoption and restart have one position ownership effect.
- Verified deposits do not appear as trading profit.

## Out of Scope

Live account access, credentials, orders, deployment, automatic promotion, unrelated refactors and changes to DONE evidence. Implement only the named service boundaries; DATA-07 does not own UI/API routers.

## User / Actor Behavior

The operator supplies versioned inputs through the named interface and receives durable evidence or an explicit blocked/rejected reason. Failed and superseded evidence remains inspectable.

## Functional Requirements

- **PM-07-AC0** Stale snapshot or unresolved existing order prevents adoption.
- **PM-07-AC1** Unknown cost basis stays unknown while post-adoption baseline is separately attributed.
- **PM-07-AC2** Unadopted assets affect exposure but cannot be sold by a strategy.
- **PM-07-AC3** Unexplained external account change blocks new entry until reviewed reconciliation.
- **PM-07-AC4** Duplicate adoption and restart have one position ownership effect.
- **PM-07-AC5** Verified deposits do not appear as trading profit.

## Domain Rules / Invariants

BOT-TRADE-PROGRAM is normative for this task. Preserve Decimal accounting, UTC availability, immutable identity, no future information, exactly-once effects and separation of Research from Production authority.

## Architecture / Design Contract

propose_adoption(snapshot_ref, assignments) and approve_adoption(proposal_id, expected_revision, actor, reason, request_id) return a durable AdoptionRecord with release/owner refs, quantity, cost-basis validity and reconciliation evidence. Reuse financial transaction/revision ownership from PM-02.

## Planned Files / Artifacts

- `src/indodax_lab/portfolio/adoption.py`
- `src/indodax_lab/execution/reconciliation.py`
- `src/indodax_lab/execution/ledger_store.py`
- `tests/unit/lab/portfolio/test_adoption.py`

Paths are owned implementation targets, not claims that new files already exist. Reuse the current equivalent and record actual paths in handoff.

## Interfaces & Contracts

propose_adoption(snapshot_ref, assignments) and approve_adoption(proposal_id, expected_revision, actor, reason, request_id) return a durable AdoptionRecord with release/owner refs, quantity, cost-basis validity and reconciliation evidence. Reuse financial transaction/revision ownership from PM-02.

Reuse ServiceError, ArtifactRef, existing API envelope and revision contracts. Unavailable values carry null plus reason; money is Decimal text on wire.

## Data / Persistence Impact

Inventory from read-only evidence, propose exact assignments, then apply only through guarded reviewed commands. Preserve unknown basis and existing journal IDs. Tests use fake account snapshots, never live account reads.

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

Run `python -m pytest tests/unit/lab/portfolio/test_adoption.py -q` after implementation. Use fake transport and temporary state. Full suite is required when changing shared contracts/schemas.

- `test_pm_07_0`: Stale snapshot or unresolved existing order prevents adoption.
- `test_pm_07_1`: Unknown cost basis stays unknown while post-adoption baseline is separately attributed.
- `test_pm_07_2`: Unadopted assets affect exposure but cannot be sold by a strategy.
- `test_pm_07_3`: Unexplained external account change blocks new entry until reviewed reconciliation.
- `test_pm_07_4`: Duplicate adoption and restart have one position ownership effect.
- `test_pm_07_5`: Verified deposits do not appear as trading profit.

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

Inventory from read-only evidence, propose exact assignments, then apply only through guarded reviewed commands. Preserve unknown basis and existing journal IDs. Tests use fake account snapshots, never live account reads.

## Rollback / Recovery

Revert only compatible code/configuration before activation. Preserve journal and immutable evidence; never erase committed fills, restore stale balances or re-enable entry by rollback. Reconciliation governs recovery.

## Acceptance Criteria

- [ ] **PM-07-AC0** Stale snapshot or unresolved existing order prevents adoption. Evidence: `test_pm_07_0` at exact committed SHA.
- [ ] **PM-07-AC1** Unknown cost basis stays unknown while post-adoption baseline is separately attributed. Evidence: `test_pm_07_1` at exact committed SHA.
- [ ] **PM-07-AC2** Unadopted assets affect exposure but cannot be sold by a strategy. Evidence: `test_pm_07_2` at exact committed SHA.
- [ ] **PM-07-AC3** Unexplained external account change blocks new entry until reviewed reconciliation. Evidence: `test_pm_07_3` at exact committed SHA.
- [ ] **PM-07-AC4** Duplicate adoption and restart have one position ownership effect. Evidence: `test_pm_07_4` at exact committed SHA.
- [ ] **PM-07-AC5** Verified deposits do not appear as trading profit. Evidence: `test_pm_07_5` at exact committed SHA.

## Definition of Done

All task acceptance and affected checks pass, exact-SHA handoff exists, independent reviewer PASS, zero Critical/Important findings. Manifest coordinator alone marks DONE. Activation gates remain separate.

## Reviewer Checklist

Check every AC, actual caller integration, state ownership, failure/recovery and compatibility. Verify no secret/live effects. Preserve review-round count and report exact SHA.

## Commit Guidance

Work in current checkout unless isolation is needed. Stage explicit owned paths. Commit coherent passing slices using `feat(pm-07): ...`; no merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-07-HANDOFF.md` with source/implementation SHA, actual paths, environment, commands/results, migration, review state and external gates.

## Ready-to-Run Implementation Prompt

Implement PM-07 only when manifest READY and dependencies DONE. Read Required Reading and dependency handoffs; follow the interfaces, tests and owned scope above. Preserve user work and live system boundaries. Return a committed implementation plus handoff at REVIEW, not self-approved DONE.
