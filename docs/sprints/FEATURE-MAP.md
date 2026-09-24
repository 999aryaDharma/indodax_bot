# Feature map

CORE is initial paper/research scope; EXTENSION/EXPERIMENTAL require owner activation.

## agent-governance

- [AGENT-01 — Governed research curator](agent-governance\AGENT-01-governed-research-curator.md) — CORE; Agent riset mengusulkan challenger melalui branch dan review terpisah dengan bukti budget.

## bars

- [BAR-01 — Causal time and event bars](bars\BAR-01-causal-time-and-event-bars.md) — CORE; Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage.

## baseline

- [BASE-01 — Offline verification harness](baseline\BASE-01-offline-verification-harness.md) — CORE; CI membuktikan perilaku bot dengan fixture tanpa HTTP atau Telegram nyata.
- [BASE-02 — Reachable bullish risk reward](baseline\BASE-02-reachable-bullish-risk-reward.md) — CORE; Rencana bullish yang memenuhi minimum RR dapat melewati risk gate.
- [BASE-03 — Trade v2 ownership parsing](baseline\BASE-03-trade-v2-ownership-parsing.md) — CORE; Riwayat transaksi v2 menghasilkan sisi dan urutan kepemilikan yang benar.
- [BASE-04 — Exact paper accounting migration](baseline\BASE-04-exact-paper-accounting-migration.md) — CORE; Paper trade mempertahankan debit kas dan fee secara exact setelah upgrade schema lama.
- [BASE-05 — Unbiased signal observations](baseline\BASE-05-unbiased-signal-observations.md) — CORE; Setiap keputusan dan outcome tercatat walau Telegram gagal atau pengguna tidak mengklik.
- [BASE-06 — Baseline trust checkpoint](baseline\BASE-06-baseline-trust-checkpoint.md) — CORE; Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint.

## deep-learning

- [D01-01 — Tabular MLP baseline](deep-learning\D01-01-tabular-mlp-baseline.md) — EXTENSION; MLP menguji manfaat nonlinearitas dengan fitur tabular yang sama seperti M01/M02.
- [D02-01 — Causal TCN baseline](deep-learning\D02-01-causal-tcn-baseline.md) — EXPERIMENTAL; Eksperimen D02-01 menghasilkan forecast yang tunduk pada evaluator bersama.
- [D03-01 — ResNet LSTM challenger](deep-learning\D03-01-resnet-lstm-challenger.md) — EXPERIMENTAL; Eksperimen D03-01 menghasilkan forecast yang tunduk pada evaluator bersama.
- [D04-01 — Compact iTransformer challenger](deep-learning\D04-01-compact-itransformer-challenger.md) — EXPERIMENTAL; Eksperimen D04-01 menghasilkan forecast yang tunduk pada evaluator bersama.
- [DL-01 — Isolated resumable neural training](deep-learning\DL-01-isolated-resumable-neural-training.md) — EXTENSION; Optional DL worker membuat checkpoint lengkap dan tidak membebani core runtime.
- [DL-02 — Causal sequence datasets](deep-learning\DL-02-causal-sequence-datasets.md) — EXTENSION; Window sequence tidak menyeberangi pair, gap, split atau target.
- [F01-01 — Foundation provenance gate](deep-learning\F01-01-foundation-provenance-gate.md) — EXPERIMENTAL; Loader memverifikasi asal, lisensi, checksum dan cutoff external model sebelum artifact boleh digunakan atau diberi status EXPLORATORY.
- [F01-02 — Staged foundation adaptation](deep-learning\F01-02-staged-foundation-adaptation.md) — EXPERIMENTAL; Eksperimen F01-02 menghasilkan forecast yang tunduk pada evaluator bersama.
- [G01-01 — Point-in-time graph challenger](deep-learning\G01-01-point-in-time-graph-challenger.md) — EXPERIMENTAL; Eksperimen G01-01 menghasilkan forecast yang tunduk pada evaluator bersama.

## evaluation

