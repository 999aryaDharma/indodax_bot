# fix-review

**Goal:** Resolve the frozen blocking review set without feature expansion.

**Read:** `_BASELINE.md`, exact reviewed SHA, consolidated review report, frozen Critical/Important set, current SHA and fix-cycle count.

**Steps:**

1. Fix all accepted Critical + Important findings in one batch where practical; do not spend a blocking cycle on Minor-only cleanup.
2. For behavioral, safety/security, accounting, persistence, state-machine or public-contract defects, reproduce the failure and add/strengthen regression evidence before the fix.
3. For docs/naming/formatting/non-behavioral cleanup, a new regression test is not mandatory unless the sprint contract requires one.
4. Apply the smallest root correction and verify directly affected/adjacent invariants using the risk-appropriate test tier.
5. Record one new SHA and a finding-by-finding disposition. Do not broaden scope to unrelated reviewer ideas.
6. Normal sprint: one fix cycle total. Safety/security/accounting/ledger/risk/OMS/reconciliation/migration/shared-contract sprint: one coordinator-authorized emergency second cycle is allowed only when documented. Exhausted cycles with an open blocker → `BLOCKED` and root-cause/redesign review.

**Output:** New commit SHA, focused/affected exits, each frozen finding disposition, remaining risk and status `REVIEW`—never self-approved `DONE`.
