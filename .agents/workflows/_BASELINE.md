# Shared workflow baseline

Apply this baseline before any workflow-specific step.

1. Check `AGENTS.md`, manifest and `git status` once. Read the chosen sprint, relevant references, dependency handoffs and affected code; reuse context already read.
2. Batch READY sprints only when dependencies are DONE and paths are independent. Assign one owner per sprint and one writer per shared path. Preserve user WIP (`dashboard.pen`, `DESIGN.md`, unrelated changes); never reset, clean, overwrite or stage it.
3. Work in the current checkout by default. Use a worktree only when isolation is needed or requested. Start without a separate plan/claim dossier when scope is clear.
4. Production Main is live. Control-plane tasks are read-only: no live credentials, orders, withdrawals, activation, host changes or runtime DB mutation.
5. Code: add the smallest behavior regression, show RED when practical, make the root fix, then run focused GREEN and relevant lint/regression checks. Run broad suites for shared contracts, schema/migration or release changes. Docs: validate planning files only when changed and run `git diff --check`.
6. Commit coherent passing slices promptly. Keep a concise handoff with exact SHA, commands/results, scope, review state and remaining gates. Missing evidence is `REVIEW` or `BLOCKED`, never PASS.
7. An independent reviewer checks the exact final batch SHA against each sprint's acceptance criteria and risk-specific negative cases. Implementers cannot self-approve or mark `DONE`.
8. Never bypass dependencies, manufacture status/reviewer identity, expand scope, or merge/push/deploy without explicit authorization. Do not ask again for authorization already given.

Shared stop conditions: unsafe capability, unknown ownership, dirty-path conflict, missing dependency, missing evidence, required external resource, or any test that cannot be reproduced honestly.
