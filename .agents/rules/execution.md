# Execution rules

1. Assign one owner per sprint and one writer per shared path. Record sprint, owner and paths only when parallel work needs an explicit claim; worktree and base SHA are not mandatory ceremony.
2. Verify dependencies and real execution gates; do not edit manifest to manufacture eligibility.
3. Implement only acceptance behaviors. Additional ideas go to CR; findings that reveal unsafe prerequisites block downstream work.
4. Tests use isolated fixtures and public contracts. No real orders, accounts, live DB mutations or uncontrolled networking.
5. Stage explicit owned paths, inspect the diff, and commit coherent passing slices. Preserve unrelated WIP.
6. Keep one concise handoff with exact SHA, checks/results, scope and unresolved gates; link existing evidence.
7. An independent reviewer checks the exact final batch SHA against every included sprint's acceptance criteria and risk-specific negative cases. The author cannot approve their own work.
8. Coordinator updates all affected status/projection files once after PASS; stale or cancelled agents cannot transition state.
9. Major policy changes require review outside the affected candidate's author. Never optimize gates against a candidate result.
