# Kontrak bersama eksperimen ekstensi

## Input dan waktu
Gunakan public StrategySpecification/DecisionFrame/SignalIntent dari STRAT-01; field di bawah adalah requirement semantik, bukan alasan membuat tipe paralel. Sebelum coding, petakan ke tipe aktual pada handoff.

DecisionFrame membawa snapshot, pair, bar/event identity, UTC decision timestamp, available_at, quality/session flags, feature version dan posisi yang sudah dimiliki. Hanya data `available_at <= decision_ts` dan bar tertutup yang eligible. Missing/stale/NaN/inf adalah abstain dengan reason, bukan nol. Keputusan pada close t paling cepat dieksekusi pada kesempatan setelah decision + latency; harga close yang membentuk sinyal tidak otomatis menjadi fill.

`NO_CHANGE/ABSTAIN` berarti tidak menambah atau mengubah posisi; `TARGET_ZERO` berarti exit posisi yang ada. Adapter wajib membedakan keduanya. Bila API aktual FLAT ambigu, selesaikan contract/version dalam EXP-00 sebelum kandidat dibuat. Circuit breaker tetap bisa memaksa exit menurut SIM-02.

## Artifact specification
Setiap recipe wajib memiliki hypothesis_id, canonical_family_id, parent_ids, logic_version, parameter_config/hash, source_ids, dataset/quality/feature/split/cost/execution identities, train/calibration/evaluation boundaries, decision frequency, risk policy, trial budget ancestry, seed jika stochastic, environment dan code SHA.

Unknown field/config ditolak. Semua artifact fitted membawa train_end serta available_at. Perubahan parameter memberi recipe identity baru tanpa mereset family budget. Numeric PnL/cash tetap Decimal; feature float memakai finite checks dan toleransi yang didaftarkan. Universe tie dipecahkan canonical pair ascending.

## Evaluasi yang dapat dibandingkan
1. Bekukan snapshot, universe, cost schedule, capital, fold boundaries, slippage/latency serta parameter sebelum run.
2. Training/tuning di train dan inner validation; calibration window berurutan sesudah train, sebelum evaluation. Purge/embargo mengikuti horizon posisi/label aktual melalui SPLIT-01.
3. Compare pada timestamp dan universe eligible yang sama; laporkan exclusion/coverage, tidak membuang periode sulit diam-diam.
4. Baseline cash, buy-and-hold universe beku, serta keluarga canonical terdekat. Laporkan net return, drawdown, turnover, exposure, trade count, capacity/fill/rejection dan distribusi per fold/regime.
5. Stress baseline cost, 1.5x dan 2x komponen biaya non-negatif; tidak memilih skenario termurah setelah melihat hasil. Fee/rebate aktual tetap versi COST-01.
6. Semua trial termasuk kegagalan tersimpan EVAL-01. Jangan menjumlah performa independent ledger sebagai satu portfolio.
7. Threshold lulus mengikuti EVAL-02/EVAL-03; paket ini tidak membuat angka Sharpe minimum baru. Outcome software PASS berbeda dari edge penelitian.

## Acceptance bersama
- SAME-01: input beku di dua temp root menghasilkan semantic output identity sama.
- TIME-01: menambah/mengubah future rows tidak mengubah keputusan sebelumnya.
- DATA-01: quarantine, unavailable feature atau malformed input tidak menghasilkan entry.
- COST-01: fee/slippage dibebankan judge sekali; strategi tidak menulis ledger.
- BUDGET-01: alias, versi baru dan technical retry tidak memberi budget baru atau duplicate semantic run.
- EVID-01: test name -> acceptance -> command/exit -> source SHA; independen reviewer memberi verdict spec dan quality.

Tidak ada backtest historis yang bisa mengganti kebutuhan forward paper >=90 hari dan >=100 closed trades serta gate master. Hasil tanpa jumlah observasi memadai dilabel INSUFFICIENT_EVIDENCE, tidak dipromosikan.
