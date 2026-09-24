# Research Workbench — QuantOps MCP Contract

## Purpose

QuantOps MCP lets an AI coding/research assistant operate Research Workbench safely from conversation or automation.

It is a **research control plane**, not a direct exchange execution API.

## Security boundary

MCP must never expose:
- withdrawal;
- real venue order submit/cancel;
- production write credentials;
- bypass-promotion;
- bypass-risk;
- direct mutation of a production release.

The strongest promotion action exposed to research MCP is **request promotion**.

## Proposed tool groups

### Dataset

```text
list_pairs
find_dataset
fetch_candles
create_dataset
validate_dataset
extend_dataset
list_datasets
get_dataset
```

`fetch_candles` should:
1. resolve venue/pair/timeframe/range;
2. reuse compatible cached data where possible;
3. fetch missing historical ranges;
4. normalize;
5. detect gaps/duplicates/out-of-order/non-finite values;
6. create an immutable dataset version;
7. return dataset identity + quality report.

### Strategy

```text
create_strategy_draft
clone_strategy
update_strategy_draft
validate_strategy
list_strategies
get_strategy
```

Only drafts may be edited.

### Model

```text
register_model
create_training_job
run_training
evaluate_model
list_models
get_model
clone_model_config
```

Heavy training should be routed to the research workstation/GPU environment.

### Pipeline composer

```text
create_pipeline
clone_pipeline
add_component
remove_component
configure_ensemble
validate_pipeline
get_pipeline
```

Supported component classes:
- TA strategy;
- indicator/filter;
- regime gate;
- ML/DL model;
- ensemble;
- veto/gate;
- sizing;
- exit;
- simulator/execution-cost policy.

### Experiment/backtest

```text
create_experiment
clone_experiment
validate_experiment
run_backtest
cancel_backtest
get_backtest_status
get_backtest_result
compare_experiments
```

### Candidate/tournament

```text
create_candidate
register_shadow_agent
start_shadow_agent
pause_shadow_agent
retire_shadow_agent
get_agent
list_agents
get_agent_metrics
get_leaderboard
compare_agents
request_promotion
```

## Safe creation workflow

An AI request such as:

> Create a more selective ETH Donchian strategy with ADX + volume filter and test 2021-2025.

must resolve to:

```text
find/fetch dataset
 -> create strategy draft
 -> validate
 -> create pipeline
 -> create experiment
 -> run backtest
 -> report result
```

It must **not** automatically start real-money execution.

Starting forward shadow may be automatic only after validation because it is isolated/no-real-capital.

## Auditability

Every mutating MCP tool records:
- actor/tool caller;
- request ID;
- timestamp;
- before/after artifact IDs;
- reason;
- generated hash/version;
- outcome.

No destructive deletion of historical experiments, candidates or trade evidence. Retirement/archive is preferred.

## Implementation phases

1. read-only registry tools;
2. dataset fetch/validate;
3. draft strategy/model/pipeline mutation;
4. backtest job control;
5. candidate registration;
6. isolated shadow agent lifecycle;
7. leaderboard queries;
8. promotion-request integration.

Production write tools remain outside this MCP.

## Form and YAML parity

The [program contract](../../implementation/BOT-TRADE-PROGRAM.md) requires form, declarative YAML and MCP to resolve one manifest/validator. Model listing includes compatibility and readiness, collection returns actual coverage, and batch results expose each pair independently. Production guarded commands remain outside Research MCP.
