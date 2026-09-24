# CR-20260924-BOT — Workbench and shared-capital Main Bot

Status: ACCEPTED by owner for documentation and future implementation planning, 2026-09-24. This delivery writes specifications and sprint tasks, not trading code or deployment.

## Request

Freeze the agreed Workbench flow: form/YAML/MCP composition, real Indodax historical collection by pair/range/timeframe, independent per-pair backtests, detailed trade results, realtime isolated shadow and drawdown-filtered Top 10.

Extend Main Bot planning to multiple immutable strategies sharing one account portfolio, one owner per pair, strategy caps, equity-based stop-risk sizing, reviewed adoption, candidate-owned exits, draining replacement and guarded dashboard controls.

## Impact and authority

[ADR-010](ADR-010-multi-strategy-production-and-guarded-controls.md) amends the single-candidate release interpretation and admits the named guarded command tasks beyond the earlier read-only control-plane CR. [Program contract](../implementation/BOT-TRADE-PROGRAM.md) contains the exact accepted behavior and interfaces. Research isolation, G0–G7, host allocation and backend financial authority remain mandatory.

Add DATA-07, PM-07–PM-09, API-04 and UI-03. Extend PLANNED owner tasks and regenerate the manifest projections. Do not reopen completed collector/registry/API/UI tasks or claim new acceptance under their historic evidence. Resolve shared-capital portfolio policy at PM-08, consumed by RW6 and release qualification; avoid a dependency cycle through PM-06.

## Validation and rollback

Run `python docs/quality/validate_planning.py --refresh --self-test` and `git diff --check`. Review exact documentation SHA. Revert only this packet if rejected; preserve user edits, runtime data and historical evidence. New tasks remain READY/PLANNED based on dependencies, not DONE. No deployment or live account operation follows from documentation acceptance.
