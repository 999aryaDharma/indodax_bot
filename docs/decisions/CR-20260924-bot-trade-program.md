# CR-20260924-BOT — Workbench and shared-capital Main Bot

Status: ACCEPTED by owner for documentation and future implementation planning, 2026-09-24. This delivery writes specifications and sprint tasks, not trading code or deployment.

## Request

Freeze the agreed Workbench flow: form/YAML/MCP composition, real Indodax historical collection by pair/range/timeframe, independent per-pair backtests, detailed trade results, realtime isolated shadow and drawdown-filtered Top 10.

Extend Main Bot planning to multiple immutable strategies sharing one account portfolio, one owner per pair, dynamic shared-pool allocation, equity-based stop-risk sizing, reviewed adoption, candidate-owned exits, draining replacement and guarded dashboard controls.

## Impact and authority

[ADR-010](ADR-010-multi-strategy-production-and-guarded-controls.md) amends the single-candidate release interpretation and admits the named guarded command tasks beyond the earlier read-only control-plane CR. [Program contract](../implementation/BOT-TRADE-PROGRAM.md) contains the exact accepted behavior and interfaces. Research isolation, G0–G7, host allocation and backend financial authority remain mandatory.

Add DATA-07, PM-07–PM-09, API-04 and UI-03. Extend PLANNED owner tasks and regenerate the manifest projections. Do not reopen completed collector/registry/API/UI tasks or claim new acceptance under their historic evidence. Resolve shared-capital portfolio policy at PM-08, consumed by RW6 and release qualification; avoid a dependency cycle through PM-06.

## Validation and rollback

Run `python docs/quality/validate_planning.py --refresh --self-test` and `git diff --check`. Review exact documentation SHA. Revert only this packet if rejected; preserve user edits, runtime data and historical evidence. New tasks remain READY/PLANNED based on dependencies, not DONE. No deployment or live account operation follows from documentation acceptance.

## Accepted owner refinement — dynamic allocation

On 2026-09-24 the owner approved a shared IDR 500,000 pool without fixed agent quotas, candidate-owned adaptive sizing/SL/TP under central risk limits, and skipping below-minimum orders without inflating risk. ADR-010 and the program record the supersession, three selected agents and unresolved numerical limits. PM-08 acceptance/contract text is updated in place; RP-03, PM-09, RW6 and guarded API/UI consume it through existing dependencies. No new sprint, status change, runtime change or deployment is implied.

## Accepted owner refinement — configurable defaults and controlled close-out

The owner requests dashboard-customizable supported Main and agent parameters, initialized from agreed defaults. Record the IDR 500,000 shared pool, initial-capital 20% loss floor, controlled close-out and manual resume, monthly reporting objective and unresolved risk settings. Impact: extend PM-08 floor/default validation, PM-09 durable close-out lifecycle, API-04 versioned draft approval and UI-03 default/draft/active presentation. Agent parameter changes use the existing candidate/release flow; no bypass endpoint or new scheduler is introduced. Amend ADR-010, program and existing sprint acceptance mappings; preserve statuses, dependencies and unrelated implementation work.

## Accepted owner refinement — absolute peak drawdown

Supersede the earlier initial-capital 20% rule: absolute portfolio drawdown allowance is IDR 100,000 from adjusted peak equity at any capital size. Retain controlled close-out, write gates and manual resume. Document reinvestment, negative-month evaluation, trading-cost-only profit target and operator absence of 8-12 hours. Update the program, ADR-010, affected sprint acceptance and manifest in place; statuses/dependencies and runtime are unchanged. Preserve other implementer work and historical handoffs; cash-flow adjustment and incident notification choices remain explicit future decisions.

## Accepted owner refinement — separately approved risk periods

Permit a new risk period after completed drawdown close-out and independent operator decision; retain old-period loss/peak/incident evidence and cumulative accounting. Bind actual opening equity, release and risk policy to the proposal; ordinary resume cannot reset the peak. Preserve 5% net monthly target and add rolling 90-day evaluation without weakening candidate qualification. Extend existing PM-08/PM-09/API-04/UI-03 contracts and acceptance mappings; no new service, endpoint, runtime change, status change or dependency change is implied. Unconfirmed numerical baseline proposals remain outside this freeze.

## Decision-register coverage

Record all 14 discussed policy aspects in `docs/implementation/PRODUCTION-RISK-POLICY-V1.md`, separating DECIDED, PROPOSED and OPEN/BLOCKING. Preserve numerical proposals awaiting owner confirmation, pending execution/liquidity/incident details and verified venue documentation separately from operational evidence. The register does not authorize implementation outside each owning sprint or weaken existing gates.

## Confirmed numerical policy defaults

Owner confirmation admits the IDR 4,000/trade, IDR 10,000/global, IDR 8,000/cluster and IDR 15,000/day defaults plus two positions, 25% per-pair and 50% total notional ceilings for qualification before activation. Update PM-08 and UI-03 acceptance mappings. Other proposed settings retain explicit PROPOSED/OPEN status; this is documentation, not live configuration.
