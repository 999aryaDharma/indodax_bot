# pre-merge

**Goal:** Qualify one exact branch diff for authorized integration.

**Read:** `_BASELINE.md`, authorized scope, target branch, independent verdict, and fresh evidence SHA.

**Steps:** Check conflicts, untracked/user files, secrets/data blobs, docs/tests/release gates, and rollback. Produce the merge summary; merge only when the user explicitly authorized it.

**Output:** Exact diff/SHA, independent verdict, checks/exits, unresolved risks, and whether the branch is ready or blocked.
