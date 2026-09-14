# Master product and technical specification

Version: 2.0.0 | Planning baseline: `8a8e9f2` | Date: 2026-09-14
Classification: **PARTIALLY IMPLEMENTED; RESEARCH / EXPERIMENTAL SYSTEM**.
Status: documented scope; implementation proceeds only through verified sprint gates.

## Vision and problem

Bangun lab trading Indodax yang mampu menguji hipotesis big-cap dan small-cap secara terus-menerus, membandingkan classical/ML/DL dengan biaya realistis, lalu menjalankan kandidat layak secara forward paper. Masalah utama bukan kekurangan indikator: data bocor, biaya salah, selection bias, tuning tak terbatas, dan bukti eksperimen tidak dapat direproduksi dapat membuat hasil buruk tampak bagus.

Besarnya proyek tidak menjadi alasan menambah arsitektur terdistribusi atau semua model sekaligus. Kompleksitas hanya diterima bila kapabilitas memberi nilai yang dapat diuji. Prioritas: data terpercaya → judge terpercaya → baseline → automation → forward evidence → kompleksitas opsional.

## Actors

| Actor | Tujuan dan otoritas |
|---|---|
| Arya / research owner | Memilih backlog, menyetujui perubahan material, menerima residual risk; tidak boleh mengubah label hasil lama |
| Collector / sentry | Menyimpan sumber serta keputusan quality; tidak boleh mempromosikan strategi |
| Experiment worker | Menjalankan recipe beku pada input immutable; tidak boleh menulis raw ulang |
| Evaluator | Menentukan validity dan lifecycle menurut policy versioned; tidak menjalankan order nyata |
| Paper runner | Simulasi modal dan risiko forward; tidak punya kemampuan order exchange |
| Implementer / reviewer | Implementer satu sprint, reviewer independen pada SHA yang sama |
| Telegram reader | Melihat sinyal/health/report pada chat berizin; intent manual terpisah dari outcome |

## Goals and measurable outcomes

- Semua hasil terkait Git SHA, hash environment/config/data/features/labels/split/cost/execution serta seed.
- Kandidat Wave 1: C01 C02 C03 C04 C07 C10 S01 S02 M01 M02 dibandingkan pada judge, cost, fold dan modal yang sama.
- Registry menyimpan hasil invalid dan gagal; tidak hanya menyimpan pemenang.
- Background pipeline punya admission resource, durable queue, retry terbatas dan audit perubahan.
- Forward paper memakai ledger independen Rp500.000 per kandidat dan satu shared ledger Rp500.000; hasilnya tidak dijumlah sebagai satu modal.
- Release software tidak sama dengan bukti edge. Champion membutuhkan sealed historical eligibility dan >=90 hari **serta** >=100 closed forward trades dengan policy risk terpenuhi.

## Non-goals and rejected designs

Auto-trading dana nyata; trade/withdraw API credentials; leverage/short/futures; martingale; averaging down tanpa batas; jaminan return; optimasi win rate saja; LLM langsung memutuskan order; auto-merge agent; random time-series split; current cap untuk masa lalu; candle sintetis sebagai order book; asumsi perfect maker fill. Dashboard web, aplikasi mobile, multi-tenant SaaS, billing dan public API bukan kebutuhan yang disetujui. RL merupakan spike opsional tanpa scheduler default.

## Core workflows

1. Wire collection → immutable bronze → verified quality decision → bars/universe → typed immutable snapshot.
2. Snapshot → versioned features → cost-aligned labels → purged fold assignment → dataset terverifikasi.
3. Registered strategy/model → deterministic judge → immutable result → evaluation gates → freeze/sealed review.
4. Qualified frozen candidate → forward decisions → shared/independent paper ledger → reconciliation → promotion review.
5. Outcome evaluator → bounded retry/archive/hypothesis revision → new challenger. Komputer idle tidak membuka ulang HARD_FAIL.

## Functional requirements

