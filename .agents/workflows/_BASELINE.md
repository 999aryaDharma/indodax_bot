# Shared workflow baseline

Apply this baseline before any workflow-specific step.

1. Read `AGENTS.md`, the manifest, the chosen sprint/spec, dependency handoffs, and only affected code.
2. Inspect `git status` and worktrees. Preserve user WIP (`dashboard.pen`, `DESIGN.md`, unrelated changes); never reset, clean, overwrite, or stage another owner's paths.
3. Confirm one bounded owner, branch/worktree, base SHA, reviewer, dependencies, external gates, and allowed paths. The manifest is the only status authority.
4. Keep production paper/shadow-only: no credentials, real orders, withdrawals, live activation, uncontrolled network, or runtime database mutation.
5. Code: write a behavior RED test, implement the smallest root fix, run focused GREEN tests, then required regression/lint checks. Docs: run planning validator and `git diff --check`.
6. Record exact command, exit, environment, source SHA, changed paths, assumptions, failures, and remaining gates. Missing evidence is `REVIEW` or `BLOCKED`, never PASS.
7. Implementers stop at acceptance criteria and submit exact-SHA handoff; they cannot self-approve or mark `DONE`. Reviewers independently falsify spec and quality, preserve fix rounds, and report severity.
8. Never bypass dependencies, manufacture status/reviewer identity, expand scope, or merge/push/deploy without explicit authorization.

Shared stop conditions: unsafe capability, unknown ownership, dirty-path conflict, missing dependency, missing evidence, required external resource, or any test that cannot be reproduced honestly.
