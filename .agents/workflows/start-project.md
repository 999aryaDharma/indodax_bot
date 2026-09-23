# start-project

**Goal:** Recover project context on a true cold start, without repeating the full audit on every task.

**Read:** `_BASELINE.md`, `docs/README.md`, master spec, repository audit, branch/worktrees, manifest, imported evidence, and runtime constraints.

**Steps:** On a cold start, validate the manifest and inspect dirty WIP without mutation. On follow-up tasks, reuse established context and check only the active sprint, current working tree and changed dependencies. Identify only the implementation and gates relevant to requested work.

**Output:** Cold start: compact baseline and eligible work. Follow-up: active scope, relevant blocker and next action.