- [EVAL-01 — Immutable experiment registry](evaluation\EVAL-01-immutable-experiment-registry.md) — CORE; Setiap percobaan termasuk gagal tersimpan dengan konfigurasi dan ancestry yang dapat diaudit.
- [EVAL-02 — Hard gates and selection diagnostics](evaluation\EVAL-02-hard-gates-and-selection-diagnostics.md) — CORE; Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned.
- [EVAL-03 — Sealed candidate lifecycle](evaluation\EVAL-03-sealed-candidate-lifecycle.md) — CORE; Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.

## features

- [FEAT-01 — Versioned feature registry](features\FEAT-01-versioned-feature-registry.md) — CORE; Definisi fitur Wave 1 dapat dimuat dengan identitas versi dan metadata lengkap.
- [FEAT-02 — Golden technical and liquidity transforms](features\FEAT-02-golden-technical-and-liquidity-transforms.md) — CORE; Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit.
- [FEAT-03 — As-of market context](features\FEAT-03-as-of-market-context.md) — CORE; Fitur BTC, rank dan breadth hanya memakai universe dan closed bars yang tersedia saat keputusan.
- [FEAT-04 — Immutable feature materialization](features\FEAT-04-immutable-feature-materialization.md) — CORE; CLI membangun feature matrix dengan sample identity, warmup mask dan lineage penuh.

## labels

- [LABEL-01 — Execution-aligned net return labels](labels\LABEL-01-execution-aligned-net-return-labels.md) — CORE; Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.
- [LABEL-02 — Triple barrier outcomes](labels\LABEL-02-triple-barrier-outcomes.md) — CORE; Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap.
- [SPLIT-01 — Sealed purged chronological folds](labels\SPLIT-01-sealed-purged-chronological-folds.md) — CORE; Fold assignment memisahkan train validation dan sealed test tanpa overlap label.
- [TRAIN-01 — Verified training dataset assembly](labels\TRAIN-01-verified-training-dataset-assembly.md) — CORE; Materializer menggabungkan fitur label dan fold hanya melalui ID yang telah diverifikasi.

## market-data

- [DATA-01 — Canonical market contracts](market-data\DATA-01-canonical-market-contracts.md) — CORE; Collector dan lab berbagi identity pair, UTC, Decimal dan version lineage yang ketat.
- [DATA-02 — Durable immutable publication](market-data\DATA-02-durable-immutable-publication.md) — CORE; Dataset dan manifest tidak dapat tertimpa oleh retry dengan konten berbeda.
- [DATA-03 — Auditable candle backfill](market-data\DATA-03-auditable-candle-backfill.md) — CORE; Backfill menyimpan wire asli sebelum parsing dan resume hanya dari window yang durable.
- [DATA-04 — Snapshot quality decisions](market-data\DATA-04-snapshot-quality-decisions.md) — CORE; Snapshot rusak menghasilkan quality finding dan tidak dapat menjadi input eligible.
- [DATA-05 — Reliable forward market collection](market-data\DATA-05-reliable-forward-market-collection.md) — CORE; Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal.
- [DATA-06 — Provider-derived reproducible snapshot](market-data\DATA-06-provider-derived-reproducible-snapshot.md) — CORE; Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi.
- [DATA-07 — Selectable public collection and coverage workflow](market-data\DATA-07-selectable-public-collection-and-coverage-workflow.md) — CORE; Selectable public collection and coverage workflow

## microstructure

- [L01-01 — DeepLOB baseline](microstructure\L01-01-deeplob-baseline.md) — EXPERIMENTAL; DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi.
- [L02-01 — TLOB style challenger](microstructure\L02-01-tlob-style-challenger.md) — EXPERIMENTAL; Attention LOB challenger dibandingkan dengan DeepLOB pada biaya dan budget yang sama.
- [LOB-01 — Forward book dataset eligibility](microstructure\LOB-01-forward-book-dataset-eligibility.md) — EXPERIMENTAL; LOB dataset hanya mengizinkan sesi PASS yang punya coverage dan event efektif cukup.

## models

