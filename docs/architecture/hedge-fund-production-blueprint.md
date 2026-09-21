> [!CAUTION]
> **STATUS: SUPERSEDED FOR PRODUCTION DECISIONS — 2026-09-21**
>
> Dokumen ini dipertahankan sebagai historical design draft. Sumber authoritative untuk
> real-money architecture, risk, ledger, deployment, disaster recovery, dan release gates sekarang:
> - `docs/production/README.md`
> - `docs/quality/release-gates.md`
> - master product/technical specification yang ditautkan dari `docs/README.md`
>
> Asumsi berikut dari draft ini **tidak lagi authoritative**:
> - ASUS X441U sebagai sole production execution node;
> - fixed 1.5% risk per trade;
> - 100% maker/post-only execution atau exact ticker fill;
> - fixed fee 0.1111% buy / 0.3211% sell lintas waktu;
> - promotion setelah 14 hari atau 15 closed trades;
> - dashboard toggle langsung ke full-autonomous;
> - klaim double-entry sebelum venue fills benar-benar masuk ledger dan reconciliation;
> - target backtest berbasis angka detik sebagai release criterion;
> - hardware latency/RAM claims yang belum dibuktikan benchmark target host.
>
> Gunakan dokumen ini hanya untuk ide UI/fitur yang belum bertentangan dengan kontrak production baru.

# Cetak Biru Produksi & Spesifikasi Sistem: Hedge-Fund Grade Trading Platform
**Target Deployment: Homelab Server ASUS X441U (Intel Core i3-6006U | 4GB RAM | 500GB HDD)**

---

## 1. Visi & Filosofi Desain Institusional

Sistem ini dirancang dengan standar hedge fund kuantitatif modern:
1. **Capital Preservation First**: Melindungi modal kas adalah prioritas absolut. Tidak ada trade yang dibuka tanpa konfirmasi rezim tren makro ($Price > EMA_{200}$) dan rasio *Risk-to-Reward* minimal 2:1.
2. **Positive Mathematical Expectancy ($E > 0.40R$)**: Memadukan pergerakan eksplosif aset *High-Beta* (ETH & SOL) dengan filter kecerdasan buatan (*M02 XGBoost CUDA Trained, Platt-Calibrated*) untuk mengatasi hurdle fee transaksi bursa Indodax (0.4322% round-trip).
3. **Hardware-Aware Engineering**: Dioptimalkan secara radikal untuk berjalan 24/7 di server hemat energi laptop bekas ASUS X441U dengan alokasi RAM ketat (< 1.1 GB) dan beban disk I/O minimal pada HDD 5400 RPM, tanpa mengganggu project *staging bimbel* dan *landing page* yang sudah ada.
4. **Zero Uncontrolled RL / Hallucination**: 100% deterministik pada manajemen risiko, pembukuan kas, dan eksekusi order. AI digunakan secara terukur sebagai *Meta-Probability Filter*, bukan *discretionary black-box*.

---

## 2. Analisis & Partisi Sumber Daya: Homelab ASUS X441U

### A. Profil Perangkat Keras
* **Prosesor**: Intel Core i3-6006U (Skylake, 2 Cores / 4 Threads @ 2.0 GHz, Cache 3MB, TDP 15W).
* **RAM**: 4 GB DDR4-2133 Single-Channel (Total addressable: ~3.85 GB setelah shared VRAM).
* **Penyimpanan**: 500 GB 5400 RPM SATA 2.5" HDD (Throughput sekuensial ~80-100 MB/s, Random 4K IOPS sangat lambat: ~50-70 IOPS).
* **Fitur Bawaan Spesial**: Baterai internal laptop berfungsi otomatis sebagai **Built-In Hardware UPS (Uninterruptible Power Supply)** saat terjadi pemadaman listrik PLN.

### B. Anggaran Memori (RAM Budgeting)
Untuk mencegah laptop mengalami *swapping* / *disk thrashing* (yang akan membekukan seluruh sistem pada HDD 5400 RPM), alokasi RAM dipartisi secara ketat:

```
+-------------------------------------------------------------------+
| Total RAM: 4096 MB                                                |
+------------------------------------+------------------------------+
| Beban Kerja yang Sudah Ada:        | Alokasi Bot Trading:         |
| - OS Ubuntu Server + Kernel: 450 MB| - Python FastAPI Engine: 180 MB
| - Nginx (Reverse Proxy):     30 MB | - XGBoost C-Inference:    50 MB
| - Bimbel Staging App:       550 MB | - In-Memory Candle Cache: 40 MB
| - Database Bimbel (MySQL):  350 MB | - Web Static Bundle:       0 MB
| - OS Buffer / Page Cache:   900 MB | - Cadangan Spikes:       150 MB
| Subtotal:                  2280 MB | Subtotal Bot:            420 MB
+------------------------------------+------------------------------+
| SISA MARGIN AMAN: ~1396 MB (Bebas dari risiko Out-Of-Memory / OOM)|
+-------------------------------------------------------------------+
```

### C. Strategi I/O Storage (Mitigasi HDD 5400 RPM)
HDD 5400 RPM sangat rentan melambat jika menerima operasi *random write* terus-menerus. Sistem menerapkan kaidah:
1. **In-Memory Ring Buffer**: Data 250 candle terakhir untuk seluruh pair disimpan di RAM. Komputasi indikator teknikal (EMA, RSI, ATR) berjalan 100% di memori tanpa membaca HDD.
2. **SQLite WAL Mode Optimasi**:
   ```sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   PRAGMA temp_store = MEMORY;
   PRAGMA wal_autocheckpoint = 1000;
   ```
   Menghindari disk-flush setiap baris; penulisan transaksi dikumpulkan dalam satu batch sekuensial.
3. **Log Rotation Ketat**: Menggunakan `logrotate` Linux maksimal 50 MB dengan kompresi gzip (maksimal 5 arsip) agar tidak memakan ruang 500 GB HDD.

### D. Strategi Inferensi AI (CPU Optimized)
* **Pelatihan Model (Offline)**: Dilakukan di komputer riset menggunakan NVIDIA GeForce RTX 3050 Laptop GPU (CUDA).
* **Penyajian Model (Inference di Homelab)**:
  * Model XGBoost diekspor ke format binary ringan (`.ubj` atau ONNX Runtime CPU).
  * Menghindari penggunaan library PyTorch/CUDA di laptop Asus X441U (menghemat 700 MB+ RAM).
  * Latensi inferensi XGBoost C-API pada Core i3-6006U: **< 1.8 milidetik per candle**, beban CPU < 1%.

---

## 3. Arsitektur Sistem 8-Tier (The Institutional Stack)

```
[ Indodax Public API ] <---> [ WebSocket / REST Connector ]
                                     |
                                     v
+-----------------------------------------------------------------------+
| LAYER 1: SENSORY INGESTION ENGINE                                     |
| In-Memory Ring Buffer (250 Bars 1h) | Clock Sync Guard (NTP UTC)      |
+-----------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------+
| LAYER 2: TECHNICAL FEATURE PROCESSOR                                  |
| 11 Normalized Features: EMA(20/50/200), ATR-14, RSI-14, ADX, BB-Z     |
+-----------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------+
| LAYER 3: MODULAR STRATEGY ENGINE & RULE-TREE BUILDER                  |
| Hybrid Config-Driven DSL | Copy-Trading Importer | Python Plugins     |
+-----------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------+
| LAYER 4: PREDICTIVE BRAIN (AI META-FILTER)                            |
| M02 XGBoost CPU Booster | Platt Sigmoid Calibrator (P >= Threshold)   |
+-----------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------+
| LAYER 5: PORTFOLIO & RISK GOVERNOR                                    |
| Fixed Fractional 1.5% Risk | Inverse ATR Lot Sizing | Max 2 Positions |
| Plafon Kas 25% | Circuit Breakers (Daily DD 3%, Max DD 10%)           |
+-----------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------+
| LAYER 6: ORDER MANAGEMENT SYSTEM (OMS / EMS)                          |
| 100% Maker Post-Only Limit Orders | Trailing Stop & Time Decay Exit   |
+-----------------------------------------------------------------------+
                                     |
                                     v
+-----------------------------------------------------------------------+
| LAYER 7: INSTITUTIONAL DOUBLE-ENTRY ACCOUNTING LEDGER                 |
| Multi-Book: [SHADOW_CORE] | [BACKTEST_SANDBOX] | [PROD_LIVE]          |
| Exact Fee Deduction (0.1111% Buy, 0.3211% Sell) | Audit Trail         |
+-----------------------------------------------------------------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
+---------------------------+                 +---------------------------+
| LAYER 8A: FASTAPI BACKEND |                 | LAYER 8B: REACT/NEXT UI   |
| REST API & WebSockets     |                 | TradingView Charts        |
| Background Task Runner    |                 | Live Cockpit & Ledger     |
+---------------------------+                 +---------------------------+
```

