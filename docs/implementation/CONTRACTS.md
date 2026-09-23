# Workbench and shared-runtime domain contracts

Classification: TARGET ARCHITECTURE / PLANNED. No interface in this document is claimed implemented unless the current-state audit says so. Implements frozen v1.0 and ADR-005/006/007. Task files name the owning implementation; consumers cannot independently redefine these types.

The [ADR-008 amendment](../decisions/ADR-008-shared-market-runtime-and-asus-edge.md) and [Shared Market Runtime](../production/research-workbench/SHARED-MARKET-RUNTIME.md) refine feed ownership, event provenance, shared features/predictions and ASUS admission. These are extensions of the contracts below, not a second registry or execution kernel. Owning RW0/RP/RW2 tasks must version schema additions and register their implementation dependencies before code work.

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
| RuntimePlan | RW0-01/RP-02 | resolved pipeline/strategy/model refs and byte hashes, ordered feature schema/hash, universe/timeframe, dataset refs, sizing/exit/risk/cost/execution refs, Git/environment identity and seed; no completed experiment or candidate reference |
| CandidateManifest | RW0-01/RW4-01 | exact RuntimePlan ref, reviewed completed experiment ref, pipeline graph/ref, strategy/model byte hashes, ordered feature schema/hash, universe/timeframe, risk/cost/execution refs, Git/environment identity, evaluation evidence refs |
| AgentManifest | RW0-01/RW5-01 | candidate ref, cohort ID, initial virtual cash/currency, immutable runtime policy refs, unique namespace ID, canonical feed identity |
| PortfolioShadowManifest | RW6-01 | candidate refs, initial shared cash/currency, allocation policy, concentration/correlation policy refs, cost/execution refs, namespace ID; distinct from AgentManifest |
| PromotionRequest | RW9-01 | request ID, actor/reason/time, candidate digest, historical/forward/incident/restart evidence refs, qualification policy version; no deployment mode or credentials |

Dataset actual range is unknown for zero bars; such a version cannot validate for experiment use. Historical source evidence is immutable even if duplicate/gap repair creates a clean descendant. Dataset schema includes UTC `available_at`, closed bars and exact venue units; ADR-002 and existing dataset-feature contracts still govern temporal details.

Pipeline node kinds: dataset input, indicators/features, TA, regime/filter, ML, DL, ensemble, gate/veto, sizing, exits, execution policy. Ports are typed `MarketObservation`, `FeatureFrame`, `DecisionProposal`, `ProbabilityVector`, `SignalIntent` or `ExecutionPolicyRef`; edges must match. The executable decision DAG terminates in intents; execution policy configures the adapter and is not a second runtime. Require acyclic graph, reachable outputs, one explicit sizing policy, one exit policy, no ambiguous multiple writers to a scalar port. Fan-in must use a declared ensemble node. Soft voting requires nonnegative finite weights with positive sum, ordered compatible model outputs and explicit threshold. Missing required output means abstain with reason, never silent neutral vote.

Seed registrations are manifests for BTC-C07 and ALT-C02, with pair-specific versioned parameters. TA-only has zero model nodes. M02+D04 is admissible only when verified artifacts/schema/environment exist. Never silently substitute M02 for a declared ensemble.

## Domain interfaces (RP-01..04)

RP-01 moves only existing `SignalIntent` ownership; its current fields/defaults remain byte compatible. RP-03 separately versions semantic changes where needed.

`CanonicalMarketEvent(event_id, feed_id, sequence, pair, event_time, available_at, observation, quality_ref)` has immutable content-derived event ID and monotonically ordered feed sequence. UTC availability cannot exceed evaluation time. Duplicate ID/same bytes is replay; duplicate ID/different bytes is corruption. One gateway owns collection per stream; agents cannot poll independently.

