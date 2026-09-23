# Shared Market Runtime — WebSocket migration and ASUS Research Edge

Status: ACCEPTED TARGET DESIGN; integration/host qualification not implemented by this document. Date: 2026-09-23. Authority: [Frozen Systems](../FROZEN-SYSTEMS.md), [ADR-008](../../decisions/ADR-008-shared-market-runtime-and-asus-edge.md), [change request](../../decisions/CR-20260923-shared-market-runtime.md). Code audit baseline: `dev` at `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Existing worktree planning amendments ADR-005/006/007 remain applicable; they are not represented as code present at that baseline.

This is the single detailed design for the owner's shared-market and ASUS hardware briefs. It belongs under the canonical Research Workbench documents rather than the historical `docs/architecture/hedge-fund-production-blueprint.md`. Existing production documents link here instead of duplicating runtime contracts. All new symbols/paths below are proposed unless section B explicitly identifies existing code. Inspection establishes source behavior; no product suite, venue smoke or ASUS benchmark was run for this documentation change.

## A. Executive summary

The repo already has a bounded public WebSocket collector with book recovery and immutable publication. The operator shadow entrypoint still fetches ticker/history using REST, recomputes Pandas indicators, eagerly loads pair-specific XGBoost files and evaluates hard-coded branches against one paper portfolio. The gap is integration and shared runtime ownership, not absence of a WebSocket adapter.

Extend that collector into a centrally owned, multi-channel feed. Commit validated events once; distribute local immutable references to shared features, qualified inference and candidate-driven shadow. Admit only bounded workloads. Keep raw evidence and execution decisions recoverable independently. Training and artifact optimization remain on Lenovo; Production Main remains a separate execution authority with its existing frozen chain and gates.

Selected topology: one supervised ASUS runtime process containing collector, journal coordinator, bounded fan-out, incremental features and lightweight candidate objects; one shared inference subprocess only when models are admitted. This isolates native inference hangs without one Python process/model copy per strategy. An in-process-only inference thread cannot enforce a hard native-call deadline; a broker introduces unnecessary service/memory cost at this stage. No Kafka, RabbitMQ, NATS, Redis, Kubernetes or database-server dependency is required.

## B. Repository evidence

IMPLEMENTED means source and associated tests exist, not qualification or sprint DONE. Manifest status remains exclusively owned by `docs/sprints/sprint-manifest.json`; historical DONE and existing source must not be converted into fresh PASS evidence.

| Classification | Exact evidence at audited dev | Implication |
|---|---|---|
| IMPLEMENTED | `src/indodax_lab/data/indodax_stream.py`: `PublicMarketCollector`, `AppendOnlyStreamWriter`, `CollectorConfig` | Injected transport, heartbeat timeout, backoff/jitter, bounded batches, durable offsets; extend these owners |
| IMPLEMENTED | `data/stream_protocol.py`: `parse_public_message`, `BookSessionProtocol`, `StreamState`, `BookEvent`; `data/book_recovery.py`: `BookRecoveryCoordinator` | Trade/book parsing, book duplicate/gap/regression/recovery/quarantine behavior exists |
| IMPLEMENTED | `cli/collect_market_stream.py`: `main`, `_run`, `_connect` | Public WebSocket CLI, lazy transport import, SIGTERM shutdown, single `--pair` configuration; no shadow fan-out |
| IMPLEMENTED | `contracts/market.py`: `TradeEvent`, `CandleRecord`; `data/trade_wire.py`, `data/publication.py` | Existing Decimal/UTC/availability and immutable wire primitives must be reused |
| PARTIAL | `market/gateway.py`: `MarketGateway.get_market_snapshot`, `fetch_ticker_raw`; `market/quality.py`, `clock.py`, `health.py` | Quality/clock/health abstractions exist, but gateway remains REST-based; no canonical stream composition |
| LEGACY | `run_shadow_bot.py`: `run_single_scan`, `run_continuous_watch`; `paper/live_shadow_engine.py`: `fetch_live_market_data`, `compute_features`, `_load_models`, `predict_probability`, `evaluate_market_scan` | REST ticker + 1h history, default 60s watch, repeated DataFrames, BTC/ETH/SOL artifact loading and hard-coded strategy selection |
| PARTIAL | `paper/live_shadow_engine.py`, `paper/shadow_store.py`: `ShadowStateStore`; `backtest/ledger.py`: `ResearchLedger` | One shared portfolio and SQLite WAL/FULL checkpoints exist; not an isolated live-agent tournament |
| PARTIAL | `paper/portfolio.py`: `SharedCapitalLedger`, `SharedLedgerCheckpoint` | Shared cash allocation and in-memory checkpoint contracts; not a complete durable multi-candidate execution runtime |
| IMPLEMENTED | `features/registry.py`: `FeatureRegistry`, `LoadedFeatureRegistry`; `features/builder.py`: `build_feature_frame`; `features/technical.py` | Versioned offline feature definitions and causal batch calculation exist; live incremental sharing is missing |
| PARTIAL | `models/artifacts.py`: `PortableBundle`, `PortableBundleLoader`; model-specific trainers/bundles | Verified JSON logistic replay exists; it is not a universal XGBoost/DL runtime loader or bounded shared model cache |
| PARTIAL | `evaluation/lifecycle.py`: `CandidateRecord`, `CandidateLifecycleManager`; `evaluation/registry.py`: `ExperimentRegistry`; `strategies/registry.py`: `StrategyRegistry` | Reuse registries/lifecycle/strategy primitives; current CandidateRecord alone is not the frozen complete runtime manifest |
| LEGACY | `evaluation/tournament.py`: `run_wave1_tournament` | Offline metric classification/checkpoint, not continuous isolated forward agents |
| PARTIAL | `orchestration/resources.py`: `HostProfile`, `ResourceClass`, `SystemResourceReading`, `AdmissionPolicy`, `evaluate_admission`, `guard_asus_training_import` | Existing ASUS training/admission rules; extend for continuous runtime, sensor freshness, RSS/swap/disk/soft-hard controls |
| MISSING | `deploy/lab-shadow.service` → `indodax_lab.cli.shadow`; `deploy/lab-collector.service` → `indodax_lab.cli.collector` | Those two modules are absent from audited dev; unit files are not ready-to-run evidence |
| PARTIAL | `deploy/lab-worker.service` → `indodax_lab.orchestration.worker`; `configs/schedules/host_profiles.yaml` | Module path exists, but host config calls ASUS `asus_zenbook`, enables shadow without local collector, and is not a measured X441U profile |
| PLANNED | Frozen `research-workbench/DOMAIN-AND-LIFECYCLE.md`; later `docs/implementation/CONTRACTS.md`, ADR-005/006/007 | Complete manifests, AgentFactory, shared kernel and execution transactions have planning ownership; do not implement competing contracts |
| MISSING | Audited live-shadow composition | Multi-pair shared delivery, feature snapshot service, lazy model cache, prediction single-flight, candidate-trigger scheduling and qualified ASUS capacity |

Associated tests inspected/located include `tests/unit/lab/data/test_stream_parser.py`, `test_book_recovery.py`, `test_trade_sentry.py`, `tests/unit/lab/market/test_market_gateway.py`, `test_gap_detection_and_invalid_price.py`, `tests/unit/lab/paper/test_live_shadow_engine.py`, `test_shadow_store.py`, feature registry/builder tests, and `tests/unit/lab/orchestration/test_resources.py`. Existing tests do not establish the new end-to-end path.

Provider reference checked for this design: [official Indodax Market Data WebSocket documentation](https://github.com/btcid/indodax-official-api-docs/blob/master/Marketdata-websocket.md). It documents `wss://ws3.indodax.com/ws/`, public-token authentication, multiple subscriptions on one connection, application ping/pong, channel offsets, subscription epoch and recover requests. Its trade rows supply timestamp and sequence; its book example has no venue timestamp. It also documents summary/chart channels, which the existing parser does not support. Replay retention, channel/connection limits and operational availability are not guaranteed by those examples; record current provider evidence before activation. No new summary/chart subscription is required for the initial design.

