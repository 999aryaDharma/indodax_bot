# Architecture audit and implementation program

Planning version: 1.0.0 | Audit baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4` | 2026-09-21.

This is a documentation delivery, not implementation or authorization to trade. The owner requested a repository-wide audit, shared-runtime parity plan, RW0–RW9 program, production safety backlog and executable LUNA handoff. Frozen Production Main and Research Workbench remain authoritative. Existing code is evidence of behavior, not permission to weaken those contracts.

Read in order:

1. [Frozen systems](../production/FROZEN-SYSTEMS.md), then both systems' linked specifications.
2. [Current state](CURRENT-STATE.md) and [source inventory](SOURCE-INVENTORY.md).
3. [Runtime parity](RUNTIME-PARITY.md) and [domain contracts](CONTRACTS.md).
4. [Dependency map](SYSTEM-DEPENDENCY-MAP.md).
5. [Research roadmap](research-workbench/ROADMAP.md), [parity roadmap](runtime-parity/ROADMAP.md), [production roadmap](production-main/ROADMAP.md).
6. [ASTRA status](handoff/ASTRA-STATUS.md) and [one next LUNA task](handoff/LUNA-NEXT.md).
7. [Control-plane program plan](../superpowers/plans/2026-09-22-control-plane-program-plan.md), then the [Production API](../superpowers/plans/2026-09-22-production-api-plan.md), [Research Workbench API](../superpowers/plans/2026-09-22-research-workbench-api-plan.md), and [Unified Dashboard](../superpowers/plans/2026-09-22-unified-dashboard-plan.md) child plans when implementing API or UI work.
8. [Production control-plane change request](CHANGE-REQUEST-PRODUCTION-CONTROL-PLANE.md) and [control-plane roadmap](CONTROL-PLANE-ROADMAP.md) before claiming any API or dashboard task. The manifest and canonical sprint files determine current admission and READY status.

Delivery status/DAG is owned only by [the sprint manifest](../sprints/sprint-manifest.json). Roadmaps group tasks; they do not own status. Detailed task files live in `docs/sprints/`; old tasks are cross-referenced, not duplicated as new implementations. Read the [manifest recovery record](MANIFEST-RECOVERY.md) before interpreting status changes. REVIEW is not missing code and is not independent PASS.

## Evidence vocabulary

- FACT: observed tracked bytes or command output at the audit SHA.
- CURRENT IMPLEMENTATION: source behavior inspected; no implication of fresh test PASS.
- TARGET ARCHITECTURE: frozen requirements or the explicitly documented planning decision.
- PLANNED: future task, interface, test or migration.
- BLOCKED: named prerequisite/evidence unavailable.
- EXPERIMENTAL: research implementation/evidence without production qualification.

Subsystem classifications are IMPLEMENTED (bounded primitive exists), PARTIAL (target incomplete), MISSING (not found in tracked inventory), LEGACY, SUPERSEDED, or BLOCKED_EXTERNAL. Implementation classification and sprint status are independent axes. Product tests were not run for this documentation delivery; source inventory and historical test references are not test execution evidence.

## Boundaries and delivery

The original DOC-01 documentation delivery used branch `docs/architecture-runtime-plan` and an isolated worktree. That was delivery provenance, not a standing per-sprint workflow requirement. Live host and trading changes remain separately gated.

This program uses Python 3.11-compatible typed contracts, existing Pydantic/Decimal/SQLite/Parquet primitives, and optional model environments. No distributed scheduler, new database service, provider license or hardware capacity is presumed.

## Agent delivery workflow

Use the current `AGENTS.md` and `.agents/coordination/protocol.md` for execution. Batch independent READY sprints when dependencies are DONE and file scopes do not overlap; keep one owner per sprint and one writer per shared path. Work in the current checkout by default. Commit passing slices promptly, run focused checks by default, and have one independent reviewer check each sprint at the final batch SHA. Update manifest and projections once after review. Full audits, repeated global-doc reads, worktrees and full-suite runs are not routine requirements.

## Bot Trade Program — 2026-09-24

Read [the accepted program](BOT-TRADE-PROGRAM.md), [CR](../decisions/CR-20260924-bot-trade-program.md) and [ADR-010](../decisions/ADR-010-multi-strategy-production-and-guarded-controls.md) for Workbench product decisions and multi-strategy Production. DATA-07 and PM-07–09/API-04/UI-03 extend the manifest. No implementation completion or live activation is claimed.