| ID | Observable requirement | Domain owner |
|---|---|---|
| FR-01 | Existing signal, API ownership, Decimal paper accounting dan observation tetap valid saat migrasi | baseline |
| FR-02 | Wire, partitions, quality decisions dan snapshot identity diverifikasi sebelum downstream publish | market-data |
| FR-03 | Universe mengikuti informasi yang tersedia pada decision time termasuk delisted histories | universe |
| FR-04 | Bars memiliki boundaries, continuity, availability dan threshold lineage yang kausal | bars |
| FR-05 | Feature registry berversi dan materializer menolak leakage serta insufficient warmup | features |
| FR-06 | Judge menghitung fills, biaya, risiko, equity dan capacity secara konsisten | simulation |
| FR-07 | Labels mengikuti execution/cost; training split dipurge dan disegel menurut exposure history | labels |
| FR-08 | Katalog strategi hanya mengeluarkan intent pada eligible frame | strategies |
| FR-09 | Evaluator mengarsip semua trials dan melakukan lifecycle sesuai hard gates | evaluation |
| FR-10 | ML preprocessing, calibration, search dan model bundle dapat direproduksi | models |
| FR-11 | Queue durable, resource admission dan repeat policy membatasi pekerjaan background | orchestration |
| FR-12 | Paper forward merekonsiliasi modal dan menerapkan champion replacement gate | shadow |
| FR-13 | DL/graph/foundation tetap opsional dengan resource dan provenance gates | deep-learning |
| FR-14 | LOB research mensyaratkan data forward kontinu dan spread-aware evaluation | microstructure |
| FR-15 | Service, transfer, backup dan retention dapat dipulihkan secara aman | operations |
| FR-16 | Reports dan Telegram memisahkan data quality, hasil riset dan kondisi operasional | reporting |
| FR-17 | Agent bekerja di branch, scope dan independent review yang dapat diaudit | agent-governance |
| FR-18 | Release didukung integration, security, capacity dan recovery evidence | verification |

## Non-functional requirements

| ID | Contract and acceptance |
|---|---|
| NFR-01 Causality | `available_at <= decision_ts`; closed bars only; fitted statistics use authorized train data; mutation future input leaves past output invariant |
| NFR-02 Reproducibility | Same verified logical inputs give same identity; numeric float tolerance explicitly registered; no absolute path or ambient clock in content hash |
| NFR-03 Exact accounting | Decimal/integer money, separate quantities and valuation; journal balances; no duplicate fee deduction |
| NFR-04 Durability | Atomic publication with file and directory fsync where supported; failed/indeterminate result never treated as success |
| NFR-05 Security | No real trading credentials; safe local paths/artifact loaders; chat allowlist; secret redaction; untrusted content cannot become code |
| NFR-06 Resources | Bounded collection queues/batches; measured admission limits; no heavy imports on collector; no unbounded retries/search |
| NFR-07 Recovery | Checkpoints after durable artifacts; idempotent restart; backup restore rehearsed; no stale-worker publication |
| NFR-08 Auditability | Every gate has reason, policy version, source IDs and evidence SHA; implementer is not final reviewer |

## Source of truth and change control

Current user instruction → this master + accepted ADR → subsystem spec → detailed dataset contract → sprint scope → historical plan. For exact existing schema/API, inspect committed code and tests; discrepancies are findings, not permission to silently change runtime. Runtime evidence describes **what exists**, specifications describe **what is required**. Accepted ADR lists targeted overrides to legacy wording. Manifest owns sprint status/dependencies; index and waves are projections. Material product changes require CR + impact + spec/DAG updates before implementation.

## Domain concepts and persistence

See [data model](02-domain-data-model.md). Pair has canonical identity distinct from venue symbol. Snapshot identity commits to verified bytes and typed provenance. Decision differs from intent, fill, label and outcome. Trial differs from frozen candidate version and from run. Sealed split records exposure, not just year labels. Local SQLite stores operational metadata and ledgers; immutable Parquet/files hold datasets and artifacts outside Git.

