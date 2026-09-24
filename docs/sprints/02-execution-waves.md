# Execution waves

Depth in full dependency DAG, not days or weeks. Historical DONE entries remain to show lineage. Work in same wave is only theoretically parallel.

## Ownership exclusions

Central catalog/config, manifest/status/index, SQLite migrations, CI/pyproject, src/main.py and src/telegram_bot.py need one named owner per edit window. Feature technical and context implementations may run in separate worktrees after registry stabilizes; common config edited by registry owner. M01/M02 share trainer interfaces; serialize those edits. Host concurrency policy overrides theoretical DAG parallelism.

## Computed initial queue

None. Verify external gates and shared-file ownership before claim.

## Wave 0

- BASE-01 — Offline verification harness [DONE; CORE]
- DOC-01 — Frozen architecture audit and delivery program [DONE; CORE]
- API-00 — Shared API envelope, error, provenance and capability contracts [DONE; CORE]
- UI-00 — Kumo and Geist shell foundation with typed API client [DONE; CORE]

## Wave 1

- BASE-02 — Reachable bullish risk reward [DONE; CORE]
- BASE-03 — Trade v2 ownership parsing [DONE; CORE]
- BASE-04 — Exact paper accounting migration [DONE; CORE]
- DATA-01 — Canonical market contracts [DONE; CORE]
- RP-01 — Shared SignalIntent ownership with compatibility [DONE; CORE]
- API-03 — Fail-closed read capability policy and audit context [DONE; CORE]

## Wave 2

- BASE-05 — Unbiased signal observations [DONE; CORE]
- DATA-02 — Durable immutable publication [DONE; CORE]
- COST-01 — Time-valid exchange cost schedules [REVIEW; CORE]
- RW0-01 — Immutable Workbench domain manifests [DONE; CORE]
- UI-01 — Production and Research context navigation with capability boundary [DONE; CORE]

## Wave 3

- BASE-06 — Baseline trust checkpoint [DONE; CORE]
- DATA-03 — Auditable candle backfill [DONE; CORE]
- DATA-05 — Reliable forward market collection [DONE; CORE]
- LED-01 — Balanced research postings [DONE; CORE]
- PM-01 — Authoritative fail-closed pre-write gate [DONE; CORE]

## Wave 4

- DATA-04 — Snapshot quality decisions [DONE; CORE]
- PM-02 — Atomic financial execution state and recovery [DONE; CORE]

## Wave 5

- BAR-01 — Causal time and event bars [DONE; CORE]
- UNIV-01 — Point-in-time investable universe [DONE; CORE]
- PM-03 — Recovery mode and durable operator risk governance [DONE; CORE]
- PM-04 — Venue parser cancellation and supported order semantics [DONE; CORE]

## Wave 6

- DATA-06 — Provider-derived reproducible snapshot [DONE; CORE]
- SIM-01 — Conservative execution simulator [REVIEW; CORE]
- API-01 — Production service-derived read models [DONE; CORE]

## Wave 7

- FEAT-01 — Versioned feature registry [DONE; CORE]
- SIM-02 — Portfolio risk and circuit breakers [REVIEW; CORE]
- RW1-01 — Reusable immutable dataset registry [DONE; CORE]
- API-02 — Read-only Production API application and routes [DONE; CORE]

## Wave 8

- FEAT-02 — Golden technical and liquidity transforms [DONE; CORE]
- FEAT-03 — As-of market context [DONE; CORE]
- SIM-03 — Deterministic replay judge [REVIEW; CORE]
- RP-03 — Shared portfolio sizing and risk semantics [PLANNED; CORE]
- UI-02 — Read-only Production operational pages [DONE; CORE]
- API-07 — Tailscale-authenticated Production read composition [DONE; CORE]

## Wave 9

- FEAT-04 — Immutable feature materialization [DONE; CORE]
- SIM-04 — Net-cost risk and capacity metrics [REVIEW; CORE]
- UI-09 — Same-origin Production API access [DONE; CORE]