---

## 4. Desain Sistem Modular & Studio Strategi (Copy-Trading Importer)

Agar pengguna dapat dengan mudah meracik strategi sendiri, mencoba indikator teknikal baru, atau mengimpor strategi dari *copy-trading*, sistem menyediakan **Hybrid Strategy Architecture**:

### A. Format Konfigurasi Deklaratif (Rule-Tree DSL)
Setiap strategi dapat diracik langsung dari UI visual tanpa coding, disimpan sebagai format JSON/YAML terstruktur:

```yaml
strategy_metadata:
  strategy_id: "CUSTOM_COPYTRADE_MOMENTUM_V1"
  name: "Donchian Trend + RSI Pullback"
  author: "CopyTrade_TraderX"
  version: "1.0.0"

universe:
  eligible_pairs: ["eth_idr", "sol_idr"]
  timeframe: "1h"

entry_rules:
  logical_operator: "AND"
  conditions:
    - indicator: "close"
      operator: "GREATER_THAN"
      target: "ema_200"
    - indicator: "ema_20"
      operator: "GREATER_THAN"
      target: "ema_50"
    - indicator: "rsi_14"
      operator: "BETWEEN"
      range: [45.0, 65.0]
    - indicator: "close"
      operator: "PULLBACK_BOUNCE"
      target: "ema_20"
      tolerance_atr: 0.5

ai_filter:
  enabled: true
  model_id: "m02_xgboost_v2"
  probability_threshold: 0.40

risk_rules:
  fixed_risk_equity_pct: 0.015   # 1.5% modal dipertaruhkan
  stop_loss_atr_mult: 1.75       # SL = Entry - 1.75x ATR
  take_profit_atr_mult: 3.50     # TP = Entry + 3.50x ATR (R:R 2:1)
  trailing_stop:
    enabled: true
    activation_atr: 1.50
    trail_distance_atr: 2.00
  time_decay_breakeven_bars: 14  # Geser SL ke BEP jika 14 bar stagnan
```

### B. Katalog Indikator Bawaan (*Indicator Catalog*)
UI menyediakan daftar indikator teknikal siap pakai yang langsung terintegrasi dengan mesin komputasi matematis NumPy:
* **Trend Following**: EMA (20, 50, 100, 200), SMA, SuperTrend, MACD, Donchian Channel.
* **Momentum & Reversal**: RSI (14), Stochastic, Williams %R, Rate-of-Change (ROC).
* **Volatilitas**: Average True Range (Wilder ATR-14), Bollinger Bands (Z-Score & Bandwidth), Keltner Channel.
* **Volume & Likuiditas**: Volume Z-Score (20-bar rolling), Volume Moving Average, VWAP.

### C. Antarmuka Ekstensi Python Plugin
Untuk logika eksotis yang tidak bisa diwakili oleh form visual (misal: algoritma grid berjarak dinamis atau pola candle multi-bar kustom), pengguna dapat menambahkan file script Python dengan dekorator standar:

```python
from indodax_lab.strategies.base import BaseStrategy, register_strategy

@register_strategy("EXOTIC_COPY_PINBAR")
class ExoticCopyPinbarStrategy(BaseStrategy):
    def evaluate_entry(self, frame, pair) -> bool:
        curr = frame.get_latest_bar(pair)
        prev = frame.get_previous_bar(pair)
        # Logika custom Python bebas di sini
        is_pinbar = (prev.high - max(prev.open, prev.close)) > 2 * abs(prev.open - prev.close)
        return is_pinbar and curr.close > curr.ema_20
```

---

## 5. Spesifikasi Halaman & Fitur Dashboard Analitik (Cloudflare Kumo Design System)

Dashboard web mengusung standar **Cloudflare Kumo Design System** (`@cloudflare/kumo`) yang ultra-profesional, berdensitas informasi tinggi, dan sangat ringan untuk laptop homelab:
* **Palet Warna & Token Kumo**: Latar belakang kanvas *Charcoal Slate* (`#080B11`), kartu & kontainer (`#0D121D`), garis batas presisi 1px (`#1E293B`), teks utama *Slate-50* (`#F8FAFC`), aksen ikonik **Cloudflare Orange** (`#F6821F`) untuk status aktif & brand badge, serta *Emerald Green* (`#22C55E`) untuk metrik laba.
* **Tipografi**: Font *Inter* untuk antarmuka UI dan *JetBrains Mono* untuk seluruh nominal Rupiah, persentase PnL, timestamp UTC, dan nonce transaksi.
* **Layout Shell**: Fixed Left Sidebar (lebar 240px), Top Telemetry Header dengan status pill berdenyut (`● Live Operational Status`), dan 4 Hero Metric Cards di bagian atas.

### Halaman 1: Live Bot Cockpit (Pusat Komando Otonom Kumo)
* **4-Column Hero Metric Cards**:
  * `TOTAL PORTFOLIO EQUITY`: Nominal besar `Rp 500.000` (+0.00% Alpha, modal kas utuh 100%).
  * `AVAILABLE CASH IDR`: `100.0%` (Rp 500.000, batas cadangan minimum 10%).
  * `ACTIVE RISK EXPOSURE`: `0.0%` (0 / Dynamic Capacity, plafon risiko 1.5% per trade).
  * `WATCHDOG & UPTIME`: `100.0%` (Detak jantung 60s OK, status baterai laptop 98% [AC ONLINE]).
* **Market Radar Table (Cloudflare Analytics Style)**: Memantau alam semesta koin cair (BTC, ETH, SOL, DOGE, XRP) dengan format tabel bergaris tipis: Pair, Last Price, 24h Volume, Bid-Ask Spread, Pills Rezim EMA200 (`[BEAR: Close <= EMA]`), dan Skor Probabilitas AI Platt Sigmoid.
* **Active Positions & Execution OMS Card**:
  * Menampilkan status posisi berjalan dengan indikator geser *Trailing Stop Ratchet*.
  * Kondisi *Empty State*: Menampilkan lencana proteksi kas 100% (*Cash Protection Shield*) saat seluruh pasar berada di bawah EMA200.
* **AI Decision Telemetry Box**: Menampilkan latensi inferensi ONNX CPU Core i3 (1.6 ms), status kalibrasi Platt Sigmoid ($a=0.98$), dan log reasoning penolakan/persetujuan entri.
* **Double-Entry Ledger Audit Strip**: Jurnal transaksi real-time di bagian bawah dashboard yang mencatat setiap debet/kredit, potongan fee bursa, dan pajak PMK-68.
* **Tombol Kontrol Darurat Kumo**:
  * `🚨 PANIC CLOSE (2FA)`: Tombol merah di pojok kanan atas dengan proteksi PIN 4-digit untuk penutupan paksa seluruh posisi jika terjadi anomali makro.

### Halaman 2: Interactive Backtester & Simulation Replay
* **Form Konfigurasi Pengujian**:
  * Pilihan Pair (BTC, ETH, SOL, atau multi-pair portofolio).
  * Rentang Tanggal (2021 s/d 2026).
  * Pemilihan Strategi (C01, C02, C07, atau racikan kustom).
  * Pengaturan Modal Awal & Fee Bursa (Default: Rp 500.000, 0.4322% Maker).
