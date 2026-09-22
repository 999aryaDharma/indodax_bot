# parallel-plan

**Goal:** Plan independent work without shared-file races.

**Read:** `_BASELINE.md`, READY nodes, dependency contracts, worktrees, shared-path list, and host budget.

**Steps:** Partition by ownership; list path/schema/migration overlaps; serialize manifest, central registries, CI, and migrations; assign one owner/reviewer/worktree per unit; publish merge order without merging.

**Output:** Parallel batch, serialized edges, owner/reviewer map, allowed paths, resource limits, and blockers. DAG independence alone is not permission to write concurrently.
