# Bot Trade Program — Workbench and Shared-Capital Production

Date: 2026-09-24. Status: owner-approved requirements for future implementation; not deployment evidence. Status and DAG authority: [sprint manifest](../sprints/sprint-manifest.json). Architecture amendment: [ADR-010](../decisions/ADR-010-multi-strategy-production-and-guarded-controls.md).

## Research workflow

Compose a strategy in a component form, declarative YAML, or QuantOps MCP; select historical pairs, date range, timeframe and virtual starting cash; inspect per-pair results; freeze a reviewed candidate; start isolated realtime shadow; compare comparable agents in a Top 10 tournament.

- TA-only, TA+ML, TA+DL and TA+ML+DL resolve published components through the existing registries. Experiment objectives are descriptive evaluation targets, not an automatic strategy generator.
- Form, YAML and MCP use the same PipelineManifest and validator. YAML is a presentation format for canonical JSON identity; reject duplicate keys, custom tags, executable expressions, unknown fields, non-finite values and excessive nesting/size. No arbitrary imports, downloads or loaders. Safe import/export must preserve semantic digest.
- MCP lists strategies, datasets and models with versions, feature/pair compatibility, artifact verification and runtime eligibility. Registered does not mean ready or qualified. Mutations use existing audit, revision and idempotency contracts.
- Pair/timeframe options reflect verified source capabilities and available datasets. The inspected collector already accepts pair, interval and UTC start/end; its current mapping is BTC/IDR, ETH/IDR, SOL/IDR and 1m/5m/15m/1h/4h/1d. This is code inventory, not current provider proof.
- DATA-07 extends the existing public collector/catalog flow. Reuse cached compatible partitions, fetch missing ranges with bounded requests, retain raw bytes, resume only durable windows, and publish immutable dataset versions. Display requested versus actual coverage, gaps, rejected rows and provenance. A request such as 2021–2025 is not a guarantee of available history. Never silently shorten the requested experiment interval or fabricate candles.
- Human date ranges display their timezone; convert once to explicit UTC half-open intervals. Preserve the existing availability and warm-up contracts. Reject training/test leakage and unknown applicable historical costs.
- Multi-pair historical selection creates a batch of independent ExperimentManifest records with equal starting cash per pair. Persist the batch request and child IDs idempotently; child failure does not erase successful siblings. No aggregate result may imply shared-capital performance.
- Reports expose entry/exit times and prices, quantity, IDR notional, actual modeled fees, gross/net PnL, return and exit reason; retain individual fills and position lifecycle links. Open positions/unrealized PnL are separate. Win rate is positive net-PnL closed lifecycles divided by all closed lifecycles; no closed trades is unavailable. Net return uses net equity change over initial cash. Max drawdown uses peak-to-trough marked equity. Missing marks produce unavailable, never zero.
- Historical candles do not establish tick ordering, order-book history or real fills. Reports disclose the versioned conservative execution model.

## Shadow and Top 10

- Candidate and policy identities are frozen before shadow. Research agents share validated observations but never cash, ledger, positions or risk state.
- Cohorts pin pair/universe, start/evaluation window, capital, feed, costs and execution comparison policies. Late entrants join a new comparable cohort. Gaps, incidents and unavailable metrics are visible and prevent a misleading rank.
- Each cohort requires an explicit immutable maximum-drawdown threshold in (0, 1]. Rank only comparable, valid entries with drawdown at or below that threshold: net return descending, drawdown ascending, candidate ID then agent ID ascending. Threshold equality passes. Negative returns remain rankable when otherwise eligible.
- Show at most 10 eligible strategy candidates, one ranked representative per immutable candidate version per cohort. Reject duplicate ranked registrations of the same candidate in that cohort; do not fill missing places with ineligible agents. Preserve excluded/retired/failed entries with reasons outside Top 10.
- Rank is distinct from qualification: at least 90 calendar days AND 100 closed forward trades on an unchanged candidate, plus existing operational evidence. Rank never deploys or allocates real money.
- RP-02–RP-05 supply shared evaluation, sizing/risk, OMS/fill/accounting semantics and parity evidence. Environment adapters differ; equivalent decisions do not promise identical fill prices or profit.

## Production portfolio contract

One reviewed Production release may contain multiple immutable strategy candidates. Examples are a BTC strategy, an ETH strategy and an altcoin strategy. One central portfolio/risk/OMS/ledger authority manages their shared capital. Research agent namespaces never become Production financial authorities.

### Account ownership and adoption