## Wave 10

- EVAL-01 — Immutable experiment registry [REVIEW; CORE]
- LABEL-01 — Execution-aligned net return labels [REVIEW; CORE]
- LOB-01 — Forward book dataset eligibility [DONE; EXPERIMENTAL]
- STRAT-01 — Declarative strategy protocol [REVIEW; CORE]

## Wave 11

- EVAL-02 — Hard gates and selection diagnostics [REVIEW; CORE]
- LABEL-02 — Triple barrier outcomes [REVIEW; CORE]
- JOB-01 — Durable leased jobs [REVIEW; CORE]
- C01-01 — Donchian breakout [REVIEW; CORE]
- C02-01 — EMA pullback [REVIEW; CORE]
- C03-01 — Time series momentum [REVIEW; CORE]
- C04-01 — Cross sectional momentum [REVIEW; CORE]
- C05-01 — Volatility breakout [PLANNED; EXTENSION]
- C06-01 — Directional trend strength [PLANNED; EXTENSION]
- C07-01 — Bollinger RSI reversion [REVIEW; CORE]
- C08-01 — Multi timeframe confirmation [PLANNED; EXTENSION]
- C09-01 — VWAP deviation reversion [PLANNED; EXTENSION]
- C11-01 — Volatility allocation [PLANNED; EXTENSION]
- S01-01 — Liquidity screened breakout [REVIEW; CORE]
- S02-01 — Squeeze expansion [REVIEW; CORE]
- S03-01 — Abnormal volume continuation [PLANNED; EXTENSION]
- S04-01 — Order flow imbalance [PLANNED; EXPERIMENTAL]
- S05-01 — Micro pullback [PLANNED; EXTENSION]
- S06-01 — Post listing maturation [PLANNED; EXTENSION]
- S08-01 — Passive mean reversion [PLANNED; EXPERIMENTAL]
- S09-01 — Tail risk abstention [PLANNED; EXTENSION]
- RW2-01 — Durable versioned strategy registry [PLANNED; CORE]

## Wave 12

- SPLIT-01 — Sealed purged chronological folds [REVIEW; CORE]
- OPS-02 — Snapshot transfer and restore [REVIEW; CORE]
- JOB-02 — Resource-aware idle admission [REVIEW; CORE]
- C10-01 — Regime ensemble [REVIEW; CORE]
- C12-01 — Relative strength rotation [PLANNED; EXTENSION]
- S07-01 — Small cap rotation [PLANNED; EXTENSION]

## Wave 13

- EVAL-03 — Sealed candidate lifecycle [REVIEW; CORE]
- TRAIN-01 — Verified training dataset assembly [REVIEW; CORE]
- OPS-03 — Storage retention and integrity maintenance [REVIEW; CORE]
- DATA-07 — Selectable public collection and coverage workflow [PLANNED; CORE]

## Wave 14

- ML-01 — Train-only preprocessing [REVIEW; CORE]
- REPORT-01 — Compact experiment reports [REVIEW; CORE]

## Wave 15

- ML-02 — Held-out calibration and cost mapper [REVIEW; CORE]

## Wave 16

- ML-03 — Bounded trial search [REVIEW; CORE]

## Wave 17

- M01-01 — Calibrated logistic baseline [REVIEW; CORE]

## Wave 18

- M02-01 — XGBoost challenger [REVIEW; CORE]

## Wave 19

- ML-04 — Portable model bundles and replay [REVIEW; CORE]

## Wave 20

- M03-01 — Random forest regime gate [REVIEW; EXTENSION]
- M04-01 — Quantile risk regression [REVIEW; EXTENSION]
- M05-01 — Meta-label signal filter [REVIEW; EXTENSION]
- M06-01 — Market anomaly risk gate [REVIEW; EXTENSION]
- JOB-03 — Evaluator-controlled research DAG [REVIEW; CORE]
- SHADOW-01 — Auditable forward paper decisions [REVIEW; CORE]
- RW2-02 — Model registry and offline training services [PLANNED; CORE]

