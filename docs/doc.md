# Project Documentation: IndoBot Signal (IBS)

### Versi 2.0 — Revisi Final

_Diperbarui berdasarkan sesi perencanaan & validasi kebutuhan pengguna_

---

## 1. Project Brief

| Atribut               | Detail                                           |
| --------------------- | ------------------------------------------------ |
| **Project Name**      | IndoBot Signal (IBS)                             |
| **Versi Dokumen**     | 2.0 (Final, siap build)                          |
| **Platform Target**   | Telegram (UI/Notifikasi) & Indodax (Sumber Data) |
| **Budget Deployment** | Rp 0 (Zero-Cost — GCP e2-micro Free Tier)        |
| **Modal Awal**        | Rp 500.000 (Indodax IDR Market)                  |
| **Status**            | ✅ Disetujui — Siap masuk fase build iteratif    |

### Core Objective

Membangun asisten trading berbasis Telegram yang menganalisis pergerakan harga aset kripto Big Cap di Indodax secara real-time menggunakan sistem **multi-layer Technical Analysis scoring**. Bot ini tidak mengeksekusi perdagangan secara otomatis. Setiap sinyal Buy yang dikirim dilengkapi dengan **Conviction Signal Format** — format briefing lengkap yang mencakup alasan sinyal, trading plan, position sizing, dan langkah eksekusi manual — sehingga pengguna dapat mengeksekusi dengan percaya diri tanpa keraguan.

### Key Constraints & Principles

- **Capital Protection First:** Melindungi modal Rp 500.000 adalah prioritas absolut. Risiko per transaksi dibatasi maksimal 1-2% dari total saldo.
- **No Direct Execution:** Bot hanya memiliki akses Read-Only ke akun Indodax. Eksekusi beli/jual 100% dilakukan manual oleh pengguna.
- **Quality Over Quantity:** Target 3-5 sinyal berkualitas per hari. Sinyal hanya dikirim jika skor multi-layer mencapai minimal 80%.
- **Data Quality:** Hanya memantau 7 koin Big Cap di pair IDR untuk menghindari manipulasi dan spread lebar.
- **Conviction-First Messaging:** Setiap pesan sinyal harus mampu menjawab keraguan pengguna secara mandiri — tanpa perlu pengguna membuka chart secara terpisah untuk memvalidasi.

---

## 2. User Profile & Validated Requirements

> _Bagian ini disintesis dari sesi validasi kebutuhan pengguna. Mendokumentasikan temuan ini penting agar seluruh keputusan desain dapat ditelusuri alasannya._

### 2.1 Profil Pengguna

- **Level:** Menengah — sudah memahami TA dasar, pernah mengalami profit dan loss.
- **Hambatan Utama Eksekusi (validated):**
  1. Ragu apakah sinyal valid → butuh penjelasan alasan sinyal di dalam pesan
  2. Takut salah memasang Stop-Loss & Take-Profit secara manual
  3. Tidak yakin dengan cara menghitung jumlah beli yang tepat di Indodax
- **Insight Kritis:** Masalah pengguna bukan pada kemampuan analisis, melainkan pada **kepercayaan diri saat eksekusi**. Solusinya adalah desain format pesan sinyal, bukan penambahan indikator.

### 2.2 Prioritas (Urutan dari Tertinggi)

1. Akurasi sinyal tinggi (sedikit sinyal, tapi presisi)
2. Proteksi modal di atas segalanya
3. Profit konsisten jangka panjang
4. Belajar & memahami logika TA dari sinyal yang muncul

### 2.3 Target Frekuensi Sinyal

- **3-5 sinyal per hari** — balance antara peluang dan kualitas.
- Ini adalah target yang diturunkan ke dalam parameter scoring engine, bukan sekedar preferensi.

---

## 3. Product Requirements Document (PRD) v2

### 3.1 Features & Capabilities

#### A. Market Monitoring (Public Data)

- **Asset Whitelist (immutable):** `btc_idr`, `eth_idr`, `sol_idr`, `bnb_idr`, `xrp_idr`, `ada_idr`, `doge_idr`
- **Timeframe Analisis:** 15m, 1H, 4H
- **Primary Timeframe (Entry Timing):** 1H
- **Trend Timeframe (Konfirmasi Mayor):** 4H

