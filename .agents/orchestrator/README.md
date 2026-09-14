# Proposed orchestration contract for coding agents

Status: DOCUMENTED ONLY; no listener, scheduler, daemon or automatic task is created by this planning branch. Product research queue is separately owned by JOB-01…03; it is not this coding-agent coordinator.

## Input and output

Inputs: validated sprint manifest, explicit active portfolio, claim records, handoffs, independent review reports, user changes. Outputs: one bounded agent assignment or a concrete blocker; coordinator-authored status projection changes. It must never launch real trading activity.

## Scheduler rules for a future implementation

Reconcile manifest dependency status before assignment. A claim includes sprint_id, owner_id, reviewer_id, branch/worktree, base_sha, allowed_paths, lease_generation, heartbeat, fix_round. Allow one implementation owner; reserve overlapping paths. A reviewer must differ from implementation author. Lease loss requires inspection/preservation of WIP before reassignment. Fencing prevents stale owner from changing coordinator state.

When work reaches REVIEW, schedule independent review; on CHANGES_REQUESTED increment round and return scoped fixes. At five unsuccessful rounds set BLOCKED, preserve all evidence and request root redesign review. On DONE recompute descendants, never recursively run every unblocked optional track. Data/compute budget and owner activation remain independent admission checks.

## Idempotency and audit

Assignment key = sprint + base SHA + claim generation. Review key = sprint + exact code SHA + reviewer identity. Same report cannot mark a different SHA done. Record all transitions, time and reason. No auto-merge. If no callable agent runner exists, follow workflows manually; documentation is not a claim of background execution.

## Implementation boundary

Any future automatic coding supervisor needs a separate change request, capability decomposition and tool/permission design. Do not slip its implementation into AGENT-01, whose scope is research curator policy.