* **Mode Pemutaran Ganda (*Dual-Speed Mode*)**:
  * **Interactive Streaming Mode**: Mengalirkan progres candle demi candle via WebSocket, dilengkapi grafik TradingView dengan marker panah hijau (Buy) dan merah (Sell) yang muncul berurutan, serta kurva ekuitas yang bergerak dinamis.
  * **Turbo Instant Mode**: Menjalankan simulasi 5 tahun dalam 2 detik menggunakan engine vektor NumPy dan langsung menyajikan laporan akhir.
* **Laporan Kinerja Institusional (*Performance Tearsheet*)**:
  * Metrik Kunci: Total Return (%), Net Profit (Rp), Fee Paid (Rp), Win Rate (%), Profit Factor, Sharpe Ratio, Sortino Ratio, Maximum Drawdown (%).
  * Tabel Rincian Trade-by-Trade (Timestamp Masuk/Keluar, Harga, Alasan Exit: TP/SL/Decay, Laba Bersih Rupiah).
  * Histogram Distribusi Return & Heatmap Kinerja Bulanan.

### Halaman 3: Strategy & Indicator Studio
* Visual Drag-and-Drop / Form Builder untuk merancang aturan Entry, Exit, dan Stop Loss.
* Dropdown pemilihan model AI (M02 XGBoost, D04 iTransformer, None) dengan slider ambang batas probabilitas ($P \ge 38\% - 50\%$).
* Tombol instan *"Backtest Strategy Ini"* untuk langsung menguji ide baru dalam satu klik.

### Halaman 4: Buku Besar Akuntansi (Institutional Multi-Tab Ledger)
Sistem pembukuan berpasangan (*Double-Entry Bookkeeping*) yang menjamin akurasi modal tanpa selisih sen:
* **Multi-Tab Isolation**:
  * **Tab 1: Live Shadow Ledger**: Rekening aktif saldo berjalan Rp 500.000.
  * **Tab 2: Backtest Experiments**: Arsip buku besar dari pengujian historis sebelumnya.
  * **Tab 3: Real Production**: Rekening terpisah saat dihubungkan dengan modal uang nyata.
* **Jurnal Transaksi Lengkap**: Kolom Tanggal, Ref ID, Tipe Transaksi (`BUY_DEBIT`, `SELL_CREDIT`, `FEE_EXPENSE`), Nominal Debet, Nominal Kredit, Saldo Akhir Kas, dan Saldo Ekuitas.
* **Fee Burn Analytics**: Grafik area komparasi antara Laba Kotor (*Gross Alpha*) versus Biaya Bursa (*Exchange Fees Paid*).
* **Fitur Ekspor**: Unduh laporan lengkap dalam format `.CSV` dan `.JSON`.

### Halaman 5: Homelab System & Hardware Health
* Indikator Beban Laptop ASUS X441U:
  * Utilisasi CPU (%) per Core.
  * Pemakaian RAM (Bot Trading vs Project Lain vs Bebas).
  * Aktivitas Disk I/O HDD 5400 RPM (Read/Write KB/s).
  * Suhu Prosesor & Latensi Ping ke API Indodax (ms).
  * **Status Baterai Laptop (UPS Internal)**: Persentase daya dan status pengisian AC listrik PLN.

---

## 6. Prosedur Ketahanan & Fail-Safe Operasional (24/7 Homelab)

### A. Pemanfaatan Baterai Laptop Sebagai Built-In UPS
Laptop ASUS X441U memiliki keunggulan dibanding PC desktop karena memiliki baterai internal:
1. **Deteksi Pemadaman Listrik**: Daemon latar belakang memantau status daya AC melalui `upower` / `/sys/class/power_supply/BAT0`.
2. **Reaksi Otomatis**:
   * Jika listrik padam: Bot mengirimkan notifikasi Telegram: `⚠️ [PLN LISTRIK PADAM] Laptop beralih ke baterai internal (Sisa baterai: 85%). Bot tetap aktif memantau posisi.`
   * Bot mengaktifkan *Eco-Mode* (mengurangi polling log dan menurunkan kecerahan layar ke 0%).
   * Jika baterai tersisa 15%: Bot secara aman membatalkan pending order, menyimpan seluruh state transaksi ke HDD, dan mematikan sistem secara teratur (*graceful shutdown*) untuk mencegah kerusakan database.

### B. Systemd Auto-Healing & Watchdog
Aplikasi didaftarkan sebagai Linux Systemd Service (`/etc/systemd/system/indodax-shadow.service`):
* `Restart=always`: Jika terjadi crash memori atau jaringan terputus, service akan restart otomatis dalam 5 detik.
* `MemoryMax=1200M`: Batasan tegas cgroups agar bot tidak pernah mengonsumsi lebih dari 1.2 GB RAM, menjaga server *bimbel* tetap stabil.
* `Nice=10`: Menetapkan prioritas proses CPU di tingkat moderat agar tidak mendominasi proses sistem lainnya.

### C. Integrasi Notifikasi Dua Arah Telegram Bot
Operator dapat mengendalikan dan memantau bot dari smartphone tanpa perlu membuka laptop:
* `/status`: Menampilkan ringkasan kas, ekuitas, dan posisi aktif.
* `/radar`: Menampilkan kondisi pasar terkini (harga, EMA, RSI).
* `/pause`: Menghentikan sementara pembukaan posisi baru.
* `/resume`: Mengaktifkan kembali pencarian sinyal.
* `/panic_close`: Menutup seluruh posisi terbuka saat terjadi anomali makro darurat.

---

## 7. Tata Kelola Produksi, Siklus Strategi & Otoritas Eksekusi (Konsensus Grill-Me)

Berdasarkan pendalaman arsitektur melalui sesi peninjauan intensif (*Grill-Me*), ditetapkan 5 pilar tata kelola eksekusi uang riil:

### A. Siklus Hidup Strategi: Champion-Challenger (Incubation Pipeline)
* **Katalog Tak Terbatas**: Pengguna dapat merancang dan menyimpan puluhan strategi baru (baik racikan manual maupun hasil adaptasi *copy-trading*).
* **Mode Inkubator Bersama**: Seluruh strategi baru dapat berjalan secara *live* di mode **Shadow/Paper Trading** secara simultan tanpa memperebutkan modal riil.
* **Gerbang Promosi Objektif (*Objective Milestone Gates*)**:
  Sebuah strategi baru berstatus *Challenger* HANYA berhak dipromosikan menjadi *Champion* (diberi alokasi uang nyata) jika memenuhi 4 syarat kaku:
  1. Telah terbukti berjalan di mode Shadow minimal **14 hari kalender** atau menyelesaikan minimal **15 kali transaksi tertutup**.
  2. **Net PnL Positif Bersih** setelah dikurangi hurdle fee Indodax (0.4322%).
  3. **Win Rate $\ge 45\%$** (dengan rasio *Risk-to-Reward* minimal 2:1).
  4. **Maksimum Drawdown $\le 5\%$** dari saldo simulasi.
  Saat seluruh kriteria terpenuhi, sistem akan membuka lencana *"ELIGIBLE FOR PROMOTION"* dan mengaktifkan tombol promosi di dashboard.

### B. Model Otoritas Eksekusi: Staged Hybrid Toggle
Menjawab dilema *"Apakah eksekusi manual oleh trader atau langsung otomatis oleh bot?"*, sistem menyediakan saklar transisi fleksibel di Dashboard dan Telegram:
1. **Fase Shadow/Paper**: **100% Otonom oleh Bot** (tanpa risiko modal, untuk menguji kecepatan dan akurasi logika sistem).
2. **Fase Uang Nyata (Real Capital)**: Pengguna memiliki saklar kendali:
   * **Mode Semi-Autonomous (1-Click Human Approval)**: Bot mendeteksi sinyal, menghitung lot matematis, lalu mengirim pesan interaktif ke Telegram dengan tombol `[ SETUJUI ORDER ]` dan `[ BATALKAN ]`. Jika tidak direspons dalam 10 menit, order kedaluwarsa demi keamanan.
   * **Mode Full-Autonomous (Bot Direct Execution)**: Bot langsung mengirimkan order limit Maker ke Indodax tanpa campur tangan manusia, sangat krusial saat peluang breakout terjadi pada dini hari (pukul 01:00 - 04:00 WIB).
   * Pengguna dapat berpindah antar mode kapan saja dengan satu klik tombol toggle di dashboard.