#### B. Technical Analysis Engine (Revisi dari v1)

Indikator dipilih berdasarkan karakteristik spesifik market crypto (volatile, 24/7, tanpa circuit breaker):

| Indikator           | Parameter                  | Fungsi                                                    | Perubahan dari v1                                      |
| ------------------- | -------------------------- | --------------------------------------------------------- | ------------------------------------------------------ |
| **EMA**             | Fast 20, Slow 50           | Deteksi trend direction & Golden/Death Cross              | Tetap                                                  |
| **Stochastic RSI**  | RSI 14, Stoch 14, K 3, D 3 | Entry timing — lebih sensitif dari RSI biasa untuk crypto | **Pengganti RSI murni**                                |
| **MACD**            | 12, 26, 9                  | Konfirmator momentum trend, filter falling knife          | **Baru**                                               |
| **Bollinger Bands** | Period 20, StdDev 2        | Konfirmator level support/resistance                      | Dipertahankan sebagai konfirmator, bukan trigger utama |
| **ATR**             | Period 14                  | Kalkulasi SL/TP yang adaptif terhadap volatilitas aktual  | **Pengganti fixed-% SL/TP**                            |
| **Volume MA**       | Period 20, Multiplier 1.5× | Konfirmasi partisipasi buyer (smart money)                | Tetap, diperketat                                      |

> **Mengapa RSI murni digantikan Stochastic RSI?**
> Di pasar crypto, kondisi RSI < 30 (oversold) bisa bertahan berhari-hari saat downtrend kuat, menghasilkan banyak false positive (falling knife signals). Stochastic RSI mengukur posisi RSI relatif terhadap range-nya sendiri, menghasilkan sinyal reversal yang jauh lebih presisi dan tepat waktu.

> **Mengapa ATR menggantikan fixed-% SL/TP?**
> Fixed percentage (-2% SL, +4% TP) bersifat buta terhadap volatilitas. Pair volatil seperti SOL akan sering kena SL dari noise market, sementara SL-nya terlalu sempit. ATR menghasilkan SL/TP yang proporsional dengan perilaku harga aktual pair tersebut.

#### C. Signal Scoring System (Fitur Kritis Baru)

Untuk mencapai target 3-5 sinyal berkualitas per hari dari potensi puluhan raw signals, diterapkan **sistem scoring berbobot**:

| Kondisi                                             | Bobot | Timeframe Evaluasi |
| --------------------------------------------------- | ----- | ------------------ |
| MACD histogram baru berubah positif                 | 25%   | 4H                 |
| Stoch RSI K-line cross UP dari zona oversold (< 20) | 25%   | 1H                 |
| Harga menyentuh/melewati Lower Bollinger Band       | 20%   | 1H                 |
| Volume candle terakhir ≥ 1.5× MA Volume 20          | 20%   | 1H                 |
| EMA 20 > EMA 50 (trend minor bullish)               | 10%   | 1H                 |

**Threshold Kelulusan: ≥ 80%**

Sinyal hanya dikirim ke Telegram jika total skor ≥ 80%. Skor ini juga ditampilkan di pesan sinyal sebagai indikator transparansi kepada pengguna.

#### D. Multi-Layer Signal Logic

```
Sinyal BUY dikirim HANYA jika SEMUA layer berikut lolos:

LAYER 1 — Trend Alignment (4H):
  ✓ Harga di atas EMA50 (bullish mayor), ATAU
  ✓ MACD Histogram baru berubah negatif → positif (reversal setup)

LAYER 2 — Entry Timing (1H):
  ✓ StochRSI K-line < 20 DAN baru crossover D-line (ke atas)
  ✓ Harga menyentuh atau di bawah Lower Bollinger Band

LAYER 3 — Volume Confirmation (1H):
  ✓ Volume candle terakhir ≥ 1.5× MA Volume 20

LAYER 4 — Risk Filter:
  ✓ ATR-based Risk/Reward Ratio ≥ 1:2
  ✓ Nilai risiko dalam IDR ≤ 2% dari saldo IDR aktif
  ✓ Saldo IDR aktif ≥ Rp 50.000 (minimum viable balance)

LAYER 5 — Scoring Gate:
  ✓ Total skor ≥ 80%

LAYER 6 — Cooldown Check:
  ✓ Tidak ada sinyal yang dikirim untuk pair ini dalam 60 menit terakhir
```

