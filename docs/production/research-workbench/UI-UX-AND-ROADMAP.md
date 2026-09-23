# Research Workbench — UI/UX and Implementation Roadmap

## Executable program — 2026-09-21

Frozen UI/roadmap requirements below are implemented through the [RW task roadmap](../../implementation/research-workbench/ROADMAP.md) and [runtime parity program](../../implementation/runtime-parity/ROADMAP.md). Backend services/contracts precede MCP mutations and dashboard editing. [Current-state audit](../../implementation/CURRENT-STATE.md) distinguishes existing primitives from missing Workbench services. The sprint manifest owns status; this frozen roadmap does not assert implementation completion.

## 1. Dashboard information architecture

```text
RESEARCH
├── Workbench
├── Strategies
├── Models
├── Pipelines
├── Datasets
├── Experiments
├── Backtests
├── Candidates
└── Tournament
```

Research UI can be highly customizable. Production UI remains intentionally constrained.

## 2. Workbench

Primary action: **New Experiment**.

Support two synchronized editing modes:

### Form Mode
Fast for normal experiments:
- pair/universe;
- timeframe;
- dataset;
- TA strategy;
- filters;
- model(s);
- ensemble;
- thresholds;
- sizing;
- exits;
- execution/cost assumptions.

### Visual Graph Mode
For complex hybrid pipelines:

```text
[Dataset/Pair]
      |
[Indicators]
      |
[TA Strategy]
   /      \
[M02]    [D04]
   \      /
  [Ensemble]
      |
 [Risk/Sizing]
      |
 [Simulator]
```

The graph is a visualization/editor of the same declarative pipeline manifest, not a separate execution engine.

## 3. Dataset experience

New Dataset:
- venue;
- pair;
- timeframe;
- from/to;
- fetch/extend.

Show:
- available coverage;
- requested coverage;
- bars;
- missing intervals;
- duplicates;
- quality status;
- hash/version;
- experiments using the dataset.

Never silently overwrite repaired data; create a new version.

## 4. Experiment detail

Show:
- exact manifest;
- dataset/candidate identities;
- progress/logs;
- equity curve;
- drawdown;
- monthly returns;
- trade distribution;
- fee/turnover;
- regime performance;
- metrics;
- downloadable immutable result artifact.

Allow **Clone Experiment**, never edit a completed experiment.

## 5. Compare mode

Select multiple experiments and compare:
- return;
- max DD;
- PF;
- expectancy;
- Sharpe/Sortino/Calmar;
- trades;
- fees;
- turnover;
- monthly/regime stability;
- equity overlays.

Comparison must not automatically declare a winner.

## 6. Tournament

Primary table:

| Agent | Candidate | Cohort | Equity | Net Return | Max DD | PF | Sharpe | Trades | Age | Qualification |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|

Filters:
- all;
- BTC;
- altcoin;
- trend;
- mean reversion;
- hybrid;
- new;
- qualified;
- retired.

Agent detail:
- isolated wallet/ledger;
- open positions;
- equity curve;
- trade history;
- costs;
- incidents;
- market-event lag;
- candidate manifest;
- qualification checklist.

**Leaderboard rank != production qualification.**

## 7. Portfolio Shadow

Separate screen from Tournament.

Purpose:
- combine selected candidate agents;
- shared virtual cash;
- correlation/capital contention;
- one-position-per-asset policies;
- portfolio concentration/risk;
- compare against isolated tournament results.

## 8. UX visual direction

Use the production dashboard design language:
- Cloudflare-like shell;
- Linear-like spacing/polish;
- Grafana-like observability hierarchy;
- dark graphite surfaces;
- restrained semantic colors;
- tabular numbers;
- no neon/crypto-exchange aesthetic.

Research can be denser and more interactive than Production but must preserve provenance and state clarity.

## 9. Implementation roadmap

### RW0 — contracts
- schemas for dataset/strategy/model/pipeline/experiment/candidate/agent;
- version/hash rules;
- registry interfaces.

### RW1 — dataset registry
- fetch/caching;
- normalize/quality;
- immutable versions;
- history extension.

### RW2 — component registries
- TA strategy registry;
- model registry;
- pipeline manifest validator.

### RW3 — backtest orchestration
- experiment store;
- job runner;
- result artifact;
- clone/compare.

### RW4 — candidate packaging
- immutable candidate identity;
- evidence references;
- artifact hashes.

### RW5 — tournament runtime
- AgentFactory;
- isolated virtual ledger per agent;
- shared canonical market feed;
- durable checkpoints;
- scheduler;
- cohort/leaderboard metrics.

Runtime detail and dependencies: [Shared Market Runtime](SHARED-MARKET-RUNTIME.md#q-incremental-migration-plan). ASUS shares one canonical WebSocket acquisition, bounded local delivery, feature calculations, model instances and deterministic predictions across lightweight agents. Agent wallets/risk remain isolated. Capacity is admitted from measured ASUS qualification; model registration does not load or activate it.

### RW6 — portfolio shadow
- selected candidate composition;
- shared virtual portfolio;
- cross-strategy risk.

### RW7 — QuantOps MCP
- registry/data/backtest tools first;
- mutation tools only for drafts;
- shadow lifecycle;
- promotion request.

### RW8 — dashboard
- Workbench form + visual composer;
- Datasets;
- Experiments;
- Compare;
- Candidate;
- Tournament;
- Agent detail;
- Portfolio Shadow.

### RW9 — production bridge
- candidate export compatible with Production Main release contract;
- no direct live activation.