### C. Sistem Rem Darurat: Triple-Layer Circuit Breaker
Untuk mencegah kerugian beruntun saat terjadi anomali pasar global atau kegagalan koneksi:
1. **Daily Loss Limit (3%)**: Jika total kerugian dalam 1 hari kalender mencapai 3% modal (misal: Rp 15.000 dari modal Rp 500.000), bot seketika mematikan pembukaan order baru hingga pergantian hari UTC berikutnya.
2. **Consecutive Loss Cooldown (3x Stop-Loss)**: Jika terjadi 3 kali *stop loss* berturut-turut, bot otomatis masuk masa *cooldown* selama 24 jam penuh untuk menghindari jebakan rezim *sideways whipsaw*.
3. **Emergency Max Drawdown (10%)**: Jika akumulasi penurunan ekuitas menyentuh 10% (modal sisa Rp 450.000), bot melakukan *hard halt*, membunyikan alarm merah darurat ke Telegram, dan hanya bisa diaktifkan kembali setelah audit manual oleh operator.

### D. Standar Keamanan Kredensial Indodax
1. **Zero-Withdraw Permission (Kunci Mutlak)**: API Key yang dibuat di akun Indodax **DILARANG KERAS** mencentang izin penarikan (*Withdraw*). Kunci HANYA memiliki izin *Read Account* dan *Trade / Order Placement*. Dengan demikian, peretasan server homelab sekalipun tidak akan pernah bisa mencuri atau menarik modal kas keluar dari bursa.
2. **Proteksi Izin File Linux**: API Key disimpan di file lokal `.env` pada server ASUS X441U dengan hak akses ketat `chmod 600` (hanya dapat dibaca oleh user Linux pemilik proses bot).
3. **Penyensoran Kredensial**: Seluruh secret key dilarang keras masuk ke dalam Git repository, output console, log file, maupun response JSON API dashboard.

### E. Pemilihan Alam Semesta Koin: Dynamic Liquid Universe (Top 10–15 Koin)
Menghindari bahaya koin illikuid (spread 5-8%, delisting risk, jebol rate limit 180 req/min) maupun keterbatasan hanya 3 koin saat pasar sideways:
1. **Sistem Saringan Likuiditas 3 Tingkat**:
   * **Gerbang 1 (Volume Harian)**: Volume perdagangan 24 jam di Indodax wajib $\ge \text{Rp } 2.000.000.000$ (Rp 2 Miliar/hari).
   * **Gerbang 2 (Spread Rapat)**: Selisih harga jual-beli (*Bid-Ask Spread*) $\le 0.25\%$ agar order Maker terisi tanpa slippage negatif.
   * **Gerbang 3 (Volatilitas Minimum)**: Volatilitas lilin 1-jam ($ATR\% \ge 0.75\%$) agar pergerakan harga mampu melompati hurdle fee 0.4322%.
2. **Kategori Koin**:
   * **Tier 1 (Core Champions - Selalu Aktif)**: `BTC/IDR`, `ETH/IDR`, `SOL/IDR` (Likuiditas tertinggi, penggerak portofolio utama).
   * **Tier 2 (Liquid Altcoin Watchlist - Aktif Dinamis)**: `DOGE/IDR`, `XRP/IDR`, `ADA/IDR`, `PEPE/IDR`, `BNB/IDR`. Hanya dipindai jika memenuhi Gerbang 1, 2, dan 3.
   * Menjaga server ASUS X441U hanya memproses 8–12 koin berkualitas tinggi per menit (sangat hemat RAM/CPU dan aman dari rate limit).

### F. Jembatan QuantOps: Indodax Quant MCP Server (Lenovo $\leftrightarrow$ Homelab)
Menghubungkan Workstation Lenovo (Laptop Riset AI dengan GPU NVIDIA RTX 3050 CUDA) dengan Server Homelab ASUS X441U (Server Eksekusi 24/7):
1. **Pemisahan Beban Kerja yang Sempurna**:
   * **Laptop Lenovo**: Riset strategi, backtest mendalam, pelatihan model AI berat (XGBoost GPU, PyTorch Deep Learning), dan komando via AI Assistant (Antigravity/Cursor).
   * **Server ASUS X441U**: Menjalankan engine FastAPI 24/7, inferensi CPU ultra-ringan (< 1.8 ms), eksekusi order Maker, dan pencatatan buku besar.
2. **Koleksi Tool MCP Bawaan**:
   * `register_strategy`: Mendaftarkan 1 strategi baru ke server via konfigurasi JSON/YAML.
   * `bulk_register_strategies`: Mendaftarkan puluhan strategi sekaligus dalam satu instruksi chat.
   * `deploy_model_bundle`: Mengirimkan bobot model `.ubj`, kalibrasi Platt Sigmoid, dan normalisasi mean/std dari Lenovo ke ASUS X441U (mendukung *hot-reload* tanpa mematikan bot).
   * `trigger_remote_backtest`: Memerintahkan server mengeksekusi backtest historis dan mengembalikan ringkasan metrik.
   * `get_live_portfolio_telemetry`: Menampilkan status saldo, posisi aktif, dan log bot di chat Lenovo.
   * `promote_strategy`: Mempromosikan strategi yang lolos inkubasi Shadow menjadi Champion.

### G. Jaringan & Akses Remote: Tailscale Mesh VPN (Zero Open Ports)
1. **Pemanfaatan Tailscale yang Sudah Ada**: Server ASUS X441U sudah terpasang Tailscale.
2. **Koneksi Privat Terenkripsi**:
   * Laptop Lenovo dan HP terhubung langsung ke IP Tailscale privat ASUS X441U (misal: `100.x.y.z:8000`).
   * **Nol Port Terbuka di Router**: Tidak memerlukan *port forwarding* di router WiFi rumah, kebal dari pemindaian botnet publik, dan secara otomatis menembus CGNAT provider internet (IndiHome/Biznet/FirstMedia).
   * Klien MCP di laptop Lenovo memanggil endpoint API homelab secara mulus melalui IP Tailscale.

### H. Manajemen Basis Data & Penyimpanan: Embedded SQLite WAL + Parquet
1. **Zero-RAM Footprint (< 5 MB)**: Menolak penggunaan database terpisah seperti PostgreSQL/MySQL tambahan yang memakan ratusan megabyte RAM. SQLite berjalan *in-process* di dalam runtime Python.
2. **Kompabilitas Piringan HDD 5400 RPM**:
   * Mengaktifkan mode Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) dan `PRAGMA synchronous = NORMAL;` untuk meminimalkan *head-seek* mekanis HDD.
   * Data lilin candle historis disimpan dalam format terkompresi Apache Parquet untuk pemrosesan backtest berkecepatan tinggi.

### I. Ketahanan Gangguan Jaringan: Automatic Gap Backfill & Barrier Replay
Jika koneksi internet WiFi rumah terputus selama 1–2 jam akibat gangguan ISP:
1. **Pendeteksi Putus Koneksi (*Heartbeat Monitor*)**: Saat API Indodax gagal diakses 3 kali berturut-turut, bot menahan eksekusi baru dan mencatat timestamp terputus.
2. **Rekonstruksi Data Tertinggal (*Historical Backfill*)**: Begitu internet pulih, bot secara otomatis memanggil endpoint `history_v2` untuk mengunduh seluruh lilin 1-jam yang terlewat selama masa offline.
3. **Pemeriksaan Barrier Retrospektif (*Retrospective Settlement*)**:
   * Untuk posisi yang sedang terbuka saat internet mati: Bot memeriksa lilin demi lilin apakah `High >= Take Profit` atau `Low <= Stop Loss`.
   * Jika batas tersentuh di masa offline, bot mencatat *fill* retrospektif pada harga dan timestamp lilin kejadian, menghitung laba/rugi riil, dan menyelaraskan saldo kas.
