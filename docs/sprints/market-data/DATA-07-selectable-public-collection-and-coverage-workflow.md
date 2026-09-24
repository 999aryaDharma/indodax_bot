# DATA-07 — Selectable public collection and coverage workflow

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: market-data | Requirements: FR-19

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Planning only; claim only when manifest READY. No runtime acceptance yet.

## Goal

Selectable public collection and coverage workflow.

## Why This Sprint Exists

Collector input already includes pair, interval, start and end. Current source mapping is three pairs and six timeframes; current provider reachability and retention are unverified.

## Depends On

- DATA-03 — Auditable candle backfill
- DATA-05 — Reliable forward market collection
- RW1-01 — Reusable immutable dataset registry
- JOB-01 — Durable leased jobs
- JOB-02 — Resource-aware idle admission

## Unlocks

RW3-01, RW7-01

## Required Reading

- `AGENTS.md`
- `docs/production/FROZEN-SYSTEMS.md`
- `docs/production/main/README.md`
- `docs/production/research-workbench/README.md`
- `docs/decisions/ADR-010-multi-strategy-production-and-guarded-controls.md`
- `docs/implementation/BOT-TRADE-PROGRAM.md`
- `docs/implementation/CONTRACTS.md`
- `docs/specs/20-testing-strategy.md`
- `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`

## Current Context

Collector input already includes pair, interval, start and end. Current source mapping is three pairs and six timeframes; current provider reachability and retention are unverified.

## In Scope

2026-09-24 capacity extension: follow `docs/implementation/ASUS-BOT-CAPACITY-CROSSCHECK.md`; additional cases remain unverified, including for REVIEW tasks.

Public capability catalog and collect(DatasetRequest, request_id) return durable job/dataset refs and QualityReport using the existing collector, job and registry contracts. Inspect CanonicalPair ownership before extending it; update its existing owner rather than creating a competing pair type.

- Unsupported pair or timeframe rejects before fetch.
- Requested range gaps remain explicit and never become complete coverage.
- Identical retry resumes durable windows without duplicate publication.
- Public collection needs no account credential and retains raw response bytes.
- Extending pair eligibility preserves existing canonical pair validation and historical hashes.

## Out of Scope

Live account access, credentials, orders, deployment, automatic promotion, unrelated refactors and changes to DONE evidence. Implement only the named service boundaries; DATA-07 does not own UI/API routers.

## User / Actor Behavior

The operator supplies versioned inputs through the named interface and receives durable evidence or an explicit blocked/rejected reason. Failed and superseded evidence remains inspectable.

## Functional Requirements

- **DATA-07-AC0** Unsupported pair or timeframe rejects before fetch.
- **DATA-07-AC1** Requested range gaps remain explicit and never become complete coverage.
- **DATA-07-AC2** Identical retry resumes durable windows without duplicate publication.
- **DATA-07-AC3** Public collection needs no account credential and retains raw response bytes.
- **DATA-07-AC4** Extending pair eligibility preserves existing canonical pair validation and historical hashes.

## Domain Rules / Invariants

BOT-TRADE-PROGRAM is normative for this task. Preserve Decimal accounting, UTC availability, immutable identity, no future information, exactly-once effects and separation of Research from Production authority.

## Architecture / Design Contract

Public capability catalog and collect(DatasetRequest, request_id) return durable job/dataset refs and QualityReport using the existing collector, job and registry contracts. Inspect CanonicalPair ownership before extending it; update its existing owner rather than creating a competing pair type.

## Planned Files / Artifacts

- `src/indodax_lab/data/indodax_candles.py`
- `src/indodax_lab/cli/backfill_candles.py`
- `src/indodax_lab/data/dataset_registry.py`
- `src/indodax_lab/contracts/common.py`
- `tests/integration/lab/test_selectable_collection.py`

Paths are owned implementation targets, not claims that new files already exist. Reuse the current equivalent and record actual paths in handoff.

## Interfaces & Contracts

Public capability catalog and collect(DatasetRequest, request_id) return durable job/dataset refs and QualityReport using the existing collector, job and registry contracts. Inspect CanonicalPair ownership before extending it; update its existing owner rather than creating a competing pair type.

Reuse ServiceError, ArtifactRef, existing API envelope and revision contracts. Unavailable values carry null plus reason; money is Decimal text on wire.

## Data / Persistence Impact

Preserve existing pair identifiers, dataset versions and checksums. Extend allowed symbols through validated metadata, retain immutable source snapshots, and reject ambiguous symbols. No edits to prior datasets.

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

Run `python -m pytest tests/integration/lab/test_selectable_collection.py -q` after implementation. Use fake transport and temporary state. Full suite is required when changing shared contracts/schemas.

- `test_data_07_0`: Unsupported pair or timeframe rejects before fetch.
- `test_data_07_1`: Requested range gaps remain explicit and never become complete coverage.
- `test_data_07_2`: Identical retry resumes durable windows without duplicate publication.
- `test_data_07_3`: Public collection needs no account credential and retains raw response bytes.
- `test_data_07_4`: Extending pair eligibility preserves existing canonical pair validation and historical hashes.

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

Preserve existing pair identifiers, dataset versions and checksums. Extend allowed symbols through validated metadata, retain immutable source snapshots, and reject ambiguous symbols. No edits to prior datasets.

## Rollback / Recovery

Revert only compatible code/configuration before activation. Preserve journal and immutable evidence; never erase committed fills, restore stale balances or re-enable entry by rollback. Reconciliation governs recovery.

## Acceptance Criteria

- [ ] **DATA-07-AC5** Historical collection defers without fresh qualified headroom and resumes only durable windows. Evidence: `test_data_07_capacity_5` plus applicable measured host artifact; not established by historical tests.

- [ ] **DATA-07-AC0** Unsupported pair or timeframe rejects before fetch. Evidence: `test_data_07_0` at exact committed SHA.
- [ ] **DATA-07-AC1** Requested range gaps remain explicit and never become complete coverage. Evidence: `test_data_07_1` at exact committed SHA.
- [ ] **DATA-07-AC2** Identical retry resumes durable windows without duplicate publication. Evidence: `test_data_07_2` at exact committed SHA.
- [ ] **DATA-07-AC3** Public collection needs no account credential and retains raw response bytes. Evidence: `test_data_07_3` at exact committed SHA.
- [ ] **DATA-07-AC4** Extending pair eligibility preserves existing canonical pair validation and historical hashes. Evidence: `test_data_07_4` at exact committed SHA.

## Definition of Done

All task acceptance and affected checks pass, exact-SHA handoff exists, independent reviewer PASS, zero Critical/Important findings. Manifest coordinator alone marks DONE. Activation gates remain separate.

## Reviewer Checklist

Check every AC, actual caller integration, state ownership, failure/recovery and compatibility. Verify no secret/live effects. Preserve review-round count and report exact SHA.

## Commit Guidance

Work in current checkout unless isolation is needed. Stage explicit owned paths. Commit coherent passing slices using `feat(data-07): ...`; no merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/DATA-07-HANDOFF.md` with source/implementation SHA, actual paths, environment, commands/results, migration, review state and external gates.

## Ready-to-Run Implementation Prompt

Implement DATA-07 only when manifest READY and dependencies DONE. Read Required Reading and dependency handoffs; follow the interfaces, tests and owned scope above. Preserve user work and live system boundaries. Return a committed implementation plus handoff at REVIEW, not self-approved DONE.
