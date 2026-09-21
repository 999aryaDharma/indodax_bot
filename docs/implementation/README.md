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

Work is on `docs/architecture-runtime-plan`, isolated from `dev`; no main change, merge, push, deployment, new credentials or runtime DB operation. LUNA implements one READY unit in its own worktree; an independent reviewer checks exact committed SHA. Critical/Important findings block DONE; preserve review rounds (maximum five). Current branch review is recorded in `handoff/REVIEW.md` and the DOC-01 handoff.

This program uses Python 3.11-compatible typed contracts, existing Pydantic/Decimal/SQLite/Parquet primitives, and optional model environments. No distributed scheduler, new database service, provider license or hardware capacity is presumed.
