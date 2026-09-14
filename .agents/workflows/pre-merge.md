# pre-merge

## Goal

Qualify the exact branch diff for integration.

## Inputs and preconditions

Read authorized merge scope, target branch, independent verdict and fresh evidence SHA. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Check rebase/merge conflicts, no untracked work staged, no secret/data blobs, validate docs and required product gates.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Produce reviewable merge summary; merge only if user task already authorizes it, otherwise leave branch ready.

## Output and failure handling

Produce reviewable merge summary; merge only if user task already authorizes it, otherwise leave branch ready. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
