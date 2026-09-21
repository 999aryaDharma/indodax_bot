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

- canonical private **read-only** venue adapter is implemented, but has not yet been
  smoke-tested with a designated view-only Indodax credential/account;
- reconciliation engine/service plus durable cursor/coordinator are implemented, but
  have not yet accumulated real-account operational evidence or a completed operator runbook;
- durable OMS uncertain-order state machine/store is implemented, but there is still no
  write-capable venue adapter and no real uncertain-write recovery drill;
- venue-fill -> ledger normalization exists for IDR-denominated commission, but automated
  production fill ingestion/cursoring and non-IDR fee valuation remain blocked;
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
- shadow cash/inventory now derives from the balanced double-entry ledger;
- ledger state restore validates cash, positions, fills, fees, PnL, and initial capital postings;
- time-valid Indodax tax/CFX intervals and observed-current Pro minimum;
- central portfolio risk authority + persistent drawdown halt;
- missing ticker, stale closed bars, model-pair mismatch, and feature-schema mismatch fail closed;
- canonical quantity flows from risk approval into fill, ledger, and checkpoint;
- cross-platform path traversal rejection;
- portable content-addressed snapshot path encoding;
- architecture guard prevents canonical `indodax_lab` code from importing legacy flat engines;
- private read-only Indodax adapter uses current Trade API v2 for order/fill history;
- private reconciliation fails closed on balance/order/fill/staleness mismatches;
- OMS persists `UNKNOWN` outcomes across restart with integrity/version fencing;
- verified IDR-denominated venue fills can be normalized into the canonical ledger Fill contract.

These fixes strengthen research/shadow truth; they do not authorize live trading.
