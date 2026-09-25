# Proposed orchestration contract for coding agents

Status: DOCUMENTED ONLY; no listener, scheduler, daemon or automatic task is created by this planning branch. Product research queue is separately owned by JOB-01…03; it is not this coding-agent coordinator.

## Input and output

Inputs: validated sprint manifest, explicit active portfolio, claim records, handoffs, independent review reports, user changes. Outputs: one bounded agent assignment or a concrete blocker; coordinator-authored status projection changes. It must never launch real trading activity.

## Scheduler rules for a future implementation

Reconcile manifest dependency status before assignment. A claim includes sprint_id, owner_id, reviewer_id, branch/worktree, base_sha, allowed_paths, lease_generation, heartbeat and fix_cycle. Allow one implementation owner per sprint; reserve overlapping paths. A reviewer must differ from implementation author. Lease loss requires inspection/preservation of WIP before reassignment. Fencing prevents stale owner from changing coordinator state.

A sprint is one reviewable unit, not one mandatory agent session. After a committed handoff, the implementation owner may claim a different independent READY sprint while the previous sprint is being reviewed, provided dependency and shared-path locks allow it.

When work reaches REVIEW, schedule one comprehensive independent review for the exact code SHA. The reviewer consolidates all currently observable Critical/Important/Minor findings. Critical + Important form the frozen blocking set; Minor is non-blocking unless acceptance explicitly requires it.

On CHANGES_REQUESTED, return the full frozen blocking set to the owner for one batched fix. The next reviewer action is DELTA_REVIEW: verify those fixes and adjacent contracts touched by them, not another unrestricted audit.

Normal sprint: maximum one fix cycle. Safety/security/accounting/ledger/risk/OMS/reconciliation/migration/shared-contract work may receive one coordinator-authorized emergency second cycle with a recorded reason. If blockers remain after the allowed cycle(s), set BLOCKED, preserve evidence and request root-cause/redesign review. Never reset the cycle by changing agents.

A new blocker discovered during DELTA_REVIEW is accepted only when introduced by the fix or when it is a newly discovered Critical defect that invalidates the previous acceptance/safety verdict. Other new Important/Minor observations are recorded as backlog/change request.

On DONE recompute descendants, never recursively run every unblocked optional track. Data/compute budget and owner activation remain independent admission checks.

## Verification scheduling

Use risk-based checks:

- focused tests/static/diff checks for every change;
- affected subsystem/negative/recovery checks for high-risk or shared-contract changes;
- full repository/security/release suite at integration checkpoints or release candidate qualification, and earlier when blast radius requires it.

Do not schedule the largest suite after every local patch by default.

## Idempotency and audit

Assignment key = sprint + base SHA + claim generation. Review key = sprint + exact code SHA + reviewer identity + review phase. Same report cannot mark a different SHA done. Record all transitions, time and reason. No auto-merge. If no callable agent runner exists, follow workflows manually; documentation is not a claim of background execution.

## Implementation boundary

Any future automatic coding supervisor needs a separate change request, capability decomposition and tool/permission design. Do not slip its implementation into AGENT-01, whose scope is research curator policy.
