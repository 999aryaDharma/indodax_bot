# CR-2026-09-21 — Frozen architecture implementation planning

Status: authorized documentation work by repository owner; no product activation. Baseline `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`.

Request: audit reality, restore planning authority, express shared-runtime parity, map RW0–RW9 and production gaps, and prepare LUNA execution units. Frozen system boundaries win over older scope/topology statements.

Impact: documentation precedence clarified; malformed manifest conservatively reconstructed; historical imports retained; unverified later completion stays REVIEW; new dependency nodes and projections added. No source/runtime/test/credential/financial state changes. ADR-005/006/007 record implementation choices not previously specified in sufficient detail.

Compatibility: legacy requirements FR-01..FR-18 and task crosswalk retained. New requirements FR-19..FR-23 trace frozen Workbench/parity/control-plane/bridge capability; no automatic widening of real-money permission. Shared kernel does not transfer execution authority to Research. New API/schema plans are versioned and staged through LUNA tasks.

Validation: existing planning validator plus program coverage checks, links, DAG/readiness, exact task fields and diff check. Independent reviewer checks final committed SHA. Rollback is scoped documentation revert with source SHA/provenance retained; do not reset another worktree.

## Follow-on Production API/UI admission

[CR-2026-09-23](CHANGE-REQUEST-PRODUCTION-CONTROL-PLANE.md) admits the read-only Production API and desktop/smartphone UI sprint nodes. It resolves the API/UI ID collisions from the earlier planning proposal, records explicit dependencies, and adds Kumo UI 2.14.0 plus local Geist Sans/Mono under the existing `DESIGN.md` visual contract. It does not authorize deployment or real-money operation.
