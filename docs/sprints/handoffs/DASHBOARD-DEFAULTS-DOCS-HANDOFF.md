# Dashboard defaults documentation handoff

Date: 2026-09-24. Source HEAD: `1b77868`.

Scope: amend CR, ADR-010 and Bot Trade Program with configurable default/draft/active settings, initial-capital floor, controlled close-out and manual resume. Extend PM-08, PM-09, API-04 and UI-03 contracts/acceptance mappings in their specs and manifest. No status/dependency changes, runtime code, live account/host access or deployment.

Checks: Windows PowerShell, `C:/Users/User/miniconda3/envs/ML/python.exe docs/quality/validate_planning.py` PASS (134 nodes, 264 edges, zero cycles); `git diff --check -- docs` PASS. Existing generated projections require no change. Runtime tests are not applicable to documentation; added test names are future acceptance requirements, not executed evidence.

Review: independent PASS by `/root/docs_review` on exact documentation SHA `6ef2d13b4ca5391cbede0436a555d0ce7df6225c`, round 1; no Critical/Important findings. Reviewer confirmed spec/manifest parity, unchanged statuses/dependencies, preserved write gates and recovery, and separation of defaults from active policy. Exact-commit diff-check passed; reviewer ran no runtime tests. No implementation sprint is marked DONE by this packet.

External decisions/gates: select live per-trade, aggregate and daily-loss limits after evaluation; approve external cash-flow baseline rules; verify candidate bindings, venue execution/minima/costs, shared-capital evidence and staged release/host qualification. The capital floor is an action threshold, not guaranteed liquidation proceeds.