## C. As-is architecture

```text
run_shadow_bot.py --watch (default 60s)
  -> LiveShadowEngine.fetch_live_market_data
  -> requests.Session -> ticker REST + candle-history REST per pair
  -> closed-candle filter -> full Pandas feature calculation
  -> hard-coded rules + eagerly loaded pair XGBoost models
  -> PortfolioRiskManager -> ResearchLedger -> ShadowStateStore

Separate path:
cli.collect_market_stream --pair
  -> PublicMarketCollector -> trade/book parser + BookSessionProtocol
  -> BookRecoveryCoordinator -> immutable wire batches + checkpoints
  [no connection into the operator shadow loop]

MarketGateway -> REST ticker + quality/clock guards
  [available abstraction; not the shared WebSocket shadow source]
```

## D. Target architecture

```text
LENOVO — Research Compute
historical wire/datasets -> research features -> backtest/walk-forward
 -> bounded tuning + ML/DL/RL training -> reviewed immutable RuntimePlan
 -> candidate/model artifacts + optimization/parity evidence
                         |
               verified immutable transfer
                         v
ASUS — Research Runtime / Shadow Edge
public Indodax WS -> canonical local feed -> shared features/inference
 -> Tournament Shadow | Portfolio Shadow -> durable forward evidence
                         |
              artifacts + promotion REQUEST
                         v
FUTURE PRODUCTION MAIN — separate authority
Market Gateway -> Data Quality / Clock Guard -> Frozen Feature Runtime
 -> Frozen Candidate -> Portfolio Constructor -> Independent Risk Engine
 -> Pre-Write Authority Gate -> Durable OMS -> Venue Adapter -> Indodax
 -> Fill Normalizer -> Durable Ledger -> Reconciliation
```

Production may reuse reviewed market/runtime code and artifact formats. It independently verifies its own release, health, account truth and write authority; ASUS uptime does not become a mandatory remote write-authority dependency by this design.

```text
ASUS: one supervised composition (lab-shadow.service)
  Subscription/connection owner -> existing public transport/protocol
                 |                    ^ centralized REST repair/bootstrap
                 v
  raw recorder -> normalize/quality/clock -> durable canonical feed journal
                                                   |
                                     bounded in-process fan-out
                          +------------------------+------------------+
                          v                        v                  v
                shared feature state       shadow market marks     metrics
                          |
                    FeatureSnapshot
                     /           \
              rule evaluation    bounded IPC -> ONE inference process
                     \           /              model cache + single-flight
                      PredictionResult
                             |
                candidate trigger scheduler
                  /                     \
       tournament agent objects     portfolio-shadow run
       isolated W/L/R/cursor         shared W/L/R/cursor
                  \                     /
                 namespace-local durable execution stores
```

No strategy thread/process/container by default. The journal owns feed ordering; the shared execution kernel owns per-namespace decision/accounting transitions. Watchdog and resource probes remain responsive independently of native inference.

## E. Architectural invariants

1. One acquired public event feeds every eligible local consumer without per-strategy exchange calls.
2. One semantic feature calculation/snapshot feeds every compatible consumer.
3. One loaded instance per admitted model artifact/runtime configuration; registered does not mean loaded.
4. One deterministic prediction per identical input identity is shared; stateful/non-deterministic models need an explicit state/seed identity or are not admitted to this cache.
5. Training is outside ASUS and outside Production Main. No fallback to online fitting.
6. Tournament wallets, ledgers, positions and risk state are isolated; Portfolio Shadow deliberately shares capital.
7. Research promotion evidence never grants execution authority; strategies never own exchange order credentials.
8. All queues, caches, windows, model memory, payload sizes, workers, retry buffers and retention are bounded.
9. Missing quality/clock/cost/model identity blocks eligible evaluation/execution. Recovery never creates fictitious live coverage.
10. UTC availability, closed-bar causality, Decimal accounting, immutable lineage and existing G0–G7 remain authoritative.

## F. Component responsibilities

Paths below are relative to `src/indodax_lab/` unless explicitly prefixed with `docs/`, `configs/`, `deploy/` or `tests/`.

| Component / owner | Responsibility; input → output | State / persistence | Failure behavior | Forbidden responsibility |
|---|---|---|---|---|
| Connection/subscription owner; extend `data/indodax_stream.py` | Union of admitted input requirements → subscribed public channels/raw frames | Per-connection session/request IDs; per-channel subscription status/epoch/durable offset | Bounded reconnect; reject unsupported channels/auth errors; no per-agent retry | Strategy selection or order submission |
| Protocol/recovery; existing `stream_protocol.py`, `book_recovery.py` | Frames → typed trade/book observations, gaps, recovery evidence | Per-channel protocol state, bounded dedup/recovery window; durable gap records | Conflicting duplicate/regression/missing replay quarantines channel | Inventing missing sequence/history |
| Recorder/journal; extend writer + proposed `market/event_store.py` | Raw bytes + normalized envelope → durable bytes/event cursor | Immutable wire segments, SQLite feed index, schema/version/checksums | Disk/commit failure blocks publish/ack; startup verifies orphan/committed references | Financial state or promotion |
| Gateway; extend `market/gateway.py` | Typed observations + clock/quality evidence → eligible snapshot/health | Latest verified state per pair/input; references to durable sources | Non-healthy dependency blocks dependent decisions | Treating connection liveness as data quality |
| Local fan-out; proposed `market/runtime.py` | Committed events → bounded consumer references | Queues/cursors; consumer durable cursor belongs to its store | Detach/pause lagging consumer; replay within bounds or record coverage gap | Hiding event loss |
| Feature runtime; proposed `features/runtime.py` | Verified observations + registry → immutable snapshots | Shared finite windows/recurrence state, versioned checkpoint + feed cursor | Gap/schema/missing warmup → ineligible snapshot | Targets, bfill, training or HTTP |
| Artifact resolver/inference; extend `models/artifacts.py`, proposed `models/runtime.py` | Verified manifest + snapshot → prediction result | Bounded loaded-model and prediction caches; durable decision references | Fail closed on corrupt artifact, deadline or admission failure; kill stuck worker | Training, arbitrary pickle, another registry |
| Shadow scheduler/kernel; proposed `paper/runtime.py`, existing planned RP/RW owners | Candidate + trigger + shared snapshots/predictions → intents/evidence | Per-agent/run mutable state under existing execution store protocol | Pause/HALT by namespace; recheck freshness before financial commit | Direct exchange writes or shared tournament cash |
| Resource governor; existing `orchestration/resources.py` | Qualified host policy + fresh probes → admit/defer/shed | Hysteresis and cooldown; recorded admission incidents | Required sensor unknown/stale → deny new optional/compute work | Guessing capacity from core count |
| Health/supervision; existing market health + CLI/systemd | State/lag/probes → readiness, watchdog, metrics | Bounded metric aggregates; durable critical incidents | Bound restart loop; dependency failure not erased by restart | Changing candidate or production gates |

### Bounded delivery contract

Use stdlib `asyncio.Queue(maxsize=...)` for component wakeups and one bounded ring of immutable event references; allocate no copy of a raw payload per agent. Queue capacity is constrained by both item count and estimated serialized bytes. A host qualification manifest must supply positive `ingress_max_items/bytes`, `fanout_max_items/bytes`, `inference_max_items/bytes`, `max_event_bytes`, `max_consumer_lag`, `replay_max_batch` and `shutdown_drain_deadline`. Startup rejects missing/unqualified live limits. Tests use small explicit limits, including capacity two; they are not ASUS throughput defaults.

