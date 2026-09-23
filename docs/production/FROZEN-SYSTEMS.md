# Frozen System Boundaries — Production Main + Research Workbench

**Architecture freeze:** v1.0  
**Date:** 2026-09-21  
**Branch:** `dev`

This document freezes the two-system architecture of the Indodax systematic trading platform.

**2026-09-23 planning amendment:** [ADR-008](../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) makes ASUS the Research Workbench runtime/shadow edge and specifies the shared WebSocket substrate. Its explicit host-role override supersedes the older observer-only description. The two-system authority boundary and G0–G7 remain frozen. See [Shared Market Runtime](research-workbench/SHARED-MARKET-RUNTIME.md) for implementation status, contracts and qualification.

## Canonical systems

### 1. Production Main
Path: `docs/production/main/`

Mission:
- operate one reviewed production release safely;
- protect capital;
- own OMS, durable financial ledger, reconciliation and risk authority;
- never perform research/training;
- never hot-edit a strategy/model.

### 2. Research Workbench
Path: `docs/production/research-workbench/`

Mission:
- fetch/version historical data;
- compose TA + ML + DL + hybrid pipelines;
- train/evaluate models;
- run backtests;
- package immutable candidates;
- spawn isolated live-shadow agents;
- run tournaments and portfolio-shadow simulations;
- expose safe research operations through QuantOps MCP.

## Boundary

```text
RESEARCH WORKBENCH
customizable / experimental
        |
        | immutable candidate + evidence
        v
PROMOTION REQUEST
        |
        | G0-G7 governed release process
        v
PRODUCTION MAIN
frozen / safety-first
```

No research component may directly write a real venue order.

The two systems occupy three logical compute planes: Lenovo Research Compute (training, historical work and packaging), ASUS Research Runtime (shared public collection, features, qualified inference and shadow), and a separate future Production Main execution node. ASUS never trains models and never owns Production Main order-write authority. Sharing feed/feature/model/prediction work does not share candidate wallets or production credentials.

## Source-of-truth precedence

When documents conflict:

1. `docs/production/main/*` and `docs/production/research-workbench/*`
2. explicit newer ADRs that state they supersede frozen v1.0
3. other `docs/production/*`
4. legacy `docs/research/*` reports/design notes
5. experiment reports/results

Historical documents remain useful evidence but may contain superseded gates, host plans, fee assumptions, terminology or runtime topology.

## Superseded decisions

Frozen v1.0 explicitly supersedes:
- 14-day OR 15-trade promotion shortcuts;
- unrestricted automatic promotion;
- shared-ledger shadow as the only strategy evaluation model;
- direct online mutation of a deployed model;
- unrestricted `AUTONOMOUS` mode;
- the assumption that one hard-coded shadow engine is equivalent to a multi-agent tournament;
- any claim that local tests alone prove venue or operational readiness.

## Frozen principles

1. Research maximizes experimentation.
2. Production minimizes mutation.
3. Candidate identity is immutable.
4. Tournament agents use isolated virtual portfolios.
5. Portfolio Shadow is a separate shared-capital experiment.
6. All agents consume one canonical validated market feed.
7. Leaderboard rank is not qualification.
8. Forward promotion requires >=90 days AND >=100 closed trades plus clean operational evidence.
9. MCP may create/research/test/request promotion; it may not bypass production gates.
10. Real-money execution remains centrally governed by Portfolio + Risk + OMS + Venue + Ledger + Reconciliation.
