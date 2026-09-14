# fix-review

## Goal

Close reported defects without feature expansion.

## Inputs and preconditions

Read reviewer report, current SHA and fix-round count; confirm every finding is understood. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Reproduce finding with regression; implement minimal root correction; verify related invariants and record new SHA.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Submit CHANGES_REQUESTED -> REVIEW with finding-by-finding evidence; stop at five rounds if unresolved.

## Output and failure handling

Submit CHANGES_REQUESTED -> REVIEW with finding-by-finding evidence; stop at five rounds if unresolved. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
