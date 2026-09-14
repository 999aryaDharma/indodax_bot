# Domain data and interface model

Exact source table definitions remain in [dataset contracts](../research/dataset-feature-contracts.md); existing implementation can impose stricter validation documented in subsystem specs. New fields below are target contracts until their sprint is DONE.

| Entity | Identity and key fields | State / relationships |
|---|---|---|
| Wire artifact | body bytes/hash, endpoint, params, source/ingestion time, metadata hash | Immutable original evidence; omit auth headers |
| Market record | pair, venue_symbol, source_event_id, event_ts, ingested_at, available_at, schema_version | Decimal price/qty, quality flags; valid canonical pair separate from venue casing |
| Quality decision | source content IDs, complete policy, findings, canonical decision hash | PASS/WARN/FAIL/QUARANTINED; recompute from bytes before publication |
| Bar | bar_id, pair, bar_type, interval, open/close times, availability, session, config/artifact IDs | [open,close); threshold lineage and continuity mandatory |
| Universe snapshot | as_of_date, build_cutoff, listing/components, provider cap evidence, tier, eligible, reasons | Keep delisted rows; LIQUIDITY_ONLY when historical cap absent |
| Feature row | sample_id, decision_ts, bar_id, snapshot, universe, registry version, ordered columns, row_ready_at | Eligible only after required warmup; no label columns |
| Label | sample_id, entry_ts, label_end_ts, target, costs, execution version, label_available_at | Future outcome stored separately; excluded/censored distinct from zero |
| Fold assignment | sample_id, fold_id, role, policy version, exposure record | TRAIN / INNER_VALIDATION / CALIBRATION / OUTER_VALIDATION / SEALED; purge and embargo explicit |
| Intent | decision_ts, pair, LONG/FLAT, strength, stop/target, strategy ID/version | No authority over fills; quantity approved only by risk |
| Fill | fill_id, order_id, event_id, qty, price, gross, fees by component, maker/taker assumption | REJECTED/PARTIAL/FILLED execution with precision/minimum policy |
| Ledger transaction | transaction_id, fill/event, accounts, signed valued postings, base_qty delta | Sum valued postings = 0; quantity not added to IDR; exact TEXT Decimal or quantized units |
| Experiment run | run_id, parent, git/environment hashes, config/data/feature/label/split/cost/execution IDs, seed | Run validity distinct from strategy lifecycle and job state |
| Model bundle | model/preprocessor/calibrator/threshold, feature order, target semantics, all hashes | Local verified artifact; no arbitrary executable pickle upload |
| Job | job_id, idempotency key, lease generation, attempt, heartbeat, resource class, checkpoint, input/output IDs | Claim atomically, stale fencing, bounded retry; local SQLite |
| Forward decision | frozen candidate, sample/feature IDs, decision time, forecast, risk result, intent | Persist before outcome; manual click separate record |

## Accounting equations

`buy_cash_debit = gross_buy_notional + quote-denominated costs` (base-denominated fee reduces received units and remains valued/audited). `net_sell_credit = gross_sell_notional - quote-denominated costs`. Realized PnL = net sell credit minus allocated gross buy cash basis. Equity = cash + current marked asset value; do not subtract already-paid fees again. Double entry is balanced in a single valuation currency per ledger; asset units remain a separate quantity dimension. USDT-to-IDR valuation requires a time-valid conversion source; otherwise keep quote-separated exploratory ledger.

## Temporal rules

Canonical UTC timestamps with explicit timezone. Distinguish event time, observed ingestion time, and available time; clock anomalies cannot silently satisfy causality. Inference uses `row_ready_at <= decision_ts`. Label availability is at least the latest availability of all source events used to determine the exit, so source latency can make it later than `exit_ts`. Event-time horizon does not authorize early label access.

## Persistence and migration

Immutable data corrections create new identities and preserve old references. SQLite upgrades backup first, transactionally retain foreign keys, triggers, indexes and sequence high-water mark. Apply migrations on temporary copies in tests; unknown legacy accounting becomes LEGACY_ESTIMATE. No real database migration is part of this documentation branch. Artifact publication completion requires durable content plus manifest/checkpoint ordering; partial artifacts never qualify as completed input.
