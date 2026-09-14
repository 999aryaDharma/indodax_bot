# CR-CATALOG-01 — audit dan perluasan katalog

Status: INTEGRATED INTO PLANNED BACKLOG atas instruksi pemilik; implementasi belum dimulai. Tujuan: menambah hipotesis berbeda tanpa menggandakan keluarga atau mengubah scope spot.

## Pemetaan seluruh usulan percakapan
| Usulan sebelumnya | Pemilik canonical / keputusan |
|---|---|
| C13 ATR breakout | C05-01; variasi ATR dalam keluarga volatilitas |
| C14 volatility targeting trend | C03-01; sizing milik SIM-02 |
| C15 multi-timeframe | C08-01 |
| C16 RSI/Bollinger reversal | C07-01 |
| C17 cointegration pairs | DEFERRED: short/hedge di luar LONG/FLAT; long-only spread tidak boleh disebut market-neutral |
| C18 cross-sectional reversal | EXP-H01, kandidat baru |
| C19 size–momentum | EXP-H02, interaksi bersyarat dengan C04/C12/S07 |
| C20 volume breakout | C01/S01/S03; ablation volume, bukan keluarga baru |
| C21 OBV/flow reversal | Audit S04/S08 terlebih dahulu; hipotesis reversal terpisah hanya dengan CR |
| C22 book imbalance | S04-01 |
| C23 microprice | EXP-H03; benchmark deterministik untuk S04/LOB |
| C24 liquidity reversion | S08-01; jangan menyamakan spread melebar dengan peluang pasti |
| C25 market making inventory | DEFERRED: protokol multi-order, inventory dan queue model baru diperlukan |
| C26 HMM regime | Metode opsional C10/M03, bukan sinyal mandiri; filtering causal, bukan smoothing full sample |
| C27 meta-labeling | M05-01 |
| C28 conformal filter | EXP-O02; eksperimen ketidakpastian, tidak menjamin coverage pada drift |
| C29 risk parity | EXP-O01; bedakan full covariance dengan inverse-vol C11 |
| C30 drawdown allocation | SIM-02; ablation risk overlay |
| C31 sentiment | DEFERRED: sumber historical available-time dan lisensi belum ada |
| C32 anomaly reversal | M06 untuk filter; arah reversal baru perlu hipotesis terpisah |
| C33 pump defense | S09/M06; hindari klaim dapat mengidentifikasi manipulasi dari OHLCV saja |
| C34 execution aware | SIM-01/SIM-03; ablation metode fill, bukan alpha baru |
| C35 ensemble abstention | C10-01 |
| C36 drift detection | Monitoring/lifecycle; jangan menghitungnya sebagai strategi entry |

## Dampak
- Feature registry: rank lintas aset, cap cohort, microprice; hanya tambahkan yang belum ada.
- Judge: tetap satu cost/fill/ledger authority. Kandidat hanya intent/target allocation.
- EVAL: provenance keluarga dan jumlah percobaan mencakup varian gagal, alias, seeds, serta overlay.
- Data: EXP-H01 bisa OHLCV; H02 memerlukan cap PIT; H03 memerlukan L2 RELIABLE. Tidak ada synthetic replacement.
- Compute: satu kandidat pilot pada satu waktu. Baseline satu config dahulu; maksimal 6 config terdaftar per unit pada pilot, di dalam sisa budget ADR-003. Kehabisan budget tidak boleh diatasi dengan ID baru.
- Total lima unit bukan lima alpha baru: tiga hipotesis, satu allocation overlay, satu uncertainty filter.

## Gate penerimaan CR
Coordinator mencatat keputusan integrasi, ancestry budget, dependency dan data gate, menentukan ID yang belum terpakai, membuat sprint rinci mengikuti template repo, lalu memperbarui feature map/traceability/manifest/status/DAG. Jalankan validator. Perubahan ke short, venue lain, data berbayar atau protokol order memerlukan CR terpisah.

## Risiko dan penghentian
HARD_FAIL diarsip menurut ADR-003. Menambah hipotesis setelah melihat holdout membuat holdout itu tidak lagi tersegel untuk hipotesis tersebut. H02 BLOCKED_DATA tanpa cap historis terverifikasi; H03 BLOCKED_DATA tanpa stream sehat; jangan menurunkan syarat untuk mengejar hasil.
