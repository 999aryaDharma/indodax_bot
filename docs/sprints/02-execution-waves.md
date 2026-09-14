# Execution waves

Depth in full dependency DAG, not days or weeks. Historical DONE entries remain to show lineage. Work in same wave is only theoretically parallel.

## Ownership exclusions

Central catalog/config, manifest/status/index, SQLite migrations, CI/pyproject, src/main.py and src/telegram_bot.py need one named owner per edit window. Feature technical and context implementations may run in separate worktrees after registry stabilizes; common config edited by registry owner. M01/M02 share trainer interfaces; serialize those edits. Host concurrency policy overrides theoretical DAG parallelism.

## Computed initial queue

FEAT-01, COST-01. Verify external gates and shared-file ownership before claim.

## Wave 0

- BASE-01 — Offline verification harness [DONE; CORE]

## Wave 1

- BASE-02 — Reachable bullish risk reward [DONE; CORE]
- BASE-03 — Trade v2 ownership parsing [DONE; CORE]
- BASE-04 — Exact paper accounting migration [DONE; CORE]
- DATA-01 — Canonical market contracts [DONE; CORE]

## Wave 2

- BASE-05 — Unbiased signal observations [DONE; CORE]
- DATA-02 — Durable immutable publication [DONE; CORE]
- COST-01 — Time-valid exchange cost schedules [READY; CORE]

## Wave 3

- BASE-06 — Baseline trust checkpoint [DONE; CORE]
- DATA-03 — Auditable candle backfill [DONE; CORE]
- DATA-05 — Reliable forward market collection [DONE; CORE]
- LED-01 — Balanced research postings [PLANNED; CORE]

## Wave 4

- DATA-04 — Snapshot quality decisions [DONE; CORE]

## Wave 5

- UNIV-01 — Point-in-time investable universe [DONE; CORE]
- BAR-01 — Causal time and event bars [DONE; CORE]

## Wave 6

- DATA-06 — Provider-derived reproducible snapshot [DONE; CORE]
- SIM-01 — Conservative execution simulator [PLANNED; CORE]

## Wave 7

- FEAT-01 — Versioned feature registry [READY; CORE]
- SIM-02 — Portfolio risk and circuit breakers [PLANNED; CORE]

## Wave 8

- FEAT-02 — Golden technical and liquidity transforms [PLANNED; CORE]
- FEAT-03 — As-of market context [PLANNED; CORE]
- SIM-03 — Deterministic replay judge [PLANNED; CORE]

## Wave 9

- FEAT-04 — Immutable feature materialization [PLANNED; CORE]
- SIM-04 — Net-cost risk and capacity metrics [PLANNED; CORE]

## Wave 10

- LABEL-01 — Execution-aligned net return labels [PLANNED; CORE]
- STRAT-01 — Declarative strategy protocol [PLANNED; CORE]
- EVAL-01 — Immutable experiment registry [PLANNED; CORE]
- LOB-01 — Forward book dataset eligibility [PLANNED; EXPERIMENTAL]

## Wave 11

- LABEL-02 — Triple barrier outcomes [PLANNED; CORE]
- C01-01 — Donchian breakout [PLANNED; CORE]
- C07-01 — Bollinger RSI reversion [PLANNED; CORE]
- C02-01 — EMA pullback [PLANNED; CORE]
- C03-01 — Time series momentum [PLANNED; CORE]
- C04-01 — Cross sectional momentum [PLANNED; CORE]
- S01-01 — Liquidity screened breakout [PLANNED; CORE]
- S02-01 — Squeeze expansion [PLANNED; CORE]
- C05-01 — Volatility breakout [PLANNED; EXTENSION]
- C06-01 — Directional trend strength [PLANNED; EXTENSION]
- C08-01 — Multi timeframe confirmation [PLANNED; EXTENSION]
- C09-01 — VWAP deviation reversion [PLANNED; EXTENSION]
- C11-01 — Volatility allocation [PLANNED; EXTENSION]
- S03-01 — Abnormal volume continuation [PLANNED; EXTENSION]
- S04-01 — Order flow imbalance [PLANNED; EXPERIMENTAL]
- S05-01 — Micro pullback [PLANNED; EXTENSION]
- S06-01 — Post listing maturation [PLANNED; EXTENSION]
- S08-01 — Passive mean reversion [PLANNED; EXPERIMENTAL]
- S09-01 — Tail risk abstention [PLANNED; EXTENSION]
- EVAL-02 — Hard gates and selection diagnostics [PLANNED; CORE]
- JOB-01 — Durable leased jobs [PLANNED; CORE]