- [M01-01 — Calibrated logistic baseline](models\M01-01-calibrated-logistic-baseline.md) — CORE; M01 memberi probabilitas net-positive dengan recipe linear teratur yang reproducible.
- [M02-01 — XGBoost challenger](models\M02-01-xgboost-challenger.md) — CORE; M02 dibandingkan secara fair dengan linear dan classical pada outer folds yang sama.
- [M03-01 — Random forest regime gate](models\M03-01-random-forest-regime-gate.md) — EXTENSION; Kandidat M03-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [M04-01 — Quantile risk regression](models\M04-01-quantile-risk-regression.md) — EXTENSION; Kandidat M04-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [M05-01 — Meta-label signal filter](models\M05-01-meta-label-signal-filter.md) — EXTENSION; Kandidat M05-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [M06-01 — Market anomaly risk gate](models\M06-01-market-anomaly-risk-gate.md) — EXTENSION; Kandidat M06-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [ML-01 — Train-only preprocessing](models\ML-01-train-only-preprocessing.md) — CORE; Preprocessor menyimpan fitted statistics dan feature order tanpa mengakses test.
- [ML-02 — Held-out calibration and cost mapper](models\ML-02-held-out-calibration-and-cost-mapper.md) — CORE; Forecast terkalibrasi hanya menjadi intent ketika net edge melampaui margin.
- [ML-03 — Bounded trial search](models\ML-03-bounded-trial-search.md) — CORE; Search mencatat trial budget dan tidak memakai sealed test sebagai objective.
- [ML-04 — Portable model bundles and replay](models\ML-04-portable-model-bundles-and-replay.md) — CORE; Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik.
- [R01-01 — Constrained allocation feasibility](models\R01-01-constrained-allocation-feasibility.md) — EXPERIMENTAL; Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal.

## operations

- [OPS-01 — Host profiles and service lifecycle](operations\OPS-01-host-profiles-and-service-lifecycle.md) — CORE; Production Main and Research Runtime dapat dikelola sebagai service terpisah pada ASUS dengan resource headroom Production terukur; ML/DL training dan tuning berjalan pada profil Lenovo terukur.
- [OPS-02 — Snapshot transfer and restore](operations\OPS-02-snapshot-transfer-and-restore.md) — CORE; Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.
- [OPS-03 — Storage retention and integrity maintenance](operations\OPS-03-storage-retention-and-integrity-maintenance.md) — CORE; Cleanup hanya menghapus artifact tidak direferensikan setelah retention dan dry-run audit.

## orchestration

- [JOB-01 — Durable leased jobs](orchestration\JOB-01-durable-leased-jobs.md) — CORE; Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result.
- [JOB-02 — Resource-aware idle admission](orchestration\JOB-02-resource-aware-idle-admission.md) — CORE; Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.
- [JOB-03 — Evaluator-controlled research DAG](orchestration\JOB-03-evaluator-controlled-research-dag.md) — CORE; Scheduler hanya mengulang eksperimen yang diizinkan evaluator pada input immutable.

## reporting

- [REPORT-01 — Compact experiment reports](reporting\REPORT-01-compact-experiment-reports.md) — CORE; Pengguna dapat melihat kualitas data, performa net dan alasan penolakan tanpa membaca raw logs.
- [REPORT-02 — Read-only Telegram research status](reporting\REPORT-02-read-only-telegram-research-status.md) — CORE; Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat.

## shadow

- [SHADOW-01 — Auditable forward paper decisions](shadow\SHADOW-01-auditable-forward-paper-decisions.md) — CORE; Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias.
- [SHADOW-02 — Shared capital reconciliation](shadow\SHADOW-02-shared-capital-reconciliation.md) — CORE; Satu ledger bersama Rp500k menyelesaikan konflik kas dan restart secara konsisten.
- [SHADOW-03 — Champion replacement gate](shadow\SHADOW-03-champion-replacement-gate.md) — CORE; Challenger menggantikan champion hanya setelah historical dan forward evidence cukup.

## simulation

- [COST-01 — Time-valid exchange cost schedules](simulation\COST-01-time-valid-exchange-cost-schedules.md) — CORE; Lookup fee memilih schedule historis yang tepat atau memblokir klaim promosi.
- [LED-01 — Balanced research postings](simulation\LED-01-balanced-research-postings.md) — CORE; Simulasi kas dan posisi memakai posting balance dengan cost basis exact.
- [SIM-01 — Conservative execution simulator](simulation\SIM-01-conservative-execution-simulator.md) — CORE; Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis.
- [SIM-02 — Portfolio risk and circuit breakers](simulation\SIM-02-portfolio-risk-and-circuit-breakers.md) — CORE; Sizing menghormati modal bersama, exposure dan batas rugi sebelum order dibuat.
- [SIM-03 — Deterministic replay judge](simulation\SIM-03-deterministic-replay-judge.md) — CORE; Replay market memproduksi fill, posting dan equity identik pada input identik.
- [SIM-04 — Net-cost risk and capacity metrics](simulation\SIM-04-net-cost-risk-and-capacity-metrics.md) — CORE; Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas.

