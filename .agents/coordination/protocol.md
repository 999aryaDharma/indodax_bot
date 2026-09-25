# Coordination protocol

## Start a batch

1. Check the sprint manifest and working-tree status once.
2. Pick READY sprints with DONE dependencies. Batch independent sprints when their file scopes do not overlap.
3. Assign one owner per sprint and one writer per shared path. Record only sprint ID, owner and paths when parallel work makes ownership ambiguous; no separate pre-work dossier is required.
4. Use the current checkout by default. Create a worktree only when isolation is needed or requested. Preserve all unrelated and user-owned changes.

Before editing, coordinator records sprint ID, owner, branch/worktree, base SHA, requested paths and review owner in a handoff/work log. Claims are exclusive for that sprint. Shared paths (`sprint-manifest.json`, main.py, telegram_bot.py, pyproject.toml, CI, central registry and migrations) need explicit single-writer ownership even when DAG nodes are independent. Actual implementation of a lock service is outside this documentation task.

A sprint is one independently reviewable unit, not necessarily one whole agent session. After an owner commits a complete handoff, that owner may claim another independent READY sprint while the prior sprint is under review when the coordinator confirms there is no dependency or shared-path conflict.

## Build and checkpoint

Default lifecycle:

```text
READY
→ IN_PROGRESS
→ REVIEW
→ PASS → DONE
          or
→ CHANGES_REQUESTED
→ one batched fix
→ DELTA_REVIEW
→ PASS → DONE
```

The first independent review is comprehensive and must consolidate all observable findings for the exact reviewed SHA. Critical and Important findings form the frozen blocking set; Minor findings are non-blocking follow-up unless the sprint explicitly makes them acceptance requirements.

The implementer fixes the frozen blocking set in one batch where practical and updates SHA/evidence. Re-review is delta verification: verify the frozen findings and adjacent contracts touched by the fix, not another unrestricted sprint audit.

A new blocker during delta review is valid only when it was introduced by the fix or is a newly discovered Critical defect proving the previous acceptance/safety verdict invalid. Unrelated new Important/Minor observations become backlog/change request.

Normal sprint: one fix cycle. Safety/security/accounting/ledger/risk/OMS/reconciliation/migration/shared-contract sprint: coordinator may authorize one emergency second cycle with recorded reason. Exhausted cycles with unresolved blockers → BLOCKED and root-cause/redesign review. Changing owner/reviewer does not reset the cycle count.

Coordinator releases claim and marks DONE only after independent PASS. A third person/agent can coordinate; cannot substitute self-review for independent review.

## Parallel two-agent use

Codex and Antigravity should be staggered where the DAG and path ownership allow it: while reviewer B reviews sprint A, implementer A may claim a different independent READY sprint. Cross-review is allowed; self-approval is not. Shared-file single-writer ownership always overrides theoretical parallelism.

## Review and close

If owner disappears, preserve dirty worktree and record last heartbeat/time; do not reset/clean. Coordinator may reassign after inspecting state, but new owner resumes from recorded WIP and same fix-cycle count. Merge conflicts require understanding both intended behaviors and rerunning affected acceptance, never blindly ours/theirs. If dependency changes while work runs, rebase review target deliberately and reverify.

After review, the coordinator updates all affected manifest entries and generated projections in one pass. Only independent PASS plus evidence permits DONE. Shared manifest/projection files have one coordinator writer. If review is unavailable, leave REVIEW honestly.

If work is interrupted, preserve changes and report the last committed SHA and remaining scope. Never reset/clean another owner's work. No push, merge, deployment, live host change, credential access or trading action without explicit task authorization.
