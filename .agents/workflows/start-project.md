# start-project

## Goal

Recover the project before selecting implementation.

## Inputs and preconditions

Read AGENTS, docs/README, master and repository-audit; inspect branch/worktree status and runtime constraints. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Validate manifest; inspect imported evidence and uncommitted WIP without mutation.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Output current baseline, READY queue, missing external evidence and ownership proposal.

## Output and failure handling

Output current baseline, READY queue, missing external evidence and ownership proposal. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