- Account use is bot-exclusive. All assets, locked balances and outstanding orders are inventoried and reconciled. A pair has exactly one active strategy owner; overlapping assignments reject the entire proposed release.
- Existing assets require a reviewed AdoptionRecord bound to the exact account snapshot revision, quantity, owning strategy and exit-policy reference. Existing orders must be resolved/reconciled before adoption; unknown ownership is never inferred.
- Non-adopted assets remain visible and consume account exposure, but cannot be sold by a strategy. Unsupported assets remain unmanaged; missing trustworthy marks block equity-based new entry rather than treating them as zero.
- Historical cost basis carries evidence or explicit unknown status. The mark at adoption is an operational baseline, not a fabricated purchase price. Post-adoption performance can be reported separately from unavailable lifetime PnL.
- Unexplained external trades, transfers or order changes block new account-wide entry pending reconciliation and explicit review. Expected operator-reviewed cash flows remain separately attributed. Deposits/withdrawals are not strategy profit; withdrawal commands are outside scope.

### Allocation and risk

- AllocationPolicy is immutable and revisioned: candidate/strategy refs, exclusive pair ownership, account/pair exposure limits, maximum per-trade risk, aggregate open/pending risk, capital ceiling, loss/drawdown limits and fixed strategy priority. Main uses one shared cash pool without fixed per-agent quotas or a sum-of-agent-caps rule. Values require reviewed configuration, never legacy defaults.
- Each agent owns its versioned sizing, risk-request, entry, SL, TP and trailing rules. Those rules may produce different sizes and exits from current conditions without changing candidate identity. Editing rules, parameters or model artifacts creates a new candidate. Agent requests cannot widen central limits or authorize orders themselves.
- Filled exposure plus outstanding buy reservations (including fees) consume shared cash, exposure and risk headroom exactly once. Main may reduce a proposal or reject it, never enlarge its risk to meet venue minimums. There are no agent-local wallets or reserved capital entitlements.
- Risk budget uses current reconciled, marked equity and the smaller of the candidate request and central allowance. Quantity uses entry-to-stop distance plus versioned cost/slippage allowance, bounded by available cash, pair/account exposure, aggregate open/pending risk, liquidity and verified venue constraints. Invalid/absent stop, stale marks or unknown costs reject entry. Round down to the permitted increment and recheck costs, risk and venue minimums.
- Below-minimum orders are skipped with a reason; never round upward or tighten a strategy stop solely to qualify. Verify both entry and planned exit quantities/notionals, including partial TP and residual dust after fees, against applicable venue rules at planned exit prices. Reject infeasible plans; partial fills and price moves can still create dust, handled explicitly by OMS/reconciliation rather than erased.
- Risk is a modeled loss budget, not a guaranteed maximum realized loss: gaps, liquidity and outages can worsen fills. API pair metadata and the actual order route require current evidence; neither the Lite minimum nor documentation sample values are universal API limits.
- Process simultaneous proposals deterministically by policy priority then strategy ID then intent ID, reserving atomically before accepting the next. This makes the cash-contention result reproducible across backtest, Portfolio Shadow and Production.
- Risk/exposure limit reduction below current usage stops affected new entry; it does not liquidate or erase reservations. Loss/drawdown reference equity is adjusted for verified external cash flows so deposits cannot mask losses.
- RW6 shared-capital Portfolio Shadow must test the exact candidate set and allocation policy before a multi-strategy release qualifies. Independent per-pair or tournament results alone do not prove shared-capital behavior.


### Owner-selected agents and initial capital

Strategy, agent and bot name the same trading decision unit in product language. BTC-C07 (BTC/IDR), ETH-C02 (ETH/IDR) and SOL-C02 (SOL/IDR) are the three owner-selected Main candidates. ML/DL models are internal components, not extra agents. Exact candidate versions, artifact bindings and release qualification remain to be verified; selection does not certify readiness or override staged release gates.

The owner-provided experimental capital is IDR 500,000 total in the shared pool. The 5% net monthly objective is a target, not a promise or sizing input. The owner selected a 20% capital-loss threshold relative to initial capital, not peak equity; the default threshold is IDR 400,000. Peak-to-trough drawdown remains a separate reported metric. A one-month report does not replace forward qualification.

Illustration only: IDR 2,500 risk (0.5% of IDR 500,000), a 2% stop and an assumed 0.6% combined cost/slippage allowance imply approximately IDR 96,154 notional before rounding and other constraints. Neither 0.5% risk nor 0.6% costs is an approved live default. Compare 0.5% and 1% per-trade ceilings as evaluation scenarios; neither is approved for live activation. Aggregate risk and daily-loss limits remain unset.

