# fix-review

**Goal:** Resolve review findings without feature expansion.

**Read:** `_BASELINE.md`, the exact reviewed SHA, report, and fix-round count.

**Steps:** Reproduce each finding as a regression; apply the smallest root correction; run adjacent invariants; record the new SHA and finding-by-finding evidence. At five unresolved rounds, preserve evidence and set `BLOCKED`.

**Output:** New commit SHA, focused/full exits, each finding disposition, remaining risk, and status `REVIEW`—never self-approved `DONE`.
