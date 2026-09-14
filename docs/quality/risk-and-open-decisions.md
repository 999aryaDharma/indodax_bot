# Risk, external evidence and cost register

Unknown facts are explicit gates, not fabricated defaults. Owner roles below are responsibilities to assign, not claims an individual has accepted work.

| ID | Risk / unresolved fact | Affected capability | Required evidence / action | Blocking scope | Owner role |
|---|---|---|---|---|---|
| R-01 | Official historical candles may not reach 2018 reliably | DATA-03, SPLIT-01 | Per-pair first_reliable_at, gaps, licensing/source audit | Historical claim for unavailable period | Data owner |
| R-02 | Historical cost/tax/CFX schedule unknown | COST-01, SIM/LABEL | Dated official sources + intervals; unknown remains exploratory | Promotion on affected dates | Research owner |
| R-03 | Existing 2024/2025 data already inspected | SPLIT-01, EVAL-03 | Exposure log by hypothesis family; freeze genuinely unseen period | Sealed claim | Evaluator reviewer |
| R-04 | Actual September host RAM/GPU/disk/workload unknown | JOB-02, OPS-01, QA-03 | Local host probe and representative benchmark | Active heavy jobs / service release | Operator |
| R-05 | Paid cap/history source quota and license unknown | UNIV-01, F01 | Official plan/rights/cutoff/checksum audit before acquisition | Acquisition, redistribution and promotion | Data owner |
| R-06 | No sufficient forward LOB collection proven | LOB-01, L01/L02, S04/S08 | >=90 days PASS plus effective samples/regimes/continuity | Real LOB run eligibility | Data owner |
| R-07 | No qualified forward champion yet | SHADOW-03 | >=90 days AND >=100 closed forward trades with risk compliance | Champion replacement | Evaluator |
| R-08 | Restore RPO/RTO and retention not measured | OPS-02/03, REL-01 | Rehearsal on target host and owner-approved objectives | Service activation | Operator |
| R-09 | Dependency versions loosely ranged; old tmp environment gone | ML-04, OPS-01, REL-01 | Reproducible lock per selected host; test import isolation | Reproducible run/release | Implementer |
| R-10 | Cross-currency valuation for USDT unproven | SIM/LABEL | Versioned conversion and separate unit/currency accounting | Aggregated IDR claim for USDT | Judge owner |
| R-11 | Legacy private read secrets/old deployment may still exist operationally | QA-02, OPS-01 | Authorized read-only config audit, no secret outputs | Activation on real host | Operator |
| R-12 | Advanced strategy hyperparameters not empirical recommendations | Catalog extensions | Registered hypothesis/config and train-only search budget before run | Research execution | Research owner |

## Budget method

Virtual Rp500k is simulation capital, not project development budget. No user project-budget amount is assumed. Track separately: data subscription/license cost, storage growth, compute hours/power, backup copies, hardware upgrade and agent usage. Forecast using measured bytes/day per pair × retention × copies; trials × folds × seeds × measured run cost. Report low/base/high scenarios from actual probes and source quotes, not invented prices. Paid acquisition requires owner authorization; no purchase is made by this docs task.

## Default policies versus factual evidence

Risk defaults inherited: big-cap risk/trade0.50%, open1%, allocation40%; small-cap0.25%, open0.50%, allocation25%; shared max2 positions. Daily loss1.5%, weekly4%, drawdown8% are versioned simulator defaults. Daily/weekly boundaries UTC; include realized+unrealized losses, persist halt. Drawdown halt requires audited owner reset. Min order example Rp25k is dated legacy input: verify current/historical applicability in COST-01, never treat as freshly confirmed rule.

Promotion defaults inherited: pooled100 trades, relevant regime20 where present, positive net expectancy/PF>1, 1.5x cost stress resilient, parameter plateau, concentration review. Statistical evidence sufficiency and uncertainty must accompany numbers. PBO/DSR unavailable for inadequate samples is not an invented favorable score.