#### E. Portfolio Reading (Private Data — Read-Only)

- Bot terhubung ke Indodax Private API menggunakan Read-Only API Key.
- Membaca saldo IDR aktif secara real-time **hanya saat sinyal hendak dikirim** (bukan setiap scan) — untuk efisiensi API quota dan keamanan.
- Menggunakan Trade History V2 API untuk mendeteksi apakah pengguna sudah memegang posisi di pair tertentu (mencegah sinyal duplikat).

#### F. Market Context Layer (Gratis, Tanpa LLM)

Sebagai pengganti LLM Sentiment Analysis yang berbayar dan kompleks, dua indikator makro gratis digunakan sebagai **context filter**, bukan trigger sinyal:

**Fear & Greed Index (alternative.me — gratis, tanpa API key):**

| Nilai  | Klasifikasi   | Efek pada Sinyal                                 |
| ------ | ------------- | ------------------------------------------------ |
| 0–24   | Extreme Fear  | Bobot sinyal BUY +10% (contrarian setup terbaik) |
| 25–49  | Fear          | Tidak ada penyesuaian                            |
| 50–74  | Greed         | Tidak ada penyesuaian                            |
| 75–100 | Extreme Greed | Bobot sinyal BUY -15%, perketat SL               |

**BTC Dominance (CoinGecko — gratis):**

- BTC Dominance naik → tahan sinyal untuk altcoin (ETH, SOL, ADA, DOGE, XRP)
- BTC Dominance turun → aktifkan sinyal untuk semua pair (altseason)

> **Mengapa tidak LLM Sentiment?**
> Tiga alasan utama: (1) bertentangan dengan zero-cost constraint — API LLM komersial membutuhkan biaya $5–50/bulan, (2) RAM e2-micro (1GB) tidak mendukung LLM lokal, (3) LLM membaca teks dengan baik tapi tidak memahami psikologi pasar yang sering berlawanan dengan sentimen berita (buy the rumor, sell the news). Fear & Greed Index + BTC Dominance adalah proxy sentimen yang lebih battle-tested di crypto trading, tanpa biaya tambahan.

#### G. Telegram Commands

| Command    | Fungsi                                                     |
| ---------- | ---------------------------------------------------------- |
| `/start`   | Mengaktifkan bot dan menampilkan panduan singkat           |
| `/status`  | Status server, uptime, versi, jadwal scan berikutnya       |
| `/saldo`   | Saldo IDR aktif + estimasi nilai aset kripto yang dipegang |
| `/market`  | Snapshot kondisi TA semua pair whitelist + skor saat ini   |
| `/history` | 5 sinyal terakhir yang dikirim beserta statusnya           |

### 3.2 Conviction Signal Format (Format Pesan Sinyal Final)

Dirancang spesifik untuk mengatasi tiga hambatan eksekusi pengguna yang tervalidasi:

```
╔══════════════════════════════════════╗
  🚨 SINYAL BUY — SOL/IDR  |  ⚡ 85%
  Sabtu, 28 Jun 2025 | 14:35 WIB
╚══════════════════════════════════════╝

💡 KENAPA SINYAL INI VALID?
┌─────────────────────────────────────┐
│ ✅ Trend 4H   : Bullish (harga > EMA50)
│ ✅ MACD       : Histogram baru positif (reversal)
│ ✅ StochRSI   : Cross UP dari 18 → 26 (oversold)
│ ✅ Volatility : Menyentuh Lower BB, mulai rebound
│ ✅ Volume     : 2.1× rata-rata (buyer aktif)
│ 🌡 Sentimen  : Fear & Greed 28 — Fear (contrarian ✅)
└─────────────────────────────────────┘

💰 TRADING PLAN
  Entry      :  Rp  2.450.000
  Stop-Loss  :  Rp  2.376.500  (−3.0%)
  Take Profit:  Rp  2.635.000  (+7.6%)
  R/R Ratio  :  1 : 2.5  ✅

💼 SIZING (dari saldo aktualmu)
  Saldo IDR    :  Rp  487.500
  Beli         :  Rp  146.250  (30%)
  Est. coin    :  ≈  0.0597 SOL
  Risiko maks  :  Rp  7.310  (1.5% portfolio)

🛠 LANGKAH EKSEKUSI DI INDODAX:
  1️⃣ Buka market SOL/IDR
  2️⃣ Tab "Beli" → masukkan nominal: Rp 146.250
  3️⃣ Pasang Stop-Loss Limit di: Rp 2.376.500
  4️⃣ Pasang Take-Profit di: Rp 2.635.000
  ⚠️ Jangan ubah sizing — risiko sudah dihitung ketat

⚡ Skor Sinyal : ████████░░  85%
🔕 Cooldown   : Pair ini terkunci 60 menit
```

