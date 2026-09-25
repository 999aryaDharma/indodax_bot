# two-agent-handoff

**Goal:** Transfer only the context the receiver needs to continue or review safely.

**Read:** `_BASELINE.md`, sprint, owner/reviewer, base/code/evidence SHAs and changed paths.

**Steps:**

1. Reuse the sprint handoff as the canonical packet; do not duplicate the same narrative in multiple reports.
2. Record only:
   - sprint/status;
   - owner/reviewer;
   - base/code/evidence SHA;
   - changed paths;
   - AC → exact test/result mapping;
   - contracts/migrations actually changed;
   - known risks/deviations/open blockers;
   - rollback/recovery note when relevant.
3. Receiver verifies Git state and the listed evidence before acting.
4. During fix handoff, send only the frozen blocking finding dispositions and delta evidence; do not reconstruct the whole original review.

**Output:** One receiver-ready canonical packet with no duplicated prose or invented progress.