## Wave 21

- AGENT-01 — Governed research curator [REVIEW; CORE]
- SHADOW-02 — Shared capital reconciliation [REVIEW; CORE]
- RW2-03 — Typed declarative pipeline composer [PLANNED; CORE]

## Wave 22

- OPS-01 — Host profiles and service lifecycle [REVIEW; CORE]
- REPORT-02 — Read-only Telegram research status [REVIEW; CORE]
- SHADOW-03 — Champion replacement gate [REVIEW; CORE]
- QA-01 — Wave 1 tournament checkpoint [REVIEW; CORE]
- RP-02 — Shared candidate feature and exit evaluation [PLANNED; CORE]

## Wave 23

- DL-01 — Isolated resumable neural training [REVIEW; EXTENSION]
- R01-01 — Constrained allocation feasibility [REVIEW; EXPERIMENTAL]
- QA-02 — Boundary security verification [REVIEW; CORE]
- QA-03 — Capacity and crash recovery qualification [REVIEW; CORE]
- RP-04 — Canonical feed and environment runtime adapters [PLANNED; CORE]

## Wave 24

- D01-01 — Tabular MLP baseline [REVIEW; EXTENSION]
- DL-02 — Causal sequence datasets [REVIEW; EXTENSION]
- F01-01 — Foundation provenance gate [REVIEW; EXPERIMENTAL]
- REL-01 — Paper research release candidate [REVIEW; CORE]
- RP-05 — Runtime parity qualification fixtures [PLANNED; CORE]
- RW3-01 — Experiment lifecycle and backtest orchestration [PLANNED; CORE]

## Wave 25

- D02-01 — Causal TCN baseline [REVIEW; EXPERIMENTAL]
- F01-02 — Staged foundation adaptation [REVIEW; EXPERIMENTAL]
- G01-01 — Point-in-time graph challenger [REVIEW; EXPERIMENTAL]
- L01-01 — DeepLOB baseline [REVIEW; EXPERIMENTAL]
- RW4-01 — Immutable candidate packaging and lifecycle [PLANNED; CORE]

## Wave 26

- D03-01 — ResNet LSTM challenger [REVIEW; EXPERIMENTAL]
- D04-01 — Compact iTransformer challenger [REVIEW; EXPERIMENTAL]
- L02-01 — TLOB style challenger [REVIEW; EXPERIMENTAL]
- RW5-01 — Isolated durable forward-shadow agents [PLANNED; CORE]
- RW7-01 — Read-only QuantOps MCP boundary [PLANNED; CORE]
- PM-05 — Candidate-bound release provenance [PLANNED; CORE]

## Wave 27

- RW5-02 — Tournament cohorts leaderboard and qualification [PLANNED; CORE]
- PM-07 — Reviewed account portfolio adoption [PLANNED; CORE]

## Wave 28

- RW9-01 — Promotion request and production export bridge [PLANNED; CORE]
- PM-08 — Shared capital allocation and stop risk sizing [PLANNED; CORE]

## Wave 29

- RW6-01 — Separate shared-capital Portfolio Shadow [PLANNED; CORE]
- PM-09 — Candidate exits and draining strategy replacement [PLANNED; CORE]

## Wave 30

- RW7-02 — Audited QuantOps research mutations [PLANNED; CORE]
- RW8-01 — Research read models and dashboard navigation [PLANNED; CORE]
- API-04 — Guarded Production portfolio and lifecycle commands [PLANNED; CORE]

## Wave 31

- RW8-02 — Workbench form and graph editors [PLANNED; CORE]
- UI-03 — Guarded portfolio and strategy operator workflows [PLANNED; CORE]

## Wave 32

- PM-06 — CI security and operational release evidence [PLANNED; CORE]
