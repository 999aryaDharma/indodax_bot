# Shared agent control plane

Operational documentation shared by Codex and Antigravity. Product specs remain under docs/specs; do not duplicate them here. This directory is a specification and workflow set, not a running scheduler.

- `rules/execution.md`: claim, scope, evidence and change rules.
- `roles/`: implementer, reviewer, coordinator responsibilities.
- `coordination/protocol.md`: locks, staggered two-agent work, handoff and conflict resolution.
- `workflows/`: bounded procedures per action.
- `workflows/_BASELINE.md`: shared safety/evidence/ownership and risk-based verification rules.
- `orchestrator/README.md`: prospective supervisor contract and fail-closed status transitions.

## Fast review lane

Default lifecycle:

```text
IMPLEMENT
→ focused/affected verification
→ one comprehensive independent REVIEW
→ PASS → DONE

or

→ CHANGES_REQUESTED
→ one batched fix
→ delta-only re-review
→ PASS → DONE
```

Minor findings are non-blocking unless explicitly required by sprint acceptance. Normal work gets one fix cycle; high-risk shared/safety work may receive one documented emergency second cycle. Persistent blockers are redesigned rather than patched through repeated reviews.

Full repository/release verification belongs primarily at integration/release checkpoints; focused and affected-subsystem evidence remains mandatory during sprint implementation.

First read root `AGENTS.md`. Run planning validator before using READY queue. A tool that does not auto-load AGENTS must be prompted with the exact path.