Critical data includes trade/book publications, closed candles, health transitions, decisions, fills and checkpoints. Persist before decision eligibility. Never silently drop critical data. If recorder/journal capacity is exhausted, stop intake/close transport, mark affected channels unreliable and recover from the last durable provider cursor. A full slow-consumer queue pauses that namespace; its durable cursor allows bounded replay. Consumer lag beyond retention marks an irrecoverable coverage incident and requires a new synchronized segment. Do not freeze healthy consumers behind an optional candidate.

Run blocking publication/SQLite work through one shared bounded writer worker for the ASUS composition, serializing each store's transactions; namespace isolation does not allocate a thread per agent. Bound its open-connection cache and pending submissions before executor entry (an executor's default internal queue is not the admission boundary). Do not call synchronous fsync on the transport/watchdog event loop. Feature/rule updates execute in bounded cooperative slices; a candidate that repeatedly exceeds its evaluation budget is paused. The shared inference subprocess handles native numerical calls. Queue backpressure and missed deadlines remain visible even if disk or CPU delays scheduling.

Metrics/dashboard updates may coalesce latest values and increment drop counts. Order-book/trade data may not coalesce for event-sensitive consumers. Candidates that declare time-sampling consume explicit as-of snapshots instead of receiving every event; sampling policy is hashed, not an overload-time optimization. Feed ordering is local acceptance order, not a promised cross-channel venue chronology.

## G. Event, feature and prediction contracts

Extend the already planned `CanonicalMarketEvent` in [implementation contracts](../../implementation/CONTRACTS.md); do not introduce a competing event protocol. Its existing fields remain the core: `event_id`, `feed_id`, `sequence`, `pair`, `event_time`, `available_at`, `observation`, `quality_ref`.

The versioned envelope adds `schema_version`, `venue`, `event_type`, nullable `venue_timestamp`, `received_timestamp`, `source_connection_id`, `channel`, nullable `provider_epoch/provider_offset/provider_sequence`, `source_event_id`, `source_payload_hash`, `quality_status`, reason codes and source artifact references. `sequence` is a monotonically committed local feed position; provider fields retain their own namespaces. A provider without an epoch uses a new local session identity after restart; cross-session continuity must be re-established, not assumed.

| Observation | Reuse and supported semantics |
|---|---|
| Trade | Existing `TradeEvent`: provider timestamp/sequence, Decimal price/base/quote quantity, side, source ID; publication offset is a separate envelope field |
| Order book | One atomic publication containing existing `BookEvent` levels; full-publication semantics as current adapter, not invented deltas. Venue timestamp is null; retain `SOURCE_TIMESTAMP_UNAVAILABLE`. Existing level `event_ts=ingested_at` is explicitly receive-derived |
| Candle | Existing `CandleRecord`, with producer/aggregation policy and source lineage. Native WS closed-candle messages are not assumed. Derived bars and REST history retain different source identities |
| Ticker/market mark | Existing `TickerSnapshot`/`MarketSnapshot` projection from reliable book/trade or explicitly tagged REST; do not fabricate bid/ask/24h volume from a last trade |
| Health | Existing `MarketHealthReport`, recorded when a state changes with reason, scope and policy identity; pair-scoped health for candidate gating |

No new market payload family is necessary. `TickerEvent` and `CandleEvent` are envelope kinds wrapping the existing contracts, not duplicate models. Metadata and connection control stay operational records, not strategy market events.

**Identity:** SHA-256 over canonical, versioned semantic observation, source namespace/epoch/identity and payload content. Preserve source IDs from existing records. Local sequence, processing latency and connection IDs are provenance, not semantic price identity. Store the first accepted observation envelope immutably; re-delivery creates receipt diagnostics but does not replace original availability. Identical source key/content is duplicate; same key/different semantic content is corruption. With no stable provider identity, content hash alone cannot distinguish two real identical events: dedup only within a known receipt/publication scope, never claim global exactly-once acquisition.

**Serialization:** use ADR-006 canonical UTF-8 JSON/UTC/Decimal conventions, finite floats and deep-immutable values. Full stored envelope has its own checksum. `available_at` is no earlier than reception/validation/durable availability needed for this runtime. Newly recovered missing events become available when actually recovered, never backdated into forward decisions. Already committed replay preserves original identity/availability and is labeled replay. Unknown schema fails closed; additive schema versions need decoder tests; semantic changes require a new major identity domain. Existing artifact hashes are not rewritten.

**Ordering/durability:** journal commit assigns a unique local sequence once; bus publishes only committed envelopes. Per-channel ordering follows verified epoch/offset, with bounded replay before resuming reliability. There is no global event-time sort or unlimited reorder buffer. Late events remain evidence, may invalidate a derived interval, and never silently revise prior decisions. Atomic publication of an entire book avoids half-updated bid/ask state. Consumer decisions are idempotent by namespace and event ID under ADR-007, not by an in-memory set alone.

`feed_id` identifies a durable journal namespace pinned to venue and normalization policy, not a TCP connection. Reconnect changes connection/session provenance without resetting the local feed cursor. Incompatible normalization policy creates a new feed version/namespace; subscription additions preserve previous events. A consumer cursor binds `(feed_id,last_acknowledged_sequence,subscription_policy_hash)`. Filtered consumers receive increasing, possibly nonconsecutive local sequences; skipped unsubscribed events are not provider gaps. Replay reads the journal using the same immutable filter, while actual gap/health events for required inputs are always delivered. Do not write a no-intent financial transaction for every unrelated pair merely to make sequence numbers consecutive.

**FeatureSnapshot identity:** pair + timeframe + registry source hash/version + ordered feature definitions/parameters + calculation semantic version + immutable source-window/checkpoint lineage + candle/market identity + availability policy. Keep `sample_id` and offline dataset identity as lineage; a live snapshot need not have the same sample ID as a historical dataset to prove numeric parity. Values, readiness/missingness and source availability are frozen together. Do not include requesting candidate ID, so compatible consumers share it.

**Prediction identity:** model ID/version + artifact content hash + feature snapshot ID + pair + preprocessing/calibration hashes + runtime configuration/environment identity + output contract. The runtime hash includes numerical backend/dtype, model seed if applicable and deterministic configuration. Model state identity is required for stateful prediction; initial implementation admits only stateless deterministic serving. Same ID with different output is an integrity failure, not a cache update.

## H. WebSocket ownership, recovery and REST

The connection owner resolves the union of candidate input requirements into unique channels; many strategies never increase identical subscriptions. Reuse current public endpoint/transport. Normally one connection multiplexes admitted pairs; a provider-limit or latency-qualified profile may specify a small fixed connection count. A channel has exactly one active owner. Subscription changes are serialized; removal waits until no admitted consumer or recovery task needs the channel. Authentication and subscription acknowledgements are correlated by unique request IDs; unacknowledged channels are never RELIABLE. Handle token expiry through bounded reconnect/public-token replacement; never use account credentials.

Keep current `StreamState` values `DISCONNECTED`, `SYNCING`, `RELIABLE`, `GAP`, `RECOVERING`. CONNECTING is transport status, while STALE/DEGRADED/UNAVAILABLE/CLOCK_UNSAFE remain gateway health. Do not add equivalent competing eligibility enums.

```text
DISCONNECTED -> transport CONNECTING -> auth/subscription ACK -> SYNCING
SYNCING -> verified initial snapshot/continuity -> RELIABLE
RELIABLE -> missing/conflicting/regressed offset -> GAP -> RECOVERING
RECOVERING -> complete verified replay + durable commit -> RELIABLE
RECOVERING -> unavailable/incomplete replay -> durable quarantine -> SYNCING
any state -> disconnect/heartbeat timeout -> DISCONNECTED
gateway STALE/DEGRADED/CLOCK_UNSAFE overrides evaluation eligibility
```

