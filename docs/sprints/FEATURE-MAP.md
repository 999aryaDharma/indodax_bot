# Feature map

CORE is initial paper/research scope; EXTENSION/EXPERIMENTAL require owner activation.

## baseline

- [BASE-01 — Offline verification harness](baseline/BASE-01-offline-verification-harness.md) — CORE; CI membuktikan perilaku bot dengan fixture tanpa HTTP atau Telegram nyata.
- [BASE-02 — Reachable bullish risk reward](baseline/BASE-02-reachable-bullish-risk-reward.md) — CORE; Rencana bullish yang memenuhi minimum RR dapat melewati risk gate.
- [BASE-03 — Trade v2 ownership parsing](baseline/BASE-03-trade-v2-ownership-parsing.md) — CORE; Riwayat transaksi v2 menghasilkan sisi dan urutan kepemilikan yang benar.
- [BASE-04 — Exact paper accounting migration](baseline/BASE-04-exact-paper-accounting-migration.md) — CORE; Paper trade mempertahankan debit kas dan fee secara exact setelah upgrade schema lama.
- [BASE-05 — Unbiased signal observations](baseline/BASE-05-unbiased-signal-observations.md) — CORE; Setiap keputusan dan outcome tercatat walau Telegram gagal atau pengguna tidak mengklik.
- [BASE-06 — Baseline trust checkpoint](baseline/BASE-06-baseline-trust-checkpoint.md) — CORE; Perilaku API, risk, accounting dan observasi terbukti bersama melalui regression checkpoint.

## market-data

- [DATA-01 — Canonical market contracts](market-data/DATA-01-canonical-market-contracts.md) — CORE; Collector dan lab berbagi identity pair, UTC, Decimal dan version lineage yang ketat.
- [DATA-02 — Durable immutable publication](market-data/DATA-02-durable-immutable-publication.md) — CORE; Dataset dan manifest tidak dapat tertimpa oleh retry dengan konten berbeda.
- [DATA-03 — Auditable candle backfill](market-data/DATA-03-auditable-candle-backfill.md) — CORE; Backfill menyimpan wire asli sebelum parsing dan resume hanya dari window yang durable.
- [DATA-04 — Snapshot quality decisions](market-data/DATA-04-snapshot-quality-decisions.md) — CORE; Snapshot rusak menghasilkan quality finding dan tidak dapat menjadi input eligible.
- [DATA-05 — Reliable forward market collection](market-data/DATA-05-reliable-forward-market-collection.md) — CORE; Collector mempertahankan bukti sequence gap dan reconnect tanpa menganggap event hilang sebagai normal.
- [DATA-06 — Provider-derived reproducible snapshot](market-data/DATA-06-provider-derived-reproducible-snapshot.md) — CORE; Pipeline offline benar-benar menghubungkan wire sampai final snapshot melalui artifact yang diverifikasi.

## universe

- [UNIV-01 — Point-in-time investable universe](universe/UNIV-01-point-in-time-investable-universe.md) — CORE; Universe pada tanggal tertentu memakai hanya listing, cap dan likuiditas yang tersedia saat itu.

## bars

- [BAR-01 — Causal time and event bars](bars/BAR-01-causal-time-and-event-bars.md) — CORE; Time bar dan event bar mempertahankan session, threshold, boundary dan availability lineage.

## features

- [FEAT-01 — Versioned feature registry](features/FEAT-01-versioned-feature-registry.md) — CORE; Definisi fitur Wave 1 dapat dimuat dengan identitas versi dan metadata lengkap.
- [FEAT-02 — Golden technical and liquidity transforms](features/FEAT-02-golden-technical-and-liquidity-transforms.md) — CORE; Indikator continuous dan volume transforms menghasilkan nilai serta warmup yang dapat diaudit.
- [FEAT-03 — As-of market context](features/FEAT-03-as-of-market-context.md) — CORE; Fitur BTC, rank dan breadth hanya memakai universe dan closed bars yang tersedia saat keputusan.
- [FEAT-04 — Immutable feature materialization](features/FEAT-04-immutable-feature-materialization.md) — CORE; CLI membangun feature matrix dengan sample identity, warmup mask dan lineage penuh.

## simulation

