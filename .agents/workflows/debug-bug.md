# debug-bug

## Goal

Diagnose actual behavior before changing it.

## Inputs and preconditions

Capture input identities, logs, environment, SHA, expected vs actual; classify technical invalidity vs bad strategy. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Build minimal reproduction; isolate cause; do not tune parameters to hide a data/accounting bug.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Create scoped fix/CR with dependency impact and regression evidence; preserve failing artifact.

## Output and failure handling

Create scoped fix/CR with dependency impact and regression evidence; preserve failing artifact. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