Reuse bounded exponential backoff and injected jitter in `PublicMarketCollector`. Clamp exponent before exponentiation and clamp final jittered delay to configured maximum. Reset attempts only after a stable verified session, not any malformed/control packet. Bound recovery attempts/buffer/deadline per channel; repeated failures leave it unavailable while retrying with capped delay. Permanent authentication/configuration errors surface as unhealthy operator-action reasons rather than a tight loop.

Track application ping acknowledgement and transport liveness separately from last valid market observation per required input. An active socket on an illiquid pair does not prove fresh trade/book data. Required-input freshness policies are versioned; unknown timestamp age is explicitly receive-based. Use monotonic clocks for deadlines and UTC for evidence; unsafe clock blocks decisions. Preserve existing fakeable transport/clock interfaces.

Durable recovery cursor is `(venue, channel, provider_epoch or local_session, offset, raw_ref, canonical_feed_sequence)`. Existing per-channel acknowledged offsets are extended with epoch/session and verified linkage. Reconnect requests replay only for supported/recoverable channel semantics. Validate every replay range and duplicate boundary, response correlation, epoch, pair and final offset; a `recoverable` flag alone is insufficient. Trade sequence does not substitute for publication continuity; do not assume sequences are globally consecutive across pairs.

Book recovery extends `BookRecoveryCoordinator`; apply equivalent channel recovery for trade publications without conflating trade IDs with offsets. A new full book can restore present-book eligibility after an unrecoverable gap, but cannot make the historical gap or LOB window continuous. Trade-derived bars spanning missing data are quarantined. Epoch changes start new source segments. A late/conflicting event cannot retroactively produce a live fill.

| REST responsibility | Rule |
|---|---|
| Metadata/bootstrap/history | One centralized, rate-budgeted fetch/cache per identical request; verified closed history warms features |
| Snapshot recovery | Re-establish present state with source/receive timestamps. REST snapshot without WS offset cannot bridge a WS gap |
| Candle gap repair | Publish a new source/version with actual availability and gap evidence; never fabricate missing trades/LOB |
| Sanity checks | Scheduled bounded comparisons; discrepancy degrades the dependent feed |
| Fallback | Default: collection/diagnostics only, evaluation paused. A separately frozen REST-only experiment may operate under its own declared source policy; never silently continue the WS cohort as equivalent |
| Reconciliation | ASUS uses local paper state/evidence; private venue reconciliation belongs to separately governed Production Main |

Honor HTTP 429/Retry-After and bounded retry budgets. Backoff, timeouts, maximum message size and allowed channel count live in versioned deployment/provider policy. Their safe operating values require qualification.

## I. Shared feature runtime

Compile admitted registry requirements into shared calculation keys `(pair,timeframe,feature definition/params/lag/availability semantic digest)`. Common primitives are computed once even when two registries select different output subsets. Materialize immutable schema-specific snapshots from those shared results. Bound admitted feature graphs and history windows; arbitrary feature expressions/imports remain forbidden.

Reuse `FeatureRegistry`, the transform allowlist, `build_feature_frame`, technical/liquidity/context math, warmup rules and anti-leakage checks. Initial replay integration may call the batch builder once per shared closed-bar input to establish the oracle; continuous ASUS activation requires either qualified cost for that path or proven incremental recurrence. Never recompute a complete DataFrame on each tick/candidate.

Incremental rolling transforms maintain bounded windows/sums; EMA/Wilder-style transforms retain recurrence state, count, exact initialization convention and lag buffers. Truncating history then restarting an EWM is not equivalent. Persist recurrence/checkpoint lineage; restore and replay from the checkpoint. If absent, replay the declared original seed segment from durable/archive data under bootstrap admission, or block the candidate. A different seed convention creates a new feature/runtime version.

Close bars only after their declared interval end, required-source completeness/watermark and clock checks. No-trade intervals remain gaps under existing bar contracts unless an explicitly versioned contract permits otherwise. Preserve source sequence/session boundaries and point-in-time context availability. Multi-pair features wait for all required as-of inputs; no future row joins or bfill. Late corrections create new artifacts/incidents and do not rewrite forward snapshots.

REST historical candles and trade-derived live candles are not presumed numerically interchangeable. During cutover, compare boundaries, OHLCV units, completeness, availability and feature outputs on overlapping verified inputs. If source semantics differ, keep the legacy candidate on its compatible centralized source policy or package a new candidate; never relabel new features under old model metadata.

Offline/live parity uses identical verified source streams, registry bytes and initial state. Golden tests compare values under registered float tolerances, output order, warmup/missing flags, readiness, future-perturbation invariance, gaps, flat/zero-volume data, checkpoints and restarts. Model inputs must match ordered schema and normalization (for example legacy scaled RSI versus registry definitions); name similarity is not compatibility.

## J. Shared inference and trigger policies

Model Registry remains under RW2; immutable artifacts/resolver remain under RW0/RW4 and `models/artifacts.py`. `PortableBundleLoader` initially serves its supported logistic contract; explicitly allowlisted native XGBoost runtime adapters verify artifact/metadata/preprocessing/calibration and feature hashes before load. Additional RF/anomaly/DL formats require a compatible verified serializer/loader and parity test, not arbitrary pickle/joblib. ONNX or quantized artifacts are optional derived versions with conversion provenance and numerical qualification; neither ONNX nor LightGBM is introduced merely because it is available elsewhere.

Resolver stages immutable bytes under a permitted local root, verifies checksum/provenance/environment and rejects traversal or changed bytes. No hot downloads or remote code. A model registry label, including LIVE, cannot bypass host admission or candidate checks. Lazy load only on an admitted request. Loaded-key is artifact digest plus serving-runtime digest, not candidate/pair alone; pair-specific preprocessing is part of identity where it affects inference.

One shared inference subprocess owns all admitted model instances. Default execution concurrency is one, with one native numerical thread per inference backend until measured policy permits more. Parent event loop submits bounded requests and continues collecting. IPC uses validated bounded JSON/numeric payloads, not untrusted pickle. Worker startup imports serving modules only; training module import tests enforce the ASUS boundary.

Reserve qualified peak model-load/inference memory before loading, including temporary copies; `max_loaded_models`, total resident/cache budget and host available-memory/swap checks all apply. Pinned models still count against budget; impossible pinned sets reject startup. Evict unpinned least-recently-used models only when no request references them. If a library does not release memory, quiesce and recycle the single worker, clear its residency table and reload admitted pinned artifacts; no second live worker duplicates the cache during rollover.

Single-flight map keys identical in-progress requests to one future; every eligible consumer receives the same immutable result. Completed results use a bounded LRU by bytes/count and expire no later than input freshness/evaluation deadline. Durable decision evidence retains prediction identity/output after cache expiry. Version/config/schema/source-epoch changes prevent reuse by identity; health and freshness are checked even on hits. Failures are not cached as neutral probabilities. Do not combine candidates' risk or portfolio-dependent results into the shared prediction cache.

Each request carries an absolute monotonic deadline and cancellation token. Expired queue requests are rejected before load/inference. A native call exceeding deadline causes parent termination/restart of the worker; all affected in-flight requests fail closed and are recorded. Never return late success after its deadline. Repeated worker failures pause model consumers and use bounded restart cooldown. Rule-only consumers may continue when their input dependencies remain reliable.

### Declarative triggers