## strategies

- [C01-01 — Donchian breakout](strategies\C01-01-donchian-breakout.md) — CORE; Kandidat C01 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C02-01 — EMA pullback](strategies\C02-01-ema-pullback.md) — CORE; Kandidat C02 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C03-01 — Time series momentum](strategies\C03-01-time-series-momentum.md) — CORE; Kandidat C03 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C04-01 — Cross sectional momentum](strategies\C04-01-cross-sectional-momentum.md) — CORE; Kandidat C04 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C05-01 — Volatility breakout](strategies\C05-01-volatility-breakout.md) — EXTENSION; Kandidat C05 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C06-01 — Directional trend strength](strategies\C06-01-directional-trend-strength.md) — EXTENSION; Kandidat C06 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C07-01 — Bollinger RSI reversion](strategies\C07-01-bollinger-rsi-reversion.md) — CORE; Kandidat C07 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C08-01 — Multi timeframe confirmation](strategies\C08-01-multi-timeframe-confirmation.md) — EXTENSION; Kandidat C08 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C09-01 — VWAP deviation reversion](strategies\C09-01-vwap-deviation-reversion.md) — EXTENSION; Kandidat C09 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C10-01 — Regime ensemble](strategies\C10-01-regime-ensemble.md) — CORE; Kandidat C10 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C11-01 — Volatility allocation](strategies\C11-01-volatility-allocation.md) — EXTENSION; Kandidat C11 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C12-01 — Relative strength rotation](strategies\C12-01-relative-strength-rotation.md) — EXTENSION; Kandidat C12 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S01-01 — Liquidity screened breakout](strategies\S01-01-liquidity-screened-breakout.md) — CORE; Kandidat S01 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S02-01 — Squeeze expansion](strategies\S02-01-squeeze-expansion.md) — CORE; Kandidat S02 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S03-01 — Abnormal volume continuation](strategies\S03-01-abnormal-volume-continuation.md) — EXTENSION; Kandidat S03 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S04-01 — Order flow imbalance](strategies\S04-01-order-flow-imbalance.md) — EXPERIMENTAL; Kandidat S04 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S05-01 — Micro pullback](strategies\S05-01-micro-pullback.md) — EXTENSION; Kandidat S05 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S06-01 — Post listing maturation](strategies\S06-01-post-listing-maturation.md) — EXTENSION; Kandidat S06 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S07-01 — Small cap rotation](strategies\S07-01-small-cap-rotation.md) — EXTENSION; Kandidat S07 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S08-01 — Passive mean reversion](strategies\S08-01-passive-mean-reversion.md) — EXPERIMENTAL; Kandidat S08 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S09-01 — Tail risk abstention](strategies\S09-01-tail-risk-abstention.md) — EXTENSION; Kandidat S09 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [STRAT-01 — Declarative strategy protocol](strategies\STRAT-01-declarative-strategy-protocol.md) — CORE; Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger.

## universe

- [UNIV-01 — Point-in-time investable universe](universe\UNIV-01-point-in-time-investable-universe.md) — CORE; Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu.

## verification

- [QA-01 — Wave 1 tournament checkpoint](verification\QA-01-wave-1-tournament-checkpoint.md) — CORE; Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik.
- [QA-02 — Boundary security verification](verification\QA-02-boundary-security-verification.md) — CORE; Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate.
- [QA-03 — Capacity and crash recovery qualification](verification\QA-03-capacity-and-crash-recovery-qualification.md) — CORE; ASUS punya bukti capacity, isolation, workload co-residency dan recovery untuk Production Main + Research Runtime sebelum release/deployment.
- [REL-01 — Paper research release candidate](verification\REL-01-paper-research-release-candidate.md) — CORE; Release paper/research terpaket dengan lock, runbook dan rollback yang diverifikasi.

