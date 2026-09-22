# re-review

**Goal:** Verify only the requested fixes on a new SHA.

**Read:** `_BASELINE.md`, prior findings, old/new SHA, and the minimal fix/shared-contract diff.

**Steps:** Reproduce old failure; verify new behavior and adjacent invariants; close or retain each finding; preserve cumulative round count; report new Critical/Important findings as blockers.

**Output:** Finding-by-finding PASS/OPEN, exact commands/exits, new SHA, regression risk, and independent verdict.
