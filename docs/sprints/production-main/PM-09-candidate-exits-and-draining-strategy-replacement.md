# PM-09 — Candidate exits and draining strategy replacement

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: production-main | Requirements: FR-23

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Planning only; claim only when manifest READY. No runtime acceptance yet.

## Goal

Candidate exits and draining strategy replacement.

## Why This Sprint Exists

Candidate exit semantics are owned by RP-02; OMS and fill recovery exist. This task integrates ownership and lifecycle without creating another exit evaluator.

## Depends On

- PM-08 — Shared capital allocation and stop risk sizing
- RP-02 — Shared candidate feature and exit evaluation
- RP-04 — Canonical feed and environment runtime adapters
- PM-04 — Venue parser cancellation and supported order semantics

## Unlocks

PM-06, API-04

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

Candidate exit semantics are owned by RP-02; OMS and fill recovery exist. This task integrates ownership and lifecycle without creating another exit evaluator.

## In Scope

request_drain(strategy_id, expected_revision, request_id) returns a durable receipt; ACTIVE/DRAINING/RETIRED ownership is persisted with exit state. Transfer ownership only after positions, nonterminal orders and reservations are zero and reconciliation is fresh. Integrate the program peak-equity-floor controlled close-out with durable cancellation, reconciliation and safe exits, separate from replacement draining and operational HALT.

- Partial entry fill receives exits only for actual filled quantity.
- Cancel uncertainty and late fills never permit blind replacement or oversell.
- Draining prevents entry but retains eligible candidate exits.
- New strategy cannot own pair until old position orders and reservations are resolved.
- Unsellable dust blocks drain completion with an explicit reason.
- Restart restores trailing state ownership and pending exits before resume.
- Unsupported stop or order semantics reject rather than substitute behavior.

- Peak-equity-floor breach persists controlled close-out across restart and rebound, cancelling entry remainders and reconciling uncertain orders and late fills before safe exits.

- Close-out coordinates pending exits and bot ownership without oversell; unsafe writes or dust remain blocked and manual resume cannot bypass the peak-equity floor.

## Out of Scope

Live account access, credentials, orders, deployment, automatic promotion, unrelated refactors and changes to DONE evidence. Implement only the named service boundaries; DATA-07 does not own UI/API routers.

## User / Actor Behavior

The operator supplies versioned inputs through the named interface and receives durable evidence or an explicit blocked/rejected reason. Failed and superseded evidence remains inspectable.

## Functional Requirements

- **PM-09-AC0** Partial entry fill receives exits only for actual filled quantity.
- **PM-09-AC1** Cancel uncertainty and late fills never permit blind replacement or oversell.
- **PM-09-AC2** Draining prevents entry but retains eligible candidate exits.
- **PM-09-AC3** New strategy cannot own pair until old position orders and reservations are resolved.
- **PM-09-AC4** Unsellable dust blocks drain completion with an explicit reason.
- **PM-09-AC5** Restart restores trailing state ownership and pending exits before resume.
- **PM-09-AC6** Unsupported stop or order semantics reject rather than substitute behavior.

- **PM-09-AC7** Peak-equity-floor breach persists controlled close-out across restart and rebound, cancelling entry remainders and reconciling uncertain orders and late fills before safe exits.

- **PM-09-AC8** Close-out coordinates pending exits and bot ownership without oversell; unsafe writes or dust remain blocked and manual resume cannot bypass the peak-equity floor.

## Domain Rules / Invariants

BOT-TRADE-PROGRAM is normative for this task. Preserve Decimal accounting, UTC availability, immutable identity, no future information, exactly-once effects and separation of Research from Production authority.

## Architecture / Design Contract

request_drain(strategy_id, expected_revision, request_id) returns a durable receipt; ACTIVE/DRAINING/RETIRED ownership is persisted with exit state. Transfer ownership only after positions, nonterminal orders and reservations are zero and reconciliation is fresh. Integrate the program peak-equity-floor controlled close-out with durable cancellation, reconciliation and safe exits, separate from replacement draining and operational HALT.

## Planned Files / Artifacts

- `src/indodax_lab/control/pipeline.py`
- `src/indodax_lab/portfolio/lifecycle.py`
- `src/indodax_lab/execution/oms_store.py`
- `tests/integration/lab/test_strategy_draining.py`

Paths are owned implementation targets, not claims that new files already exist. Reuse the current equivalent and record actual paths in handoff.

## Interfaces & Contracts

