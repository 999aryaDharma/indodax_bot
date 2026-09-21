# Live release gates and current blockers

Passing CI adalah syarat perlu, bukan cukup. Gate bersifat kumulatif.

## G0 Repository truth

Fresh checkout reproducible, required CI green, no critical security finding, protected release refs, dependency/environment identity recorded.

## G1 Data and trusted judge

Causal data replay passes, point-in-time fee/tax coverage tersedia, unknown historical cost blocks promotion, simulator menangani reject/partial-fill/latency/conservative fills, ledger deterministic replay reconciles.

## G2 Candidate evidence

Sealed historical evaluation passes, failed trials preserved, cost stress dan parameter stability acceptable, tidak ada test-period retuning.

## G3 Forward shadow

Minimum: >=90 calendar days AND >=100 closed forward trades, no unresolved risk breach, no unresolved ledger/reconciliation incident, restart/recovery invariants demonstrated. Trade count bukan proof tunggal; uncertainty dan regime coverage tetap dilaporkan.

## G4 Operational readiness

Target host benchmarked, backup/restore drill passes, RPO/RTO measured, clock/network failure drill, telemetry/alerts tested, secret rotation rehearsed, current venue API/fee/minimum-order verified.

## G5 Private read-only integration

Balances/orders/trades reconcile, belum ada order-write permission, auth/rate-limit/nonce behavior tested, private payload redaction verified.

## G6 Manual micro-live

Tightly bounded capital, satu reviewed candidate, small universe, explicit human approval per order, reconciliation setelah fills, hard loss/drawdown guards.

## G7 Autonomous limited

Bounded capital + universe, immutable candidate, no online learning, no automatic model promotion, central risk authority, auto-halt on stale data/model mismatch/reconciliation breach.

## Current blockers

- no real-money venue adapter;
- no private exchange reconciliation service;
- no durable production OMS uncertain-order state machine;
- no real venue fill -> double-entry ledger integration;
- no measured production node / HA evidence;
- no selected-host restore RPO/RTO evidence;
- no recorded 90d + 100-trade qualified champion in this package;
- dev branch was observed unprotected during this hardening pass;
- current Pro minimum-order transition history is not fully time-bounded for historical simulation;
- pre-CFX historical fee assumptions retain legacy-evidence labels;
- shadow ticker proxy uses conservative taker cost but is not queue/depth-aware execution evidence.

## Recently hardened on dev

- Python 3.11-compatible TA dependency;
- missing/invalid model now fails closed;
- decisions use fully closed 1h bars;
- bars-held advances by closed-bar event, not polling cycle;
- SQLite transactional shadow checkpoint + integrity hash;
- time-valid Indodax tax/CFX intervals;
- central portfolio risk authority + persistent drawdown halt;
- cross-platform path traversal rejection;
- portable content-addressed snapshot path encoding.

These fixes strengthen research/shadow truth; they do not authorize live trading.