Extend immutable RuntimePlan/runtime policy references rather than inventing another job scheduler. `TriggerPolicy` is versioned with kind, required input keys, timeframe or positive period/UTC anchor, freshness/deadline, and missed-trigger behavior. Supported kinds: `ON_TICK` (explicit market-mark publication), `ON_TRADE`, `ON_ORDERBOOK_CHANGE`, `ON_CANDLE_CLOSE`, `EVERY_N_SECONDS`, `ON_FEATURE_CHANGE` (semantic value/readiness change). A candidate cannot request a trigger without a compatible available input/schema.

The scheduler deduplicates `(runtime plan, trigger identity, input snapshot identity)` per namespace. Candle-close uses a closed candle ID; feature-change uses the feature digest; periodic uses its fixed UTC slot and recorded as-of feed cursor. Preserve event order, then stable candidate ID tie ordering. A trigger does not independently fetch data. Market-dependent position monitoring still processes required price events even when model prediction is less frequent.

Missed live deadlines record DEFERRED/SKIPPED with reason and coverage, not retrospective live decisions. Replay may restore internal state and produce separately labeled replay diagnostics; it cannot add backdated forward trades. Overload pauses optional candidates/cohorts instead of silently changing immutable inference frequency. Changing a trigger creates a new deployment/runtime policy and candidate version where decision semantics change.

## K. Tournament Shadow

Reuse planned AgentFactory/RW5 and CandidateRuntime/RP contracts. One agent is a lightweight object/task bound to candidate version, cohort, source/feed policy, equivalent starting cash, unique namespace and consumer cursor. It owns isolated wallet, ledger, positions, reservations, risk/exit state and incidents. Share read-only market/features/predictions only.

Each cohort records common start/end observation policy, capital/currency, cost/execution assumptions and scheduling/coverage criteria. Dispatch the same canonical input identity to every eligible member; each decision records that identity before outcome. Candidate A cannot consume B's capital or advance B's cursor. Duplicate replay affects each namespace once.

A lagging agent pauses and records an interval of missing forward coverage. The leaderboard compares common valid coverage or marks the entries incomparable; healthy candidates may continue collecting evidence without falsely retaining a fair-cohort claim. A candidate replacement starts a new agent/version. No per-agent WS, full DataFrame, model copy or Python process. G3 still requires >=90 calendar days AND >=100 closed forward trades plus clean evidence; throughput/24h soak is not qualification for promotion.

## L. Portfolio Shadow

Reuse planned `PortfolioShadowManifest`/RW6 and shared execution kernel. One run owns one namespace, cash pool, ledger, reservation state and portfolio risk authority. Candidate outputs carry attribution; candidate-local signal state is separated from the aggregate positions/exposure.

For a common event/trigger batch, gather eligible proposals until the declared deadline; missing model/candidate output is an explicit abstention. Apply the immutable allocation policy, concentration/correlation rules and stable tie priority before risk/atomic cash reservation. Never allocate according to whichever asynchronous model completed first. Persist rejected proposals as well as accepted ones.

The existing `SharedCapitalLedger` remains a compatibility reference, not a second durable financial authority beside the common ResearchLedger/ExecutionStateStore. Preserve the current Rp500,000/max-two-position policy for migrated legacy experiments unless a newly reviewed manifest chooses another policy. Tests distinguish separate tournament balances from deliberately contested portfolio cash, including simultaneous proposals, opposite signals, partial fills, rejection and restart.

## M. Resource governance and ASUS qualification

### Owner-supplied hardware baseline

| Field | Planning input and consequence |
|---|---|
| Identity | ASUS X441U/X441UV, `asus-server`, Ubuntu Server 22.04.5 LTS x86_64; recheck OS/kernel/runtime versions during qualification |
| CPU | i3-6006U, 2 physical cores/4 threads, ~2 GHz; SMT is not four independent compute workers; sustained thermal throttling matters |
| RAM | 4 GB DDR4, swap ~3.7 GB; active swap-in/out is overload, not usable model capacity |
| Storage | Root/LVM ~98 GB; ~51% usage was historical, not current free space; reserve disk for journal/checkpoints and keep archival datasets on Lenovo |
| GPU | None assumed; CPU-qualified classical ML first, small DL conditional; no CUDA requirement, DL/RL training forbidden |
| Network | Prefer Ethernet `enp2s0` (historical r8169/metric ~100) over Wi-Fi `wlp3s0` (historical metric ~600); do not hard-code interface names/routes. Tailscale is administration/transfer, not shared WAL |
| Other workloads | Docker, Portainer, Homepage, Beszel/agent, socket proxy, staging/Nextcloud experiments may coexist; record actual concurrent services and memory/load during tests |

Extend `SystemResourceReading` and `AdmissionPolicy` in `orchestration/resources.py`; keep LOW/MEDIUM/HIGH/GPU and ASUS/LENOVO authoritative. Add probe age, process RSS, available memory, swap-in/out, disk free/latency and thermal throttle evidence. Sensor values must be finite, plausible and fresh. Unknown required CPU/RAM/thermal/disk state cannot pass admission merely because an existing optional field is None.

One host qualification policy owns CPU/memory soft and hard thresholds, swap activity threshold, thermal ceiling, minimum disk reserve, model-load reservations, queue budgets and worker/candidate admission. It records evidence SHA, workload fingerprint, sustained durations and recovery limits. Soft overload applies hysteresis/cooldown and stops new admission; hard overload suspends affected compute, persists state and sheds optional work. Sensor loss suspends new compute; minimal collection/checkpoint/watchdog may continue only within an explicit qualified emergency budget. Persistent unsafe pressure causes orderly halt before OOM/disk exhaustion. Existing generic resource defaults are not proof of safe ASUS limits.

| Priority | Preserve / shed policy |
|---|---|
| P0 | Watchdog, health/control and fresh resource probes |
| P1 | Market integrity/connection recovery; stop intake explicitly if integrity cannot be sustained |
| P2 | Durable journal/checkpoints and recovery; never skip fsync/transactions for speed |
| P3 | Admitted core shadow state and accounting |
| P4 | Required inference for admitted candidates; if unavailable, dependent evaluation pauses |
| P5 | Optional candidates and additional model loads; pause first |
| P6 | Analytics/UI/noncritical telemetry; coalesce/throttle first |

These are ASUS research priorities, not Production Main execution priorities. A required model is never silently bypassed to keep a strategy running. Linux cgroup/systemd memory/CPU limits form a qualified final containment boundary; they supplement the same admission policy rather than a competing policy system.

### Benchmark matrix and evidence

Run each applicable cell on both idle host and realistic co-resident workloads, with pinned code/environment/artifacts/provider trace. Vary feature count and persistence rate as explicit dimensions, not only strategy count.

| Scenario | Workload progression |
|---|---|
| A — rules | 5 pairs; 10, 20, 30, 50 strategy objects; no model |
| B — classical ML | 5 then 10 pairs; 20 strategies; 1 through 6 shared models; logistic, XGBoost, RF and isolation/anomaly models only with supported verified loaders |
| C — DL | 5 pairs; 10 then 20 strategies; one small CPU-qualified DL artifact, additional artifact only after first meets budgets |
| D — burst | Observed trace replay at 1x, 2x, 5x, 10x; preserve event chronology and label synthetic load; no profitability inference |
| E — durability/failure | Increased persistence/checkpoint rate, slow disk, disk reserve exhaustion, process kill, DNS/router outage, route change, reconnect storm and stale/missing sensors |

Measure 30-minute loads, several-hour thermal steady-state runs and 24h+ shadow soak. Capture CPU average/p50/p95, load average, peak RSS/available RAM, swap usage and I/O, temperature/throttling, messages/s, event lag, queue depths/bytes/lag, feature p50/p95/p99, inference p50/p95/p99/rate/cache hits, resident model memory/load time, SQLite write/checkpoint latency, disk utilization/growth and restart recovery time. Record dropped telemetry versus deferred evaluations separately; critical silent loss must be zero.

