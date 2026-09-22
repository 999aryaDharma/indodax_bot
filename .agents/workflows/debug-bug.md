# debug-bug

**Goal:** Diagnose actual behavior before editing.

**Read:** `_BASELINE.md`, then capture SHA, environment, input identity, logs, expected/actual behavior, and classify technical invalidity versus bad strategy.

**Steps:** Reproduce minimally; trace all callers; isolate root cause; preserve the failing artifact; add a scoped regression and fix only the shared responsible boundary.

**Output:** Reproduction command/exit, root cause, affected paths, regression evidence, dependency impact, and `BLOCKED` when proof or environment is missing.
