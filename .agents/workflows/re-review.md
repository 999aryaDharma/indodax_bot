# re-review

## Goal

Verify resolved findings on new SHA.

## Inputs and preconditions

Read previous findings and only the fix diff plus necessary shared contracts. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Check regressions truly fail old behavior and prove new result; inspect adjacent breakage introduced by fix.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Close or retain each finding; new Critical/Important blocks DONE. Preserve accumulated rounds.

## Output and failure handling

Close or retain each finding; new Critical/Important blocks DONE. Preserve accumulated rounds. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
