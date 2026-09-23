# Frozen System Boundaries — Production Main + Research Workbench

**Architecture freeze:** v1.0  
**Date:** 2026-09-21  
**Branch:** `dev`

This document freezes the two-system architecture of the Indodax systematic trading platform.

**2026-09-24 host clarification:** [ADR-009](../decisions/ADR-009-asus-production-and-research-runtime.md) records the owner's allocation: ASUS hosts Production Main and Research Workbench execution (experiments, backtests, shadow and tournaments); Lenovo handles ML/DL training and tuning. Separate Production and Research processes, state, authority and measured resource budgets are required on ASUS. Host capacity and deployment remain unqualified. ADR-009 supersedes ADR-008 only on Production host placement; the two-system authority boundary and G0–G7 remain frozen. See [Shared Market Runtime](research-workbench/SHARED-MARKET-RUNTIME.md) for its remaining contracts and qualification.

**Live Production clarification:** Production Main is the owner's live real-trading system on ASUS and reads real Indodax account/portfolio state. It owns Production orders, risk, ledger and reconciliation authority. Research, shadow and tournament runtimes are separate and cannot read or mutate Production financial state or use Production credentials. Existing live operation is distinct from this repository's read-only control-plane API/UI work; those read surfaces must show live authoritative data with provenance and freshness, and report unavailable/unknown rather than fabricate values.

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

The two systems occupy two physical host roles and separate logical authority planes: ASUS hosts Production Main plus Research Runtime; Lenovo performs ML/DL training and tuning. Production Main and Research Runtime on ASUS remain separate processes, local state stores, credentials, resource budgets, market-data truth and failure handling. Research never receives Production authority. Co-location is not capacity or recovery qualification.

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
6. Research agents consume one canonical validated Research feed; Production Main independently owns and verifies its own feed health and account truth.
7. Leaderboard rank is not qualification.
8. Forward promotion requires >=90 days AND >=100 closed trades plus clean operational evidence.
9. MCP may create/research/test/request promotion; it may not bypass production gates.
10. Real-money execution remains centrally governed by Portfolio + Risk + OMS + Venue + Ledger + Reconciliation.
