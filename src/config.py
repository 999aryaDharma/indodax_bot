"""
config.py — Centralized Configuration & Constants Management

Single source of truth untuk seluruh konfigurasi IBS.
Nilai sensitif di-load dari .env. Konstanta bisnis didefinisikan
sebagai immutable dataclasses. Fail-fast jika konfigurasi kritis absen.

v1.1 — Tambahan:
  - BearBounceConfig: parameter risiko ketat untuk counter-trend setup
  - BreakoutConfig: threshold dan bobot untuk Momentum Breakout strategy
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Final, FrozenSet, Dict
from dotenv import load_dotenv

load_dotenv()

# Project root directory (parent of src/)
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

# ==============================================================================
# LOGGING
# ==============================================================================

LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "INFO").upper()

# Ensure logs directory exists
LOG_DIR: Final[Path] = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "ibs.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


# ==============================================================================
# FAIL-FAST HELPER
# ==============================================================================

def _require_env(key: str) -> str:
    """Ambil env var; exit jika tidak ditemukan."""
    value = os.getenv(key)
    if not value:
        logger.critical(f"KONFIGURASI KRITIS TIDAK ADA: '{key}' tidak ditemukan di .env. App dihentikan.")
        raise SystemExit(1)
    return value


# ==============================================================================
# SECTION 1 — CREDENTIALS
# ==============================================================================

@dataclass(frozen=True)
class Credentials:
    indodax_api_key: str
    indodax_secret_key: str
    telegram_bot_token: str
    telegram_chat_id: str


CREDENTIALS: Final[Credentials] = Credentials(
    indodax_api_key=_require_env("INDODAX_API_KEY"),
    indodax_secret_key=_require_env("INDODAX_SECRET_KEY"),
    telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
    telegram_chat_id=_require_env("TELEGRAM_CHAT_ID"),
)


# ==============================================================================
# SECTION 2 — INDODAX API
# ==============================================================================

@dataclass(frozen=True)
class IndodaxConfig:
    public_base_url: str        = "https://indodax.com"
    private_base_url: str       = "https://indodax.com"
    private_v2_base_url: str    = "https://tapi.indodax.com"   # subdomain berbeda!
    request_timeout_sec: tuple  = (10, 30)   # (connect_timeout, read_timeout)
    max_retries: int            = 3
    retry_backoff_sec: float    = 2.0
    # 200 candle cukup untuk semua indikator (EMA50 butuh min 50 + buffer).
    # Dijaga rendah untuk RAM e2-micro.
    ohlcv_candle_limit: int     = 200
    # Jeda antar request publik agar tidak melanggar rate limit 180 req/menit
    rate_limit_sleep_sec: float = 0.4


INDODAX_CONFIG: Final[IndodaxConfig] = IndodaxConfig()


# ==============================================================================
# SECTION 3 — ASSET & MARKET
# ==============================================================================

ASSET_WHITELIST: Final[FrozenSet[str]] = frozenset({
    "btc_idr", "eth_idr", "sol_idr", "bnb_idr",
    "xrp_idr", "ada_idr", "doge_idr",
})

# tf value = parameter yang diterima Indodax API
TIMEFRAMES: Final[Dict[str, str]] = {
    "15m": "15",
    "1h":  "60",
    "4h":  "240",
    "1d":  "1D",    # Daily — untuk MTF Confluence Layer 0
}

PRIMARY_TIMEFRAME: Final[str] = "1h"   # entry timing
TREND_TIMEFRAME: Final[str]   = "4h"   # konfirmasi trend mayor
DAILY_TIMEFRAME: Final[str]   = "1d"   # MTF Confluence — gambaran besar
ENTRY_TIMEFRAME: Final[str]   = "15m"  # lazy fetch — konfirmasi entry timing (hanya jika skor >= 65%)


# ==============================================================================
# SECTION 4 — TECHNICAL ANALYSIS
# ==============================================================================

@dataclass(frozen=True)
class TAConfig:
    # EMA
    ema_fast: int               = 20
    ema_slow: int               = 50

    # Stochastic RSI (pengganti RSI biasa — lebih presisi untuk crypto)
    rsi_period: int             = 14
    stoch_rsi_period: int       = 14
    stoch_smooth_k: int         = 3
    stoch_smooth_d: int         = 3
    stoch_oversold: float       = 20.0
    stoch_overbought: float     = 80.0

    # MACD (konfirmator momentum & filter falling knife)
    macd_fast: int              = 12
    macd_slow: int              = 26
    macd_signal: int            = 9

    # Bollinger Bands (konfirmator level, bukan trigger utama)
    bb_period: int              = 20
    bb_std: float               = 2.0

    # ATR (dasar kalkulasi SL/TP yang adaptif)
    atr_period: int             = 14

    # ADX (kekuatan tren — digunakan di Breakout strategy)
    adx_period: int             = 14
    adx_strong_threshold: float = 25.0   # ADX > 25 = tren kuat

    # Volume
    volume_ma_period: int       = 20
    volume_surge_multiplier: float = 1.5


TA_CONFIG: Final[TAConfig] = TAConfig()


# ==============================================================================
# SECTION 5 — RISK MANAGEMENT (Bull Trend / default)
# ==============================================================================

@dataclass(frozen=True)
class RiskConfig:
    # Batas posisi sebagai % dari saldo IDR tersedia
    max_position_pct: float     = 0.50   # maks 50% — anti all-in
    min_position_pct: float     = 0.20   # min 20% — agar profit > fee

    # Batas risiko sebagai % dari TOTAL portfolio (hard limit)
    max_risk_pct: float         = 0.02   # 2% → Rp 10.000 dari Rp 500.000
    min_risk_pct: float         = 0.01   # 1%

    # ATR multiplier untuk SL dan TP
    sl_atr_multiplier: float    = 1.5    # ruang gerak vs noise market
    tp_atr_multiplier: float    = 2.5    # menghasilkan RR ≥ 1:1.67

    # Minimum RR yang diterima; jika < ini sinyal diabaikan
    min_rr_ratio: float         = 2.0    # 1:2

    # Minimum saldo IDR agar bot mau kirim sinyal (di bawah ini fee > profit)
    min_idr_balance: float      = 50_000.0


RISK_CONFIG: Final[RiskConfig] = RiskConfig()


# ==============================================================================
# SECTION 5a — BEAR BOUNCE RISK CONFIG (Counter-Trend — Parameter Ketat)
# ==============================================================================

@dataclass(frozen=True)
class BearBounceConfig:
    """
    Parameter risiko khusus untuk Bear Bounce strategy.

    Lebih ketat dari Bull Trend karena kita melawan tren harian.
    Prinsip: posisi kecil, RR tinggi, atau tidak masuk sama sekali.

    Perbedaan dari RiskConfig (Bull Trend):
      - Position size dipotong 3× lebih kecil (maks 15% vs 50%)
      - SL lebih sempit (ATR × 1.0 vs × 1.5) — kita butuh konfirmasi cepat
      - TP lebih jauh (ATR × 3.0 vs × 2.5) — kompensasi untuk RR yang lebih tinggi
      - Min RR dinaikkan ke 1:3 vs 1:2 — bounce harus jauh lebih kuat dari risiko
      - Max risiko per trade hanya 1% vs 2% — portfolio protection ekstra ketat
    """
    # Position sizing — jauh lebih konservatif
    max_position_pct: float     = 0.15   # maks 15% IDR (vs 50% di bull mode)
    min_position_pct: float     = 0.10   # min 10% IDR

    # Risk per trade
    max_risk_pct: float         = 0.01   # 1% total portfolio (vs 2%)

    # ATR multiplier
    sl_atr_multiplier: float    = 1.0    # SL sempit — harga harus langsung membuktikan
    tp_atr_multiplier: float    = 3.0    # TP jauh — bounce harus layak

    # RR minimum lebih ketat
    min_rr_ratio: float         = 3.0    # 1:3 (vs 1:2 di bull mode)

    # Gate harian — ketiga kondisi ini WAJIB terpenuhi di timeframe daily
    # sebelum Bear Bounce diizinkan sama sekali
    daily_rsi_oversold: float       = 35.0   # RSI(14) daily < 35
    daily_stochrsi_oversold: float  = 20.0   # StochRSI K daily < 20
    # Harga daily harus menyentuh atau di bawah Lower BB daily (checked in signal_logic)


BEAR_BOUNCE_CONFIG: Final[BearBounceConfig] = BearBounceConfig()


# ==============================================================================
# SECTION 5b — BREAKOUT CONFIG (Momentum Strategy)
# ==============================================================================

@dataclass(frozen=True)
class BreakoutConfig:
    """
    Parameter untuk Momentum Breakout strategy.

    Kapan digunakan: market sedang trending kuat ke atas (bukan sideways).
    Logika: harga menembus Upper BB dengan volume masif + ADX kuat =
            bukan akhir rally, melainkan awal momentum besar.

    ADX sebagai hard gate: jika ADX ≤ 25, breakout dianggap palsu (fake out)
    dan sinyal TIDAK dikirim, apapun kondisi lainnya.

    Bobot scoring berbeda dari Sniper karena setup-nya berbeda:
      - Volume lebih penting (35%) — tanpa volume, breakout hampir selalu fake
      - Upper BB (35%) — trigger utama
      - EMA arah (20%) — konfirmasi tren 4H searah
      - DMP > DMN (10%) — arah ADX bullish
    """
    # Hard gate — ADX wajib di atas threshold ini
    adx_threshold: float            = 25.0

    # Volume lebih ketat dari Sniper (2× vs 1.5×)
    volume_surge_multiplier: float  = 2.0

    # Scoring weights (total = 100%)
    weight_price_above_upper_bb: float  = 0.35
    weight_volume_surge: float          = 0.35
    weight_ema_bullish_4h: float        = 0.20
    weight_dmp_gt_dmn: float            = 0.10

    # v1.2: Diturunkan dari 80% → 70%. Masih lebih ketat dari Sniper
    # karena setup breakout lebih agresif (ikut momentum).
    min_score_to_signal: float          = 0.70


BREAKOUT_CONFIG: Final[BreakoutConfig] = BreakoutConfig()


# ==============================================================================
# SECTION 5c — TRAILING STOP-LOSS
# ==============================================================================

@dataclass(frozen=True)
class TrailingConfig:
    """
    Konfigurasi fitur Trailing Stop-Loss.

    Cara kerja:
      1. Saat harga naik ≥ activation_pct dari entry → trailing aktif
      2. SL digeser ke breakeven (entry) + lock_in_pct
      3. Setiap kali harga naik lebih tinggi, SL ikut naik (trailing_distance_pct di bawah high)
      4. Jika harga berbalik dan menyentuh SL baru → alert keluar dengan profit terkunci
    """
    # Harga harus naik minimal X% dari entry agar trailing aktif
    activation_pct: float           = 3.0   # 3% kenaikan → trailing mulai

    # Saat trailing aktif, SL minimum di entry + X% (mengunci profit minimal)
    lock_in_pct: float              = 1.0   # SL tidak boleh turun di bawah entry +1%

    # Jarak trailing dari highest price (SL = highest × (1 - distance_pct/100))
    trailing_distance_pct: float    = 2.0   # SL trail 2% di bawah high tertinggi

    # Interval minimum antar update SL (agar tidak spam notifikasi)
    min_update_interval_minutes: int = 15


TRAILING_CONFIG: Final[TrailingConfig] = TrailingConfig()


# ==============================================================================
# SECTION 5d — PAPER TRADING
# ==============================================================================

@dataclass(frozen=True)
class PaperConfig:
    """Konfigurasi Paper Trading (Ghost Mode / simulasi)."""
    db_path: str                    = ""  # Set dynamically below

    # Hari pengiriman weekly report (0=Senin, 6=Minggu)
    weekly_report_day: int          = 6     # Minggu
    weekly_report_hour: int         = 20    # Jam 20.00 WIB

    # Asumsi biaya trading Indodax (taker fee) untuk kalkulasi simulasi
    trading_fee_pct: float          = 0.003  # 0.3%


# Set paper trading db path using absolute path
PAPER_DB_PATH: Final[Path] = LOG_DIR / "paper_trades.db"
PAPER_CONFIG: Final[PaperConfig] = PaperConfig(db_path=str(PAPER_DB_PATH))


# ==============================================================================
# SECTION 6 — SIGNAL SCORING (Sniper / Mean-Reversion — default)
# ==============================================================================

@dataclass(frozen=True)
class ScoringConfig:
    # Bobot per kondisi (total = 100%)
    weight_macd_positive: float     = 0.25   # MACD histogram baru positif (4H)
    weight_stochrsi_cross: float    = 0.25   # StochRSI cross UP dari oversold (1H)
    weight_lower_bb: float          = 0.20   # Harga di/bawah Lower BB (1H)
    weight_volume_surge: float      = 0.20   # Volume ≥ 1.5× MA20 (1H)
    weight_ema_bullish: float       = 0.10   # EMA20 > EMA50 (1H)

    # v1.2: Diturunkan dari 80% → 65%.
    # Dengan bobot di atas, 80% membutuhkan ~4/5 kondisi terpenuhi sekaligus
    # — terlalu jarang di crypto 1H. 65% masih memfilter noise (butuh min.
    # MACD+StochRSI+Volume = 70%) tapi realistis untuk 1-2 sinyal/hari.
    min_score_to_signal: float      = 0.65


SCORING_CONFIG: Final[ScoringConfig] = ScoringConfig()


# ==============================================================================
# SECTION 7 — MARKET CONTEXT (Fear & Greed + BTC Dominance)
# ==============================================================================

@dataclass(frozen=True)
class ContextConfig:
    fear_greed_url: str         = "https://api.alternative.me/fng/"
    btc_dominance_url: str      = "https://api.coingecko.com/api/v3/global"

    # Threshold Fear & Greed
    extreme_fear_threshold: int = 25    # < 25 → bonus +10% ke skor
    extreme_greed_threshold: int = 75   # > 75 → penalti -15% dari skor

    score_bonus_extreme_fear: float     = 0.10
    score_penalty_extreme_greed: float  = 0.15

    # BTC Dominance: jika naik > threshold ini, tahan sinyal altcoin
    btc_dominance_rising_threshold: float = 0.5  # naik > 0.5% dalam 1 jam


CONTEXT_CONFIG: Final[ContextConfig] = ContextConfig()


# ==============================================================================
# SECTION 8 — APPLICATION BEHAVIOR
# ==============================================================================

@dataclass(frozen=True)
class AppConfig:
    scan_interval_minutes: int      = 5
    signal_cooldown_minutes: int    = 30   # v1.2: 60 → 30 menit
    context_fetch_interval_hours: int = 1
    health_check_interval_hours: int  = 6

    timezone: str               = "Asia/Jakarta"
    datetime_format: str        = "%A, %d %b %Y | %H:%M WIB"

    app_version: str            = "1.2.0"
    app_name: str               = "IndoBot Signal (IBS)"


APP_CONFIG: Final[AppConfig] = AppConfig()

# ==============================================================================
# STARTUP CONFIRMATION
# ==============================================================================

logger.info(
    f"✅ Config loaded | "
    f"Pairs: {len(ASSET_WHITELIST)} | "
    f"Scan: {APP_CONFIG.scan_interval_minutes}m | "
    f"Cooldown: {APP_CONFIG.signal_cooldown_minutes}m | "
    f"Min score (Sniper): {int(SCORING_CONFIG.min_score_to_signal * 100)}% | "
    f"Min score (Breakout): {int(BREAKOUT_CONFIG.min_score_to_signal * 100)}% | "
    f"Bear Bounce RR: 1:{BEAR_BOUNCE_CONFIG.min_rr_ratio:.0f} | "
    f"Max risk/trade: {int(RISK_CONFIG.max_risk_pct * 100)}%"
)