> Bagian "Kenapa Sinyal Ini Valid?" menjawab keraguan hambatan #1. Bagian "Sizing" menjawab hambatan #3. Bagian "Langkah Eksekusi" menjawab hambatan #2.

### 3.3 Out of Scope — v1.0

- Eksekusi otomatis (Auto Buy/Sell)
- Analisis sentimen berbasis LLM/Machine Learning
- Pemantauan altcoin di luar whitelist
- Short Selling (Indodax spot market hanya mendukung posisi Long/Buy)
- Multi-user / SaaS mode

---

## 4. Risk Management Specification

### 4.1 ATR-Based Dynamic SL/TP

Menggantikan pendekatan fixed-percentage yang buta terhadap volatilitas:

```
Stop-Loss  = Harga Entry − (ATR(14) × 1.5)
Take-Profit = Harga Entry + (ATR(14) × 2.5)

Minimum Risk/Reward Ratio yang diterima: 1:2.0
Jika RR yang dihasilkan < 1:2.0 → sinyal DIABAIKAN
```

### 4.2 Dynamic Position Sizing

```
Risiko per Trade (IDR) = Total Portfolio × max_risk_pct (maks 2%)

Contoh:
  Total saldo    = Rp 500.000
  Max risk 2%    = Rp 10.000
  ATR-based SL   = 3% dari harga entry
  Position Size  = Rp 10.000 / 3% = Rp 333.333

  Namun position size dibatasi antara 20%–50% saldo IDR tersedia.
  Jika hasil kalkulasi melebihi batas atas, dikap di 50%.
  Jika di bawah batas bawah, sinyal tetap dikirim dengan minimum 20%.
```

### 4.3 Capital Protection Rules

| Rule               | Nilai                  | Keterangan                                      |
| ------------------ | ---------------------- | ----------------------------------------------- |
| Max risk per trade | 2% total portfolio     | Hard limit, tidak bisa dikonfigurasi di runtime |
| Min risk per trade | 1% total portfolio     | Agar posisi tetap meaningful                    |
| Max position size  | 50% saldo IDR tersedia | Mencegah all-in                                 |
| Min position size  | 20% saldo IDR tersedia | Agar profit setelah fee masih meaningful        |
| Min IDR balance    | Rp 50.000              | Di bawah ini, sinyal tidak dikirim              |
| SL ATR multiplier  | 1.5×                   | Ruang gerak untuk noise market                  |
| TP ATR multiplier  | 2.5×                   | Menghasilkan RR ≥ 1:1.67 minimum                |
| Min RR Ratio       | 1:2.0                  | Jika tidak tercapai, sinyal diabaikan           |

---

## 5. Architecture Design System

