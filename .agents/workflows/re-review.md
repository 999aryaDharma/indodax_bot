# re-review

**Goal:** Delta-verify the requested fixes on a new SHA; do not perform a second unrestricted sprint audit.

**Read:** `_BASELINE.md`, frozen blocking findings, old/new SHA, regression evidence, and only the fix diff plus necessary adjacent shared contracts.

**Steps:**

1. Verify each previously blocking finding against the new SHA and reproduce its regression evidence.
2. Inspect adjacent behavior actually touched by the fix for fix-induced breakage.
3. Close or retain each frozen finding.
4. Do not reopen the sprint for unrelated new Important or Minor observations; record those as backlog/change request.
5. A new blocking finding is permitted only when:
   - it was introduced by the fix; or
   - it is a newly discovered **Critical** defect proving the previous acceptance/safety verdict invalid.
6. If all blocking findings are closed, PASS. If blockers remain, use the remaining allowed cycle from `AGENTS.md`/`_BASELINE.md`; if no cycle remains, set `BLOCKED` for root-cause/redesign review.

**Output:** Finding-by-finding PASS/OPEN, exact commands/exits, new SHA, any fix-induced/new Critical blocker, regression risk and independent verdict.
