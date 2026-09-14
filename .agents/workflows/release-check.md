# release-check

## Goal

Qualify software delivery separately from champion edge.

## Inputs and preconditions

Read REL-01, deployment profile, locks, migration/restore record and operational risk register. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Verify core feature gates, security/resource/backup checks, rollback and no real-order capability; label pending forward duration.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Prepare release candidate evidence and activation instructions; do not equate software PASS with champion eligibility.

## Output and failure handling

Prepare release candidate evidence and activation instructions; do not equate software PASS with champion eligibility. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