### 5.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                        │
│                                                             │
│  Indodax Exchange          Telegram API                     │
│  ├─ Public API (OHLCV)     └─ Bot API (Push Notification)   │
│  ├─ Private API (Balance)                                   │
│  └─ Private API V2 (Trade History)                          │
│                                                             │
│  alternative.me            CoinGecko                        │
│  └─ Fear & Greed Index     └─ BTC Dominance                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   IBS CORE ENGINE                           │
│                                                             │
│  indodax_api.py            ta_processor.py                  │
│  ├─ HTTP Client            ├─ EMA 20/50                     │
│  ├─ HMAC-SHA512 Auth       ├─ Stochastic RSI 14             │
│  └─ Retry & Timeout        ├─ MACD 12/26/9                  │
│                            ├─ Bollinger Bands 20            │
│                            ├─ ATR 14                        │
│                            └─ Volume MA 20                  │
│                                                             │
│  signal_logic.py           risk_manager.py                  │
│  ├─ Multi-layer Evaluator  ├─ ATR-based SL/TP               │
│  ├─ Scoring Engine         ├─ Dynamic Position Sizing       │
│  └─ Cooldown State Mgr     └─ RR Ratio Validator            │
│                                                             │
│  telegram_bot.py           main.py                          │
│  ├─ Conviction Formatter   ├─ APScheduler Orchestrator      │
│  └─ Command Handlers       └─ Startup Health Check          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 INFRASTRUCTURE (GCP e2-micro)               │
│                                                             │
│  systemd (process supervisor — auto-restart on crash)       │
│  └── main.py (Python process, berjalan terus-menerus)       │
│          └── APScheduler (in-process job scheduler)         │
│                  ├── scan_market()  → setiap 5 menit        │
│                  ├── fetch_context() → setiap 1 jam         │
│                  └── health_check() → setiap 6 jam          │
└─────────────────────────────────────────────────────────────┘
```

> **Mengapa APScheduler, bukan cron OS?**
> Cron menjalankan proses Python baru setiap 5 menit — state aplikasi (misalnya "sinyal SOL sudah dikirim 30 menit lalu") tidak bisa di-share antar proses. APScheduler berjalan di dalam satu proses Python yang sama, sehingga in-memory state (cooldown tracker, skor terakhir per pair) tetap terjaga.

### 5.2 Data Flow (Alur Kerja Sinyal)

```
[APScheduler — setiap 5 menit]
      │
      ▼
1. [indodax_api.py] → fetch OHLCV semua pair (7 pair × 3 timeframe)
      │
      ▼
2. [ta_processor.py] → kalkulasi EMA, StochRSI, MACD, BB, ATR, Volume
      │
      ▼
3. [signal_logic.py] → evaluasi multi-layer + hitung scoring per pair
      │
   (Jika skor ≥ 80% DAN cooldown clear)
      │
      ▼
4. [indodax_api.py] → fetch saldo IDR aktif (Private API, HMAC auth)
      │
      ▼
5. [indodax_api.py] → fetch trade history (cek apakah pair sudah dipegang)
      │
      ▼
6. [risk_manager.py] → kalkulasi ATR-based SL/TP + position sizing
      │
   (Jika RR ≥ 1:2 DAN risiko IDR ≤ 2% portfolio)
      │
      ▼
7. [telegram_bot.py] → susun Conviction Signal Format (Markdown)
      │
      ▼
8. [Telegram Bot API] → kirim pesan ke HP pengguna 🔔
      │
      ▼
9. [signal_logic.py] → set cooldown 60 menit untuk pair ini
```

### 5.3 Project Directory Structure

```
indobot-signal/
│
├── .env                     # Secret keys — JANGAN di-commit ke Git
├── .env.example             # Template setup untuk server baru
├── .gitignore               # Exclude .env, logs/, __pycache__/
├── requirements.txt
├── README.md                # Panduan lengkap: dari buka GCP sampai bot live
│
├── src/
│   ├── __init__.py
│   ├── config.py            # ✅ SELESAI — env vars, konstanta, fail-fast validation
│   ├── indodax_api.py       # HTTP client: Public, Private, Private V2 API
│   ├── ta_processor.py      # Kalkulasi semua indikator TA
│   ├── signal_logic.py      # Multi-layer evaluator + scoring + cooldown state
│   ├── risk_manager.py      # ATR-based SL/TP + dynamic position sizing
│   ├── telegram_bot.py      # Conviction formatter + async command handlers
│   └── main.py              # APScheduler orchestrator + startup health check
│
├── logs/
│   └── .gitkeep             # Placeholder agar folder ter-commit ke Git
│
└── deploy/
    ├── ibs.service          # systemd unit file untuk GCP Ubuntu
    ├── setup.sh             # One-command server setup (dari nol ke running)
    └── logrotate.conf       # Rotasi log otomatis agar disk tidak penuh
