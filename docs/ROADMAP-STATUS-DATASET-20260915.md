# Indodax Trading Bot Research Lab — Roadmap Status

Tanggal pembaruan: 2026-09-15
Branch: `dev`
Scope: paper/shadow research only; tidak ada live order, withdrawal, leverage, futures, short selling, martingale, atau LLM discretionary execution.

## Ringkasan posisi saat ini

Repository berada pada tahap **offline research scaffold yang sudah diperkuat**, belum pada tahap training resmi atau promotion model.

Bukti utama yang sudah tersedia:

- Regression gabungan kelompok judge, temporal data, artifact, queue, lifecycle, dan recovery: **259 passed**.
- Full lab collection terakhir: **649 tests collected**.
- Test kontrak model RL/foundation/graph/LOB: **20 passed**.
- Modul backfill dan perubahan data boundary berhasil `py_compile` dan `git diff --check`.
- Tidak ada API key yang digunakan; fetch hanya memakai endpoint publik Indodax.

Verdict keseluruhan tetap **BLOCKED** karena evidence model, governance manifest, dan independent review belum lengkap.

## Capability yang sudah dikerjakan

### Judge, risk, accounting

Sudah diperkuat:

- reservation cash dan exposure untuk pending intent;
- fee-inclusive admission dan re-check saat execution;
- Decimal accounting dan failure atomicity;
- independent risk exits dan halt yang tetap mengizinkan reduction;
- causal open/close/availability event ordering;
- deterministic replay reset dan execution-fidelity version;
- transaction identity yang mengikat pair, quantity, timestamp, dan postings.

Status: **implemented, regression-green, independent review masih pending**.

### Temporal feature, label, dan dataset

Sudah diperkuat:

- closed-bar dan UTC validation;
- `available_at`, gap/session boundary, dan no-bfill;
- point-in-time universe/BTC context;
- feature/label/split/training content identity;
- finite-value dan warmup/readiness gate;
- role-restricted causal sequence windows;
- immutable sequence arrays;
- label price proxy diberi status `RESEARCH_PRICE_PROXY_ONLY` dan `promotion_eligible=False`.

Status: **implemented, regression-green, belum promotion-ready karena label belum memakai fill simulator penuh**.

### Artifact, recovery, queue, dan lifecycle

Sudah diperkuat:

- canonical artifact hash dan schema gate;
- immutable versioned transfer dengan active pointer atomik;
- traversal/symlink/junction confinement;
- Windows writable-handle fsync untuk backup;
- queue attempt cap, lease fencing, rollback, dan foreign-key enforcement;
- host-local OS lock;
- lifecycle fail-closed bila hook nyata tidak tersedia;
- recovery report tidak lagi mengklaim benchmark verified tanpa evidence nyata.

Status: **implemented, regression-green, platform durability dan independent review masih pending**.

### RL allocation safety

Sudah diperbaiki:

- Decimal down-rounding mencegah allocation overspend;
- bobot negatif atau total di atas simplex ditolak;
- laporan RL tidak lagi mengeluarkan Sharpe hardcoded;
- status feasibility sekarang `UNEVALUATED`/`INCONCLUSIVE` sampai evaluator offline nyata tersedia;
- export ke live scheduler tetap dilarang.

Status: **safety boundary siap; feasibility belum dievaluasi**.

## Dataset yang sudah tersedia

Semua data berada di root yang di-ignore Git dan memiliki raw wire response, metadata, manifest, checkpoint, serta checksum.

| Root | Pair / interval | Coverage | Status |
|---|---|---|---|
| `lab-data-fetch2` | BTC/IDR 1h | 2021-01-01–2026-01-01 | 60 monthly checkpoints, 43.824 accepted rows |
| `lab-data-eth-final` | ETH/IDR 1h | 2021-01-01–2026-01-01 | 60 monthly checkpoints, 43.824 accepted rows |
| `lab-data-5m` | BTC/IDR 5m | 2021-01-01–2026-01-01 | 60 monthly checkpoints; BTC complete |
| `lab-data-5m` | ETH/IDR 5m | 2021-01-01–2026-01-01 | 60 monthly checkpoints, 525.888 accepted rows; inventory integrity PASS |
| `lab-data-5m-eth-final` | ETH/IDR 5m | partial retry | stopped on another immutable provider-byte conflict |
| `lab-data-5m-sol` | SOL/IDR 5m | 2021-11-11 onward, partial | listing-aware; initial 2021-11–2022-01 and Jan 2025 windows validated |

SOL listing start is treated as 2021-11-11 based on Indodax listing reference. Data before listing must remain `NOT_LISTED`, not an imputed zero or empty market.

Approximate total local storage across these roots: **254.66 MB**.

## Blocker yang masih tersisa

### Critical/important research blockers

1. **ETH 5m provider byte instability**
   Identical historical requests returned different response bytes. The immutable store correctly fails closed, but ETH 5m five-year coverage is not yet complete.

2. **SOL 5m coverage belum lengkap**
   SOL harus dimulai dari listing point-in-time dan dilanjutkan sampai 2026. Coverage yang ada masih parsial.

3. **Graph belum menjadi trained GNN**
   Ranker masih menginisialisasi random weights. Output tidak boleh disebut hasil model terlatih atau evidence performa.

4. **Foundation belum memiliki verified weights/backend**
   Belum ada checksum, lisensi, cutoff training, dan runtime backend yang dapat diaudit.

5. **LOB belum memiliki dataset dan archive durable yang lengkap**
   Gate 90 hari harus dibuktikan dengan event order-book nyata, continuity, availability, dan archive trial yang dapat dibaca setelah restart.

