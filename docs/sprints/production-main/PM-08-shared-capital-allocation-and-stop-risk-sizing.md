# PM-08 — Shared capital allocation and stop risk sizing

## Metadata

Status: PLANNED

Priority: P1 | Type: integration | Domain: production-main | Requirements: FR-23

Implementation Owner: UNASSIGNED | Independent Reviewer: UNASSIGNED

Planning only; claim only when manifest READY. No runtime acceptance yet.

## Goal

Shared capital allocation and stop risk sizing.

## Why This Sprint Exists

Reuse PortfolioConstructor, PortfolioRiskManager, central RiskEngine and transactional execution state; existing sizing alone does not establish multi-strategy capital arbitration.

## Depends On

- PM-07 — Reviewed account portfolio adoption
- PM-05 — Candidate-bound release provenance
- RP-03 — Shared portfolio sizing and risk semantics

## Unlocks

RW6-01, PM-09

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

Reuse PortfolioConstructor, PortfolioRiskManager, central RiskEngine and transactional execution state; existing sizing alone does not establish multi-strategy capital arbitration.

## In Scope

AllocationPolicy pins shared-pool allocation without fixed agent quotas, pair owners, priority, account/pair exposure, aggregate risk, capital ceiling and cost-aware stop-risk sizing. Candidate-owned adaptive sizing and exits remain bounded by central risk limits. Central assessment atomically reserves against one portfolio revision and returns approved quantity or explicit rejection; all environments call this same implementation. Enforce the program dashboard defaults, initial-capital floor and explicit unset live-risk settings; publish the durable floor-breach intent for PM-09.

- Concurrent strategy signals share available cash without fixed quotas and cannot spend the same cash twice.
- Invalid risk or exposure limits and overlapping pair owners reject the policy.
- Filled exposure and pending reservations including fees consume shared cash and portfolio risk headroom exactly once.
- Missing stop stale marks or unavailable costs reject new entry.
- Below-minimum rounded size rejects without rounding upward or tightening the strategy stop; entry and planned exits satisfy verified pair-specific venue constraints.
- Risk or exposure limit reduction below current usage stops affected entry without forced sale.
- Verified cash flows adjust risk baselines without hiding losses.
- Priority and intent ordering reproduce identical allocation on replay.

- Initial capital 500000 yields a 400000 floor; rising equity does not raise it and equality triggers a durable close-out request.

- Unset live per-trade aggregate daily-loss limits or unreviewed cash-flow baseline rules block new-policy activation; defaults and restart never reset active policy or losses.

- Missing marks or exit costs block entry; capital-floor valuation counts costs once and reports peak drawdown separately.

## Out of Scope

Live account access, credentials, orders, deployment, automatic promotion, unrelated refactors and changes to DONE evidence. Implement only the named service boundaries; DATA-07 does not own UI/API routers.

## User / Actor Behavior

The operator supplies versioned inputs through the named interface and receives durable evidence or an explicit blocked/rejected reason. Failed and superseded evidence remains inspectable.

## Functional Requirements

- **PM-08-AC0** Concurrent strategy signals share available cash without fixed quotas and cannot spend the same cash twice.
- **PM-08-AC1** Invalid risk or exposure limits and overlapping pair owners reject the policy.
- **PM-08-AC2** Filled exposure and pending reservations including fees consume shared cash and portfolio risk headroom exactly once.
- **PM-08-AC3** Missing stop stale marks or unavailable costs reject new entry.
- **PM-08-AC4** Below-minimum rounded size rejects without rounding upward or tightening the strategy stop; entry and planned exits satisfy verified pair-specific venue constraints.
- **PM-08-AC5** Risk or exposure limit reduction below current usage stops affected entry without forced sale.
- **PM-08-AC6** Verified cash flows adjust risk baselines without hiding losses.
- **PM-08-AC7** Priority and intent ordering reproduce identical allocation on replay.

- **PM-08-AC8** Initial capital 500000 yields a 400000 floor; rising equity does not raise it and equality triggers a durable close-out request.

- **PM-08-AC9** Unset live per-trade aggregate daily-loss limits or unreviewed cash-flow baseline rules block new-policy activation; defaults and restart never reset active policy or losses.

- **PM-08-AC10** Missing marks or exit costs block entry; capital-floor valuation counts costs once and reports peak drawdown separately.

## Domain Rules / Invariants

BOT-TRADE-PROGRAM is normative for this task. Preserve Decimal accounting, UTC availability, immutable identity, no future information, exactly-once effects and separation of Research from Production authority.

## Architecture / Design Contract

AllocationPolicy pins shared-pool allocation without fixed agent quotas, pair owners, priority, account/pair exposure, aggregate risk, capital ceiling and cost-aware stop-risk sizing. Candidate-owned adaptive sizing and exits remain bounded by central risk limits. Central assessment atomically reserves against one portfolio revision and returns approved quantity or explicit rejection; all environments call this same implementation. Enforce the program dashboard defaults, initial-capital floor and explicit unset live-risk settings; publish the durable floor-breach intent for PM-09.

## Planned Files / Artifacts

- `src/indodax_lab/portfolio/constructor.py`
- `src/indodax_lab/portfolio/allocation.py`
- `src/indodax_lab/risk/engine.py`
- `src/indodax_lab/backtest/risk.py`
- `tests/unit/lab/portfolio/test_shared_allocation.py`

Paths are owned implementation targets, not claims that new files already exist. Reuse the current equivalent and record actual paths in handoff.

## Interfaces & Contracts