```

---

## 6. Tech Stack

| Komponen           | Teknologi                  | Alasan Pemilihan                                     |
| ------------------ | -------------------------- | ---------------------------------------------------- |
| Language           | Python 3.9+                | Ekosistem library TA terlengkap                      |
| HTTP Client        | `requests` 2.31            | Stabil, mature, cukup untuk REST API                 |
| Data Manipulation  | `pandas` 2.1               | Standar de-facto untuk time-series OHLCV             |
| Technical Analysis | `pandas-ta` 0.3.14b        | Pure Python, zero C-dependency → mudah deploy di GCP |
| Telegram           | `python-telegram-bot` 20.7 | Async (asyncio), v20+ adalah standar saat ini        |
| Scheduler          | `APScheduler` 3.10         | In-process scheduler, menjaga state antar job        |
| Config             | `python-dotenv` 1.0        | Load .env ke os.environ                              |
| Timezone           | `pytz` 2024                | Handling WIB (Asia/Jakarta)                          |

> **Mengapa pandas-ta, bukan TA-Lib?**
> TA-Lib membutuhkan kompilasi library C (`libta-lib-dev`) yang sering gagal di environment GCP free tier dan menambah kerumitan setup. pandas-ta adalah pure Python dan menghasilkan indikator yang identik untuk semua indikator yang dibutuhkan proyek ini.

---

## 7. API Specification

### 7.1 Public API (Market Data)

- **Rate Limit:** 180 req/menit → wajib implementasi `time.sleep(1)` antar request
- **Base URL:** `https://indodax.com`

| Endpoint                  | Method | Fungsi                          |
| ------------------------- | ------ | ------------------------------- |
| `/api/ticker/<pair_id>`   | GET    | Harga terakhir (e.g., `btcidr`) |
| `/tradingview/history_v2` | GET    | Data OHLCV candlestick          |

Parameter OHLCV: `symbol` (uppercase, e.g., `BTCIDR`), `tf` (`15`, `60`, `240`), `from` (unix timestamp), `to` (unix timestamp)

### 7.2 Private API — Balance (Read-Only)

- **Base URL:** `https://indodax.com`
- **Endpoint:** `POST /tapi`
- **Auth:** HMAC-SHA512 signature dari request body menggunakan Secret Key
- **Headers:** `Key` (API Key), `Sign` (signature)
- **Payload:** `method=getInfo&timestamp=<ms>`
- **Response:** Saldo IDR aktif di `response["return"]["balance"]["idr"]`

### 7.3 Private API V2 — Trade History (Read-Only)

- **Base URL:** `https://tapi.indodax.com` _(subdomain berbeda!)_
- **Endpoint:** `GET /api/v2/myTrades`
- **Auth:** HMAC-SHA512 signature dari query string
- **Headers:** `X-APIKEY`, `Sign`, `Accept: application/json`
- **Query Params:** `symbol=<pair_id>&limit=10&timestamp=<ms>`
- **Fungsi:** Deteksi apakah pengguna sudah memegang posisi di pair tertentu → mencegah sinyal duplikat dan memungkinkan kalkulasi PnL aktual

### 7.4 External Context APIs (Gratis)

| API                | Endpoint                                  | Fungsi                | Interval Fetch |
| ------------------ | ----------------------------------------- | --------------------- | -------------- |
| Fear & Greed Index | `https://api.alternative.me/fng/`         | Sentimen makro market | Setiap 1 jam   |
| BTC Dominance      | `https://api.coingecko.com/api/v3/global` | Filter sinyal altcoin | Setiap 1 jam   |

### ⛔ STRICT RULE: Endpoint yang DILARANG

Bot tidak boleh, dalam kondisi apapun, mengakses endpoint berikut:

- `/trade` — eksekusi order
- `/cancelOrder` — membatalkan order
- `/withdraw` — penarikan dana
- Semua endpoint yang membutuhkan permission selain **"View/Info"**

---

## 8. Deployment Guide (GCP e2-micro — Zero Cost)

### 8.1 Target Infrastructure