4. **Penyelarasan Saldo Indodax**: Memverifikasi saldo riil di bursa dan mengirimkan rangkuman rekonsiliasi ke Telegram.

### J. Pengemasan Produksi: Native Systemd + Nginx Reverse Proxy
1. **Nginx yang Sudah Ada**: Nginx server di ASUS X441U melayani file web statis hasil build React di `/var/www/trading-dashboard` dan mem-proxy request `/api` serta `/ws` ke backend FastAPI (`localhost:8000`).
2. **Native Systemd Service**: Bot berjalan sebagai service background Linux murni (`indodax-bot.service`):
   * `MemoryMax=1200M`: Batas keras cgroups agar bot tidak pernah memakan lebih dari 1.2 GB RAM.
   * `Restart=always` & `RestartSec=5`: Otomatis bangkit kembali jika terjadi kendala tak terduga.
   * **Nol Beban Docker**: Menghemat 150 MB+ RAM dan menghilangkan overhead I/O container pada HDD 5400 RPM.

### K. Pemicu Continual Retraining: Kuartalan / Milestone 25 Trade
1. **Pemisahan Peran**: Log trade dan memory penalti kegagalan (*Hard Negative*) diunduh dari server ASUS X441U ke workstation Lenovo via MCP tool.
2. **Pelatihan GPU di Lenovo**: Pelatihan pohon boosting baru (25 pohon inkremental) dilakukan di GPU RTX 3050 CUDA.
3. **Gerbang Validasi Otomatis Sebelum Deploy**:
   Model baru WAJIB lulus uji validasi out-of-sample:
   * $AUC \ge 0.52$
   * Precision $\ge 38\%$
   * Kemiringan kalibrasi Platt Sigmoid $a \in [0.8, 1.2]$
   Hanya model yang lolos yang diunggah kembali ke server ASUS X441U via `deploy_model_bundle` untuk *hot-reload*.

### L. Skema Notifikasi Telegram: 3-Tier Severity Alert Filter
Mencegah *alert fatigue* (kebisingan notifikasi) sambil menjamin keamanan 24/7:
1. **Tier 1 (INFO - Silent / Dashboard Only)**: Pemindaian rutin per jam tanpa sinyal dicatat hening di dashboard tanpa membunyikan notifikasi HP.
2. **Tier 2 (ACTION - Notifikasi Berbunyi)**:
   * Eksekusi Buy atau Sell (lengkap dengan pair, harga, lot, dan alasan exit: TP/SL).
   * Permintaan persetujuan order pada mode Semi-Autonomous (tombol Setujui/Tolak dengan timer 10 menit).
3. **Tier 3 (CRITICAL - Alarm Merah Darurat)**:
   * Listrik PLN padam (laptop berjalan dengan baterai internal < 25%).
   * Pemicu Circuit Breaker aktif (rugi harian 3% atau 3x stop-loss berturut-turut).
   * Gangguan koneksi internet atau kegagalan otentikasi API Indodax.

### M. Protokol Snapshot & Rollback Otomatis 1-Klik
Jika strategi atau model AI baru yang di-deploy berperilaku buruk atau anomali:
1. **Pencadangan Otomatis (*Pre-Deploy Snapshot*)**:
   Sebelum model `.ubj` atau konfigurasi strategi baru diterapkan, sistem otomatis membuat snapshot terkompresi dari versi sebelumnya (`models/snapshots/snapshot_YYYYMMDD_HHMMSS/` yang berisi file model lama, calibrator, dan state buku besar).
2. **Tombol Rollback Instan**:
   Dashboard dan Telegram dilengkapi tombol darurat `[ ⏪ Rollback to Previous Version ]`.
3. **Pemulihan Cepat (< 3 Detik)**:
   Saat ditekan, sistem langsung me-reload snapshot versi stabil sebelumnya ke memori tanpa perlu restart server dan tanpa kehilangan riwayat transaksi buku besar.

### N. Penanganan Order Menggantung & Partial Fills: 15-Minute Timeout Guard
1. **Batas Waktu Order Maker**: Setiap order limit Maker yang dikirimkan ke Indodax diberi waktu tunggu maksimal **15 menit**. Jika dalam 15 menit harga lari dan order belum terisi sama sekali, bot secara otomatis membatalkan order tersebut agar dana kas IDR tidak terkunci.
2. **Penanganan Partial Fill (Terisi Sebagian)**:
   Jika order beli hanya terisi sebagian (misal: hanya 40% yang berhasil terbeli), bot langsung membatalkan sisa 60% yang belum terisi, dan secara otomatis menyesuaikan ukuran posisi aktif serta stop-loss/take-profit sesuai dengan jumlah koin riil yang didapatkan.

### O. Kapasitas Portofolio Dinamis & Composite Alpha Tie-Breaker
1. **Penghapusan Kuota Slot Kaku**: Kuota slot maksimal 2 posisi dihapus. Portofolio bebas membuka posisi baru sebanyak apa pun yang didukung oleh saldo kas yang tersedia, dengan batasan:
   * **Fixed Fractional Risk**: Setiap trade tetap dibatasi risiko maksimal 1.5% dari total ekuitas.
   * **Plafon Kas per Trade**: Maksimal 25% kas per koin.
   * **Batas Cadangan Kas**: Sisa kas IDR menganggur minimal 10% dari total ekuitas.
   * **Satu Posisi per Pair**: Dilarang melakukan *pyramiding* pada pair yang sama untuk mencegah konsentrasi risiko.
2. **Composite Alpha Score (Penentu Prioritas Alokasi Kas)**:
   Jika pada jam yang sama muncul beberapa sinyal valid sekaligus (misal: ETH, SOL, dan DOGE bersamaan), alokasi kas diberikan berurutan dari koin dengan skor tertinggi menggunakan rumus gabungan:
   $$\text{Composite Alpha Score} = P_{\text{AI}} \times \left(\frac{\text{TP Distance}}{\text{SL Distance}}\right) \times \left(\frac{\text{ATR}}{\text{Price}}\right)$$
   Menggabungkan tingkat keyakinan probabilitas AI ($P_{\text{AI}}$) dengan rasio ekspektasi keuntungan bersih dan volatilitas harga.

### P. Pertahanan Flash-Crash & "V-Shape Rebound Sniper" (Peluang dalam Kesempitan)
1. **Spread Sanity Check ($\le 0.50\%$)**: Jika *Bid-Ask Spread* di Indodax melebar di atas 0.50% (likuiditas mengering akibat panik), bot menolak masuk demi menghindari slippage negatif.
2. **Mode V-Shape Rebound Sniper**: Saat terjadi *flash crash* ekstrem (harga anjlok $> 3.0 \times \text{ATR}$ dalam 1 jam), bot tidak pasif membeku, melainkan mengaktifkan mode *Sniper*:
   * Menunggu konfirmasi absorpsi pembeli pada lilin 1-jam (muncul ekor bawah / *lower pinbar wick* $\ge 50\%$ dari panjang rentang lilin).
   * Masuk dengan **Half-Lot Sizing (0.75% modal dipertaruhkan)** untuk meminimalkan risiko pisau jatuh.
   * Memasang Take-Profit lebar ($4.0 \times \text{ATR}$) untuk menangkap momentum pantulan balik agresif (*mean reversion snapback*).

### Q. Akuntansi Pajak Kripto Indonesia (PMK 68 PPh/PPN) & Dust Sweeper
1. **Pemisahan Transparan di Buku Besar**:
   Buku besar mencatat secara terpisah setiap komponen potongan agar saldo kas rupiah cocok 100% dengan saldo mutasi rekening Indodax:
   * `Gross Proceeds` (Nilai Kotor)
   * `Maker Fee Indodax` (0.1111% Beli, 0.3211% Jual)
   * `Tax Withholding` (PPh Final 0.1% + PPN 0.11% = 0.21% saat transaksi jual)
   * `Net Cash Credit` (Kas bersih yang benar-benar masuk ke saldo kas IDR)
