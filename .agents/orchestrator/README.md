# Proposed orchestration contract for coding agents

Status: DOCUMENTED ONLY; no listener, scheduler, daemon or automatic task is created by this planning branch. Product research queue is separately owned by JOB-01…03; it is not this coding-agent coordinator.

## Input and output

Inputs: validated sprint manifest, requested portfolio, working-tree ownership and user changes. Outputs: a small batch of independent assignments or a concrete blocker; coordinator-authored status projection changes. It must never launch real trading activity.

## Scheduler rules for a future implementation

Reconcile manifest dependency status once before assignment. Batch READY sprints with DONE dependencies when paths do not overlap; assign one owner per sprint and reserve shared paths to one writer. Keep the current checkout by default; use a worktree only when isolation is needed. A reviewer must differ from implementation authors. Inspect and preserve WIP before reassignment. Avoid lease/heartbeat machinery unless an actual concurrent coordinator needs it.

Schedule one independent review at the end of the implementation batch, with per-sprint acceptance results on the exact batch SHA. On CHANGES_REQUESTED increment the round and return scoped fixes. At five unsuccessful rounds set BLOCKED and preserve evidence. After PASS, recompute readiness once; do not recursively run unrelated optional tracks. Data/compute budget and owner activation remain independent admission checks.

## Idempotency and audit

Review key = sprint + exact code SHA + reviewer identity. Same report cannot mark a different SHA done. Record only decisions needed to explain ownership, review and status changes. No auto-merge. If no callable agent runner exists, follow workflows manually; documentation is not a claim of background execution.

## Implementation boundary

Any future automatic coding supervisor needs a separate change request, capability decomposition and tool/permission design. Do not slip its implementation into AGENT-01, whose scope is research curator policy.
