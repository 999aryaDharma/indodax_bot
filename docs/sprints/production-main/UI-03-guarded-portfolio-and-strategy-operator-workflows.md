# UI-03 — Guarded portfolio and strategy operator workflows

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: production-main | Requirements: FR-23

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Planning only; claim only when manifest READY. No runtime acceptance yet.

## Goal

Guarded portfolio and strategy operator workflows.

## Why This Sprint Exists

Reuse existing pages.tsx, route.tsx, typed client, Kumo and Geist. Read Impeccable before frontend implementation; dashboard.pen remains read-only.

## Depends On

- API-04 — Guarded Production portfolio and lifecycle commands
- UI-02 — Read-only Production operational pages
- API-07 — Tailscale-authenticated Production read composition
- UI-09 — Same-origin Production API access

## Unlocks

PM-06

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

Reuse existing pages.tsx, route.tsx, typed client, Kumo and Geist. Read Impeccable before frontend implementation; dashboard.pen remains read-only.

## In Scope

Render adoption review, allocation proposal/decision, pause-entry, resume, halt and drain against API-04 receipts. Show exact policy/release revision, current exposure and impact. No local financial authority or hot SL/TP edits.

- Viewer and Research context cannot reach operator commands.
- Stale proposal forces refresh and never silently resubmits approval.
- Duplicate click uses one idempotency key and displays one outcome.
- Unknown basis unadopted assets and unavailable marks are explicitly labeled.
- Draining shows pending positions orders reservations and blocked dust.
- Keyboard and smartphone layouts preserve command context and confirmation details.

## Out of Scope

Live account access, credentials, orders, deployment, automatic promotion, unrelated refactors and changes to DONE evidence. Implement only the named service boundaries; DATA-07 does not own UI/API routers.

## User / Actor Behavior

The operator supplies versioned inputs through the named interface and receives durable evidence or an explicit blocked/rejected reason. Failed and superseded evidence remains inspectable.

## Functional Requirements

- **UI-03-AC0** Viewer and Research context cannot reach operator commands.
- **UI-03-AC1** Stale proposal forces refresh and never silently resubmits approval.
- **UI-03-AC2** Duplicate click uses one idempotency key and displays one outcome.
- **UI-03-AC3** Unknown basis unadopted assets and unavailable marks are explicitly labeled.
- **UI-03-AC4** Draining shows pending positions orders reservations and blocked dust.
- **UI-03-AC5** Keyboard and smartphone layouts preserve command context and confirmation details.

## Domain Rules / Invariants

BOT-TRADE-PROGRAM is normative for this task. Preserve Decimal accounting, UTC availability, immutable identity, no future information, exactly-once effects and separation of Research from Production authority.

## Architecture / Design Contract

Render adoption review, allocation proposal/decision, pause-entry, resume, halt and drain against API-04 receipts. Show exact policy/release revision, current exposure and impact. No local financial authority or hot SL/TP edits.

## Planned Files / Artifacts

- `frontend/src/features/production/commands.tsx`
- `frontend/src/features/production/pages.tsx`
- `frontend/src/features/production/route.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`
- `frontend/src/features/production/commands.test.tsx`

Paths are owned implementation targets, not claims that new files already exist. Reuse the current equivalent and record actual paths in handoff.

## Interfaces & Contracts

Render adoption review, allocation proposal/decision, pause-entry, resume, halt and drain against API-04 receipts. Show exact policy/release revision, current exposure and impact. No local financial authority or hot SL/TP edits.

Reuse ServiceError, ArtifactRef, existing API envelope and revision contracts. Unavailable values carry null plus reason; money is Decimal text on wire.

## Data / Persistence Impact

Preserve existing read-only pages for viewers and disabled command environments. Removing the UI does not alter backend strategy mode or cancel orders.

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

Run `cd frontend; npm test -- src/features/production/commands.test.tsx; npm run typecheck; npm run build` after implementation. Use fake transport and temporary state. Full suite is required when changing shared contracts/schemas.

- `test_ui_03_0`: Viewer and Research context cannot reach operator commands.
- `test_ui_03_1`: Stale proposal forces refresh and never silently resubmits approval.
- `test_ui_03_2`: Duplicate click uses one idempotency key and displays one outcome.
- `test_ui_03_3`: Unknown basis unadopted assets and unavailable marks are explicitly labeled.
- `test_ui_03_4`: Draining shows pending positions orders reservations and blocked dust.
- `test_ui_03_5`: Keyboard and smartphone layouts preserve command context and confirmation details.

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

Preserve existing read-only pages for viewers and disabled command environments. Removing the UI does not alter backend strategy mode or cancel orders.

## Rollback / Recovery

Revert only compatible code/configuration before activation. Preserve journal and immutable evidence; never erase committed fills, restore stale balances or re-enable entry by rollback. Reconciliation governs recovery.

## Acceptance Criteria

- [ ] **UI-03-AC0** Viewer and Research context cannot reach operator commands. Evidence: `test_ui_03_0` at exact committed SHA.
- [ ] **UI-03-AC1** Stale proposal forces refresh and never silently resubmits approval. Evidence: `test_ui_03_1` at exact committed SHA.
- [ ] **UI-03-AC2** Duplicate click uses one idempotency key and displays one outcome. Evidence: `test_ui_03_2` at exact committed SHA.
- [ ] **UI-03-AC3** Unknown basis unadopted assets and unavailable marks are explicitly labeled. Evidence: `test_ui_03_3` at exact committed SHA.
- [ ] **UI-03-AC4** Draining shows pending positions orders reservations and blocked dust. Evidence: `test_ui_03_4` at exact committed SHA.
- [ ] **UI-03-AC5** Keyboard and smartphone layouts preserve command context and confirmation details. Evidence: `test_ui_03_5` at exact committed SHA.

## Definition of Done

All task acceptance and affected checks pass, exact-SHA handoff exists, independent reviewer PASS, zero Critical/Important findings. Manifest coordinator alone marks DONE. Activation gates remain separate.

## Reviewer Checklist

Check every AC, actual caller integration, state ownership, failure/recovery and compatibility. Verify no secret/live effects. Preserve review-round count and report exact SHA.

## Commit Guidance

Work in current checkout unless isolation is needed. Stage explicit owned paths. Commit coherent passing slices using `feat(ui-03): ...`; no merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/UI-03-HANDOFF.md` with source/implementation SHA, actual paths, environment, commands/results, migration, review state and external gates.

## Ready-to-Run Implementation Prompt

Implement UI-03 only when manifest READY and dependencies DONE. Read Required Reading and dependency handoffs; follow the interfaces, tests and owned scope above. Preserve user work and live system boundaries. Return a committed implementation plus handoff at REVIEW, not self-approved DONE.
