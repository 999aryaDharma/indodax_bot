# Workbench and shared-runtime domain contracts

Classification: TARGET ARCHITECTURE / PLANNED. No interface in this document is claimed implemented unless the current-state audit says so. Implements frozen v1.0 and ADR-005/006/007. Task files name the owning implementation; consumers cannot independently redefine these types.

## Identity and storage (RW0-01)

`ArtifactRef(kind: str, id: str, version: str, sha256: str, schema_version: str)` identifies verified bytes; SHA-256 is lowercase 64-hex. IDs/versions are nonempty opaque strings, never filesystem paths. Storage resolves IDs within configured roots and rejects traversal, symlinks escaping roots and mismatched bytes. No user-supplied import path or executable expression.

`canonical_bytes(value: Manifest) -> bytes` encodes UTF-8 canonical JSON: sorted keys, compact separators, finite numbers, UTC timestamps as ISO8601 with `Z`, Decimal as normalized non-exponent strings, immutable tuples serialized as arrays. No absolute paths, hostnames, elapsed times or ambient clocks in semantic identity. Explicit creation timestamps are audit metadata excluded from semantic digest; input version/schema and all execution-relevant references are included. Full envelope bytes also have a storage checksum. No ambient creation time generated inside hashing. Nested data is deep immutable or defensively copied at every public read boundary. `manifest_digest(value) -> str` hashes canonical semantic bytes, excluding its own digest.

Immutable registry operation `publish(manifest, expected_absent=True) -> ArtifactRef`: same identity/same bytes returns existing reference; same logical ID/version with changed semantics raises `IMMUTABLE_VERSION_CONFLICT`. Publication is atomic/no-clobber across processes, not exists-then-replace. Catalog visibility follows durable artifact publication. Failed publication cannot expose a completed record. Mutable drafts use revision compare-and-swap; published manifests never mutate. Lifecycle events are appended separately from artifact identity.

## Manifest fields

All manifests carry `schema_version`, logical ID, version and semantic digest. A reference is verified before use, not trusted because its string matches.

| Type | Owning task | Required semantic fields |
|---|---|---|
| DatasetManifest | RW0-01/RW1-01 | venue, canonical pair, timeframe, requested start/end, actual start/end, bar count, source ID/version, partition refs and byte hashes, quality report ref, missing half-open intervals, duplicate count, parent dataset ref on repair/extension, created_at audit metadata |
| StrategyManifest | RW0-01/RW2-01 | strategy ID/family/version, implementation artifact ref, parameter schema and parameters, required feature schema, timeframe constraints, decision/exit contract versions |
| ModelManifest | RW0-01/RW2-02 | architecture/loader ID from allowlist, artifact refs, ordered feature schema, preprocessing/calibration refs, training/validation/test evidence refs, metrics ref, universe, runtime/dependency requirements |
| PipelineManifest | RW0-01/RW2-03 | typed nodes, explicit ports/edges, component refs, dataset/timeframe constraints, ensemble/gate parameters, sizing/exit refs, risk/cost/execution policy refs |
| ExperimentManifest | RW0-01/RW3-01 | dataset ref, pipeline ref, initial_virtual_cash Decimal + currency, cost/risk/execution refs, Git SHA, environment digest, seed, parent experiment ID if cloned |
| CandidateManifest | RW0-01/RW4-01 | reviewed completed experiment ref, pipeline graph/ref, strategy/model byte hashes, ordered feature schema/hash, universe/timeframe, risk/cost/execution refs, Git/environment identity, evaluation evidence refs |
| AgentManifest | RW0-01/RW5-01 | candidate ref, cohort ID, initial virtual cash/currency, immutable runtime policy refs, unique namespace ID, canonical feed identity |
| PortfolioShadowManifest | RW6-01 | candidate refs, initial shared cash/currency, allocation policy, concentration/correlation policy refs, cost/execution refs, namespace ID; distinct from AgentManifest |
| PromotionRequest | RW9-01 | request ID, actor/reason/time, candidate digest, historical/forward/incident/restart evidence refs, qualification policy version; no deployment mode or credentials |

Dataset actual range is unknown for zero bars; such a version cannot validate for experiment use. Historical source evidence is immutable even if duplicate/gap repair creates a clean descendant. Dataset schema includes UTC `available_at`, closed bars and exact venue units; ADR-002 and existing dataset-feature contracts still govern temporal details.

Pipeline node kinds: dataset input, indicators/features, TA, regime/filter, ML, DL, ensemble, gate/veto, sizing, exits, execution policy. Ports are typed `MarketObservation`, `FeatureFrame`, `DecisionProposal`, `ProbabilityVector`, `SignalIntent` or `ExecutionPolicyRef`; edges must match. The executable decision DAG terminates in intents; execution policy configures the adapter and is not a second runtime. Require acyclic graph, reachable outputs, one explicit sizing policy, one exit policy, no ambiguous multiple writers to a scalar port. Fan-in must use a declared ensemble node. Soft voting requires nonnegative finite weights with positive sum, ordered compatible model outputs and explicit threshold. Missing required output means abstain with reason, never silent neutral vote.

Seed registrations are manifests for BTC-C07 and ALT-C02, with pair-specific versioned parameters. TA-only has zero model nodes. M02+D04 is admissible only when verified artifacts/schema/environment exist. Never silently substitute M02 for a declared ensemble.