## planning

- [DOC-01 — Frozen architecture audit and delivery program](planning\DOC-01-frozen-architecture-audit-and-delivery-program.md) — CORE; Recover evidence-backed status and publish complete RW/RP/PM tasks and one next LUNA unit.

## runtime-parity

- [RP-01 — Shared SignalIntent ownership with compatibility](runtime-parity\RP-01-shared-signalintent-ownership-with-compatibility.md) — CORE; Neutral ownership needed before widening parity; preserve exact class behavior.
- [RP-02 — Shared candidate feature and exit evaluation](runtime-parity\RP-02-shared-candidate-feature-and-exit-evaluation.md) — CORE; One verified evaluator independent of venue, training and ambient clock.
- [RP-03 — Shared portfolio sizing and risk semantics](runtime-parity\RP-03-shared-portfolio-sizing-and-risk-semantics.md) — CORE; Deterministic allocation preserving lineage, costs, exits and order semantics.
- [RP-04 — Canonical feed and environment runtime adapters](runtime-parity\RP-04-canonical-feed-and-environment-runtime-adapters.md) — CORE; One production-shaped core with simulated adapters and credential-free research wiring.
- [RP-05 — Runtime parity qualification fixtures](runtime-parity\RP-05-runtime-parity-qualification-fixtures.md) — CORE; Evidence of shared decisions, risk, OMS and accounting before tournament qualification.

## research-workbench

- [RW0-01 — Immutable Workbench domain manifests](research-workbench\RW0-01-immutable-workbench-domain-manifests.md) — CORE; Deep immutable portable identities and state-machine contracts.
- [RW1-01 — Reusable immutable dataset registry](research-workbench\RW1-01-reusable-immutable-dataset-registry.md) — CORE; Range-aware reusable versions, atomic catalog publication and explicit quality lineage.
- [RW2-01 — Durable versioned strategy registry](research-workbench\RW2-01-durable-versioned-strategy-registry.md) — CORE; Draft revisions, stable code identity and published component discovery.
- [RW2-02 — Model registry and offline training services](research-workbench\RW2-02-model-registry-and-offline-training-services.md) — CORE; One model identity/loader contract and immutable training/evaluation evidence.
- [RW2-03 — Typed declarative pipeline composer](research-workbench\RW2-03-typed-declarative-pipeline-composer.md) — CORE; One validated graph for TA-only and hybrid compositions.
- [RW3-01 — Experiment lifecycle and backtest orchestration](research-workbench\RW3-01-experiment-lifecycle-and-backtest-orchestration.md) — CORE; Immutable experiment revisions with durable run/cancel/finalization and comparable results.
- [RW4-01 — Immutable candidate packaging and lifecycle](research-workbench\RW4-01-immutable-candidate-packaging-and-lifecycle.md) — CORE; Verified configuration plus evidence binding and append-only candidate lifecycle.
- [RW5-01 — Isolated durable forward-shadow agents](research-workbench\RW5-01-isolated-durable-forward-shadow-agents.md) — CORE; Candidate-bound isolated agent state and restart-safe lifecycle.
- [RW5-02 — Tournament cohorts leaderboard and qualification](research-workbench\RW5-02-tournament-cohorts-leaderboard-and-qualification.md) — CORE; Comparable live cohorts and evidence-based qualification distinct from rank.
- [RW6-01 — Separate shared-capital Portfolio Shadow](research-workbench\RW6-01-separate-shared-capital-portfolio-shadow.md) — CORE; Intentional multi-candidate capital sharing through one common ledger/risk authority.
- [RW7-01 — Read-only QuantOps MCP boundary](research-workbench\RW7-01-read-only-quantops-mcp-boundary.md) — CORE; Allowlisted read-only discovery over existing typed service contracts.
- [RW7-02 — Audited QuantOps research mutations](research-workbench\RW7-02-audited-quantops-research-mutations.md) — CORE; Idempotent draft/job/agent control with append-only audit and promotion-request ceiling.
- [RW8-01 — Research read models and dashboard navigation](research-workbench\RW8-01-research-read-models-and-dashboard-navigation.md) — CORE; Service-derived views with provenance and explicit qualification state.
- [RW8-02 — Workbench form and graph editors](research-workbench\RW8-02-workbench-form-and-graph-editors.md) — CORE; Synchronized form/visual editing of one backend-validated pipeline draft.
- [RW9-01 — Promotion request and production export bridge](research-workbench\RW9-01-promotion-request-and-production-export-bridge.md) — CORE; Immutable export and governed request only; production owns release approval.

