# Repository current-state audit

Classification: FACT / CURRENT IMPLEMENTATION. Baseline `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`, 2026-09-21. Inspection of tracked source, configuration, deployment files and test definitions; not a fresh product test run or host audit. [Source inventory](SOURCE-INVENTORY.md) enumerates files and symbols. Binary model artifacts were not deserialized. No private account or live dataset was accessed.

## Subsystem map

Paths below are repository-relative. IMPLEMENTED applies only to the described primitive.

| Area | Classification | Actual implementation and boundary | Remaining work |
|---|---|---|---|
| Flat bot | LEGACY | `src/main.py`, signal/TA/cache/observer, paper trader/accounting, risk manager, position tracker, Telegram | Preserve compatibility; no reuse through imports into canonical lab. Architecture test enforces this boundary. |
| Canonical contracts | IMPLEMENTED | `contracts/common.py`, `contracts/market.py`; Decimal and UTC market records | Decision contracts still owned by backtest; RP-01. |
| Historical ingestion | PARTIAL | `data/indodax_candles.py`, wire/parquet stores, publication, quality, sentry; backfill CLI | Workbench dataset identity, coverage discovery and immutable extension service; RW1-01. |
| Dataset inventory | PARTIAL | `cli/dataset_inventory.py` hashes partitions; `dataset_registry.py` builds inventory aggregate | Registry identity includes local root; empty inventory can report PASS; no full requested/actual-range catalog lifecycle. |
| Universe/bars | IMPLEMENTED | Universe snapshot/materializer/lineage, time/event bars, eligibility | Historical review/real-data gates remain separate from these primitives. |
| Features/labels | PARTIAL | Versioned feature registry/builder, technical/context/liquidity/LOB, return/barrier labels and purged splits | Live-shadow feature computation is independent; feature/replay identity must be unified, RP-02. |
| TA catalog | IMPLEMENTED | In-memory `StrategyRegistry`, C01/C02/C03/C04/C07/C10/S01/S02, multitimeframe; YAML specs | Durable drafts/versions, deterministic logic identity, declarative composition; RW2-01/RW2-03. |
| ML/DL | EXPERIMENTAL / PARTIAL | M01–M06; D01–D04; graph, foundation, LOB and RL modules; training/calibration/bundle utilities | General registry and verified loaders; optional dependency, data and resource gates. No assumption of champion or production eligibility. |
| Artifacts | PARTIAL | JSON/UBJ/PT artifacts in `models/artifacts`; portable M01 bundle verification | Filenames are not candidate manifests. Verify exact bytes, preprocessing and environment before loading; RW2-02/RW4-01. |
| Backtest | PARTIAL | `ReplayBacktestEngine`, conservative simulator, costs, risk, ledger, feature replay and result JSON | No OMS path; no common candidate runner/portfolio constructor; RP-02..05 and RW3-01. |
| Experiment evidence | PARTIAL | Immutable SQLite `ExperimentRunRecord` history; SUCCESS/FAILED/INVALID_RUN | Not DRAFT→VALIDATED→QUEUED→RUNNING lifecycle; no complete clone/cancel service. |
| Jobs | IMPLEMENTED | SQLite leased queue with generation fencing, worker checkpoints, resource/repeat policies | Connect lifecycle services, cancellation fencing, artifact finalization; RW3-01. |
| Candidate registry | MISSING | Candidate IDs occur in records; portable model/release bundles exist | Frozen composition/evidence package and registry lifecycle; RW4-01. |
| Live shadow | PARTIAL | `run_shadow_bot.py` → `LiveShadowEngine`: BTC/ETH/SOL, M02 loaders, shared portfolio, ticker fills, checkpoint store | No isolated AgentFactory, OMS or canonical fan-out. D04 artifacts exist but this engine loads XGBoost only. |
| Shared-capital paper | LEGACY / PARTIAL | `paper/portfolio.py` has separate `SharedCapitalLedger` allocation/checkpoint model | Not the same financial journal and not tournament isolation; replace through explicit migration, RW6-01. |
| Tournament | PARTIAL | `evaluation/tournament.py` is historical candidate evaluation/report/follow-up utility | Not live agent tournament. Durable isolated agents, cohorts, comparable coverage and qualification required; RW5-01/02. |
| Promotion | PARTIAL | `paper/promotion.py` checks forward duration/trades and has in-memory champion registry | Research champion terminology must not grant production authority. Incident/identity evidence and request bridge required. |
| Market gateway | PARTIAL | Ticker fetching, clock and quality guards, market health snapshots | No durable shared event stream/cursor fan-out; RP-04. |
| Portfolio | PARTIAL | `PortfolioConstructor` combines desired changes and emits rebalance intents | Last same-pair intent wins; new random IDs; stop/TP/role/TIF lineage can be lost; RP-03. |
| Risk | PARTIAL | `RiskEngine` wraps common `PortfolioRiskManager`; halt/rate limits and optional persistence | Missing-state fail-closed behavior, durable high-water state and fresh portfolio authority; PM-01/03. |
| OMS/venue | PARTIAL | Durable OMS store/router, fake venue and read/write Indodax adapters | Reviewed semantics, terminal late fills, cancel/fill races and execution firewall; PM-02/04, RP-04. |
| Financial ledger | PARTIAL | Shared double-entry `ResearchLedger`; `ProductionLedgerStore` journal/snapshot/applied-fill storage | Atomic OMS+ledger application and linked integrity/revision validation; PM-02. |
| Reconciliation | PARTIAL | Read-only service, reports, durable cursor coordinator | Pipeline accepts absent evidence; report lacks enforced write-scope binding; PM-01. |
| Control/approval | PARTIAL | Modes, durable mode journal, proposals, optional HMAC and fresh risk call | Optional evidence/authentication, capital fallback, startup bypasses; PM-01/03. |
| API/CLI | PARTIAL | Canonical Python services and many dataset/operator/research CLIs | No tracked Workbench HTTP API or QuantOps MCP server found. Planned adapters follow services. |
| Dashboard | MISSING | `dashboard.pen` design artifact; shadow console dashboard | No implemented Workbench web app found; RW8-01/02 after services. |
| Metrics/audit | PARTIAL | Logging/metrics helpers, OMS events, shadow checkpoint events, result metrics | Shared event identity and replay-stable audit contract; RP-04/05. |
| Operations | PARTIAL | Backup/restore/staging/recovery modules, scripts and service templates | `lab-shadow.service` points to missing `indodax_lab.cli.shadow`; host drills/entrypoint proof outstanding. |
| CI/release | PARTIAL | Pytest, compile, fatal checks, selected strict lint; release bundle hashes | No demonstrated full lock/SBOM/CVE/history scan or complete candidate binding; PM-05/06. |
| Deployment | LEGACY / BLOCKED_EXTERNAL | Workflow pulls main and restarts `ibs.service`; disables strict SSH checking | Not governed candidate deployment. Host/secret/venue capability unverified; do not invoke. |
| Planning authority | PARTIAL → repaired documentation | Corrupted manifest reconstructed from 92 specs and handoffs | Historical provenance preserved; review status and external gates still apply. |

