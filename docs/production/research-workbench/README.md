# Research Workbench — Frozen Architecture v1.0

**Status:** FROZEN ARCHITECTURE  
**Branch:** `dev`  
**Freeze date:** 2026-09-21

Research Workbench is the canonical research operating system for strategy discovery, model development, historical backtesting, forward-shadow tournaments and candidate packaging.

It is intentionally flexible. It must never become a shortcut around Production Main safety gates.

## 1. Core principle

**Research is maximally customizable. Production is minimally customizable.**

A researcher may compose technical-analysis rules, ML/DL models, ensembles, datasets, pairs, timeframes, sizing rules, exit logic and execution assumptions. Once promoted to a candidate, the exact composition becomes immutable.

## 2. Canonical flow

```text
IDEA
  |
Strategy / Model Components
  |
Composable Pipeline
  |
Dataset
  |
Experiment
  |
Historical Backtest
  |
Candidate Artifact
  |
Isolated Forward-Shadow Agent
  |
Tournament / Leaderboard
  |
Qualification
  |
Promotion Request
  |
Production release process
```

Research may create evidence. It may not directly authorize real capital.

## 3. Major subsystems

```text
Research Workbench
├── Dataset Registry
├── Technical Strategy Registry
├── Model Registry
├── Pipeline Composer
├── Experiment Registry
├── Backtest Engine
├── Candidate Registry
├── Agent Factory
├── Tournament Engine
├── Portfolio Shadow Simulator
├── Leaderboard / Qualification
├── Artifact Registry
└── QuantOps MCP Control Plane
```

## 4. Workbench composition

A pipeline can combine:

- pair/universe;
- timeframe;
- technical indicators;
- TA entry/exit rules;
- regime filters;
- ML model;
- DL model;
- model ensemble;
- rule ensemble;
- model veto/gate;
- probability thresholds;
- position sizing;
- stop-loss/take-profit/trailing/time-decay logic;
- historical cost model;
- execution simulation policy.

Examples:

```text
BTC/IDR 1H
 -> C07 Mean Reversion
 -> M02 XGBoost + D04 iTransformer
 -> soft ensemble
 -> probability gate
 -> risk sizing
 -> simulator
```

```text
ETH/IDR 1H
 -> C02 EMA Pullback
 -> M02 gate
 -> ATR exits
 -> simulator
```

The implementation must move away from hard-coded pair-to-strategy branches toward registries + manifests.

## 5. Seed challengers

Frozen v1.0 starts with two **seed families**, not permanent champions:

### BTC-C07
- universe: BTC/IDR;
- family: C07 mean reversion;
- intended research direction: M02 + D04 ensemble where evidence/artifacts support it;
- rare-event strategy; model retraining must be conservative.

### ALT-C02
- universe: initially ETH/IDR + SOL/IDR;
- family: C02 EMA trend pullback/recovery;
- pair-specific model thresholds/config are allowed as versioned manifest fields;
- trend family may be evaluated for scheduled retraining, but retraining creates a new candidate.

Current code may not yet match every seed specification. That mismatch is implementation backlog, not permission to alter the frozen architecture silently.

## 6. Tournament vs Portfolio Shadow

These are different experiments.

### Tournament
Every agent receives:
- same canonical live market events;
- isolated virtual wallet;
- isolated ledger;
- isolated positions/risk state;
- same starting capital for a comparable cohort unless experiment explicitly states otherwise.

Agents cannot consume each other's capital.

### Portfolio Shadow
Selected candidates share one simulated portfolio to study:
- capital contention;
- correlation;
- simultaneous signals;
- concentration;
- portfolio-level risk.

The existing shared-ledger shadow concept belongs here, not as the only tournament model.

## 7. Shared market-data principle

Never fetch the same live market independently per agent.

```text
Indodax
  -> canonical Market/Data Service
  -> validated immutable event
  -> fan-out to N research agents
```

This improves rate-limit behavior and guarantees that tournament agents see the same event.

## 8. Research/production firewall

Forbidden from Research Workbench:
- order-write credentials;
- withdrawal credentials;
- direct real venue order calls;
- direct promotion to real money;
- mutation of an already frozen candidate;
- hot model replacement inside a running production release.

Research outputs artifacts and promotion requests only.

See:
- `DOMAIN-AND-LIFECYCLE.md`
- `QUANTOPS-MCP.md`
- `UI-UX-AND-ROADMAP.md`
