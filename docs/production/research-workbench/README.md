# Research Workbench — Frozen Architecture v1.0

**Status:** FROZEN ARCHITECTURE  
**Branch:** `dev`  
**Freeze date:** 2026-09-21

Research Workbench is the canonical research operating system for strategy discovery, model development, historical backtesting, forward-shadow tournaments and candidate packaging.

It is intentionally flexible. It must never become a shortcut around Production Main safety gates.

The [Shared Market Runtime design](SHARED-MARKET-RUNTIME.md), [ADR-008](../../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) and [ADR-009](../../decisions/ADR-009-asus-production-and-research-runtime.md) extend this frozen boundary with ASUS Production/Research co-location, Lenovo ML/DL training/tuning, WebSocket recovery, shared Research features/inference and mixed-load qualification. They describe planned integration; the current REST shadow path and standalone WebSocket collector remain separate at the audited `dev` SHA.

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

WebSocket is the target continuous public source. One centrally owned subscription set covers admitted candidate inputs; REST supplies bootstrap/history/metadata/recovery and bounded sanity checks. In-process bounded fan-out delivers durable validated events to recorder, feature runtime and shadow consumers. The same feature snapshot, loaded model instance and deterministic prediction are reused across eligible consumers. Slow consumers pause/resynchronize with recorded coverage gaps; queues never grow without limit.

## 7.1 Compute planes and host boundaries

- ASUS `asus-server` hosts both Production Main and Research Workbench execution: experiments, backtests, isolated shadow agents, tournaments and qualified CPU inference. The services have separate identities, roots, local state stores, authority and resource budgets. This is one physical host, not independent HA.
- Lenovo is the owner's daily laptop and is reserved for ML/DL model training and tuning. Model artifacts move to ASUS only through immutable export and receiving-side verification; Lenovo does not manage ASUS processes or state.
- Research Runtime owns the shared public market-data feed, feature processing, shadow/tournament evidence and its own local SQLite state. Production Main independently owns Production market-data health and authoritative financial state; no feed status, DB, credential or ledger is shared.
- Read-only SSH inventory on 2026-09-24 00:24 WITA found Ubuntu 22.04.5, kernel `5.15.0-187-generic`, 4 logical CPUs (2 cores), 3.7 GiB RAM (1.9 GiB available), 3.7 GiB swap (1.7 GiB used), and 29 GiB free on the 98 GiB root volume. Several Docker co-tenants were active; one container was restarting. These point-in-time facts are not capacity qualification; the owner-reported CPU-only baseline still needs stress and thermal verification.
- Training and parameter sweeps stay on Lenovo. ASUS must preserve measured Production headroom; under pressure optional Research work is deferred/stopped first. Unknown resource state blocks new admission.

Qualification covers actual host inventory and realistic co-resident Production + Research workloads, including 30-minute and several-hour tests and a 24h+ soak, restart isolation, disk recovery and bounded queues. The [runtime design](SHARED-MARKET-RUNTIME.md#m-resource-governance-and-asus-qualification) and [QA-03](../../sprints/verification/QA-03-capacity-and-crash-recovery-qualification.md) define evidence; no strategy/model capacity is promised from CPU/RAM specifications.

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
