# Coordination protocol

## Start a batch

1. Check the sprint manifest and working-tree status once.
2. Pick READY sprints with DONE dependencies. Batch independent sprints when their file scopes do not overlap.
3. Assign one owner per sprint and one writer per shared path. Record only sprint ID, owner and paths when parallel work makes ownership ambiguous; no separate pre-work dossier is required.
4. Use the current checkout by default. Create a worktree only when isolation is needed or requested. Preserve all unrelated and user-owned changes.

Read each sprint spec, its relevant required references and dependency handoff. Reuse context already read in this task. Start coding when scope and dependencies are clear; do not wait for a planning ceremony or routine approval.

## Build and checkpoint

- Keep changes scoped and use the smallest behavior-level regression check. Show RED when practical, then GREEN.
- Run focused checks by default. Run broad suites only for shared contracts, schemas/migrations, broad refactors or release gates.
- Commit coherent, passing slices as they are ready. Stage explicit owned paths; never include another owner's or user's work.
- Keep one concise handoff per sprint: exact SHA, changed scope, commands/results, review state and external gates. Link existing evidence instead of copying it.

## Review and close

An independent reviewer checks the final batch SHA once, verifies each sprint's acceptance criteria, and probes risk-specific negative cases. Record a separate PASS/CHANGES_REQUESTED result for each sprint in the batch. Critical/Important findings block DONE; fixes are scoped and the changed SHA is reviewed again. Preserve review-round count.

After review, the coordinator updates all affected manifest entries and generated projections in one pass. Only independent PASS plus evidence permits DONE. Shared manifest/projection files have one coordinator writer. If review is unavailable, leave REVIEW honestly.

If work is interrupted, preserve changes and report the last committed SHA and remaining scope. Never reset/clean another owner's work. No push, merge, deployment, live host change, credential access or trading action without explicit task authorization.
