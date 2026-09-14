# Shared agent control plane

Operational documentation shared by Codex and Antigravity. Product specs remain under docs/specs; do not duplicate them here. This directory is a specification and workflow set, not a running scheduler.

- `rules/execution.md`: claim, scope, evidence and change rules.
- `roles/`: implementer, reviewer, coordinator responsibilities.
- `coordination/protocol.md`: locks, handoff and conflict resolution.
- `workflows/`: bounded procedures per action.
- `orchestrator/README.md`: prospective supervisor contract and fail-closed status transitions.

First read root AGENTS.md. Run planning validator before using READY queue. A tool that does not auto-load AGENTS must be prompted with the exact path.