## Architecture and runtime model

Existing flat Python bot remains alongside `src/indodax_lab`. Collector/sentry/paper processes are lightweight; heavy backtest/ML/DL workers are separate optional environments. Existing design allocates ASUS to light collection/paper and Lenovo to research; actual service activation requires host audit. No assumption that September hardware/workload matches August observations. Local-only single-host profile is supported by logical roots; cross-host transfer is immutable-file staging, never network-shared SQLite WAL. See [architecture](01-system-architecture.md).

## Integrations, security and privacy

Indodax public REST/WebSocket and market-cap provider adapters consume untrusted payloads; persist raw audit bytes without credentials. Legacy private account reads remain read-only and optional, never a lab dependency. Verify official endpoint, cost schedule and license at capability implementation/activation time; inherited dated examples are not current rates. Telegram token belongs only to delivery process. Artifact deserialization is a code execution boundary: require verified locally produced files and hashes; no arbitrary remote pickle or trust_remote_code defaults. Retain account/chat IDs only for authorized operations, redact exported evidence.

## Reliability, failure recovery and observability

Data errors return structured FAIL/QUARANTINED; caller invocation errors remain distinct. Retry only classified transient failure with configured maximum attempts and backoff. All stateful writes are transactional or immutable with atomic publication. Metric dimensions: run/job/strategy version/snapshot/pair/session; do not log secret headers. Track lag, dropped/rejected rows, gap windows, queue age, retries, admission reasons, posting mismatches and policy breaches. Alert delivery may fail without changing decisions.

## Performance, scale and cost control

No RPS, concurrency, GPU or profitability promise is made from laptop specs. Scope size is measured in pairs × event rate × retained days × feature count × trials × folds × seeds. Use byte-per-row and measured runtime/resource curves before budgeting storage/compute. Resource smoke in Phase 1 is runner evidence only. Search defaults remain budgets, not performance guarantees: classical 24 coarse+12 refine; ML <=30 trials; DL <=12 configs, <=50 epochs, patience 7; graph/LOB <=8 configs. See [risk and cost register](../quality/risk-and-open-decisions.md).

## Testing philosophy and deployment

Each capability proves successful behavior, invalid input rejection, failure recovery and its critical invariants. Offline fixtures use production interfaces; direct private helper shortcuts cannot establish end-to-end claims. Unit/integration/replay/golden/property/attack tests chosen by risk; no decorative coverage target. Research-only docs do not run product mutation. Deploy only after host profile, secret review, restore rehearsal, release gate and owner activation instruction. Pin runtime dependencies per host; don't assume `/tmp` historical dependency paths exist.

## Future scope

All catalog extensions have named sprints but no default scheduling activation. New live trading mode, additional exchanges, news/on-chain ingestion, external paid feeds, distributed queue services and public dashboards require new CR and boundary design. They are not implied by the phrase large project.

## Global acceptance criteria

- [ ] FR-01 through FR-18 traced to sprint acceptance and commit-specific evidence.
- [ ] No unresolved critical/important review finding in release scope.
- [ ] Snapshot, features, judge and Wave 1 checkpoints pass on verified inputs.
- [ ] Risk, costs, data quality, lineage, leakage and recovery gates enforced by behavior tests.
- [ ] Paper release and actual champion performance are labeled separately.
- [ ] Operator can stop, restore, restart and explain each run's lineage.
- [ ] No production promise based solely on synthetic offline fixtures.

Unchecked release acceptance is deliberate: this document is planning, not proof of full implementation.

## Integrated catalog extension

Technical contracts: [catalog expansion](22-catalog-expansion-and-rl.md) and [RL allocation spike](23-rl-allocation-feasibility.md). C13-01/C14-01/S10-01/C15-01/M07-01 are PLANNED additions; R01-01 remains EXPERIMENTAL with original dependencies. No default scheduler activation.
