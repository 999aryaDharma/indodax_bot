# Runtime parity contract and divergence audit

Baseline: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. CURRENT IMPLEMENTATION is source-inspected; TARGET is not deployed. Production columns describe production-oriented components, not a verified active production service.

## Layer matrix

| Layer | Backtest today | Forward shadow today | Production-oriented code today | Classification / target |
|---|---|---|---|---|
| Clock | Sorted bar availability/open events | Ambient datetime/time and polling | ClockGuard plus injected step time | SAME CONTRACT / DIFFERENT ADAPTER target; current shadow time/cursor coupling is DIVERGENCE TO FIX |
| Market source | MarketBar replay | Independent HTTP ticker/candle fetch | MarketGateway guarded ticker snapshots | SAME CONTRACT / DIFFERENT ADAPTER target; shadow bypass and no fan-out are DIVERGENCE TO FIX |
| Feature runtime | Feature registry/builder/replay | Local compute_features, hard-coded FEATURE_COLS | Pipeline accepts intents; frozen feature runner not wired | DIVERGENCE TO FIX, RP-02 |
| Candidate runtime | strategy_fn callback | Pair-specific C07/C02 branches and M02 paths | Pipeline accepts intents; release check separate | DIVERGENCE TO FIX; same verified candidate evaluator required |
| Portfolio | Direct pending intents/reservations | Own risk-per-trade sizing/shared wallet | PortfolioConstructor | DIVERGENCE TO FIX; preserve intent semantics and explicit allocation policy |
| Risk | PortfolioRiskManager | Same financial manager, custom caller sizing | RiskEngine wraps financial manager | SAME IMPLEMENTATION financial primitive; wrapper/caller behavior DIVERGENCE TO FIX |
| OMS | Pending lists, direct simulator fills | Direct Fill posting, no OMS | OmsStateMachine/OmsStore/OrderRouter | DIVERGENCE TO FIX; all qualify through shared OMS semantics |
| Venue | ConservativeExecutionSimulator | Ticker taker proxy | IndodaxTradingClient, FakeTradingVenue | SAME CONTRACT / DIFFERENT ADAPTER target; current shadow lacks venue interface |
| Fill | Simulator produces Fill | Constructs Fill directly | VenueFill normalization and ingester | SAME CONTRACT common Fill; DIVERGENCE TO FIX in application/recovery |
| Ledger | ResearchLedger | Same ledger plus float shadow metadata; separate SharedCapitalLedger elsewhere | ResearchLedger + ProductionLedgerStore | SAME IMPLEMENTATION accounting core; SAME CONTRACT / DIFFERENT ADAPTER persistence target; float/parallel ledger is DIVERGENCE TO FIX |
| Reconciliation | Internal replay balance checks | Checkpoint cash/position consistency | Venue evidence + durable cursor | DIFFERENT IMPLEMENTATION — JUSTIFIED authority; same health/freshness contract required |
| Metrics | BacktestResult + metric helpers | Own summary and float trade statistics | Metrics helpers, no complete common aggregation | DIVERGENCE TO FIX; same normalized trade/accounting evidence |
| Audit | Postings hash and result JSON | Checkpoint events and bounded diagnostics | OMS/control/journal/logging records | DIVERGENCE TO FIX; stable correlation IDs and schema |
| Restart | Re-run deterministically from beginning | Restores ledger/risk/position checkpoint | OMS/ledger/control stores restored separately | DIFFERENT IMPLEMENTATION — JUSTIFIED replay vs durable resume; missing coordinated recovery is DIVERGENCE TO FIX |

## Frozen target path

Canonical event → verified feature schema → immutable CandidateRuntime → SignalIntent → PortfolioConstructor → RiskEngine → authority gate → OMS → environment venue → normalized Fill → accounting transaction → reconciliation → audit/metrics.

- BACKTEST: HistoricalEventClock, historical source, simulator venue/fill model, isolated research persistence. Completed-bar/open ordering and availability remain causal. Simulator differences are versioned assumptions, not different accounting.
- FORWARD SHADOW: real clock, one validated canonical feed, ShadowVenueAdapter, durable per-agent store, internal shadow reconciliation. All common decisions/risk/OMS/fill/accounting logic exercised. Production writer code/credentials unavailable from research composition root.
- PRODUCTION: same candidate/runtime/core, real venue fill adapter, separate durable production namespace and venue reconciliation authority. All frozen pre-write gates remain mandatory.

The shared core must not import concrete live clients. Environment wiring supplies narrow capabilities. Moving a class file does not prove runtime parity; RP-01 is deliberately only compatibility groundwork.

## Migration ownership

RP-01 moves SignalIntent ownership with an identical legacy alias. RW0-01 defines stable immutable manifests and event identity. RP-02 brings feature/TA/model/exit evaluation behind the verified candidate contract. RP-03 preserves lineage and sizing/risk semantics. PM-02 establishes authoritative transactional execution state, consumed by RP-04's adapters and isolated namespaces. RP-05 provides parity evidence; RW5 cannot begin qualification before it passes.

Do not relabel old shadow runs as new runtime evidence. Keep old checkpoints/results read-only and versioned. A migration must copy into a new namespace, validate cash/positions/fees/risk/cursors, and retain old evidence; incompatible float-derived state is archived and restarted as a new agent rather than silently rounded into qualification history.

## Required executable invariants

1. Same candidate hash + canonical event sequence + initial state + policies gives identical decision intent content before venue effects. Intent identifiers are deterministic, not UUID-normalized away.
2. Same state + intent + risk/cost version gives identical risk quantity/reason; fees and cash reservations count once.
3. Simulator and shadow drive the same allowed OMS transitions, including partial fill, reject, cancel uncertainty and UNKNOWN recovery.
4. Same normalized fill sequence yields exact Decimal ledger balances and fee totals; duplicates have zero effect.
5. Kill at each transaction boundary, restart, replay input: one financial effect, one OMS application, consistent cursor and audit.
6. Agent A's fill/halt/corruption changes no Agent B namespace, cash, risk, positions or cursor. A slow consumer cannot change the event bytes delivered to others.
7. Shared-capital experiments intentionally arbitrate collisions deterministically; isolated tournaments never contend for cash.
8. Historical OHLCV outcomes and ticker proxy fills may differ; compare domain decisions at equivalent information boundaries, never claim identical realized PnL from different fill models.
9. Missing/corrupt identities, non-finite values, future availability, unsafe clock or incomplete reconciliation fail closed with explicit reason codes.
10. No Research MCP/worker/shadow composition can instantiate or resolve production venue write capability, including through wrappers.
