# Absolute drawdown documentation handoff

Date: 2026-09-24. Source HEAD: `5eae6e8`.

Scope: owner-approved IDR 100,000 drawdown from adjusted peak equity supersedes initial-capital 20% rule. Records reinvestment, negative-month evaluation, trading-cost-only return target and operator absence of 8-12 hours. Updates program, CR, ADR-010, PM-08/PM-09/API-04/UI-03 and OPS-01/QA-03 specs plus manifest. No status/dependency change, code, active configuration, live account access or deployment.

Checks: Windows PowerShell, `C:/Users/User/miniconda3/envs/ML/python.exe docs/quality/validate_planning.py` PASS (134 nodes, 264 edges, zero cycles); `git diff --check -- docs` PASS. No runtime tests apply to this docs-only slice. New acceptance mappings are planned, not historical PASS evidence. Projections are unchanged. Other implementer's COST-01 handoff and user files are excluded.

Independent review: pending on the exact documentation commit containing this handoff, round 1. No implementation task is marked DONE.

Open decisions/gates: cash-flow peak adjustment, live per-trade/aggregate/daily risk, notification and detailed incident policies remain to be specified/qualified. Existing manual resume and write gates remain; absence of operator response is not a guarantee of execution during an outage. The absolute allowance is an action trigger, not a guaranteed realized-loss ceiling.
