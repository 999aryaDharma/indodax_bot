# change-request

## Goal

Keep major changes traceable.

## Inputs and preconditions

Record idea, user/system value, alternatives and target capability. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Analyze contracts, migration, security, compute/data cost, old result validity and DAG impacts; create ADR when material.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Update master/subsystem/feature map/sprints/manifest together and validate before implementation.

## Output and failure handling

Update master/subsystem/feature map/sprints/manifest together and validate before implementation. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