request_drain(strategy_id, expected_revision, request_id) returns a durable receipt; ACTIVE/DRAINING/RETIRED ownership is persisted with exit state. Transfer ownership only after positions, nonterminal orders and reservations are zero and reconciliation is fresh. Integrate the program peak-equity-floor controlled close-out with durable cancellation, reconciliation and safe exits, separate from replacement draining and operational HALT.

Reuse ServiceError, ArtifactRef, existing API envelope and revision contracts. Unavailable values carry null plus reason; money is Decimal text on wire.

## Data / Persistence Impact

Use a new verified lifecycle/state version. Retain old position ownership through draining. Rollback may restore compatible code but never reactivate old entry while a replacement owns the pair.

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

Run `python -m pytest tests/integration/lab/test_strategy_draining.py -q` after implementation. Use fake transport and temporary state. Full suite is required when changing shared contracts/schemas.

- `test_pm_09_0`: Partial entry fill receives exits only for actual filled quantity.
- `test_pm_09_1`: Cancel uncertainty and late fills never permit blind replacement or oversell.
- `test_pm_09_2`: Draining prevents entry but retains eligible candidate exits.
- `test_pm_09_3`: New strategy cannot own pair until old position orders and reservations are resolved.
- `test_pm_09_4`: Unsellable dust blocks drain completion with an explicit reason.
- `test_pm_09_5`: Restart restores trailing state ownership and pending exits before resume.
- `test_pm_09_6`: Unsupported stop or order semantics reject rather than substitute behavior.

- `test_pm_09_7`: Peak-equity-floor breach persists controlled close-out across restart and rebound, cancelling entry remainders and reconciling uncertain orders and late fills before safe exits.

- `test_pm_09_8`: Close-out coordinates pending exits and bot ownership without oversell; unsafe writes or dust remain blocked and manual resume cannot bypass the peak-equity floor.

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

Use a new verified lifecycle/state version. Retain old position ownership through draining. Rollback may restore compatible code but never reactivate old entry while a replacement owns the pair.

## Rollback / Recovery

Revert only compatible code/configuration before activation. Preserve journal and immutable evidence; never erase committed fills, restore stale balances or re-enable entry by rollback. Reconciliation governs recovery.

## Acceptance Criteria

- [ ] **PM-09-AC0** Partial entry fill receives exits only for actual filled quantity. Evidence: `test_pm_09_0` at exact committed SHA.
- [ ] **PM-09-AC1** Cancel uncertainty and late fills never permit blind replacement or oversell. Evidence: `test_pm_09_1` at exact committed SHA.
- [ ] **PM-09-AC2** Draining prevents entry but retains eligible candidate exits. Evidence: `test_pm_09_2` at exact committed SHA.
- [ ] **PM-09-AC3** New strategy cannot own pair until old position orders and reservations are resolved. Evidence: `test_pm_09_3` at exact committed SHA.
- [ ] **PM-09-AC4** Unsellable dust blocks drain completion with an explicit reason. Evidence: `test_pm_09_4` at exact committed SHA.
- [ ] **PM-09-AC5** Restart restores trailing state ownership and pending exits before resume. Evidence: `test_pm_09_5` at exact committed SHA.
- [ ] **PM-09-AC6** Unsupported stop or order semantics reject rather than substitute behavior. Evidence: `test_pm_09_6` at exact committed SHA.

- [ ] **PM-09-AC7** Peak-equity-floor breach persists controlled close-out across restart and rebound, cancelling entry remainders and reconciling uncertain orders and late fills before safe exits. Evidence: `test_pm_09_7` at exact committed SHA.

- [ ] **PM-09-AC8** Close-out coordinates pending exits and bot ownership without oversell; unsafe writes or dust remain blocked and manual resume cannot bypass the peak-equity floor. Evidence: `test_pm_09_8` at exact committed SHA.

## Definition of Done

All task acceptance and affected checks pass, exact-SHA handoff exists, independent reviewer PASS, zero Critical/Important findings. Manifest coordinator alone marks DONE. Activation gates remain separate.

## Reviewer Checklist

Check every AC, actual caller integration, state ownership, failure/recovery and compatibility. Verify no secret/live effects. Preserve review-round count and report exact SHA.

## Commit Guidance

Work in current checkout unless isolation is needed. Stage explicit owned paths. Commit coherent passing slices using `feat(pm-09): ...`; no merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-09-HANDOFF.md` with source/implementation SHA, actual paths, environment, commands/results, migration, review state and external gates.

## Ready-to-Run Implementation Prompt

Implement PM-09 only when manifest READY and dependencies DONE. Read Required Reading and dependency handoffs; follow the interfaces, tests and owned scope above. Preserve user work and live system boundaries. Return a committed implementation plus handoff at REVIEW, not self-approved DONE.