- [COST-01 — Time-valid exchange cost schedules](simulation/COST-01-time-valid-exchange-cost-schedules.md) — CORE; Lookup fee memilih schedule historis yang tepat atau memblokir klaim promosi.
- [LED-01 — Balanced research postings](simulation/LED-01-balanced-research-postings.md) — CORE; Simulasi kas dan posisi memakai posting balance dengan cost basis exact.
- [SIM-01 — Conservative execution simulator](simulation/SIM-01-conservative-execution-simulator.md) — CORE; Order intent menghasilkan fill paling awal di event yang eligible berikutnya dengan biaya realistis.
- [SIM-02 — Portfolio risk and circuit breakers](simulation/SIM-02-portfolio-risk-and-circuit-breakers.md) — CORE; Sizing menghormati modal bersama, exposure dan batas rugi sebelum order dibuat.
- [SIM-03 — Deterministic replay judge](simulation/SIM-03-deterministic-replay-judge.md) — CORE; Replay market memproduksi fill, posting dan equity identik pada input identik.
- [SIM-04 — Net-cost risk and capacity metrics](simulation/SIM-04-net-cost-risk-and-capacity-metrics.md) — CORE; Report menghitung performa dari ledger dan menunjukkan batas data serta kapasitas.

## labels

- [LABEL-01 — Execution-aligned net return labels](labels/LABEL-01-execution-aligned-net-return-labels.md) — CORE; Target return mengukur net proceeds relatif terhadap gross cash debit dari execution model yang sama.
- [LABEL-02 — Triple barrier outcomes](labels/LABEL-02-triple-barrier-outcomes.md) — CORE; Outcome upper/lower/vertical barrier mulai dari entry dan menyimpan akhir overlap.
- [SPLIT-01 — Sealed purged chronological folds](labels/SPLIT-01-sealed-purged-chronological-folds.md) — CORE; Fold assignment memisahkan train validation dan sealed test tanpa overlap label.
- [TRAIN-01 — Verified training dataset assembly](labels/TRAIN-01-verified-training-dataset-assembly.md) — CORE; Materializer menggabungkan fitur label dan fold hanya melalui ID yang telah diverifikasi.

## strategies

- [STRAT-01 — Declarative strategy protocol](strategies/STRAT-01-declarative-strategy-protocol.md) — CORE; Strategi terdaftar hanya menghasilkan intent dan tidak memiliki otoritas fill atau ledger.
- [C01-01 — Donchian breakout](strategies/C01-01-donchian-breakout.md) — CORE; Kandidat C01 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C07-01 — Bollinger RSI reversion](strategies/C07-01-bollinger-rsi-reversion.md) — CORE; Kandidat C07 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C02-01 — EMA pullback](strategies/C02-01-ema-pullback.md) — CORE; Kandidat C02 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C03-01 — Time series momentum](strategies/C03-01-time-series-momentum.md) — CORE; Kandidat C03 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C04-01 — Cross sectional momentum](strategies/C04-01-cross-sectional-momentum.md) — CORE; Kandidat C04 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C10-01 — Regime ensemble](strategies/C10-01-regime-ensemble.md) — CORE; Kandidat C10 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S01-01 — Liquidity screened breakout](strategies/S01-01-liquidity-screened-breakout.md) — CORE; Kandidat S01 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S02-01 — Squeeze expansion](strategies/S02-01-squeeze-expansion.md) — CORE; Kandidat S02 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C05-01 — Volatility breakout](strategies/C05-01-volatility-breakout.md) — EXTENSION; Kandidat C05 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C06-01 — Directional trend strength](strategies/C06-01-directional-trend-strength.md) — EXTENSION; Kandidat C06 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C08-01 — Multi timeframe confirmation](strategies/C08-01-multi-timeframe-confirmation.md) — EXTENSION; Kandidat C08 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C09-01 — VWAP deviation reversion](strategies/C09-01-vwap-deviation-reversion.md) — EXTENSION; Kandidat C09 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C11-01 — Volatility allocation](strategies/C11-01-volatility-allocation.md) — EXTENSION; Kandidat C11 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [C12-01 — Relative strength rotation](strategies/C12-01-relative-strength-rotation.md) — EXTENSION; Kandidat C12 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S03-01 — Abnormal volume continuation](strategies/S03-01-abnormal-volume-continuation.md) — EXTENSION; Kandidat S03 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S04-01 — Order flow imbalance](strategies/S04-01-order-flow-imbalance.md) — EXPERIMENTAL; Kandidat S04 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S05-01 — Micro pullback](strategies/S05-01-micro-pullback.md) — EXTENSION; Kandidat S05 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S06-01 — Post listing maturation](strategies/S06-01-post-listing-maturation.md) — EXTENSION; Kandidat S06 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S07-01 — Small cap rotation](strategies/S07-01-small-cap-rotation.md) — EXTENSION; Kandidat S07 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S08-01 — Passive mean reversion](strategies/S08-01-passive-mean-reversion.md) — EXPERIMENTAL; Kandidat S08 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.
- [S09-01 — Tail risk abstention](strategies/S09-01-tail-risk-abstention.md) — EXTENSION; Kandidat S09 menghasilkan intent yang dapat dibandingkan dengan baseline pada judge yang sama.