2. **Dust Sweeper (Pembersih Remah Desimal Koin)**:
   Setiap eksekusi jual selalu memanggil parameter `sell_all=True` dengan pembulatan ke bawah sesuai *step size* Indodax. Sisa remah desimal kecil (*crypto dust* bernilai < Rp 1.000) dicatat sebagai *residual inventory* tanpa menghambat perputaran kas buku besar.

### R. Protokol Pemeliharaan Sistem Bursa (Exchange Maintenance Shield)
1. **Deteksi Otomatis Status Maintenance**: Jika API Indodax mengembalikan HTTP 502/503 atau pesan pemeliharaan server, bot mengenali status `EXCHANGE_MAINTENANCE` (bukan error lokal).
2. **Standby Polling Santai**: Bot beralih ke mode standby dengan memperpanjang jeda polling menjadi 5 menit sekali (agar tidak membombardir bursa) dan mengirimkan notifikasi Telegram.
3. **Post-Maintenance State Reconciler**:
   Begitu bursa online kembali:
   * Mengambil lilin pembukaan pertama bursa untuk mengecek apakah posisi terbuka sempat melampaui level SL/TP selama jam offline.
   * Menyelaraskan saldo kas dan koin langsung dari API privat saldo bursa.
   * Mengirimkan laporan rekonsiliasi tertib ke Telegram operator.

### S. Live Incubation Scorecard di Dashboard
Dashboard menampilkan kartu progres visual real-time untuk setiap strategi yang sedang magang di mode Shadow:
* **Hari Berjalan**: Indikator hari aktif menuju batas minimal 14 hari.
* **Trade Counter**: Jumlah transaksi tertutup menuju batas minimal 15 trade.
* **Net Alpha Bar**: Nilai laba bersih Rupiah setelah dikurangi hurdle fee & pajak.
* **Drawdown Meter**: Pemantau penurunan modal real-time terhadap batas toleransi 5%.
* **Win Rate Gauge**: Pengukur akurasi real-time terhadap batas minimal 45%.
* **Interactive Promotion Progress Bar**: Saat seluruh kriteria tercapai (100% hijau), tombol `[ 🚀 Promote to Champion ]` akan menyala dan siap diaktifkan dengan konfirmasi PIN keamanan.

### T. Ketahanan Jaringan & Watchdog Dua Lapis (Dual-Layer Dead Man's Switch)
1. **Heartbeat Pinger ke Cloud Watchdog (Healthchecks.io)**:
   * Bot mengirimkan HTTP GET heartbeat (`https://hc-ping.com/<uuid>`) setiap 60 detik tepat setelah siklus evaluasi lilin 1-jam/1-menit selesai.
   * **Batas Toleransi Keterlambatan (Grace Period 2 Menit)**: Jika bot gagal mengirim detak jantung selama 120 detik berturut-turut (akibat server beku, crash fatal, atau listrik/WiFi mati total), Healthchecks.io langsung membunyikan alarm darurat prioritas tinggi ke Telegram dan ponsel pintar operator dengan nada dering darurat khusus.
2. **Auto-Failover Jaringan Lokal (Dual-WAN Linux NetworkManager)**:
   * Konfigurasi prioritas antarmuka jaringan di ASUS X441U:
     * Primer: `wifi-home` (Koneksi WiFi rumah IndiHome/Biznet, Metric 100).
     * Sekunder: `usb0` (Koneksi USB Tethering dari smartphone cadangan / modem 4G murah, Metric 200).
   * Jika gateway WiFi utama kehilangan rute internet (ISP gangguan/kabel putus), kernel Linux secara otomatis mengalihkan seluruh lalu lintas TCP ke antarmuka USB Tethering dalam kurun waktu < 3 detik tanpa memutus proses bot yang sedang berjalan.

### U. Rencana Pemulihan Bencana HDD (Zero-Loss Disaster Recovery via Tailscale)
1. **Mitigasi Kerusakan Mekanis HDD 5400 RPM**:
   * Piringan HDD mekanis 5400 RPM yang sudah berumur sangat rentan mengalami *bad sector* atau kerusakan motorik mendadak.
   * **Replikasi Berkelanjutan Tanpa Beban (Litestream / Tailscale Rsync)**:
     * Menggunakan daemon ringan `Litestream` (< 10 MB RAM, nol CPU) yang memantau penulisan SQLite WAL secara *real-time*.
     * Setiap kali transaksi ditulis ke dalam buku besar, potongan frame WAL langsung disinkronkan secara terenkripsi melalui jaringan privat Tailscale ke laptop workstation Lenovo.
2. **Target Ketahanan Institusional**:
   * **RPO (Recovery Point Objective) < 1 Detik**: Tidak ada transaksi, saldo, atau posisi yang hilang meskipun HDD laptop ASUS X441U terbakar atau rusak total pada jam 3 pagi.
   * **RTO (Recovery Time Objective) < 60 Detik**: Jika laptop server mati total, operator cukup menjalankan perintah runner di laptop Lenovo: `python run_shadow_bot.py`. Laptop Lenovo langsung melanjutkan seluruh posisi yang sedang aktif tanpa kebingungan state.

### V. Keamanan Multi-Tenant & Kompartemen Sandbox Systemd (Isolasi Staging Bimbel)
1. **Ancaman Co-Tenancy Aplikasi Web Staging**:
   * ASUS X441U menjalankan staging project bimbel dan web landing page. Lingkungan staging rentan terhadap celah keamanan web (misal: Local File Inclusion / LFI, Remote Code Execution / RCE, atau upload file bebas).
   * Penyerang yang berhasil menyusup ke aplikasi staging dilarang keras dapat membaca kredensial API Indodax atau memanipulasi database trading bot.
2. **Prinsip Hak Akses Minimal (Principle of Least Privilege)**:
   * **Dedicated Linux User (`quantbot`)**: Bot berjalan di bawah user non-root `quantbot` tanpa hak akses `sudo` dan dengan direktori home terisolasi `/opt/indodax-quant/`.
   * **Izin Berkas Ketat**: Direktori dikunci dengan `chmod 700` (`rwx------`) dan berkas kredensial `.env` dikunci dengan `chmod 600` (`rw-------`). Pengguna web server (`www-data`) tidak memiliki hak akses baca bahkan untuk melihat daftar file bot.