## production-main

- [PM-01 — Authoritative fail-closed pre-write gate](production-main\PM-01-authoritative-fail-closed-pre-write-gate.md) — CORE; All real writes need trusted current scoped evidence and exact approval re-risk.
- [PM-02 — Atomic financial execution state and recovery](production-main\PM-02-atomic-financial-execution-state-and-recovery.md) — CORE; One authoritative transaction and verified restart across all financial effects.
- [PM-03 — Recovery mode and durable operator risk governance](production-main\PM-03-recovery-mode-and-durable-operator-risk-governance.md) — CORE; Every boot enters RECOVERY; fail-closed durable mode/risk/approval authority.
- [PM-04 — Venue parser cancellation and supported order semantics](production-main\PM-04-venue-parser-cancellation-and-supported-order-semantics.md) — CORE; Verify actual internal type mapping, supported LIMIT/TIF and race/partial-fill behavior.
- [PM-05 — Candidate-bound release provenance](production-main\PM-05-candidate-bound-release-provenance.md) — CORE; Complete release manifest and fail-closed verification with explicit authenticity policy.
- [PM-06 — CI security and operational release evidence](production-main\PM-06-ci-security-and-operational-release-evidence.md) — CORE; Reproducible environment, security evidence and executable service/recovery drills.
- [API-00 — Shared API envelope, error, provenance and capability contracts](production-main\API-00-shared-api-envelope-error-provenance-and-capability-contracts.md) — CORE; Define stable typed contracts for safe Production and later Research API consumers.
- [API-01 — Production service-derived read models](production-main\API-01-production-service-derived-read-models.md) — CORE; Expose immutable live Production read snapshots, including real Indodax account balances and separately attributed managed positions/orders.
- [API-03 — Fail-closed read capability policy and audit context](production-main\API-03-fail-closed-read-capability-policy-and-audit-context.md) — CORE; Require explicit request identity and production.read capability before serving sensitive operational data.
- [API-02 — Read-only Production API application and routes](production-main\API-02-read-only-production-api-application-and-routes.md) — CORE; Expose Production read models through a capability-protected HTTP API with no write authority.
- [UI-00 — Kumo and Geist shell foundation with typed API client](production-main\UI-00-kumo-and-geist-shell-foundation-with-typed-api-client.md) — CORE; Build shared desktop/smartphone dashboard shell and typed client against the frozen API contract while backend read models progress independently.
- [UI-01 — Production and Research context navigation with capability boundary](production-main\UI-01-production-and-research-context-navigation-with-capability-boundary.md) — CORE; Keep Production and Research route contexts distinct and reflect backend capability decisions safely.
- [UI-02 — Read-only Production operational pages](production-main\UI-02-read-only-production-operational-pages.md) — CORE; Render operational truth, authoritative state and failure context through read-only Production pages.
- [PM-07 — Reviewed account portfolio adoption](production-main\PM-07-reviewed-account-portfolio-adoption.md) — CORE; Reviewed account portfolio adoption
- [PM-08 — Shared capital allocation and stop risk sizing](production-main\PM-08-shared-capital-allocation-and-stop-risk-sizing.md) — CORE; Shared capital allocation and stop risk sizing
- [PM-09 — Candidate exits and draining strategy replacement](production-main\PM-09-candidate-exits-and-draining-strategy-replacement.md) — CORE; Candidate exits and draining strategy replacement
- [API-04 — Guarded Production portfolio and lifecycle commands](production-main\API-04-guarded-production-portfolio-and-lifecycle-commands.md) — CORE; Guarded Production portfolio and lifecycle commands
- [UI-03 — Guarded portfolio and strategy operator workflows](production-main\UI-03-guarded-portfolio-and-strategy-operator-workflows.md) — CORE; Guarded portfolio and strategy operator workflows