Qualification passes only against preregistered candidate deadlines, freshness rules and measured headroom in the realistic-host run, with no sustained swapping, silent critical loss or invariant failure and successful recovery/restore. Values and resulting maximum admitted workload belong in host-specific qualification/config evidence, not this generic design. A RAM upgrade does not increase CPU/thermal throughput; repeat qualification after hardware, model/backend, runtime or co-tenant changes.

## N. Persistence, retention and crash recovery

Keep raw/publication evidence immutable using current publication/checksum helpers. Extend `AppendOnlyStreamWriter` with bounded byte/time flushing and references to durable batches; file/directory fsync precedes journal/index commit. A feed SQLite WAL store has one writer and records accepted event identity/content hash/local sequence/provider cursor, source refs, gaps and consumer registration metadata. It does not own portfolios.

Publish raw blob/segment first, then commit canonical index and durable provider cursor in one feed transaction. A crash before commit leaves an orphan raw artifact that can be verified/reindexed or retained; no downstream ACK. A crash after commit/before bus notification replays the indexed event. Never advance a provider checkpoint beyond referenced durable data. Out-of-order duplicate receipts cannot regress a checkpoint. Verify referenced bytes on restart.

Per namespace, the existing planned `ExecutionStateStore` owns decision/OMS/fill/ledger/risk/exit state and its consumer cursor using PREPARED → DECIDED → ACKNOWLEDGED from ADR-007. Shared feature checkpoints live with the feature service; namespace state retains snapshot/checkpoint references and candidate-specific feature/exit state. Feed commit, feature checkpoint and financial ACK are distinct facts, never a cross-database pseudo-transaction. Recovery reuses immutable inputs and optimistic revisions; failed commit cannot publish prospective memory state.

Retention uses bounded recent hot segments and asynchronous verified immutable transfer to Lenovo/archive. Keep bytes referenced by retained decisions, unresolved incidents and recovery checkpoints reachable; archival verification must precede local eviction of their payloads. A lagging consumer cannot pin unlimited disk: pause it, record coverage failure and require archive replay/new segment when retention reaches its qualified budget. If archive is unavailable and disk reserve is reached, stop collection explicitly; never delete unarchived required evidence to appear healthy. ASUS is not the research data lake.

SQLite WAL stays on local disk with one writer per store and bounded connections/checkpoint cadence. Back up through the consistent SQLite API with referenced artifacts, not a raw WAL copy. Test restore into an alternate root. PostgreSQL is considered only when measured writer/concurrency/storage limits remain after batching and serialization, via a new migration decision; multiple strategy objects are not a reason to adopt it.

## O. Observability and service lifecycle

| Domain | Required measurements |
|---|---|
| Market | Connection/protocol/health state, messages/s, last message and valid-input age, reconnects, gaps, duplicates, out-of-order/conflicting events, REST fallback calls, queue items/bytes, consumer lag |
| Features | Update latency, freshness, snapshots, shared calculation/cache hit ratio, schema mismatch, warmup/gap resets |
| Inference | Loaded models, reserved/observed memory, load latency, p50/p95/p99 latency, rate, cache/single-flight hits, deadline/timeouts, evictions/recycles, queue depth |
| Shadow | Active/paused candidates, event lag, decision latency, deferred/skipped evaluations, cohort comparability, reconciliation status, checkpoint age |
| Host | CPU/load, RSS/available RAM, swap usage and swap-in/out, disk/free/latency/growth, thermal/throttle, clock health |

Use bounded metric labels such as component, channel family, configured pair and reason enum. Full candidate/model/event/artifact IDs belong in structured logs and durable evidence, not unlimited metric labels. Histograms use fixed buckets; metrics/exporter failures cannot block journal commits. Distinguish liveness (process progressing) from readiness (dependencies/data/state safe for the declared workload). A blocked optional model does not mark unrelated rule candidates ready/failed incorrectly. Always retain critical health transitions durably.

### Concrete entrypoints and cutover

- Existing usable collector CLI: `python -m indodax_lab.cli.collect_market_stream --data-root <root> --pair <pair> --public-token <public-token>`; `--dry-run` validates without acquisition. Current token CLI should migrate to protected environment/file input to avoid command-line/log disclosure, even though it is a public feed token.
- Target `lab-shadow.service`: `python -m indodax_lab.cli.shadow --config <absolute-runtime-config>`. Implement that currently missing module as the single ASUS composition for collection + fan-out + features + shadow; optional one inference child is owned by it. Modes `--check-config`, `--replay <manifest>` and normal run are explicit and tested; replay uses separate namespaces.
- Target `lab-collector.service`: existing `cli.collect_market_stream`, extended with `--config` multi-channel settings for collection-only deployments. It must not run alongside `lab-shadow.service` for the same feed identity/root. Both acquire the same OS advisory lock before network/store initialization. No second collector is required by the integrated shadow service.
- `lab-worker.service`: existing `orchestration.worker` remains Lenovo-only, with host admission checked before training module import. Existence of its module alone is not operational qualification.

Update service files/config only in the owning implementation phase. Validate importable `--help`/config paths in CI. Replace the stale `asus_zenbook` profile with a correctly identified ASUS profile through explicit config migration/compatibility alias; canonical code HostProfile.ASUS remains unchanged. Do not enable services from the old templates as proof of readiness.

Cold boot: acquire exclusive local feed/namespace writer locks; validate config/host admission and artifact identities; recover stores/cursors; restore feature state; connect and synchronize inputs; verify clock/freshness; become ready. Agents restart in RECOVERY then PAUSED, with explicit governed resume following existing lifecycle contracts. Reconnect of an otherwise running agent may resume only after deterministic channel recovery and all dependencies revalidate; an unrecoverable gap pauses it.

Systemd uses network-online ordering plus retry for actual connectivity, bounded restart delay/start limits, unprivileged identity, restricted write roots and tested watchdog/stop deadlines. Remove the old shadow `After=lab-collector.service` dependency for integrated mode. A watchdog timeout is a controlled restart with preserved incidents; never an infinite rapid crash loop.

SIGTERM: disable new subscriptions/admission/triggers; stop intake; flush/quarantine pending source gaps and commit admitted feed data; drain eligible bounded work until deadline; persist/defer unfinished consumer work without fake ACK; stop inference child; flush/checkpoint stores; close transports and release locks. Drain deadline expiry exits with explicit incomplete state recoverable from durable cursors. Disk-full fails publication and readiness; forced kill restores the last committed state, never silently resets cash or clears gaps.

## P. Security and authority boundaries

ASUS runtime composition resolves public market adapters and simulated venue adapters only. Candidate files cannot supply arbitrary import paths, shell commands, account credentials or live-client factories. Boundary tests traverse import/factory reachability as well as textual imports. The common kernel may share semantics with Production Main under ADR-005 while its injected authority cannot grant real writes.

Public WS authentication is not an account-read/order-write key. Keep account-read reconciliation and all real venue credentials outside this ASUS shadow composition. Withdrawal permissions remain forbidden. Artifact input is untrusted until trusted provenance, hashes, schema, bounded size and loader allowlist are verified; a checksum alone is not permission to deserialize executable objects. Runtime releases/artifacts are read-only to the service user.

Admin uses private access/Tailscale under least privilege. Docker availability does not grant the trading runtime access to the Docker socket or host administration. Source logs exclude tokens/auth/private payloads. Network route, DNS and TLS failures degrade data eligibility and trigger bounded recovery. Changing host size never changes these authority rules.

## Q. Incremental migration plan

