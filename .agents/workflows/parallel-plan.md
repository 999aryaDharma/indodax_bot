# parallel-plan

**Goal:** Plan independent work without shared-file races.

**Read:** `_BASELINE.md`, READY nodes, dependency contracts, worktrees, shared-path list, and host budget.

**Steps:** Partition by file ownership; serialize shared schemas, migrations, CI and manifest; assign one owner per sprint and one writer per shared path; use worktrees only when needed. Commit independently passing slices; review the batch at the end.

**Output:** Parallel batch, shared-path owner, applicable resource limits and blockers. DAG independence permits parallel work only when file scopes are also disjoint.
