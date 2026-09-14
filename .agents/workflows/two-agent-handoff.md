# two-agent-handoff

## Goal

Transfer complete reviewable context.

## Inputs and preconditions

Record sprint, owner/reviewer, base/code/evidence SHAs and changed file scope. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Map each AC to exact test results, contracts, migrations, known risks, deviations and remaining blockers.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Receiver verifies Git state and evidence before resuming; do not invent progress from an incomplete report.

## Output and failure handling

Receiver verifies Git state and evidence before resuming; do not invent progress from an incomplete report. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