## Domain interfaces (RP-01..04)

RP-01 moves only existing `SignalIntent` ownership; its current fields/defaults remain byte compatible. RP-03 separately versions semantic changes where needed.

`CanonicalMarketEvent(event_id, feed_id, sequence, pair, event_time, available_at, observation, quality_ref)` has immutable content-derived event ID and monotonically ordered feed sequence. UTC availability cannot exceed evaluation time. Duplicate ID/same bytes is replay; duplicate ID/different bytes is corruption. One gateway owns collection per stream; agents cannot poll independently.

`RuntimeState` contains candidate digest, portfolio snapshot/revision, feature/exit state, risk snapshot/revision, market cursor and runtime policy digests. It has no API credentials or concrete live client.

`CandidateRuntime.evaluate(event: CanonicalMarketEvent, state: RuntimeState) -> tuple[SignalIntent, ...]` verifies candidate and feature identity before evaluation. Deterministic intent ID derives from candidate digest, event ID, output node and stable ordinal. It never submits an order. Clock, data and model inference are injected through declared ports; research training cannot be imported into production evaluation.

`RuntimeKernel.process(event: CanonicalMarketEvent) -> RuntimeStepResult` coordinates candidate, portfolio, risk, authority, OMS and normalized fills. Result fields: event ID, namespace, candidate digest, decision IDs, order IDs, transaction IDs, rejected reason codes and durable cursor. A successful result means effects and cursor committed; telemetry delivery failure does not undo the financial decision.

`ExecutionStateStore.apply_fill(fill: Fill, expected_revision: int) -> FillCommitResult` returns revision, transaction ID, OMS order ID/state, duplicate flag. Namespace is fixed by store construction. Validate fill identity/content, quantity, fees, order matching and terminal late-fill policy before mutation. One SQLite transaction per namespace persists journal, OMS quantity/state, fill identity and audit; publish in-memory state after commit. A conflicting duplicate fails closed. Unmatched fills are quarantined and block reconciliation; never dropped. Cancelled-order late fills update cumulative quantity/financial evidence while retaining cancellation lifecycle fact, with explicit late-fill event. Overfill quarantines the observation and halts; it is not silently booked into an invalid state.

`ShadowVenueAdapter` and `SimulatorVenueAdapter` implement existing `TradingVenue` order semantics but use injected fill-model/clock ports. Fill models may control latency, partial fills, slippage and rejects; they return normalized domain fills and cannot mutate cash directly. Production write client is resolved only in production composition. Research process/package import boundary rejects write-adapter reachability, including factories and wrapper injection.

## Lifecycles and control

- Experiment: DRAFT → VALIDATED → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED. DRAFT edits use new immutable revision; validation pins that revision. Terminal evidence never changes. Clone creates a new experiment ID/parent ref. Cancellation fences worker generation before final publication; failed attempts remain evidence.
- Candidate: DRAFT → BACKTEST_VERIFIED → SHADOW → QUALIFIED_CHALLENGER → PROMOTION_REQUESTED → RETIRED, plus retirement from any non-retired state. State is append-only evidence outside immutable configuration. Production deployment authority is a separate release record.
- Agent: REGISTERED → RUNNING ↔ PAUSED → RETIRED; failures enter HALTED, restart enters RECOVERY, verified restoration permits PAUSED then explicit resume. Pause permits recovery/reconciliation and records a coverage gap; no new decisions. Candidate change requires new agent. Qualification duration/trades are candidate-bound; gaps and incidents are visible and cannot be erased by resume.
- Production: frozen modes and restart rules apply. Desired mode is distinct from effective RECOVERY. HALT is never implicit flattening.
- Dataset/component publication: draft → validated immutable published version; repair/retraining creates a descendant. Retire/archive does not delete evidence.

## Qualification, fairness and costs

Qualification requires elapsed >=90 calendar days AND >=100 closed forward trades on unchanged candidate, with clean risk/ledger/reconciliation and restart evidence under frozen G3. A closed trade is completed position lifecycle after fees, not each fill. Cohort comparison discloses capital, periods, policies and feed gaps; incomparable entries are flagged, not auto-ranked as winners. Historic and forward evidence are separate. Rank never calls promotion.

Default virtual capital remains explicit per manifest; examples of Rp1,000,000 do not silently change legacy Rp500,000 evidence. No current fee/minimum-order values are asserted. Cost identity is time-valid and applied exactly once; unknown periods reject execution. Decimal cash/quantities and registered feature tolerances are distinct.

## Control-plane services and observability

Workflows expose typed local application services first. QuantOps MCP invokes only those services with actor/request ID/reason; every mutation records input refs, output refs, revision, timestamp, outcome and error code. Retry of identical request is idempotent; conflicting payload under same request ID is rejected. No arbitrary code execution, file path, pickle, model download or production write tool.

Dashboard form and graph views serialize the same PipelineManifest and call the same validator. Draft save uses expected revision; stale revision returns conflict and preserves both edits for explicit clone/retry. Reports display missing evidence as unknown, never zero. Read models derive from authoritative artifacts/stores, not UI state.

Logs/metrics correlate namespace, candidate digest, event/intent/order/fill IDs, policy version and result reason; omit secret/private payloads. Performance gates are measured on target host before activation. No host-specific absolute path is part of artifact identity.
