# Execution rules

1. A claim names sprint, owner identity, worktree path, base SHA and bounded file scope. A second owner cannot claim the same sprint.
2. Verify dependencies and real execution gates; do not edit manifest to manufacture eligibility.
3. Implement only acceptance behaviors. Additional ideas go to CR; findings that reveal unsafe prerequisites block downstream work.
4. Tests use isolated fixtures and public contracts. No real orders, accounts, live DB mutations or uncontrolled networking.
5. Stage scoped paths; inspect diff; record exact SHA. Do not stage another worktree's WIP.
6. Review packet contains source SHA, acceptance evidence, test command exits, risk/migration notes and deviations.
7. Independent reviewer returns separate spec and quality verdicts; same author cannot approve both sides of their own implementation.
8. Coordinator updates status and projections after PASS; stale or cancelled agents cannot transition state.
9. Major policy changes require review outside the affected candidate's author. Never optimize gates against a candidate result.