- **Provider:** Google Cloud Platform (GCP)
- **Instance:** e2-micro (Always Free Tier — 0.25 vCPU, 1GB RAM)
- **OS:** Ubuntu 22.04 LTS
- **Region:** asia-southeast2 (Jakarta) — latensi ke Indodax minimal
- **Storage:** 30GB HDD standard (termasuk dalam free tier)

### 8.2 Proses Setup (Diautomasi via setup.sh)

Script `deploy/setup.sh` akan menangani seluruh proses berikut secara otomatis:

1. Update & upgrade sistem Ubuntu
2. Install Python 3.11 + pip + virtualenv
3. Clone repository dari Git
4. Buat virtual environment & install semua dependencies dari `requirements.txt`
5. Generate file `.env` secara interaktif (pengguna diminta paste API key)
6. Register & enable systemd service (`ibs.service`) untuk auto-start
7. Setup log rotation via `logrotate.conf`
8. Konfigurasi firewall (UFW) — menutup semua port kecuali yang diperlukan

### 8.3 Process Management

```
systemd
  └── ibs.service (auto-restart jika crash, start on boot)
        └── python main.py
              └── APScheduler
                    ├── scan_market()    → interval 5 menit
                    ├── fetch_context()  → interval 1 jam (F&G + BTC Dom)
                    └── health_check()   → interval 6 jam (kirim status ke Telegram)
```

### 8.4 Memory Optimization untuk 1GB RAM

- Fetch OHLCV maksimal 200 candle per pair (cukup untuk semua indikator)
- Data OHLCV tidak di-cache permanen — dibebaskan setelah setiap scan
- Private API hanya dipanggil saat sinyal akan dikirim, bukan setiap scan
- Logging level default: INFO (bukan DEBUG) di production

---

## 9. Upgrade Roadmap

Arsitektur dibangun dengan **Open/Closed Principle** — fitur baru bisa ditambahkan tanpa mengubah modul yang sudah ada dan teruji.

```
v1.0 — Sekarang (Build Phase)
├── Pure TA Signal + Multi-layer Scoring
├── ATR-based Risk Management
├── Conviction Signal Format
├── GCP Deployment (Zero Cost)
└── Tujuan: Validasi profitabilitas strategi

v1.5 — Bulan ke-3 (jika v1.0 terbukti profitable)
├── + Fear & Greed Index sebagai context filter (aktif)
├── + BTC Dominance filter untuk altcoins (aktif)
├── + Tambah pair baru → edit 1 baris di config.py
├── + /history command (track record sinyal)
└── Tujuan: Tambah modal, perluas cakupan pair

v2.0 — Bulan ke-6 (jika modal sudah signifikan)
├── + Auto-execution layer (plug-in ke signal_logic.py output)
├── + LLM news summarizer (jika ada budget API)
├── + Multi-user / SaaS mode
└── Tujuan: Monetisasi atau fully automated trading
```

Kunci skalabilitas: `signal_logic.py` mengekspos interface yang bersih:

```python
def get_signal(pair: str) -> SignalResult | None: ...
```

Di v2.0, auto-trader cukup "mendengarkan" output fungsi ini tanpa perlu memahami implementasi internalnya.

---

## 10. Build Roadmap (Urutan Pengerjaan)

| Sesi | Modul             | Dependensi      | Output yang Bisa Ditest                    |
| ---- | ----------------- | --------------- | ------------------------------------------ |
| ✅ 0 | `config.py`       | —               | Import tanpa error, startup log muncul     |
| 1    | `indodax_api.py`  | config.py       | Bisa fetch OHLCV & saldo IDR secara manual |
| 2    | `ta_processor.py` | indodax_api.py  | Print nilai indikator per pair             |
| 3    | `signal_logic.py` | ta_processor.py | Print skor sinyal per pair                 |
| 4    | `risk_manager.py` | signal_logic.py | Print SL/TP/sizing per sinyal              |
| 5    | `telegram_bot.py` | risk_manager.py | Kirim test sinyal ke Telegram              |
| 6    | `main.py`         | Semua modul     | Bot berjalan end-to-end di lokal           |
| 7    | `deploy/`         | main.py         | Bot live di GCP, auto-restart aktif        |

---

_Dokumen ini adalah living document. Setiap keputusan arsitektur yang diambil selama build phase harus didokumentasikan sebagai addendum di bagian relevan._