## evaluation

- [EVAL-01 — Immutable experiment registry](evaluation/EVAL-01-immutable-experiment-registry.md) — CORE; Setiap percobaan termasuk gagal tersimpan dengan konfigurasi dan ancestry yang dapat diaudit.
- [EVAL-02 — Hard gates and selection diagnostics](evaluation/EVAL-02-hard-gates-and-selection-diagnostics.md) — CORE; Evaluator memisahkan validitas run dari kualitas strategi dengan gate versioned.
- [EVAL-03 — Sealed candidate lifecycle](evaluation/EVAL-03-sealed-candidate-lifecycle.md) — CORE; Promosi mengikuti freeze dan exposure audit sebelum gate berikutnya dibuka.

## models

- [ML-01 — Train-only preprocessing](models/ML-01-train-only-preprocessing.md) — CORE; Preprocessor menyimpan fitted statistics dan feature order tanpa mengakses test.
- [ML-02 — Held-out calibration and cost mapper](models/ML-02-held-out-calibration-and-cost-mapper.md) — CORE; Forecast terkalibrasi hanya menjadi intent ketika net edge melampaui margin.
- [ML-03 — Bounded trial search](models/ML-03-bounded-trial-search.md) — CORE; Search mencatat trial budget dan tidak memakai sealed test sebagai objective.
- [M01-01 — Calibrated logistic baseline](models/M01-01-calibrated-logistic-baseline.md) — CORE; M01 memberi probabilitas net-positive dengan recipe linear teratur yang reproducible.
- [M02-01 — XGBoost challenger](models/M02-01-xgboost-challenger.md) — CORE; M02 dibandingkan secara fair dengan linear dan classical pada outer folds yang sama.
- [ML-04 — Portable model bundles and replay](models/ML-04-portable-model-bundles-and-replay.md) — CORE; Trainer mempublikasikan bundle lengkap yang bisa diload ulang dan diuji inference identik.
- [M03-01 — Random forest regime gate](models/M03-01-random-forest-regime-gate.md) — EXTENSION; Kandidat M03-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [M04-01 — Quantile risk regression](models/M04-01-quantile-risk-regression.md) — EXTENSION; Kandidat M04-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [M05-01 — Meta-label signal filter](models/M05-01-meta-label-signal-filter.md) — EXTENSION; Kandidat M05-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [M06-01 — Market anomaly risk gate](models/M06-01-market-anomaly-risk-gate.md) — EXTENSION; Kandidat M06-01 menambah hipotesis risk/forecast yang terukur setelah Wave 1.
- [R01-01 — Constrained allocation feasibility](models/R01-01-constrained-allocation-feasibility.md) — EXPERIMENTAL; Spike menilai apakah RL layak diteruskan dengan reward bersih biaya dan constraints modal.

## orchestration

- [JOB-01 — Durable leased jobs](orchestration/JOB-01-durable-leased-jobs.md) — CORE; Dua worker tidak dapat mengeksekusi claim yang sama dan crash dapat dipulihkan tanpa duplicate result.
- [JOB-02 — Resource-aware idle admission](orchestration/JOB-02-resource-aware-idle-admission.md) — CORE; Pekerjaan berat hanya masuk saat profil host, daya, RAM, idle dan thermal memenuhi policy.
- [JOB-03 — Evaluator-controlled research DAG](orchestration/JOB-03-evaluator-controlled-research-dag.md) — CORE; Scheduler hanya mengulang eksperimen yang diizinkan evaluator pada input immutable.

## shadow

- [SHADOW-01 — Auditable forward paper decisions](shadow/SHADOW-01-auditable-forward-paper-decisions.md) — CORE; Forecast forward dan keputusan risiko tersimpan sebelum outcome tanpa callback selection bias.
- [SHADOW-02 — Shared capital reconciliation](shadow/SHADOW-02-shared-capital-reconciliation.md) — CORE; Satu ledger bersama Rp500k menyelesaikan konflik kas dan restart secara konsisten.
- [SHADOW-03 — Champion replacement gate](shadow/SHADOW-03-champion-replacement-gate.md) — CORE; Challenger menggantikan champion hanya setelah historical dan forward evidence cukup.

## verification

