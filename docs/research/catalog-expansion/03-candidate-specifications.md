# Kartu spesifikasi kandidat v0.1

Semua parameter berikut baseline beku yang belum diuji terhadap return pasar. Gunakan kontrak bersama. Threshold equality ditulis eksplisit; semua sizing dibatasi SIM-02, tidak leverage.

## EXP-H01 — Cross-sectional reversal spot

Hipotesis: aset liquid yang relatif tertinggal satu hari dapat pulih pada regime pasar mendukung. Berbeda dari oversold RSI per aset.

Dependency: STRAT-01, FEAT-04, C04-01, C07-01, SIM-03, SPLIT-01, EVAL-01. Input 1h OHLCV PIT universe; minimal 20 aset eligible dan BTC benchmark tersedia. Baseline rebalance setiap 24 jam pada 00:00 UTC memakai bar terakhir berakhir pada boundary itu.

Aturan:
- `r24 = close_t / close_(t-24) - 1` dengan 24 interval berurutan, bukan sekadar 24 row.
- Regime gate BTC close > SMA 168 jam tertutup. Equality gagal gate dan menghasilkan TARGET_ZERO saat rebalance.
- Rank ascending r24; pilih tepat 5 aset terendah dengan `r24 < 0`, tie pair ascending. Jika hanya 3 memenuhi, pilih 3.
- Alokasi per aset 10% equity, total <=50%; jika hanya 3, total 30% dan sisanya cash. Minimum universe gagal: abstain, posisi lama diserahkan time exit/risk judge.
- Stop awal 2 ATR14 di bawah reference entry; reference fill aktual milik judge, tidak menaikkan ukuran akibat stop sempit. Exit paling lambat 24 jam sejak fill pertama. Tidak pyramiding. Re-entry sesudah close diperbolehkan hanya pada rebalance berikutnya.

Golden: universe 20 aset dengan lima r24 terendah -0.08,-0.06,-0.04,-0.02,-0.01 serta gate BTC true -> lima bobot 0.10. Return nol tidak dipilih. Pertukaran urutan input tidak mengubah rank.

Acceptance H01-A: golden tepat; H01-B: benchmark future tidak memengaruhi keputusan; H01-C: 19 aset abstain; H01-D: stop dan time exit judge dengan partial fills tidak mereset horizon; H01-E: satu modal bersama tidak overspend saat rotasi; H01-F: no fill pada signal close.

Ablation: r24 rank tanpa regime dibanding recipe utama pada universe sama; dihitung trial terpisah. Invalid jika gap waktu disamakan contiguous atau rank memakai survivors masa kini.

## EXP-H02 — Size-conditioned momentum/reversal

Hipotesis: hubungan return lookback dengan return berikutnya berbeda antar cohort ukuran. Ini interaksi keluarga H01/C04, bukan izin mencari cohort terbaik di holdout.

Dependency: EXP-H01, C04-01, FEAT-03/04, approved PIT universe/cap artifacts, SIM-03, EVAL-01. Input daily bars tertutup dan cap yang sudah tersedia pada cutoff; minimum 20 aset. Rebalance setiap hari 00:00 UTC. Cap missing dikeluarkan sebelum minimum universe; proxy volume tidak boleh diberi label market cap.

Aturan:
- Rank cap descending; `floor(n/2)` pertama big cohort, sisanya small; ties pair ascending.
- Big: pilih top 3 berdasarkan return 7 hari yang strictly positif.
- Small: pilih bottom 3 return 1 hari yang strictly negatif.
- Masing-masing slot target 0.08 equity, maksimal 0.48; slot kosong tetap cash, cohort tidak saling mengisi slot kosong.
- Kedua cohort mengikuti gate BTC SMA168h H01. Stop 2 ATR14 daily; time exit 24 jam sejak fill; tanpa pyramiding.
- Cap chronology/TTL mengikuti adapter contract aktual; adapter current-only tidak dapat dipakai untuk histori. Jika cap invalid, keluarkan row dan laporkan coverage; universe kurang 20 -> abstain.

Golden dengan 20 cap terurut dan six qualifying picks -> enam bobot 0.08; satu big momentum <=0 -> paling banyak lima picks, exposure <=0.40. Aset di batas cohort diputus tie pair, tidak berdasarkan return.

Acceptance H02-A: cohort dan bobot tepat; H02-B: future cap revision tidak mengubah histori; H02-C: cap missing/expired dan survivor exclusion tercatat; H02-D: slot kosong tidak direalokasikan; H02-E: baseline momentum-only dan reversal-only memakai intersection universe yang sama.

Rejection hipotesis: keuntungan hanya berasal dari satu cohort/periode atau lenyap setelah biaya dilaporkan melalui evaluator, tidak ditutup dengan ganti cohort diam-diam.

## EXP-H03 — Microprice continuation benchmark

Hipotesis: harga berbobot best-quote depth memberi sinyal continuation jangka pendek setelah biaya; ini benchmark L2, bukan janji HFT layak.

