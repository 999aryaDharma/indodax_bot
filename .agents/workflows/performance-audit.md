# performance-audit

## Goal

Measure the feature that consumes resources.

## Inputs and preconditions

Record host CPU/RAM/storage/GPU and concurrent workload; choose representative snapshot and algorithm dimension. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Measure wall/CPU time, RSS, disk, event lag or trial throughput; test bounded memory and interruption behavior.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Propose measured versioned thresholds and uncertainty; do not extrapolate production RPS from tiny fixtures.

## Output and failure handling

Propose measured versioned thresholds and uncertainty; do not extrapolate production RPS from tiny fixtures. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
