# review-sprint

**Goal:** Independently falsify one exact sprint SHA in one comprehensive pass.

**Read:** `_BASELINE.md`, immutable code SHA, handoff, sprint spec, reviewer checklist, and affected production interfaces.

**Steps:**

1. Inspect the entire scoped diff and relevant fixtures/contracts once, not only the happy path.
2. Reproduce meaningful positive, negative and adversarial behavior; check units, provenance, rollback, scope, security and failure recovery as applicable.
3. Collect all currently observable findings before issuing the verdict. Do not deliberately drip-feed one finding per review round.
4. Classify findings:
   - **Critical:** safety/security/data/accounting/chronology/order/risk/recovery integrity failure.
   - **Important:** acceptance/public-contract/material correctness/persistence/state/evidence failure.
   - **Minor:** non-blocking cleanup, naming, style, optional polish or micro-optimization unless acceptance explicitly requires it.
5. Freeze the accepted Critical + Important set for this reviewed SHA. Minor items go to follow-up/backlog and do not force a fix round.
6. Issue separate spec and quality verdicts. PASS only when no Critical/Important finding remains for the reviewed SHA.

**Output:** Exact SHA, commands/exits, complete consolidated Critical/Important/Minor findings, frozen blocking set, spec verdict, quality verdict and PASS/CHANGES_REQUESTED.
