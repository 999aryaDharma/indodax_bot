# Shared workflow baseline

Apply this baseline before any workflow-specific step.

1. Read `AGENTS.md`, the manifest, the chosen sprint/spec, dependency handoffs, and only affected code.
2. Inspect `git status` and worktrees. Preserve user WIP (`dashboard.pen`, `DESIGN.md`, unrelated changes); never reset, clean, overwrite, or stage another owner's paths.
3. Confirm one bounded owner, branch/worktree, base SHA, reviewer, dependencies, external gates, and allowed paths. The manifest is the only status authority.
4. Keep production paper/shadow-only: no credentials, real orders, withdrawals, live activation, uncontrolled network, or runtime database mutation.
5. Code: write a behavior RED test, implement the smallest root fix, run focused GREEN tests, then the risk-appropriate affected checks. Docs: run planning validator and `git diff --check`.
6. Verification is risk-based:
   - focused checks for every change;
   - affected subsystem/negative/recovery checks for high-risk or shared-contract changes;
   - full repository/release checks at integration/release checkpoints or earlier when the blast radius is broad.
   Do not rerun an expensive full suite after every local patch unless the testing strategy or affected contract requires it.
7. Record exact command, exit, environment, source SHA, changed paths, assumptions, failures, and remaining gates. Missing evidence is `REVIEW` or `BLOCKED`, never PASS.
8. Implementers stop at acceptance criteria and submit an exact-SHA handoff; they cannot self-approve or mark `DONE`. Reviewers independently falsify spec and quality.
9. The first review is comprehensive and consolidated. Critical/Important findings block; Minor findings do not block unless explicitly required by acceptance. Accepted blocking findings are fixed as one batch where practical.
10. Re-review is delta verification of the fix and adjacent touched contracts, not another unrestricted audit. New unrelated Important/Minor observations become backlog/change request.
11. Normal work gets one fix cycle. Safety/security/accounting/ledger/risk/OMS/reconciliation/migration/shared-contract work may receive one coordinator-authorized emergency second cycle. Persistent failure becomes `BLOCKED` for root redesign.
12. Never bypass dependencies, manufacture status/reviewer identity, expand scope, or merge/push/deploy without explicit authorization.

Shared stop conditions: unsafe capability, unknown ownership, dirty-path conflict, missing dependency, missing evidence, required external resource, or any required test that cannot be reproduced honestly.