## Wave 12

- SPLIT-01 — Sealed purged chronological folds [PLANNED; CORE]
- C10-01 — Regime ensemble [PLANNED; CORE]
- C12-01 — Relative strength rotation [PLANNED; EXTENSION]
- S07-01 — Small cap rotation [PLANNED; EXTENSION]
- JOB-02 — Resource-aware idle admission [PLANNED; CORE]
- OPS-02 — Snapshot transfer and restore [PLANNED; CORE]

## Wave 13

- TRAIN-01 — Verified training dataset assembly [PLANNED; CORE]
- EVAL-03 — Sealed candidate lifecycle [PLANNED; CORE]
- OPS-03 — Storage retention and integrity maintenance [PLANNED; CORE]

## Wave 14

- ML-01 — Train-only preprocessing [PLANNED; CORE]
- REPORT-01 — Compact experiment reports [PLANNED; CORE]

## Wave 15

- ML-02 — Held-out calibration and cost mapper [PLANNED; CORE]

## Wave 16

- ML-03 — Bounded trial search [PLANNED; CORE]

## Wave 17

- M01-01 — Calibrated logistic baseline [PLANNED; CORE]

## Wave 18

- M02-01 — XGBoost challenger [PLANNED; CORE]

## Wave 19

- ML-04 — Portable model bundles and replay [PLANNED; CORE]

## Wave 20

- JOB-03 — Evaluator-controlled research DAG [PLANNED; CORE]
- SHADOW-01 — Auditable forward paper decisions [PLANNED; CORE]
- M03-01 — Random forest regime gate [PLANNED; EXTENSION]
- M04-01 — Quantile risk regression [PLANNED; EXTENSION]
- M05-01 — Meta-label signal filter [PLANNED; EXTENSION]
- M06-01 — Market anomaly risk gate [PLANNED; EXTENSION]

## Wave 21

- SHADOW-02 — Shared capital reconciliation [PLANNED; CORE]
- AGENT-01 — Governed research curator [PLANNED; CORE]

## Wave 22

- SHADOW-03 — Champion replacement gate [PLANNED; CORE]
- QA-01 — Wave 1 tournament checkpoint [PLANNED; CORE]
- OPS-01 — Host profiles and service lifecycle [PLANNED; CORE]
- REPORT-02 — Read-only Telegram research status [PLANNED; CORE]

## Wave 23

- DL-01 — Isolated resumable neural training [PLANNED; EXTENSION]
- R01-01 — Constrained allocation feasibility [PLANNED; EXPERIMENTAL]
- QA-02 — Boundary security verification [PLANNED; CORE]
- QA-03 — Capacity and crash recovery qualification [PLANNED; CORE]

## Wave 24

- D01-01 — Tabular MLP baseline [PLANNED; EXTENSION]
- DL-02 — Causal sequence datasets [PLANNED; EXTENSION]
- F01-01 — Foundation provenance gate [PLANNED; EXPERIMENTAL]
- REL-01 — Paper research release candidate [PLANNED; CORE]

## Wave 25

- D02-01 — Causal TCN baseline [PLANNED; EXPERIMENTAL]
- G01-01 — Point-in-time graph challenger [PLANNED; EXPERIMENTAL]
- F01-02 — Staged foundation adaptation [PLANNED; EXPERIMENTAL]
- L01-01 — DeepLOB baseline [PLANNED; EXPERIMENTAL]

## Wave 26

- D03-01 — ResNet LSTM challenger [PLANNED; EXPERIMENTAL]
- D04-01 — Compact iTransformer challenger [PLANNED; EXPERIMENTAL]
- L02-01 — TLOB style challenger [PLANNED; EXPERIMENTAL]
