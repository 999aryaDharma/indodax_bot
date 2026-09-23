# Shared agent control plane

Operational documentation shared by Codex and Antigravity. Product specs remain under docs/specs; do not duplicate them here. This directory is a specification and workflow set, not a running scheduler.

- `rules/execution.md`: claim, scope, evidence and change rules.
- `roles/`: implementer, reviewer, coordinator responsibilities.
- `coordination/protocol.md`: batching, shared-path ownership, concise handoffs and conflict resolution.
- `workflows/`: bounded procedures per action.
- `workflows/_BASELINE.md`: shared safety/evidence/ownership rules; each workflow file contains only its action-specific delta to avoid repeated boilerplate.
- `orchestrator/README.md`: prospective supervisor contract and fail-closed status transitions.

First read root AGENTS.md. Check the manifest when selecting work; run the planning validator when manifest/status projections change or the DAG is in doubt. A tool that does not auto-load AGENTS must be prompted with the exact path.