6. **RL belum memiliki evaluator trajectory nyata**
   Safety allocation sudah ada, tetapi tidak ada hasil Sharpe/PnL/out-of-sample yang boleh diklaim.

7. **Label belum simulator-aligned**
   Current label memakai open-price research proxy dan sengaja tidak promotion-eligible.

8. **Manifest sprint korup**
   `docs/sprints/sprint-manifest.json` tidak valid dan tidak boleh dipulihkan dengan menebak status.

9. **Independent review belum selesai**
   Exact working tree belum memperoleh reviewer independen yang dapat mengembalikan verdict.

10. **Environment verification**
    `ruff` belum tersedia dan pytest temporary directory global terkena Windows permission error.

11. **Provider replay conflicts**
    Some repeated historical requests returned different bytes. The downloader correctly preserves the first immutable response and stops on conflict; conflict roots must be quarantined or explicitly reconciled before promotion.

## Roadmap setelah dataset tersedia

### Tahap 0 — Freeze dan register dataset

1. Jangan mengubah raw roots yang sudah berhasil.
2. Buat dataset registry entry berisi:
   - source endpoint,
   - pair dan listing interval,
   - interval candle,
   - UTC range,
   - accepted/rejected counts,
   - raw/manifest/checkpoint hashes,
   - fetch command dan Git SHA.
3. Quarantine window yang memiliki immutable byte conflict.
4. Selesaikan ETH 5m dan SOL 5m dengan retry yang menghasilkan root baru atau evidence konflik yang eksplisit.

Automation yang sudah tersedia: `python -m indodax_lab.cli.dataset_inventory <root>...` membaca manifest/checkpoint secara read-only, memverifikasi partition SHA-256, menghitung pair/interval/row/reject, dan exit `2` jika ada integrity error.

Quality gate tersedia melalui `python -m indodax_lab.cli.dataset_quality <root> [--listing-start ISO8601]`. Gate memeriksa duplicate, chronology, interval step, OHLC consistency, negative volume, availability-before-close, dan listing cutoff. SOL 5m yang tersedia menghasilkan `PASS` untuk seluruh tiga manifest yang diperiksa.

Registry tersedia melalui `python -m indodax_lab.cli.dataset_registry <root...> --output <registry.json>`. Registry menggunakan `dataset-registry-v1`, content-addressed `registry_id`, dan no-clobber publication. Registry pertama berhasil dibuat di `lab-data-5m/dataset-registry-v1.json` dengan ID `sha256:c72ec369c750745fd202e75a7bad62654e4e731602ec767dd704e3cee0c2cec5`.

### Tahap 1 — Data quality dan universe

1. Validasi duplicate, missing bars, chronology, OHLC consistency, volume, dan `available_at`.
2. Bangun point-in-time universe dari listing/delisting, bukan current universe.
3. Tandai seluruh periode sebelum listing sebagai `NOT_LISTED`.
4. Publish immutable bronze snapshot dan manifest.

### Tahap 2 — Feature dan label

1. Materialize feature 5m tanpa bfill dan tanpa partial candle.
2. Tambahkan 1h sebagai context/regime feature, bukan menggantikan 5m signal.
3. Gunakan label yang memasukkan fee, slippage, latency, dan simulator execution semantics.
4. Rebuild training dataset dengan `features-v2`, `training-dataset-v2`, dan split point-in-time.

### Tahap 3 — Baseline training

1. Mulai dari baseline sederhana: logistic/MLP/inverse-volatility.
2. Gunakan train 2021–2023, validation 2024, sealed test 2025.
3. Simpan seed, environment, feature order, cost ID, split ID, dan artifact hash.
4. Evaluasi hanya melalui judge/simulator bersama.
5. Bandingkan terhadap no-trade dan naive baseline.

### Tahap 4 — Scalping qualification

1. Gunakan BTC/IDR 5m sebagai first qualification pair.
2. Tambahkan ETH/IDR setelah coverage 5m stabil.
3. Tambahkan SOL/IDR hanya dari tanggal listing resminya.
4. Uji spread, latency, stale quote, participation, partial fill, dan abstain.
5. Jangan menilai profitability sebelum semua cost dan fill assumptions terversi.

### Tahap 5 — Optional model research

1. RL hanya offline feasibility dengan evaluator nyata.
2. Graph hanya setelah checkpoint GNN terlatih dan split PIT tersedia.
3. Foundation hanya setelah weights/backend/provenance diverifikasi.
4. LOB hanya setelah coverage/archive/budget gate benar-benar terpenuhi.
5. Model yang tidak memenuhi evidence gate diberi status `BLOCKED` atau `UNEVALUATED`.

### Tahap 6 — Review dan promotion gate

1. Rekonstruksi manifest melalui sumber otoritatif atau ADR resmi.
2. Jalankan full suite, lint, compile, diff-check, dan data-quality checks.
3. Lakukan independent review exact working tree.
4. Reproduce artifact reload dan simulator results dari clean environment.
5. Hanya setelah semua gate lulus, status dapat naik ke `REVIEW_READY`.

## Definition of done berikutnya

Branch belum boleh disebut selesai sampai semua kondisi berikut terpenuhi:

- ETH dan SOL 5m memiliki coverage dan provenance yang lengkap atau rentangnya dibatasi secara eksplisit;
- training dataset memiliki identity dan split point-in-time yang dapat direbuild;
- evaluator judge menghasilkan fill/cost/ledger yang sama pada replay;
- model report tidak memiliki metrik fabricated atau unsupported;
- manifest planning valid dari sumber resmi;
- full verification dan independent review lulus;
- tidak ada live execution path atau credential requirement.