The phases below are implementation design units, not new sprint IDs or status authority. Before code work, reconcile the manifest dependencies and register each extension under its owning scope. Historical DONE is reused with fresh affected regression tests, not rebuilt wholesale. Each phase uses behavioral RED → GREEN, committed-SHA evidence and independent review; unresolved Critical/Important findings block completion. Read frozen specs plus owning sprint Required Reading and ADR-002/005/006/007/008.

### Phase 0 — Baseline, contracts and source qualification

- Goal/dependencies: pin dev baseline, legacy behavior, existing RP/RW contracts and provider evidence; reconcile DATA/FEAT/ML/JOB/RP/RW/OPS/QA ownership before implementation.
- Files: existing `docs/implementation/CONTRACTS.md`, sprint manifest/feature map under coordinator ownership; tests in `tests/unit/lab/paper/test_live_shadow_engine.py`, `tests/unit/lab/data/test_stream_parser.py` and `test_book_recovery.py`.
- Contracts/tests: characterize current REST closed bars, pair/strategy/model mapping, exits/risk/costs, persistence and offline feature output; provider fixtures capture channel/epoch/offset/replay/heartbeat/error behavior without credentials. Tests use fake transport and temporary state.
- Failure/observability: unresolved provider semantics or feature-source mismatch blocks the corresponding capability; report exact SHA and baseline deviations.
- Rollback/DoD: no runtime cutover; preserve source and evidence. Contracts and owning DAG changes reviewed, test mapping complete; no blanket DONE claim.

### Phase 1 — Durable canonical envelope and journal

- Dependencies: phase 0, DATA-01/02 primitives and approved canonical-event identity amendment.
- Files: extend `contracts/market.py`, `data/indodax_stream.py`; new `market/event_store.py`; tests `tests/unit/lab/market/test_event_store.py`.
- Contracts: versioned envelope in G, atomic local feed sequence, per-channel cursor, immutable raw refs and schema compatibility. Public `append_verified(event) -> committed event` and bounded `read_after(cursor, limit)`; no consumer sees uncommitted content.
- Tests/failures: identical/conflicting duplicates, epoch change, oversize/non-finite/malformed input, crash before raw publication/index commit/notification, disk-full and checksum damage. Assert cursor never exceeds durable evidence.
- Observability/rollback/DoD: expose commit latency/gaps/queue bytes; new store namespace beside old wire files; disable writer and replay old compatible store without deleting events. Crash/idempotency tests and schema review pass.

### Phase 2 — Shared multi-channel WebSocket owner

- Dependencies: phase 1 and DATA-05 recovery/collector tests.
- Files: extend `data/indodax_stream.py`, `stream_protocol.py`, `book_recovery.py`, `cli/collect_market_stream.py`; existing parser/recovery tests plus `tests/unit/lab/data/test_shared_subscriptions.py`.
- Contracts: one deduplicated subscription set, channel ACK/epoch/offset state, unique control IDs and bounded recovery. Preserve single-pair CLI compatibility. Trade/book payloads stay existing types.
- Tests/failures: connect/auth/subscription, N consumers requesting the same input yield one subscription, normal/provider disconnect, DNS failure, heartbeat/stale data, duplicate/regression/gap/replay expiry, partial recovery, REST rate limiting/fallback tagging and SIGTERM during recovery.
- Observability/rollback/DoD: report connection/channel health, source age, retry/fallback counts and durable cursors; collect alongside legacy in separate evidence-only roots with bounded public traffic. Stop new collector to rollback; no legacy financial state touched. Reliable publication through journal proven with fake transport and scoped authorized venue qualification.

### Phase 3 — Bounded fan-out and gateway integration

- Dependencies: phases 1–2; market quality/clock guards.
- Files: new `market/runtime.py`; extend `market/gateway.py`, `market/health.py`; tests `tests/unit/lab/market/test_fanout.py` and gateway tests.
- Contracts: publish committed event references, subscribe by declared input, bounded replay; gateway validates injected observations without hidden HTTP. Recorder is the durability prerequisite, not a lossy peer subscriber.
- Tests/failures: many/slow consumers, capacity-two saturation, deterministic local order, coalesced telemetry, no unbounded memory growth, stale clock, missing bid/ask, recovery notification loss and lag beyond retention.
- Observability/rollback/DoD: queue bytes/depth/age, consumer cursor lag, pause/gap incidents; disable fan-out and retain recorder. Every consumer receives identical committed IDs or explicit coverage failure; measured memory stays within configured bounds.

### Phase 4 — Shared causal feature snapshots

- Dependencies: phase 3, FEAT-01..04/BAR verified source semantics.
- Files: new `features/runtime.py`; reuse `features/builder.py`, `registry.py`, `technical.py` and `data/bars.py`; tests `tests/unit/lab/features/test_runtime_equivalence.py`.
- Contracts: `update(committed event) -> tuple[FeatureSnapshot,...]`, `snapshot(key, as_of)` and versioned recurrence checkpoint. Register shared calculation keys and complete source lineage before output.
- Tests/failures: offline/live and incremental/full equivalence, long recurrence beyond window length, future perturbation, closed-bar boundary, late source, warmup/gaps, multi-pair as-of, schema mismatch, checkpoint kill/restore and REST/trade-bar parity.
- Observability/rollback/DoD: latency/freshness/cache ratio/reset reasons; run side-by-side without changing candidate decisions first. Fall back to a qualified shared batch oracle only with identical semantics; otherwise pause. Golden parity and host-budget fit proven before activation.

### Phase 5 — Shared verified serving and triggers

- Dependencies: phase 4, ML artifact verification, RW0/RW2 model/runtime manifests, JOB-02 policy extension.
- Files: extend `models/artifacts.py`, `orchestration/resources.py`; new `models/runtime.py`; trigger integration in proposed `paper/runtime.py`; tests `tests/unit/lab/models/test_shared_inference.py` and resource tests.
- Contracts: `resolve(model_ref) -> verified artifact`, `predict(model_ref, snapshot, runtime_policy, deadline) -> PredictionResult`; versioned triggers and bounded single-flight worker. No second registry.
- Tests/failures: same model across candidates loads once; same deterministic request predicts once; version/preprocessing/schema differences do not reuse; corrupt/untrusted artifact rejects; finite outputs; memory/load reservation/eviction/pinned overflow; timeout worker kill/recycle; no training import; periodic/candle triggers replay deterministically without backdated forward decisions.
- Observability/rollback/DoD: model memory/load/eviction, queue, deadline/cache metrics; disable model consumers while rule-only candidates remain eligible. Prior compatible artifact selection creates explicit deployment evidence. Accepted formats and CPU budgets have parity/negative tests; unsupported DL stays Lenovo-only.

### Phase 6 — Candidate-driven Tournament Shadow cutover

- Dependencies: phases 3–5 as required by each candidate, RW4/5 and RP shared kernel/ADR-007 execution store readiness.
- Files: new `paper/runtime.py`, `cli/shadow.py` under existing AgentFactory/runtime owners; extend compatibility routing in `run_shadow_bot.py`; tests `tests/integration/lab/test_shared_shadow_runtime.py`.
- Contracts: verified CandidateManifest/RuntimePlan, AgentManifest, one namespace per agent, common feed and shared feature/inference services; legacy pair branches exported only as explicit compatible candidate manifests.
- Tests/failures: common feed/snapshot/prediction ID across agents; isolated cash/positions/risk/cursors; crash in each execution-envelope stage; stale feed/model/cost rejects; no-intent cursor once; lagging agent loses comparability rather than hiding gaps; paper composition cannot resolve live venue.
- Observability/rollback/DoD: candidate lag/deferred decisions, namespace reconciliation/checkpoint and cohort coverage. Start new runtime namespaces; preserve legacy SQLite read-only. Rollback to old binary only against its compatible preserved namespace/new declared run, never interpret new DB with old code. End-to-end fake venue and parity evidence pass.

