# parallel-plan

## Goal

Plan independent work without shared-file races.

## Inputs and preconditions

Read DAG ready nodes, input contracts, worktree list and host budget. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Partition by capability ownership, list overlapping paths and serialize central config/migrations/status changes.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Publish worktree/owner/reviewer map and merge order; DAG independence alone does not authorize parallel writes.

## Output and failure handling

Publish worktree/owner/reviewer map and merge order; DAG independence alone does not authorize parallel writes. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