Dependency: S04-01, LOB-01, SIM-01/03, COST-01, EVAL-01. Collector continuity RELIABLE; quote age <=2 detik pada decision; satu decision per 5 detik. Queue simulation tidak diwajibkan karena baseline taker; taker fill tetap depth/latency-aware.

Rumus: `mid=(ask+bid)/2`, `micro=(ask*bid_qty + bid*ask_qty)/(bid_qty+ask_qty)`, `edge_bps=10000*(micro-mid)/mid`.

Entry hanya `edge_bps > estimated_roundtrip_cost_bps + 2`, spread <=20 bps, ask>bid>0 dan kedua qty positif. Cost estimate wajib tersedia dari public cost/execution quote pada decision; jangan membuat fee konstan. Target <=0.05 equity, <=1% visible ask notional pada best ask; minimum order diperiksa judge.

Exit saat edge<=0 atau 60 detik sejak first fill atau stop 0.5% fill price, whichever first. Order latency default simulasi 500ms, stress 1000ms. Crossing signal threshold tidak menjamin execution edge. GAP/RECOVERING menghasilkan abstain; existing position tetap ditangani risk/time exit pada market sehat berikutnya sesuai SIM policy, tidak diisi harga lama.

Golden bid=99, ask=101, bid_qty=3, ask_qty=1 -> micro=100.5 dan edge=50 bps; spread=200 bps sehingga entry ditolak. Fixture accepted: bid=99.95, ask=100.05, qty 3 dan1 -> micro=100.025, edge=2.5 bps, spread=10 bps; mock public cost quote=0.4 bps memberi threshold=2.4 -> eligible. Biaya kecil ini hanya fixture matematika, bukan fee Indodax.

Acceptance H03-A: dua golden di atas dengan toleransi absolute 1e-8 bps; H03-B: equality edge threshold tidak entry; H03-C: stale/crossed/zero depth/GAP abstain; H03-D: delayed fill menggunakan depth sesudah latency; H03-E: restart tidak menggandakan intent/time horizon; H03-F: no historical L2 fabricated from candles.

## EXP-O01 — Equal risk contribution overlay

Tujuan: bandingkan alokasi covariance penuh dengan C11 inverse-vol pada sinyal aset yang sama. Bukan entry generator.

Dependency: C11-01, SIM-02/03, FEAT-04, EVAL-01. Input eligible held/selected assets dari kandidat beku, daily simple returns 60 interval berurutan; minimal 2 aset. Covariance sample ddof=1 dengan shrinkage tetap `S=0.9*sample_cov +0.1*diag(sample_cov)`. Tolak non-finite, zero variance atau matrix tidak positive definite; failure -> abstain, tidak fallback optimizer diam-diam.

Cari bobot positif sum=1 sehingga normalized risk contribution `w_i*(S*w)_i / (w.T*S*w)` dekat 1/n; max absolute residual <=1e-4, max iterations 1000. Initial equal weights, solver/version/tolerance tercatat. Jika tidak converged, abstain. Scale ke exposure 0.5, lalu cap per aset 0.2 tanpa redistribusi sisa; cash menampung selisih. Laporkan residual sesudah cap sebagai realised allocation; tidak klaim cap tetap equal-risk.

Golden dua aset covariance diagonal [0.04,0.16] -> unconstrained w=[2/3,1/3]; exposure scaled [1/3,1/6], capped [0.2,1/6], cash=19/30. Acceptance O01-A golden tolerance 1e-4; O01-B future return perturbation invariant; O01-C covariance singular/zero variance rejection; O01-D nonconvergence diagnostic; O01-E exposure/turnover/fees dibanding C11 dengan input sinyal identik.

## EXP-O02 — Conformal abstention filter pilot

Tujuan: filter ketidakpastian atas prediktor net-return yang sudah beku. Tidak memberi jaminan coverage teoretis pada time-series non-exchangeable.

Dependency: M04-01, ML-01/04, SPLIT-01, LABEL-01, EVAL-01/02. Predictor median return fit train-only; calibration terpisah kronologis dengan 200 residual berlabel matang sesudah train dan sebelum evaluation. Target return net-cost sama dengan label contract; jangan mengurangi fee dua kali.

Residual `abs(y_net - prediction)`; alpha=0.10; k=ceil((n+1)*(1-alpha)), quantile residual sorted posisi k (1-based). k>n atau n<200 -> abstain. Interval prediction +/-q. Entry dasar hanya diteruskan bila lower bound >0; equality -> abstain. Filter tidak membuat entry baru, tidak memblokir exit, tidak mengubah sizing. Calibration artifact beku untuk satu evaluation fold; refit bukan online memakai label belum matang.

Golden n=200, residual sorted i/1000 untuk i=1..200 -> k=181,q=0.181. Prediksi 0.20 -> lower=0.019 lolos; prediksi 0.181 -> lower=0 ditolak. Angka fixture tidak merepresentasikan return realistis.

Acceptance O02-A golden exact quantile; O02-B overlap calibration/evaluation ditolak; O02-C label unavailable ditolak; O02-D basic strategy no-entry tetap no-entry; O02-E exits tetap diteruskan; O02-F coverage/width/trade retention dilaporkan per fold tanpa janji coverage 90% pasti.