Venue references checked 2026-09-24: [Indodax fee/minimum explanation](https://help.indodax.com/hc/id/articles/4416646599705-Rincian-Biaya-Transaksi-di-INDODAX) distinguishes Lite IDR 10,000 and Pro IDR 25,000; [official API pair metadata](https://github.com/btcid/indodax-official-api-docs/blob/master/Public-RestAPI.md#pairs) documents pair minima and increments. Current minima for the intended API route are not certified by this documentation update.

### Dashboard defaults and capital-loss response

Defaults populate new drafts only; they never initialize financial balances, overwrite active policy, reset a baseline, or apply automatically after restart/upgrade. Main and agent settings remain configurable through reviewed, versioned policies/candidates.

| Setting | Initial draft default |
|---|---|
| Program initial capital | IDR 500,000 total; actual cash/assets come from reconciliation |
| Capital allocation | One shared pool, no fixed per-agent quota |
| Selected candidates | BTC-C07, ETH-C02, SOL-C02; exact versions and staged release gates still required |
| Agent sizing and exits | Candidate-owned adaptive sizing, SL, TP and trailing rules; no fabricated numeric parameters |
| Reporting target/window | 5% net monthly, monthly report; no forced trading or shorter qualification |
| Capital-loss threshold | 20% of reviewed initial-capital baseline; IDR 400,000 at IDR 500,000 baseline |
| Threshold action | Controlled close-out of bot-owned positions, followed by manual resume review |
| Per-trade risk ceiling | Unset for live; evaluate 0.5% and 1% |
| Aggregate risk and daily-loss limits | Unset; mandatory before new-policy activation |

- PM-08 compares reconciled cash plus trustworthy marked asset value minus estimated remaining exit costs against the capital floor, using Decimal and counting costs once. At or below the floor triggers the policy; rising equity does not raise this initial-capital floor. Missing marks/costs block entry and disclose unavailable evaluation, never assume zero or safe.
- External deposits/withdrawals require a reviewed baseline-adjustment rule before new-policy activation. Preserve cash-flow attribution and historical losses; manual resume, edits and restart cannot silently reset the baseline. This packet does not supply an unapproved adjustment formula.
- PM-09 persists a controlled-close-out intent when the floor is breached: prohibit new entries, request cancellation of outstanding entry remainders through normal OMS, reconcile uncertain orders and late fills, and close only bot-owned/adopted quantities through the existing approved execution policy when all required write gates permit it. Coordinate with existing pending exits to prevent duplicate sells. No immediate-fill, minimum final equity or automatic order-type substitution is promised.
- The close-out intent survives restart into RECOVERY; a price rebound does not clear it. Missing venue capability, unsafe execution, unknown orders and unsellable dust leave explicit blocked/residual state. Completion requires zero bot-owned positions, resolved entry/exit orders, released reservations and fresh reconciliation. Non-adopted assets remain visible but are not liquidated.
- Manual resume is required after close-out and still must pass capital-floor, risk, release, health and reconciliation checks; a resume command alone cannot override an unresolved floor breach. Controlled close-out is a portfolio-risk action, distinct from candidate replacement draining and from operational HALT. HALT continues to prohibit writes when its gates fail; eligible close-out work waits durably.
- API-04/UI-03 reuse allocation proposal/decision and existing candidate composition/release flows. Expose backend defaults, draft values, active revision, unset required fields, validation issues, affected positions and activation outcome. Editing supported agent parameters creates a new candidate draft for existing evaluation/release; no direct live agent-parameter patch route is admitted.
- Default/draft/active values stay distinct. Approval binds exact validated bytes and current revisions; stale approval requires a new proposal, identical retries return one result. Widening risk requires new shared-capital evidence. Lower limits block affected entries without implicit liquidation unless the separately approved capital-floor close-out policy is triggered. Existing positions retain candidate-bound exits; central close-out policy can override waiting for a strategy exit signal without rewriting that candidate.

### Exits, fills and replacement

- Entry, SL, TP, trailing and other exit behavior remain candidate-bound and tested. Policy edits produce a new candidate; dashboard controls do not hot-edit exits.
- OMS acceptance is not a fill. Only normalized, confirmed fills change positions/fees. Partial fills create exactly their filled quantity; exits cover actual available position quantity, with pending sells reserved to prevent oversell.
- On an exit trigger during a partially filled entry, request cancellation of its remainder, track cancel uncertainty, and reconcile subsequent fills. Do not assume cancellation succeeded. Additional confirmed entry fills remain managed by the same exit policy; never blindly resubmit an uncertain order.
- Persist exit state, trailing extrema, outstanding order identity and ownership with recovery evidence. Duplicate events/fills have one effect. Missing venue capability rejects the declared policy; no implicit switch to a different order type.
- Native stop/OCO availability, fee/tax, minimum quantity and order semantics require current venue evidence. Bot-managed stops explicitly disclose process/network outage exposure; stop price is not guaranteed fill price.
- ACTIVE -> DRAINING -> RETIRED applies to strategy ownership. Draining prevents old entries while preserving its exits when backend health permits. New owner activation waits for zero old positions, resolved terminal orders, zero reservations and fresh reconciliation. Dust that cannot be sold under venue rules blocks completion for operator review; it is never rounded away.
- Pause-entry keeps eligible exits operating. HALT does not flatten positions and does not grant an exit exception to failed safety gates. Restart enters RECOVERY and restores durable risk, ownership and exit state before explicit resume.

## Services and operator controls

Reuse existing local services and API envelopes; Decimal money stays text on wire. The named owning sprint defines the versioned Pydantic models and persistence through the existing stores, not a second financial database.

| Owner | Interface / durable result |
|---|---|
| DATA-07 | Public pair/timeframe capability catalog; collect(DatasetRequest, request_id) returns job/dataset refs and QualityReport through existing jobs/registry |
| RW2-03 | import_yaml(text), export_yaml(manifest), validate(manifest) use one PipelineManifest; draft edits retain expected revision |
| RW3-01 | create_batch(request, request_id) returns stable batch and per-pair experiment refs; get_batch exposes independent child statuses/results |
| PM-05 | Versioned release binds candidate set, per-candidate gate evidence, pair-owner map, allocation-policy digest and aggregate shared-capital evidence |
| PM-07 | propose_adoption(snapshot_ref, assignments), approve_adoption(proposal_id, expected_revision, actor, reason, request_id) return AdoptionRecord; retain cost-basis validity and reconciliation refs |
| PM-08 | AllocationPolicy and deterministic centralized assessment/reservation consume current portfolio revision and candidate intents; no agent-local money authority |
| PM-09 | request_drain(strategy_id, expected_revision, request_id) returns durable lifecycle receipt; reconcile completion before owner transfer |
| API-04 | Guarded adoption decisions, allocation proposals/approval, pause-entry, resume, halt and drain commands return durable CommandReceipt |
| UI-03 | Render backend proposals, revisions, impact and receipts; never calculate authoritative allocations or position quantities in browser |

Production command routes live under `/api/v1/production/commands/`: `adoption/propose`, `adoption/decide`, `allocation/propose`, `allocation/decide`, `pause-entry`, `resume`, `kill-switch`, and `strategies/{strategy_id}/drain`. Reuse existing mode/approval/reconciliation command contracts where applicable. Each request binds actor capability, request ID, reason and expected revision. Proposal approval is tied to exact bytes and current state; stale state requires a new proposal. Identical retries return the same receipt, conflicting retries reject. There is no generic order, withdrawal, hot-model-reload or bypass-release endpoint. Research MCP cannot obtain Production control capability.

Allocation changes are reviewed policy/release revisions. They become effective only through existing backend release and authority checks; API acknowledgement is not activation proof. A widened risk envelope requires new shared-capital evaluation. Tests/development use fake adapters and no live writer. Authentication and transport protections must be qualified before enabling commands.

## Delivery and proof

- DATA-07 owns collection extension without reopening DATA-03/05 or RW1-01 DONE evidence. RW2–RW5/RW7–RW8 consume the decisions above. RP parity and RW6 consume Production shared-capital semantics. PM-05 is extended; new PM-07/08/09, API-04 and UI-03 own adoption, allocation, exits and guarded controls. PM-06 consumes their evidence plus RP-05, RW6-01, OPS-01 and QA-03.
- Tests cover format round trips, rejected YAML, range gaps, no lookahead, exact fees/metrics, partial batch failure, Top 10 boundary/ties/exclusions, shared-cash contention, pair conflicts, adoption unknown basis, cash-flow attribution, partial fills/cancel races, stale approvals, duplicate effects and crash recovery. Fake network and temporary stores only.
- One independent reviewer checks the exact documentation commit and future implementation SHAs. Documentation validator plus diff-check verify this packet, not runtime readiness. Future task completion requires actual tests and independent PASS.
- No live credentials, account inspection, order mutation, host changes, merge/push or deployment is authorized by this packet. The owner separately authorized read-only SSH host inventory during documentation work; its non-financial results are recorded in the capacity cross-check. ASUS co-resident capacity and G0–G7 remain external gates. Lenovo remains the training/tuning host.

## ASUS capacity cross-check

The [recorded-host cross-check](ASUS-BOT-CAPACITY-CROSSCHECK.md) adds mandatory mixed-load admission and qualification cases to DATA-07, JOB-02, RP-04, RW5/RW6, OPS-01, QA-03 and PM-06. No safe agent/pair count has been established; Top 10 is a presentation limit only.
