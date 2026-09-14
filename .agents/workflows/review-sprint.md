# review-sprint

## Goal

Independently validate code against the sprint.

## Inputs and preconditions

Read immutable code SHA, handoff, spec and existing reviewer checklist. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Inspect actual diff and fixtures; reproduce success and adversarial behavior; check units, provenance, rollback and scope.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Write separate spec/quality verdicts and severity findings; do not merge automatically.

## Output and failure handling

Write separate spec/quality verdicts and severity findings; do not merge automatically. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
