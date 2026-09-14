# security-audit

## Goal

Audit changed trust boundaries.

## Inputs and preconditions

Read threat surfaces, relevant sprints, authorized local fixture scope and release target SHA. Use root AGENTS and the exact relevant feature sprint; no phase-wide implementation scope.

## Procedure

1. Confirm request scope, ownership and current Git state.
2. Probe path traversal, untrusted deserialization, chat allowlist, secret redaction and forbidden order access with offline tests.
3. Preserve failing evidence and all pre-existing WIP; record command exits rather than impressions.
4. Report reproducible severity findings, mitigation and unresolved acceptance; no live exploit or account mutation.

## Output and failure handling

Report reproducible severity findings, mitigation and unresolved acceptance; no live exploit or account mutation. If evidence is unavailable, state that explicitly and use BLOCKED/REVIEW as appropriate. Never bypass dependencies, silently expand scope or manufacture a reviewer identity. Product state changes remain owned by the coordinator.