AllocationPolicy pins shared-pool allocation without fixed agent quotas, pair owners, priority, account/pair exposure, aggregate risk, capital ceiling and cost-aware stop-risk sizing. Candidate-owned adaptive sizing and exits remain bounded by central risk limits. Central assessment atomically reserves against one portfolio revision and returns approved quantity or explicit rejection; all environments call this same implementation. Enforce the program dashboard defaults, initial-capital floor and explicit unset live-risk settings; publish the durable floor-breach intent for PM-09.

Reuse ServiceError, ArtifactRef, existing API envelope and revision contracts. Unavailable values carry null plus reason; money is Decimal text on wire.

## Data / Persistence Impact

Version the policy and state schema; legacy defaults never populate an approved live policy silently. Preserve pending reservations and risk high-water references. Existing single-candidate policies need explicit verified conversion.

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

Run `python -m pytest tests/unit/lab/portfolio/test_shared_allocation.py -q` after implementation. Use fake transport and temporary state. Full suite is required when changing shared contracts/schemas.

- `test_pm_08_0`: Concurrent strategy signals share available cash without fixed quotas and cannot spend the same cash twice.
- `test_pm_08_1`: Invalid risk or exposure limits and overlapping pair owners reject the policy.
- `test_pm_08_2`: Filled exposure and pending reservations including fees consume shared cash and portfolio risk headroom exactly once.
- `test_pm_08_3`: Missing stop stale marks or unavailable costs reject new entry.
- `test_pm_08_4`: Below-minimum rounded size rejects without rounding upward or tightening the strategy stop; entry and planned exits satisfy verified pair-specific venue constraints.
- `test_pm_08_5`: Risk or exposure limit reduction below current usage stops affected entry without forced sale.
- `test_pm_08_6`: Verified cash flows adjust risk baselines without hiding losses.
- `test_pm_08_7`: Priority and intent ordering reproduce identical allocation on replay.

- `test_pm_08_8`: Initial capital 500000 yields a 400000 floor; rising equity does not raise it and equality triggers a durable close-out request.

- `test_pm_08_9`: Unset live per-trade aggregate daily-loss limits or unreviewed cash-flow baseline rules block new-policy activation; defaults and restart never reset active policy or losses.

- `test_pm_08_10`: Missing marks or exit costs block entry; capital-floor valuation counts costs once and reports peak drawdown separately.

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

Version the policy and state schema; legacy defaults never populate an approved live policy silently. Preserve pending reservations and risk high-water references. Existing single-candidate policies need explicit verified conversion.

## Rollback / Recovery

Revert only compatible code/configuration before activation. Preserve journal and immutable evidence; never erase committed fills, restore stale balances or re-enable entry by rollback. Reconciliation governs recovery.

## Acceptance Criteria

- [ ] **PM-08-AC0** Concurrent strategy signals share available cash without fixed quotas and cannot spend the same cash twice. Evidence: `test_pm_08_0` at exact committed SHA.
- [ ] **PM-08-AC1** Invalid risk or exposure limits and overlapping pair owners reject the policy. Evidence: `test_pm_08_1` at exact committed SHA.
- [ ] **PM-08-AC2** Filled exposure and pending reservations including fees consume shared cash and portfolio risk headroom exactly once. Evidence: `test_pm_08_2` at exact committed SHA.
- [ ] **PM-08-AC3** Missing stop stale marks or unavailable costs reject new entry. Evidence: `test_pm_08_3` at exact committed SHA.
- [ ] **PM-08-AC4** Below-minimum rounded size rejects without rounding upward or tightening the strategy stop; entry and planned exits satisfy verified pair-specific venue constraints. Evidence: `test_pm_08_4` at exact committed SHA.
- [ ] **PM-08-AC5** Risk or exposure limit reduction below current usage stops affected entry without forced sale. Evidence: `test_pm_08_5` at exact committed SHA.
- [ ] **PM-08-AC6** Verified cash flows adjust risk baselines without hiding losses. Evidence: `test_pm_08_6` at exact committed SHA.
- [ ] **PM-08-AC7** Priority and intent ordering reproduce identical allocation on replay. Evidence: `test_pm_08_7` at exact committed SHA.

- [ ] **PM-08-AC8** Initial capital 500000 yields a 400000 floor; rising equity does not raise it and equality triggers a durable close-out request. Evidence: `test_pm_08_8` at exact committed SHA.

- [ ] **PM-08-AC9** Unset live per-trade aggregate daily-loss limits or unreviewed cash-flow baseline rules block new-policy activation; defaults and restart never reset active policy or losses. Evidence: `test_pm_08_9` at exact committed SHA.

- [ ] **PM-08-AC10** Missing marks or exit costs block entry; capital-floor valuation counts costs once and reports peak drawdown separately. Evidence: `test_pm_08_10` at exact committed SHA.

## Definition of Done

All task acceptance and affected checks pass, exact-SHA handoff exists, independent reviewer PASS, zero Critical/Important findings. Manifest coordinator alone marks DONE. Activation gates remain separate.

## Reviewer Checklist

Check every AC, actual caller integration, state ownership, failure/recovery and compatibility. Verify no secret/live effects. Preserve review-round count and report exact SHA.

## Commit Guidance

Work in current checkout unless isolation is needed. Stage explicit owned paths. Commit coherent passing slices using `feat(pm-08): ...`; no merge/push/deploy.

## Handoff Requirements

Write `docs/sprints/handoffs/PM-08-HANDOFF.md` with source/implementation SHA, actual paths, environment, commands/results, migration, review state and external gates.

## Ready-to-Run Implementation Prompt

Implement PM-08 only when manifest READY and dependencies DONE. Read Required Reading and dependency handoffs; follow the interfaces, tests and owned scope above. Preserve user work and live system boundaries. Return a committed implementation plus handoff at REVIEW, not self-approved DONE.