### Phase 7 — Portfolio Shadow integration

- Dependencies: phase 6 and RW6/shared portfolio allocation policy.
- Files: extend `paper/runtime.py`, adapt `paper/portfolio.py` behind common financial authority; tests `tests/integration/lab/test_portfolio_shadow_shared_runtime.py`.
- Contracts: distinct PortfolioShadowManifest/run/namespace, stable proposal arbitration and atomic common cash reservation.
- Tests/failures: intentionally shared capital contention, maximum positions/concentration, completion-order permutation invariant allocation, missing model abstention, duplicate intent/fill, crash/reconciliation, and rejection of tournament/portfolio namespace mixing.
- Observability/rollback/DoD: aggregate allocation/rejection/reconciliation and per-candidate attribution; disable portfolio run without changing tournament state. Common-feed mixed-mode test proves both accounting semantics independently.

### Phase 8 — Service and operational cutover

- Dependencies: phases 2–7 for enabled modes, OPS-01/02/03 and restore proof.
- Files: `deploy/lab-shadow.service`, `deploy/lab-collector.service`, `deploy/lab-worker.service`, `configs/schedules/host_profiles.yaml`; new versioned `configs/schedules/asus_runtime.yaml`; CLI modules from phases 2/6; tests `tests/integration/lab/test_runtime_service_lifecycle.py`.
- Contracts: actual entrypoints in O, absolute roots, single feed lock, host-trained-work prohibition, bounded shutdown/restart and archive/retention policy. `--help`/`--check-config` are network-free.
- Tests/failures: cold boot, competing collector/shadow start, unavailable network, SIGTERM drain and forced kill, missing secrets without disclosure, corrupted store, disk-full, archive outage, thermal/sensor loss and service restart/restore under temporary roots. Validate systemd units on Linux.
- Observability/rollback/DoD: readiness/watchdog/checkpoint/backup metrics; validate old unit/config rollback with matching old data namespace. Service source paths exist and documented drift is removed only after these tests; no automatic deployment authorization.

### Phase 9 — ASUS capacity, soak and legacy retirement

- Dependencies: phase 8, QA-03 and owner-controlled ASUS test environment; legacy parity/decommission gates.
- Files/evidence: extend existing capacity qualification tooling/tests under QA-03; append host-specific evidence in `docs/quality/`; qualified limits in ASUS config. Update `07-canonical-runtime-migration.md` only from measured results.
- Tests/failures: matrix M in idle/realistic-host conditions, sustained thermal load/24h+ soak and process/network/disk recovery; compare API/subscription count with candidate count, shared feature evaluations, loaded-model count and prediction calls.
- Observability: full metric matrix, exact SHA/environment/artifact IDs and host service inventory, all coverage gaps and rejected cells.
- Rollback/DoD: reduce admitted workload/pause candidates and select last qualified release; keep evidence. Retire polling only after service/CLI consumers move, parity or intentional-difference records pass, restore works and rollback no longer needs it. Publish measured limits, not a generic claim that ASUS supports a fixed N strategies/models.

## R. Architecture decisions and change control

[ADR-008](../../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) is the material new decision: ASUS role override, shared WS ownership, local delivery/serving topology and source-versus-local identity extension. [CR-20260923](../../decisions/CR-20260923-shared-market-runtime.md) records impact. ADR-005 shared-kernel authority, ADR-006 immutable identities and ADR-007 transactions are reused, not superseded.

No ADR is required merely to choose a private helper name. A future broker, cross-host live-delivery guarantee, authoritative database change, unsupported provider semantics workaround or non-deterministic/stateful serving model does require a new impact/decision record. Host threshold tuning within the qualified mechanism creates versioned evidence/policy; it cannot loosen feature/data or promotion gates.

## S. Transitional debt and retirement boundaries

- `LiveShadowEngine.fetch_live_market_data`, private feature formulas, eager pair-model loading and hard-coded dispatch are compatibility paths to retire after parity/source/candidate qualification. Do not delete them during documentation work.
- `run_shadow_bot.py --watch` becomes a compatibility frontend to the qualified shared runtime; keep explicit legacy replay/diagnostics where rollback still needs them. A production-default fallback must not silently re-enable polling per candidate.
- Fix missing `cli.shadow`/`cli.collector` service references through phase 8, not a prose claim that services run today. Preserve the existing collector CLI and its tests.
- `SharedCapitalLedger` and offline `run_wave1_tournament` are not substitutes for common durable financial state/live AgentFactory. Adapt/reference them without overwriting historical outputs.
- Correct the ASUS profile name/role, stale observer-only deployment wording and misleading source timestamp/sequence interpretations. Keep superseded architecture drafts historical.
- Keep existing candidate/model/feature registries as owners; remove duplicate legacy calculations/loader paths only after compatibility mappings and repository-wide caller audit.

## T. Acceptance checklist and scaling answer

- [ ] Current code evidence, target interfaces and manifest status are distinct; owner/reviewer evidence names exact implemented SHA.
- [ ] Lenovo training, ASUS runtime and Production Main authority remain separate; ASUS cannot import/run training or resolve a real order-write adapter.
- [ ] One subscription/acquisition per required source input serves many candidates; provider limits and recovery behavior are evidenced.
- [ ] Canonical envelopes preserve actual source timestamp/offset/sequence availability and durable local ordering; conflicting duplicates fail closed.
- [ ] Reconnect, gaps, malformed payloads, stale feed/clock, replay expiry, REST fallback and epoch changes have tested outcomes without false continuity.
- [ ] All buffers/queues/windows/caches have byte/count/lag bounds; slow consumers and saturation preserve integrity and visible coverage incidents.
- [ ] Shared closed-bar feature snapshots pass offline/live, incremental/full, causality, initialization, schema and restart equivalence tests.
- [ ] Artifact checks/provenance/schema guard lazy serving; shared models load once; identical deterministic requests single-flight once; incompatible inputs never reuse stale predictions.
- [ ] Memory budgets, eviction/recycling, inference deadlines and required-sensor failures are enforced and tested under load.
- [ ] Candidate manifests/triggers are immutable and source-compatible; missed triggers are never backfilled as live evidence.
- [ ] Tournament financial/risk state is isolated; Portfolio Shadow intentionally contends for capital with deterministic arbitration; tests cannot conflate modes.
- [ ] Feed cursors and execution ACK/checkpoints survive crashes/disk-full without double effects; consistent backup/alternate-root restore succeeds.
- [ ] Actual CLI/service paths, single-writer startup, SIGTERM, watchdog/restart and worker host restrictions pass Linux qualification.
- [ ] Metrics expose feed/features/inference/shadow/host state with bounded cardinality and quiet healthy behavior.
- [ ] Idle and realistic-host matrix, sustained thermal runs and 24h+ soak produce qualified host limits; unqualified cells remain disabled.
- [ ] Legacy cutover/rollback is proven; source changes preserve historical evidence and financial namespaces; independent review has no unresolved Critical/Important findings.
- [ ] Documentation/software completion is not real-money activation or G3 profitability/forward qualification.

**How can dozens of concurrent candidates and multiple registered ML/DL models fit a modest ASUS without multiplying traffic, calculation or memory?** Candidate count adds small strategy/state objects and isolated durable namespaces. Exchange work scales with the union of subscribed pairs/channels; feature work scales with unique calculation keys; resident model memory scales with admitted distinct artifact/runtime keys; inference work scales with unique triggered input identities. Identical requests join one computation and reuse its result. Admission, fixed queues, finite windows, lazy residency, deadlines and overload pauses cap the remaining distinct work. Lenovo handles training and archives. The measured envelope determines how many candidates actually qualify—dozens is a workload to test, not a promise. **Share first, bound resources second, benchmark third, scale hardware last.**
