# pre-merge

**Goal:** Qualify an exact integration batch or release-bound branch diff, not re-run a mini release for every small sprint.

**Read:** `_BASELINE.md`, authorized integration scope, target branch, independent sprint verdicts and fresh evidence SHA(s).

**Steps:**

1. Run at an integration checkpoint, when several independently reviewed sprints are being combined, or when an individual high-blast-radius sprint requires immediate integration qualification.
2. Check conflicts, untracked/user files, secrets/data blobs, shared contract compatibility, required docs/tests and rollback.
3. Run the repository-level verification appropriate to the combined blast radius. Do not repeat the largest suite solely because each constituent sprint already passed focused/affected gates.
4. Produce the merge summary; merge only when the user explicitly authorized it.

**Output:** Exact integration diff/SHA(s), contributing independent verdicts, checks/exits, unresolved risks, and whether the integration batch is ready or blocked.
