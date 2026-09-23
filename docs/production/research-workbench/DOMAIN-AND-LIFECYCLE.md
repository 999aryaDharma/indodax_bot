# Research Workbench — Domain Model and Lifecycle

## 1. Registries

### Dataset Registry
Stores immutable/versioned market datasets.

Required identity:
- dataset_id/version;
- venue;
- pair;
- timeframe;
- requested and actual time range;
- bar count;
- quality findings;
- gap/duplicate report;
- source metadata;
- SHA-256/content identity;
- created_at.

Fetch once, validate once, reuse many times. Extending or repairing a dataset creates a new version.

### Strategy Registry
Stores technical/rule components:
- strategy_id;
- family;
- semantic version;
- required indicators/features;
- parameter schema;
- entry/exit contract;
- supported timeframe constraints.

### Model Registry
Stores ML/DL artifacts:
- model_id/version;
- architecture;
- artifact hash;
- feature schema;
- train/validation/test references;
- calibration metadata;
- metrics;
- supported pair/universe;
- runtime requirements.

### Pipeline Registry
Defines a composable graph:
- strategy nodes;
- filter/gate nodes;
- model nodes;
- ensemble nodes;
- sizing node;
- exit node;
- simulator/execution assumptions.

Pipeline manifests are declarative and hashable.

## 2. Experiment

The primary unit of Research Workbench is an **Experiment**, not a mutable strategy file.

Example identity:

```yaml
experiment_id: EXP-2026-0042
dataset_id: indodax_btcidr_1h_2021_2025_v2
pipeline_id: pipe_btc_c07_m02d04_v4
initial_virtual_cash: 1000000
cost_policy: indodax_idr_vX
git_sha: ...
seed: ...
```

Experiment results include:
- return/equity;
- gross/net PnL;
- fees;
- drawdown;
- closed trades;
- win rate;
- profit factor;
- expectancy;
- Sharpe/Sortino/Calmar where valid;
- turnover;
- monthly/regime breakdown;
- trade-level evidence;
- execution/cost assumptions.

Experiments are append-only. Changing one field creates/clones a new experiment.

## 3. Backtest lifecycle

```text
DRAFT
 -> VALIDATED
 -> QUEUED
 -> RUNNING
 -> COMPLETED | FAILED | CANCELLED
```

A failed experiment is retained, not deleted from research history.

Backtests must be reproducible from manifest + artifact identities.

## 4. Candidate

A candidate is created from a completed reviewed experiment.

Candidate fields:
- candidate_id/version;
- pipeline hash;
- strategy/model artifact hashes;
- dataset evidence refs;
- feature schema;
- cost/risk/execution assumptions;
- Git/environment identity;
- historical evaluation refs.

Candidate state:

```text
DRAFT
 -> BACKTEST_VERIFIED
 -> SHADOW
 -> QUALIFIED_CHALLENGER
 -> PROMOTION_REQUESTED
 -> RETIRED
```

Production may separately mark a candidate as deployed through its release process. Research itself does not mark real-money deployment authority.

Any model retraining/parameter edit creates a **new candidate version**.

## 5. Forward-shadow Agent

An Agent is:

```text
immutable candidate
+ isolated virtual portfolio
+ lifecycle state
+ live evidence
```

Minimum agent state:
- agent_id;
- candidate_id;
- cohort_id;
- initial virtual cash;
- durable virtual ledger;
- open positions;
- risk state;
- start time;
- market-event cursor;
- closed trades;
- incidents;
- performance metrics.

The agent does not own the shared market feed.

Runtime integration follows [Shared Market Runtime](SHARED-MARKET-RUNTIME.md) and [ADR-008](../../decisions/ADR-008-shared-market-runtime-and-asus-edge.md). Candidate/RuntimePlan resolve immutable market-input, feature-schema, model-artifact, trigger and shadow-mode eligibility policies through existing manifest ownership. Registered model state does not imply loaded, ASUS-qualified, or production-authorized.

Agents share immutable observations, feature snapshots and eligible deterministic predictions. Each tournament agent retains its own namespace, virtual wallet, ledger, positions, risk state and durable consumer cursor. Portfolio Shadow uses a distinct manifest/namespace with one intentionally shared cash pool and allocation policy. Neither mode may reuse the other's financial state or count deferred/replayed decisions as uninterrupted live evidence.

Triggers are versioned deployment inputs; evaluation timing is reproducible. Admission and pause/defer incidents are evidence outside immutable candidate identity. Changing a candidate's declared trigger semantics, features or model creates a new RuntimePlan/candidate version; it is not a hot edit.

## 6. Tournament cohorts

Compare like with like.

Recommended cohorts:
- BTC;
- altcoin;
- trend;
- mean reversion;
- breakout;
- ML hybrid;
- new challengers;
- qualified challengers.

Leaderboard ranking and qualification are separate.

A rank #1 agent is not automatically qualified.

## 7. Qualification

Forward qualification for promotion consideration follows the Production Main gate:

- >=90 calendar days **AND**
- >=100 closed forward trades;
- no unresolved risk/ledger/reconciliation incident;
- stable immutable candidate;
- restart/recovery evidence;
- sufficient regime/fee/slippage evidence.

Sparse strategies may remain high-performing but unqualified until evidence is sufficient; the system must display that honestly.

## 8. Continual learning

A running agent never trains itself into a new production identity.

```text
Agent V2 evidence
 -> offline attribution/training
 -> Candidate V3
 -> backtest
 -> new forward-shadow Agent V3
 -> qualification
```

This preserves reproducibility and prevents silent online model mutation.