## Finding register

These are source-level findings, not newly executed exploits. Severity reflects risk if used for qualification/activation.

| ID | Severity | Evidence / consequence | Owner |
|---|---|---|---|
| A01 | Critical | `control/pipeline.py`: reconciliation checks run only when report exists, in step and approved execution. Missing report permits continuation. | PM-01 |
| A02 | Critical | Approved execution defaults equity/cash to `Decimal("100000000")`, positions to empty; risk may approve against fabricated state. | PM-01 |
| A03 | Critical | `fill_ingestion.py`: memory ledger mutates, then ledger persistence, then OMS transition, then applied-fill row in separate transactions. Crashes can leave memory/durable/OMS disagreement. | PM-02 |
| A04 | Important | Terminal-order late fill path records applied identity without updating financial OMS quantities. | PM-02 |
| A05 | Important | `ledger_store.load_ledger` verifies latest snapshot checksum, not journal linkage/replay; chain verifier is separate. | PM-02 |
| A06 | Important | Mode store permits bypass option; loads READ_ONLY/HALTED without universal RECOVERY, does not verify journal on load; pipeline mode store optional. | PM-03 |
| A07 | Important | Kill-switch CLI defaults missing OMS/report to zero UNKNOWN/healthy; constructs engine without reset secret. | PM-03 |
| A08 | Important | Risk throttle load logs and continues on corruption; durable policy/high-water state not mandatory. | PM-03 |
| A09 | Important | Shadow rejection uses concrete `isinstance(IndodaxTradingClient)` while shared pipeline imports write client; wrappers can escape class-based boundary. | RP-04 |
| A10 | Important | Portfolio reconstructs intents with default role/TIF/strategy and random IDs, loses exit fields; same-pair collisions silently overwrite. | RP-03 |
| A11 | Important | Live shadow has custom features, TA branches, float execution metadata and exits, no OMS; model loads by path without complete candidate digest. | RP-02/04, RW4-01 |
| A12 | Important | Dataset registry aggregate incorporates absolute roots; no-clobber exists-check/replace is not a cross-process exclusive publish guarantee. Empty roots can appear healthy. | RW1-01 |
| A13 | Important | `StrategySpecification` and portable bundles contain nested mutable lists/dicts despite frozen models; callable hash can include unstable string representation. | RW0-01, RW2-01 |
| A14 | Important | Release candidate fields are optional; digest is explicitly not a signature. `release-lab.sh` claims packaging but prints status instead of writing a complete immutable bundle. | PM-05 |
| A15 | Important | Service template missing shadow CLI; deployment workflow bypasses frozen release process and SSH trust discipline. | PM-06 |
| A16 | Important | Sprint manifest truncated internally; stale summaries misstate READY. | DOC-01 |

Shared parser reuse and uncertain-cancel rejection are present at this SHA; do not recreate them under claims of absence. Overfill precheck and fill IDs also exist, but do not resolve A03/A04. Manual re-risk exists but A02 prevents treating it as authoritative.

## Evidence limitations and external blocks

Tracked result JSONs are heterogeneous experimental outputs, not proof of reproducibility, sealed eligibility or current fees. Model artifact presence does not establish trustworthy training data or feature parity. Historical market coverage, licenses, current cost/minimum-order schedules, host capacity, private view-only reconciliation and 90-day/100-trade evidence were not verified. They remain BLOCKED_EXTERNAL for promotion/activation. No reason to request credentials or fetch market data during this audit.

Frozen guidance supersedes old no-dashboard/no-production-target language and old host topology. The ledger-separation wording is interpreted as separate persistence/authority, consistent with one accounting kernel; see ADR-005. No unresolved contradiction between the two frozen systems was found in this audit. An architectural conflict discovered later must record exact clauses, operational consequence, alternatives, minimal ADR and migration consequences before implementation.
