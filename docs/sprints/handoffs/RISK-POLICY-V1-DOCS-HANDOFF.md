# Risk policy v1 documentation handoff

Date: 2026-09-24. Source HEAD: `adea9cc`.

Scope: record separately approved risk-period renewal after completed drawdown close-out, preserved cumulative history, 5% monthly target plus rolling 90-day evaluation, and all 14 policy aspects with DECIDED/PROPOSED/OPEN status. Owner explicitly confirmed defaults for qualification: IDR 4,000 per trade, IDR 10,000 global, IDR 8,000 BTC/ETH/SOL cluster, IDR 15,000 daily loss, two positions, 25% equity notional per pair and 50% total. Update CR/ADR/program and PM-08/PM-09/API-04/UI-03 spec/manifest mappings; no status/dependency changes or runtime implementation.

Checks: Windows PowerShell with ML Python; `python docs/quality/validate_planning.py` PASS (134 nodes, 264 edges, zero cycles); `git diff --check -- docs` PASS. An intermediate encoding error caused a validator failure and was corrected before final validation; final manifest changes affect only the four owned sprint entries. Runtime tests are not applicable. Concurrent implementation code/tests are excluded.

Review: independent exact-commit review pending, round 1. The commit containing this handoff is the review target. No sprint is marked DONE by documentation acceptance.

Open gates: candidate identities, actual venue protection/execution evidence, fees, cash-flow adjustment, daily reset, ranking/liquidity/incident/launch details remain as marked in the decision register. Defaults are approved to evaluate, not live activation proof. Current credentials, live state and deployment are untouched.