3. **Hardening Sandbox Systemd Service**:
   ```ini
   [Unit]
   Description=Indodax Quant Trading Engine
   After=network-online.target tailscaled.service

   [Service]
   Type=simple
   User=quantbot
   Group=quantbot
   WorkingDirectory=/opt/indodax-quant
   ExecStart=/opt/indodax-quant/venv/bin/python run_shadow_bot.py --live

   # Isolasi Keamanan Tingkat Tinggi (Sandbox)
   ProtectSystem=strict
   ProtectHome=read-only
   ReadWritePaths=/opt/indodax-quant/data /opt/indodax-quant/logs
   PrivateTmp=true
   NoNewPrivileges=true
   CapabilityBoundingSet=

   # Alokasi Sumber Daya ASUS X441U
   MemoryMax=1200M
   MemorySwapMax=0B
   CPUQuota=60%
   Nice=10

   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
   Bahkan jika kernel atau proses lain dieksploitasi, Systemd melarang proses bot menulis ke file sistem sistemik dan mengunci swap memory (`MemorySwapMax=0B`) untuk mencegah HDD thrashing.

### W. Rekonsiliasi Pesanan Menggantung & State Machine Dua Fase (Ghost Fill Eliminator)
1. **Bahaya Network Timeout pada Bursa Kripto (Ghost Fill)**:
   * Saat mengirim HTTP POST `trade` ke Indodax, paket internet dapat mengalami timeout sebelum respons HTTP diterima oleh bot.
   * **Dilema Fatal**: Jika bot menganggap order gagal dan mencoba lagi, bisa terjadi *double-buy* (posisi menjadi 2x lipat dan melanggar aturan risiko 1.5%). Sebaliknya, jika dianggap sukses padahal order ditolak, bot akan melacak posisi fiktif ("hantu").
2. **Mesin Status Eksekusi Dua Fase (Two-Phase Order State Machine)**:
   * **Fase 1: PENDING_SUBMIT & Saldo Dibekukan**:
     * Bot membuat `client_order_id` unik (UUID v4 + timestamp).
     * Saldo kas sebesar lot order dibekukan sementara di memori agar tidak dialokasikan ke sinyal koin lain.
   * **Fase 2: IN_FLIGHT & Polling Rekonsiliasi**:
     * Begitu HTTP request terkirim, status berubah menjadi `IN_FLIGHT`.
     * Jika terjadi HTTP Timeout / Socket Drop / HTTP 504:
       1. Bot **TIDAK MENGIRIM ULANG** order.
       2. Bot langsung masuk ke status `RECONCILING` dan melakukan polling terarah ke endpoint privat `openOrders` Indodax (3 percobaan dengan exponential backoff: 2s, 4s, 8s).
       3. **Skenario A (Order Ditemukan di openOrders)**: Order terbukti berhasil diterima matching engine bursa. Bot mencatat `order_id` resmi bursa dan memantau status fil-nya.
       4. **Skenario B (Order Tidak Ada di openOrders)**: Bot segera memeriksa `orderHistory` (mencegah kemungkinan order langsung terisi instan sebagai Taker). Jika ada di history, catat sebagai `FILLED`.
       5. **Skenario C (Order Tidak Ada di Keduanya setelah 30 Detik)**: Dipastikan request tidak pernah sampai ke bursa. Bot membatalkan status `IN_FLIGHT`, mencatat `ABORTED_NETWORK_TIMEOUT`, mencairkan kembali saldo kas yang dibekukan, dan mengirimkan log peringatan ke Telegram.

### X. Pengarsipan Lilin Live & Engine Retensi Data (Continuous Data Harvesting)
1. **Penyimpanan Otomatis Tanpa Membebani HDD 5400 RPM**:
   * Selama lilin 1-jam sedang berjalan (menit ke-1 sampai ke-59), seluruh data pergerakan ditampung **100% di dalam RAM** (*In-Memory Ring Buffer*).
   * Tepat saat lilin 1-jam resmi ditutup (*bar close* pada `XX:00:05 UTC`), bot melakukan **1 kali penulisan sekuensial cepat** ke tabel SQLite (`market_candles_1h`) untuk seluruh koin aktif (ukuran < 5 KB per jam, nol beban IOPS).
2. **Dataset Historis Bertumbuh Otomatis**:
   * Data live tahun 2026, 2027, dan seterusnya otomatis tersimpan rapi menyambung dataset 2021–2025 tanpa perlu unduhan manual di masa depan.
   * Konsolidasi harian pada pukul 00:00 UTC mengonversi 24 lilin hari berjalan ke dalam partisi Apache Parquet (`data/curated_1h/year=YYYY/month=MM/`).
3. **Ekspor Retraining AI via MCP Tool**:
   * Laptop Lenovo dapat memanggil tool MCP `download_latest_candles` untuk menyedot arsip lilin live terbaru dari ASUS X441U sebagai bahan pelatihan GPU CUDA.

### Y. Penjaga Sinkronisasi Jam & Nonce Bursa (NTP Microsecond & Anti-Clock Drift)
1. **Bahaya Clock Drift pada Laptop Tua**:
   * Laptop bekas ASUS X441U dengan baterai CMOS yang berumur rentan mengalami pergeseran waktu sistem (*clock drift*) hingga beberapa detik per minggu.
   * API privat Indodax (`POST /trade`, `POST /getInfo`) menggunakan otentikasi HMAC-SHA512 dengan parameter `nonce` berupa timestamp milidetik monotonik. Jika jam laptop tertinggal/mendahului server Indodax $> 1.000\text{ ms}$, Indodax akan menolak seluruh request dengan pesan error: `"Invalid nonce"` atau `"Request timestamp expired"`.
2. **Mitigasi Jam Dua Lapis**:
   * **Daemon Sinkronisasi Waktu Linux (`chrony`)**: Dipasang pada OS Ubuntu ASUS X441U untuk melakukan sinkronisasi mikrodetik berkelanjutan ke server NTP Indonesia (`id.pool.ntp.org`).
   * **Dynamic Server-Time Nonce Offset Tracker**: Klien API Python mencatat selisih (*drift delta*) antara waktu lokal dengan header `Date` / server response Indodax. Setiap pembentukan `nonce` secara otomatis menambahkan offset delta ini, menjamin request tidak akan pernah tertolak akibat desinkronisasi jam.

### Z. Deteksi Peluruhan Strategi & Karantina Otomatis (Alpha Decay & Auto-Demotion)
1. **Risiko Strategi Usang (Regime Shift)**:
   * Strategi Champion yang sebelumnya menguntungkan dapat mengalami penurunan efektivitas (*Alpha Decay*) akibat perubahan rezim pasar (misal: pasar beralih dari fase tren kuat ke fase *choppy sideways* berkepanjangan).
2. **Mekanisme Karantina Otomatis (*Quarantine Circuit Breaker*)**:
   * Sistem memantau metrik performa bergulir 15 trade terakhir (*Rolling 15-Trade Window*) untuk setiap strategi Champion yang sedang memegang modal riil:
     * Jika *Rolling Win Rate* jatuh di bawah **35%**, ATAU
     * *Rolling Sharpe Ratio* berada di bawah **0.00** selama 30 hari berturut-turut, ATAU
     * Terjadi akumulasi *Drawdown* strategi menyentuh **4.0%**.
   * **Reaksi Otomatis**:
     * Bot seketika **mendemotasi strategi tersebut kembali ke status Challenger (Shadow Mode)**.
     * Alokasi modal riil dibekukan dan dikembalikan ke kas IDR.
     * Notifikasi darurat dikirim ke Telegram: `⚠️ [STRATEGY QUARANTINE] Strategi C02 didemotasi ke Shadow Mode akibat Alpha Decay (Rolling Win Rate 31%). Modal diamankan ke Kas.`
     * Strategi hanya boleh dipromosikan kembali setelah menjalani retraining AI atau perbaikan aturan logika.

### AA. Pengaman Bar-Close & Anti-Repainting (Bar-Close Latch +5s Guard)
1. **Bahaya Evaluasi Prematur (*Repainting / Unfinalized Bar*)**:
   * Jika bot mengevaluasi sinyal tepat pada detik `00:00:01`, lilin dari bursa Indodax mungkin belum sepenuhnya tertutup oleh matching engine, sehingga harga Close masih dapat berubah (fenomena *repainting*).
2. **Bar-Close Latch Protocol**:
   * Bot secara ketat menerapkan jeda penyangga 5 detik (*5-Second Grace Delay*): evaluasi indikator teknikal (EMA, RSI, ATR) dan inferensi AI HANYA dieksekusi pada detik `XX:00:05 UTC`.
   * Memastikan lilin 1-jam sebelumnya sudah 100% final, terkonfirmasi (*immutable*), dan bebas dari bias *lookahead* maupun sinyal palsu lilin berjalan.

### AB. Pengawas Termal & Kesehatan Perangkat Keras Laptop (CPU Thermal Watchdog)
1. **Karakteristik Termal ASUS X441U di Iklim Tropis**:
   * Laptop bekas di ruang homelab tanpa AC rentan mengalami penumpukan debu pada kipas pendingin atau pasta termal prosesor yang mengering.
   * Jika suhu prosesor Intel Core i3-6006U mencapai $\ge 85^\circ\text{C}$, prosesor akan mengalami *Thermal Throttling* parah (kecepatan turun dari 2.0 GHz ke 400 MHz), menyebabkan latensi eksekusi melonjak dan potensi server mati mendadak (*thermal shutdown*).
2. **Daemon Pemantau Termal Terintegrasi**:
   * Membaca `/sys/class/thermal/thermal_zone0/temp` setiap 5 menit.
   * **Ambang Batas Peringatan ($78^\circ\text{C}$)**: Mengirim notifikasi peringatan ke Telegram: `⚠️ [SUHU LAPTOP HANGAT] CPU Core i3 mencapai 78°C. Pastikan sirkulasi udara laptop lancar.`
   * **Ambang Batas Kritis ($85^\circ\text{C}$)**: Bot otomatis menangguhkan pembukaan posisi baru (*cooling pause*), menurunkan prioritas proses latar belakang, dan membunyikan alarm merah Telegram agar operator dapat memeriksa kipas fisik laptop.

### AC. Gerbang Anti-Konsentrasi Aset Tunggal (One-Position-Per-Asset Gate)
1. **Bahaya Korelasi Multi-Strategi**:
   * Ketika beberapa strategi aktif (misal C01 Breakout, C02 Pullback, C03 Momentum) secara bersamaan menghasilkan sinyal BUY pada aset yang sama (misal ETH) di jam yang sama, pembukaan order ganda akan melipatgandakan eksposur risiko modal portofolio ($3 \times 1.5\% = 4.5\%$).
2. **Aturan Satu Posisi per Aset (*Single-Asset Lock*)**:
   * Risk Governor memberlakukan gerbang mutlak: **Hanya 1 posisi aktif yang diizinkan per koin**.
   * Jika posisi ETH sudah dibuka oleh strategi C02, sinyal BUY dari C01 atau C03 pada ETH akan otomatis diabaikan (*suppressed*) dengan status `SKIP: ASSET_POSITION_ALREADY_OPEN`.
   * Melindungi portofolio dari kerugian terkonsentrasi (*correlation shock*) jika aset tersebut berbalik arah secara tajam.

### AD. Saringan Ketebalan Antrean Orderbook (Orderbook Depth Liquidity Guard)
1. **Bahaya Likuiditas Tipis pada Altcoin**:
   * Pada beberapa altcoin Indodax saat volume rendah, antrean harga terbaik (*best bid/ask*) terkadang hanya memiliki nilai ratusan ribu rupiah. Order beli bot yang bernilai jutaan rupiah rentan mengalami *slippage* parah atau ter-eksekusi di harga buruk.
2. **Aturan Kedalaman 3 Tingkat ($\ge 3\times$ Order Size)**:
   * Sebelum order Maker dikirimkan ke bursa, Order Management System (OMS) memverifikasi kedalaman buku pesanan (*order book depth*):
     $$\sum_{i=1}^{3} \text{DepthVolume}_i \times \text{Price}_i \ge 3 \times \text{OrderValue}$$
   * Likuiditas kumulatif pada 3 tingkat harga teratas wajib minimal **3 kali lipat lebih besar** dari nominal order bot kita.
   * Jika likuiditas di bawah ambang batas, entri ditunda (*postponed*) untuk mencegah dampak pasar negatif (*market impact*).

### AE. Detektor Feed Bursa Macet / Basi (Stale Data Feed Guard)
1. **Bahaya Ticker Membeku (*Frozen/Stale API Feed*)**:
   * Kadangkala server bursa merespons dengan kode HTTP 200 OK tetapi data harga di dalamnya macet (*freeze* pada timestamp beberapa menit lalu akibat kelambatan internal matching engine bursa).
2. **Pemeriksaan Keterbaruan Feed ($< 120$ Detik)**:
   * Bot membandingkan waktu sistem saat ini ($T_{\text{now}}$) dengan timestamp data bursa ($T_{\text{data}}$):
     $$\Delta T = T_{\text{now}} - T_{\text{data}}$$
   * Jika $\Delta T > 120\text{ detik}$, data dinyatakan **STALE / KADALUARSA**.
   * Bot seketika membekukan seluruh evaluasi sinyal, menolak pembukaan order baru, dan mencatat status peringatan ke log serta dashboard: `⚠️ [STALE FEED] Ticker Indodax terlambat > 120 detik. Eksekusi ditunda.`

### AF. Kunci Keamanan 2FA PIN "Anti Fat-Finger" (Command Safety Lockout)
1. **Mitigasi Kesalahan Manusia (*Fat-Finger Error*)**:
   * Menghindari ketidaksengajaan operator saat menekan tombol atau salah ketik perintah berbahaya di smartphone atau dashboard web (seperti penutupan paksa seluruh posisi saat tidak perlu atau reset buku besar).
2. **Protokol 4-Digit Security PIN**:
   * Perintah berkategori destruktif dan berisiko tinggi wajib disertai **4-Digit PIN rahasia**:
     * `/panic_close <PIN>` (contoh: `/panic_close 8821`)
     * `/reset_ledger <PIN>`
     * `/promote_strategy <ID> <PIN>`
     * `/change_risk <RATE> <PIN>`
   * Jika perintah dikirimkan tanpa PIN atau dengan PIN yang salah, permintaan langsung ditolak dan dicatat sebagai *Unauthorized Action*.

### AG. Modul Ekspor Laporan Pajak Kripto Tahunan (PMK-68 / SPT DJP Ready)
1. **Kepatuhan Pajak Kripto Indonesia (PMK 68/PMK.03/2022)**:
   * Setiap transaksi penjualan aset kripto di bursa resmi Indonesia terutang PPh Pasal 22 Final sebesar 0.1% dan PPN sebesar 0.11% (total 0.21%).
2. **Generator Laporan SPT Satu-Klik**:
   * Buku besar akuntansi (*Layer 7*) secara otomatis mengakumulasi potongan pajak pada setiap transaksi penjualan.
   * Dashboard dan Telegram menyediakan fitur ekspor: **"Export Laporan Pajak Tahunan (CSV & PDF)"** yang berisi rekapitulasi:
     * Nilai Peredaran Bruto Penjualan (Gross Sales Proceeds).
     * Total PPh Final 0.1% yang dipungut Indodax.
     * Total PPN 0.11% yang dipungut Indodax.
     * Nomor Bukti Transaksi / Ref ID per transaksi.
   * Laporan terformat sesuai kolom lampiran **SPT Tahunan Orang Pribadi (Formulir 1770-S Lampiran III)**, siap diserahkan langsung ke akuntan atau diunggah ke portal DJP Online.

---

## 8. Rencana Tahapan Pelaksanaan (*Step-by-Step Implementation Roadmap*)

Ketika siap melangkah ke tahap pembuatan (*development*), berikut adalah roadmap terstruktur yang akan dieksekusi:

1. **Fase 1: Backend Core & REST/WebSocket Engine (FastAPI)**
   * Mengintegrasikan `LiveShadowEngine` ke dalam service FastAPI asinkron.
   * Endpoint data pasar live, eksekusi strategi, dan streaming WebSocket status bot.
   * Endpoint engine backtest interaktif dengan generator streaming chunked.
2. **Fase 2: Frontend Dashboard (Vite + React / Next.js SPA)**
   * Membangun UI bertema gelap menggunakan Tailwind CSS + Shadcn UI.
   * Integrasi grafik candlestick interaktif menggunakan TradingView Lightweight Charts.
   * Implementasi halaman Live Cockpit, Interactive Backtest, Strategy Studio, dan Buku Besar.
   * Build statis (*Single Page Application*) agar dapat disajikan langsung oleh FastAPI tanpa memerlukan runtime Node.js tambahan di server homelab (menghemat RAM 200 MB+).
3. **Fase 3: Pengemasan & Uji Coba Homelab ASUS X441U**
   * Pembuatan script instalasi otomatis (setup Python virtual environment, Systemd service, UPower daemon battery watcher).
   * Konfigurasi cgroups memory limiter (1.2 GB cap).
   * Stress-test simulasi beban bersamaan dengan project staging bimbel.
4. **Fase 4: Uji Coba Shadow Forward Berkelanjutan (Paper Trading 30 Hari)**
   * Menjalankan bot selama 30 hari penuh di homelab server.
   * Mengaudit metrik profitabilitas riil, slippage, ketahanan koneksi, dan stabilitas baterai.
   * Evaluasi kesiapan promosi menuju modal nyata.