- [QA-01 — Wave 1 tournament checkpoint](verification/QA-01-wave-1-tournament-checkpoint.md) — CORE; Turnamen kecil menyatukan baseline classical ML dan follow-up jobs dengan hasil deterministik.
- [QA-02 — Boundary security verification](verification/QA-02-boundary-security-verification.md) — CORE; Audit membuktikan akses secret, artifact loader dan destructive paths tertutup pada release candidate.
- [QA-03 — Capacity and crash recovery qualification](verification/QA-03-capacity-and-crash-recovery-qualification.md) — CORE; Host yang dipilih punya bukti workload dan recovery sebelum release.
- [REL-01 — Paper research release candidate](verification/REL-01-paper-research-release-candidate.md) — CORE; Release paper/research terpaket dengan lock, runbook dan rollback yang diverifikasi.

## deep-learning

- [DL-01 — Isolated resumable neural training](deep-learning/DL-01-isolated-resumable-neural-training.md) — EXTENSION; Optional DL worker membuat checkpoint lengkap dan tidak membebani core runtime.
- [D01-01 — Tabular MLP baseline](deep-learning/D01-01-tabular-mlp-baseline.md) — EXTENSION; MLP menguji manfaat nonlinearitas dengan fitur tabular yang sama seperti M01/M02.
- [DL-02 — Causal sequence datasets](deep-learning/DL-02-causal-sequence-datasets.md) — EXTENSION; Window sequence tidak menyeberangi pair, gap, split atau target.
- [D02-01 — Causal TCN baseline](deep-learning/D02-01-causal-tcn-baseline.md) — EXPERIMENTAL; Eksperimen D02-01 menghasilkan forecast yang tunduk pada evaluator bersama.
- [D03-01 — ResNet LSTM challenger](deep-learning/D03-01-resnet-lstm-challenger.md) — EXPERIMENTAL; Eksperimen D03-01 menghasilkan forecast yang tunduk pada evaluator bersama.
- [D04-01 — Compact iTransformer challenger](deep-learning/D04-01-compact-itransformer-challenger.md) — EXPERIMENTAL; Eksperimen D04-01 menghasilkan forecast yang tunduk pada evaluator bersama.
- [G01-01 — Point-in-time graph challenger](deep-learning/G01-01-point-in-time-graph-challenger.md) — EXPERIMENTAL; Eksperimen G01-01 menghasilkan forecast yang tunduk pada evaluator bersama.
- [F01-01 — Foundation provenance gate](deep-learning/F01-01-foundation-provenance-gate.md) — EXPERIMENTAL; Loader memverifikasi asal, lisensi, checksum dan cutoff external model sebelum artifact boleh digunakan atau diberi status EXPLORATORY.
- [F01-02 — Staged foundation adaptation](deep-learning/F01-02-staged-foundation-adaptation.md) — EXPERIMENTAL; Eksperimen F01-02 menghasilkan forecast yang tunduk pada evaluator bersama.

## microstructure

- [LOB-01 — Forward book dataset eligibility](microstructure/LOB-01-forward-book-dataset-eligibility.md) — EXPERIMENTAL; LOB dataset hanya mengizinkan sesi PASS yang punya coverage dan event efektif cukup.
- [L01-01 — DeepLOB baseline](microstructure/L01-01-deeplob-baseline.md) — EXPERIMENTAL; DeepLOB mengukur short-horizon edge setelah spread dan latency melalui book dataset terverifikasi.
- [L02-01 — TLOB style challenger](microstructure/L02-01-tlob-style-challenger.md) — EXPERIMENTAL; Attention LOB challenger dibandingkan dengan DeepLOB pada biaya dan budget yang sama.

## operations

- [OPS-01 — Host profiles and service lifecycle](operations/OPS-01-host-profiles-and-service-lifecycle.md) — CORE; Collector dan paper dapat dikelola sebagai service sementara worker berat memakai profil Lenovo terukur.
- [OPS-02 — Snapshot transfer and restore](operations/OPS-02-snapshot-transfer-and-restore.md) — CORE; Dataset antar-host ditransfer dan dipulihkan melalui staging yang diverifikasi.
- [OPS-03 — Storage retention and integrity maintenance](operations/OPS-03-storage-retention-and-integrity-maintenance.md) — CORE; Cleanup hanya menghapus artifact tidak direferensikan setelah retention dan dry-run audit.

## reporting

- [REPORT-01 — Compact experiment reports](reporting/REPORT-01-compact-experiment-reports.md) — CORE; Pengguna dapat melihat kualitas data, performa net dan alasan penolakan tanpa membaca raw logs.
- [REPORT-02 — Read-only Telegram research status](reporting/REPORT-02-read-only-telegram-research-status.md) — CORE; Telegram menampilkan queue, champion dan health secara read-only dengan otorisasi chat.

## agent-governance

- [AGENT-01 — Governed research curator](agent-governance/AGENT-01-governed-research-curator.md) — CORE; Agent riset mengusulkan challenger melalui branch dan review terpisah dengan bukti budget.