`sequence` is the durable local feed position, never an Indodax channel offset or trade sequence. The versioned envelope adds venue/type/schema, receive time, nullable actual venue time, source connection/channel/epoch/offset/sequence, source identity/hash and quality/source references as defined in [event contracts](../production/research-workbench/SHARED-MARKET-RUNTIME.md#g-event-feature-and-prediction-contracts). Missing venue timestamp remains null; receive-derived `event_time` is explicitly flagged. Original admitted envelopes are immutable on replay; receipt diagnostics do not mutate event identity or availability.

RuntimePlan and candidate-bound immutable policy references also resolve required market inputs, feature schema, model artifacts, trigger policy and shadow-mode eligibility. Triggers include candle-close/event/periodic/feature-change semantics with declared deadline and missed-trigger behavior. AgentManifest/PortfolioShadowManifest retain their existing distinct ownership. Shared FeatureSnapshot/PredictionResult identities bind exact source/feature/model/preprocessing/runtime bytes and are reused only across compatible eligible consumers. Registry state never grants loading, ASUS admission or production-write authority.

`RuntimeState` contains runtime-plan digest, optional candidate digest (required in forward shadow/production), portfolio snapshot/revision, feature/exit state, risk snapshot/revision, market cursor and runtime policy digests. It has no API credentials or concrete live client.

### First-experiment bootstrap and candidate binding

RW0 owns the immutable `RuntimePlan` schema. RW2-03 resolves and validates the component graph; `ExperimentService.validate` pins a RuntimePlan before a job can run. `verify_runtime_plan(plan, resolver) -> VerifiedRuntimePlan` verifies every declared artifact/schema/policy byte without requiring a completed experiment. `CandidateRuntime.load_plan(plan: VerifiedRuntimePlan) -> CandidateRuntime` is the common evaluator entry. Historical experiments use this verified plan, never a fabricated CandidateManifest. The result binds the exact plan digest; it cannot declare production qualification.

RW4 packages a CandidateManifest only after a completed reviewed result, binding that same RuntimePlan plus evaluation evidence. `CandidateRuntime.load(candidate: VerifiedCandidate) -> CandidateRuntime` verifies candidate/package linkage then delegates to `load_plan`. Forward shadow and production require this candidate wrapper; research experiment jobs may use verified RuntimePlan directly. Neither loader compiles a different strategy/risk/exit path. Candidate provenance is additional evidence, not an input that changes strategy behavior. This removes the experiment→candidate→experiment bootstrap cycle without weakening candidate qualification.

`CandidateRuntime.evaluate(event: CanonicalMarketEvent, state: RuntimeState) -> tuple[SignalIntent, ...]` verifies candidate and feature identity before evaluation. Deterministic intent ID derives from runtime-plan digest, event ID, output node and stable ordinal; candidate digest remains separate provenance. Thus packaging completed evidence does not change decision identity. It never submits an order. Clock, data and model inference are injected through declared ports; research training cannot be imported into production evaluation.

`RuntimeKernel.process(event: CanonicalMarketEvent) -> RuntimeStepResult` coordinates candidate, portfolio, risk, authority, OMS and normalized fills. Result fields: event ID, namespace, runtime-plan digest, optional candidate digest, decision IDs, order IDs, transaction IDs, rejected reason codes, envelope status and durable cursor. ACKNOWLEDGED means the event transaction protocol below durably completed admission/decision effects, not that asynchronous orders are filled. Telemetry delivery failure does not undo the financial decision.

`ExecutionStateStore.apply_fill(fill: Fill, expected_revision: int) -> FillCommitResult` returns revision, transaction ID, OMS order ID/state, duplicate flag. Namespace is fixed by store construction. Validate fill identity/content, quantity, fees, order matching and terminal late-fill policy before mutation. One SQLite transaction per namespace persists journal, OMS quantity/state, fill identity and audit; publish in-memory state after commit. Fills are independent execution-evidence events and use the same event-envelope protocol; a market event never waits for all its future fills. A conflicting duplicate fails closed. Unmatched fills are quarantined and block reconciliation; never dropped. Cancelled-order late fills update cumulative quantity/financial evidence while retaining cancellation lifecycle fact, with explicit late-fill event. Overfill quarantines the observation and halts; it is not silently booked into an invalid state.

`ShadowVenueAdapter` and `SimulatorVenueAdapter` implement existing `TradingVenue` order semantics but use injected fill-model/clock ports. Fill models may control latency, partial fills, slippage and rejects; they return normalized domain fills and cannot mutate cash directly. Production write client is resolved only in production composition. Research process/package import boundary rejects write-adapter reachability, including factories and wrapper injection.


### Durable event protocol (PM-02 store; RP-04 coordinator)

One namespace-local `ExecutionStateStore` owns the event inbox, state revisions, financial journal, OMS, reservations, risk/feature/exit snapshots, feed cursor and submission outbox. No cross-store cursor fallback is permitted.

`prepare_event(event, expected_revision) -> EventEnvelope` transactionally inserts the immutable event hash, sequence and input state revision with PREPARED status. Duplicate same bytes returns existing envelope; conflicting bytes or out-of-order non-replay sequence halt. The input cursor is not advanced. Only one unfinished envelope may own the namespace's admission phase; asynchronous fills have their own serialized ingestion events.

Evaluation computes the prospective feature/exit/risk state, deterministic intents and reservations from the prepared input revision without publishing memory. `commit_decision(envelope_id, expected_revision, next_state, intents, reservations) -> EventEnvelope` atomically writes DECIDED, next state, risk decisions, NEW OMS orders, durable outbox entries and audit. Even zero-intent/no-fill events must commit their feature/exit/risk state. It does not advance the input cursor. Repeated same transition is idempotent; divergent recomputation is corruption.

`claim_submission(outbox_id, expected_revision) -> SubmissionAttempt` commits ATTEMPTING plus SUBMITTING OMS state before any venue call. Runtime revalidates execution permission immediately before this transition/call. It records authoritative acceptance/rejection through `record_submission(attempt_id, outcome) -> EventEnvelope`. Timeout or crash after ATTEMPTING is UNKNOWN; restart must reconcile using stable client/order IDs, never blindly resend. An unclaimed PENDING outbox can be resumed; a definitive pre-send authorization rejection is persisted as rejection without a venue call. Simulation follows these same transitions through its adapter.

`acknowledge_event(envelope_id, expected_revision) -> RuntimeStepResult` atomically records ACKNOWLEDGED and advances feed cursor after every decision outbox has a durable submit result, rejection or UNKNOWN outcome. UNKNOWN also atomically latches halt for new exposure; advancing the consumed-event cursor never clears it. Open/partially filled orders may outlive the market event. New risk-admitting events cannot run while ATTEMPTING lacks recorded/recovered outcome.

Normalized fill events call `apply_fill` to atomically write journal, OMS cumulative quantity/state, processed identity, risk/account state and fill-event ACKNOWLEDGED/cursor. Multiple fills are separate events; a crash preserves completed fill envelopes and replays only unfinished ones. A no-fill market event still goes PREPARED→DECIDED→ACKNOWLEDGED and advances feature/exit/risk state once. All public methods use optimistic revision checks; memory is reconstructed from committed state after any failed write.

`recover() -> RecoveryReport` enters RECOVERY, verifies journal/snapshot/revision linkage, reloads all state/cursors, resumes PREPARED by deterministic reevaluation, resumes DECIDED without reevaluating decisions, and resolves ATTEMPTING to reconciled outcome or UNKNOWN/HALTED. It never manufactures acceptance. PM-02 owns these atomic methods/failure tests; RP-04 owns sequencing/adapters and cross-environment restart tests.

Required crash cases: before/after PREPARED, DECIDED, ATTEMPTING, recorded outcome, ACKNOWLEDGED and each fill commit; include no-intent events, one event producing two orders with only one submitted, and delayed partial fills after market cursor advancement. Result must contain each state effect exactly once and no blind replayed real write.

### Shared service result schemas

RW0 defines `ServiceError(code: str, message: str, subject_refs: tuple[ArtifactRef,...], retryable: bool)` and `Provenance(source_sha, environment_digest, input_refs, policy_refs, runtime_plan_digest, candidate_ref=None)`. Error is not a successful zero result. An API `ServiceResponse(schema_version, request_id, data=None, error=None)` has exactly one of data/error; local services raise the corresponding typed error before adapters serialize it.

`MetricValue(value: Decimal|float|None, unit: str, validity: VALID|UNAVAILABLE|INVALID, reason: str|None)` requires finite value only for VALID; other states require null and reason. Money is Decimal text on wire. Missing data is never zero or Infinity. All reports include schema version, ID, created_at audit metadata, provenance and artifact content/storage digests where published.

| Result type / owner | Required payload beyond shared report fields |
|---|---|
| QualityReport / RW1 | accepted/rejected row counts, requested/actual intervals, gaps, duplicate/conflicting counts, source/partition refs, findings(code,interval,source_ref), valid_for_experiment bool |
| EvaluationArtifact / RW2 | model/dataset/split refs, ordered metric map, calibration evidence ref, train-only transform refs, status COMPLETED/FAILED/INVALID, failure reason |
| ResultArtifact / RW3 | experiment ref, runtime-plan ref, status COMPLETED/FAILED/CANCELLED, equity-series ref, trade/fill/journal refs, ordered metric map, execution assumptions, retained failure/attempt refs |
| ComparisonReport / RW3 and consumers | ordered subject refs, metric rows, per-subject observation window/capital/cost/feed policies, comparable bool, incompatibility reasons; no winner/deployment authority |
| RecoveryReport / PM-02 and consumers | namespace, restored revision/cursors, journal integrity status, unresolved envelope/order IDs, halt reasons, effective RECOVERY/PAUSED/HALTED state, permitted next actions |
| MigrationReport / PM-02 | read-only source hashes/revisions, target schema/namespace/revision, reconciliation deltas, verified bool, blocking reasons; never credentials |
| ExperimentRecord / RW3 | manifest ref, lifecycle, pinned runtime-plan ref after validation, job/attempt refs, terminal result ref or null, revision |
| CandidateRecord / RW4 | immutable manifest ref, lifecycle revision, append-only transition/evidence refs |
| CohortRecord / RW5 | immutable cohort manifest ref, agent refs, comparison policy ref, created_at |
| Leaderboard / RW5 | cohort ref, as-of feed cursor/time, metric/rank rows, comparability reasons and separate QualificationDecision per agent |
| QualificationDecision / RW5 | candidate/agent refs, policy ref, elapsed days, closed forward trades, incident/recovery evidence refs, qualified bool, rejection reasons; no live authority |
| ExportArtifact / RW9 | request ref, candidate/runtime-plan refs, component/evidence hashes, release schema version, qualification refs, export checksum; no execution mode |

`DraftRef` is `(id, revision, digest)`; `ValidationReport` is `(valid, errors(code,subject_id,port), resolved_refs)`. `DatasetRequest` is `(venue,pair,timeframe,start,end,source_ref,parent_ref=None)` with UTC half-open intervals. `PortfolioState` is `(cash,positions,marks,reservations,revision)` with Decimal financial values. Existing JobRecord remains the queue type, exposed by stable service mapping rather than a second queue. `PortfolioRun` carries PortfolioShadowManifest ref, namespace, lifecycle/revision and result ref; `AgentRecord` fields remain in RW5-01. Types in this table are implemented by the named owner and consumed unchanged downstream.

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
