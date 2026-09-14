# Sprint status model

Status source: `sprint-manifest.json`. Initial counts: {'DONE': 14, 'READY': 2, 'PLANNED': 76}.
Initial READY: FEAT-01, COST-01. Recommended first: FEAT-01.

| State | Meaning and allowed progression |
|---|---|
| PLANNED | Defined, dependencies incomplete; automatically READY when all are DONE |
| BLOCKED | Specific unresolved issue with reason/evidence; coordinator clears only after resolution |
| READY | Every declared dependency DONE; no active owner yet |
| IN_PROGRESS | One owner claimed READY and has isolated worktree |
| REVIEW | Scoped code committed and evidence submitted |
| CHANGES_REQUESTED | Independent reviewer lists actionable findings; returns REVIEW after fix |
| DONE | Exact reviewed SHA passed acceptance/spec/quality gates |
| PAUSED | Work intentionally suspended, WIP and reason preserved |
| CANCELLED | Removed from active scope through change request; consumers require DAG update |

Transitions: PLANNED → READY → IN_PROGRESS → REVIEW → DONE. REVIEW → CHANGES_REQUESTED → REVIEW. Active work can BLOCKED/PAUSED; clearing recalculates dependency readiness. CANCELLED is not equivalent to DONE. Reopening DONE invalidates readiness of affected descendants; audit already-completed descendants rather than silently rewriting historical evidence.

READY is structural dependency eligibility, not permission to ignore provider, real-data, resource or portfolio activation gates. LOB capability can be implemented with synthetic fixtures while real LOB research runs remain BLOCKED_DATA until coverage is proven. Extension/experimental tracks are not automatically scheduled.

Imported DONE for legacy1–14 is explicitly historical and includes source/evidence references; reviewer identity unavailable is disclosed. No active agent is claimed for original Task15 WIP. This docs task does not start product implementation.

Coordinator updates manifest, then regenerate projections following `docs/quality/STATUS-MAINTENANCE.md` and run validator. No agent may manually change a dependency to DONE solely to unlock itself.
