"""
ta_processor.py — Technical Analysis Engine

Menerima list OHLCVCandle mentah → menghasilkan TAResult yang sudah
berisi semua nilai indikator yang dibutuhkan oleh signal_logic.py.

Indikator yang dihitung:
  - EMA 20 & 50          (trend direction)
  - Stochastic RSI       (entry timing — lebih presisi dari RSI biasa)
  - MACD 12/26/9         (momentum confirmation & falling knife filter)
  - Bollinger Bands 20   (level support/resistance)
  - ATR 14               (dasar kalkulasi SL/TP dinamis)
  - Volume MA 20         (konfirmasi partisipasi buyer)
  - ADX 14               (v1.1 baru — kekuatan tren untuk Breakout strategy)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd
import pandas_ta as ta

from config import TA_CONFIG
from indodax_api import OHLCVCandle

logger = logging.getLogger(__name__)

# Minimum candle yang dibutuhkan agar semua indikator valid
# EMA50 butuh 50 candle minimum + buffer untuk warmup
MIN_CANDLES_REQUIRED = 60


# ==============================================================================
# OUTPUT DATA CLASS
# ==============================================================================

@dataclass
class TAResult:
    """
    Hasil kalkulasi Technical Analysis untuk satu pair pada satu timeframe.
    Semua nilai adalah harga/nilai dari candle TERAKHIR (terkini).
    Nilai None berarti indikator tidak bisa dihitung (data kurang).
    """
    pair: str
    timeframe: str
    candle_count: int

    # Harga
    open: float         # Open price candle terakhir (untuk 15m confirmation)
    close: float
    high: float         # High candle terakhir (untuk analisis tambahan)
    low: float          # Low candle terakhir (untuk analisis tambahan)
    volume: float

    # EMA
    ema_fast: Optional[float]       # EMA 20
    ema_slow: Optional[float]       # EMA 50

    # Stochastic RSI (K dan D line)
    stoch_k: Optional[float]        # K-line (0-100)
    stoch_d: Optional[float]        # D-line / signal line (0-100)
    stoch_k_prev: Optional[float]   # K-line candle sebelumnya (untuk deteksi crossover)
    stoch_d_prev: Optional[float]   # D-line candle sebelumnya

    # MACD
    macd_line: Optional[float]
    macd_signal: Optional[float]
    macd_hist: Optional[float]       # histogram candle terakhir
    macd_hist_prev: Optional[float]  # histogram candle sebelumnya (untuk deteksi cross)

    # Bollinger Bands
    bb_upper: Optional[float]
    bb_mid: Optional[float]
    bb_lower: Optional[float]

    # ATR (Average True Range)
    atr: Optional[float]

    # Volume
    volume_ma: Optional[float]       # MA20 volume

    # ADX (Average Directional Index) — v1.1
    # Mengukur kekuatan tren, bukan arahnya. Skala 0-100.
    # ADX > 25 = tren kuat. ADX < 20 = tren lemah / sideways.
    adx: Optional[float]             # ADX value (kekuatan)
    adx_plus_di: Optional[float]     # +DI (Directional Movement positif / bullish)
    adx_minus_di: Optional[float]    # -DI (Directional Movement negatif / bearish)

    # --- Derived Signals (True/False) — dihitung di sini untuk kemudahan ---

    @property
    def is_ema_bullish(self) -> bool:
        """EMA fast > EMA slow → trend jangka pendek bullish."""
        if self.ema_fast is None or self.ema_slow is None:
            return False
        return self.ema_fast > self.ema_slow

    @property
    def is_stochrsi_oversold(self) -> bool:
        """K-line berada di zona oversold (< 20)."""
        if self.stoch_k is None:
            return False
        return self.stoch_k < TA_CONFIG.stoch_oversold

    @property
    def is_stochrsi_crossover_up(self) -> bool:
        """
        K-line baru saja crossover D-line dari bawah (bullish signal).
        Kondisi: K sebelumnya < D sebelumnya, dan K sekarang > D sekarang.
        """
        if any(v is None for v in [self.stoch_k, self.stoch_d, self.stoch_k_prev, self.stoch_d_prev]):
            return False
        return (self.stoch_k_prev < self.stoch_d_prev) and (self.stoch_k > self.stoch_d)  # type: ignore

    @property
    def is_price_at_lower_bb(self) -> bool:
        """Harga close menyentuh atau berada di bawah Lower Bollinger Band."""
        if self.bb_lower is None:
            return False
        return self.close <= self.bb_lower

    @property
    def is_price_above_upper_bb(self) -> bool:
        """Harga close menembus atau berada di atas Upper Bollinger Band. Trigger Breakout."""
        if self.bb_upper is None:
            return False
        return self.close >= self.bb_upper

    @property
    def is_volume_surge(self) -> bool:
        """Volume candle terakhir ≥ 1.5× MA Volume 20 (threshold Sniper)."""
        if self.volume_ma is None or self.volume_ma == 0:
            return False
        return self.volume >= (self.volume_ma * TA_CONFIG.volume_surge_multiplier)

    @property
    def is_volume_surge_breakout(self) -> bool:
        """Volume candle terakhir ≥ 2.0× MA Volume 20 (threshold lebih ketat untuk Breakout)."""
        if self.volume_ma is None or self.volume_ma == 0:
            return False
        return self.volume >= (self.volume_ma * 2.0)

    @property
    def is_macd_hist_turning_positive(self) -> bool:
        """
        MACD histogram baru berubah dari negatif menjadi positif.
        Ini adalah sinyal reversal yang kuat — filter utama falling knife.
        """
        if self.macd_hist is None or self.macd_hist_prev is None:
            return False
        return (self.macd_hist_prev < 0) and (self.macd_hist >= 0)

    @property
    def is_macd_bullish(self) -> bool:
        """MACD histogram positif (momentum bullish, tidak harus baru cross)."""
        if self.macd_hist is None:
            return False
        return self.macd_hist > 0

    @property
    def is_adx_strong(self) -> bool:
        """
        ADX > 25 = tren kuat (berlaku baik untuk uptrend maupun downtrend).
        Digunakan sebagai hard gate di Breakout strategy.
        """
        if self.adx is None:
            return False
        return self.adx > TA_CONFIG.adx_strong_threshold

    @property
    def is_adx_bullish_direction(self) -> bool:
        """
        +DI > -DI = arah directional movement ke atas (bullish).
        Perlu dikombinasikan dengan is_adx_strong agar bermakna.
        """
        if self.adx_plus_di is None or self.adx_minus_di is None:
            return False
        return self.adx_plus_di > self.adx_minus_di

    def summary(self) -> str:
        """String ringkas untuk logging."""
        stoch_k_str = f"{self.stoch_k:.1f}" if self.stoch_k else "N/A"
        adx_str = f"{self.adx:.1f}" if self.adx else "N/A"
        return (
            f"[{self.pair}/{self.timeframe}] "
            f"Close: {self.close:,.0f} | "
            f"EMA Bull: {self.is_ema_bullish} | "
            f"StochRSI Cross: {self.is_stochrsi_crossover_up} (K={stoch_k_str}) | "
            f"MACD+: {self.is_macd_hist_turning_positive} | "
            f"LowerBB: {self.is_price_at_lower_bb} | "
            f"UpperBB: {self.is_price_above_upper_bb} | "
            f"VolSurge: {self.is_volume_surge} | "
            f"ADX: {adx_str} (Strong: {self.is_adx_strong}, Bull: {self.is_adx_bullish_direction})"
        )


# ==============================================================================
# MAIN PROCESSOR
# ==============================================================================

def calculate(candles: List[OHLCVCandle], pair: str, timeframe: str) -> Optional[TAResult]:
    """
    Menghitung semua indikator TA dari list candle OHLCV.

    Args:
        candles: List OHLCVCandle dari indodax_api.fetch_ohlcv(), urut lama→baru.
        pair: Pair ID, e.g. "btc_idr".
        timeframe: Timeframe key, e.g. "1h".

    Returns:
        TAResult berisi semua nilai indikator dari candle terakhir.
        None jika data tidak cukup atau terjadi error.
    """
    if len(candles) < MIN_CANDLES_REQUIRED:
        logger.warning(
            f"[{pair}/{timeframe}] Data tidak cukup: {len(candles)} candle "
            f"(minimum {MIN_CANDLES_REQUIRED})"
        )
        return None

    try:
        df = _candles_to_dataframe(candles)
        df = _compute_indicators(df)
        result = _extract_last_values(df, pair, timeframe, len(candles))
        logger.debug(result.summary())
        return result

    except Exception as e:
        logger.error(f"[{pair}/{timeframe}] Error kalkulasi TA: {e}", exc_info=True)
        return None


def _candles_to_dataframe(candles: List[OHLCVCandle]) -> pd.DataFrame:
    """Konversi list OHLCVCandle ke DataFrame pandas siap pakai."""
    df = pd.DataFrame([{
        "timestamp": c.timestamp,
        "open":   c.open,
        "high":   c.high,
        "low":    c.low,
        "close":  c.close,
        "volume": c.volume,
    } for c in candles])

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.set_index("timestamp").sort_index()

    # Pastikan kolom numerik
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop baris dengan NaN di data dasar (candle corrupt)
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    return df


def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menjalankan kalkulasi semua indikator menggunakan pandas-ta.

    pandas-ta menghasilkan kolom baru yang langsung di-append ke DataFrame.
    Naming convention pandas-ta: EMA_{period}, STOCHRSIk_{...}, MACD_{...}, dll.
    """

    # --- EMA ---
    df.ta.ema(length=TA_CONFIG.ema_fast, append=True)   # → EMA_{ema_fast}
    df.ta.ema(length=TA_CONFIG.ema_slow, append=True)   # → EMA_{ema_slow}

    # --- Stochastic RSI ---
    # pandas-ta output: STOCHRSIk_{rsi}_{stoch}_{k}_{d} dan STOCHRSId_{...}
    df.ta.stochrsi(
        length=TA_CONFIG.stoch_rsi_period,
        rsi_length=TA_CONFIG.rsi_period,
        k=TA_CONFIG.stoch_smooth_k,
        d=TA_CONFIG.stoch_smooth_d,
        append=True,
    )

    # --- MACD ---
    # pandas-ta output: MACD_{fast}_{slow}_{signal}, MACDh_{...}, MACDs_{...}
    df.ta.macd(
        fast=TA_CONFIG.macd_fast,
        slow=TA_CONFIG.macd_slow,
        signal=TA_CONFIG.macd_signal,
        append=True,
    )

    # --- Bollinger Bands ---
    # pandas-ta output: BBU_{period}_{std}, BBM_{...}, BBL_{...}
    df.ta.bbands(
        length=TA_CONFIG.bb_period,
        std=TA_CONFIG.bb_std,
        append=True,
    )

    # --- ATR ---
    # pandas-ta output: ATRr_{period}
    df.ta.atr(length=TA_CONFIG.atr_period, append=True)

    # --- Volume MA ---
    df.ta.sma(close="volume", length=TA_CONFIG.volume_ma_period, append=True, prefix="VOL")

    # --- ADX (v1.1) ---
    # pandas-ta output: ADX_{period}, DMP_{period} (+DI), DMN_{period} (-DI)
    # ADX mengukur KEKUATAN tren, bukan arahnya. Digunakan di Breakout strategy.
    df.ta.adx(length=TA_CONFIG.adx_period, append=True)

    return df


def _extract_last_values(
    df: pd.DataFrame,
    pair: str,
    timeframe: str,
    candle_count: int,
) -> TAResult:
    """
    Mengekstrak nilai dari baris terakhir (candle terkini) DataFrame.

    Menggunakan helper _get() yang aman terhadap NaN dan KeyError.
    """

    def _get(col_pattern: str, row_idx: int = -1) -> Optional[float]:
        """Ambil nilai kolom dari row tertentu. Return None jika tidak ada / NaN."""
        # Cari kolom yang mengandung pattern (karena pandas-ta naming dinamis)
        matching_cols = [c for c in df.columns if col_pattern.lower() in c.lower()]
        if not matching_cols:
            return None
        val = df[matching_cols[0]].iloc[row_idx]
        if pd.isna(val):
            return None
        return float(val)

    # Nama kolom pandas-ta yang kita butuhkan
    ema_fast_col     = f"EMA_{TA_CONFIG.ema_fast}"
    ema_slow_col     = f"EMA_{TA_CONFIG.ema_slow}"
    stoch_k_pattern  = "STOCHRSIk"
    stoch_d_pattern  = "STOCHRSId"
    macd_hist_pattern = "MACDh"
    macd_line_pattern = f"MACD_{TA_CONFIG.macd_fast}"
    macd_sig_pattern  = "MACDs"
    bb_upper_pattern  = "BBU"
    bb_mid_pattern    = "BBM"
    bb_lower_pattern  = "BBL"
    atr_pattern       = "ATRr"
    vol_ma_pattern    = "VOL_SMA"
    # ADX column patterns (pandas-ta naming: ADX_14, DMP_14, DMN_14)
    adx_pattern       = f"ADX_{TA_CONFIG.adx_period}"
    adx_plus_pattern  = f"DMP_{TA_CONFIG.adx_period}"
    adx_minus_pattern = f"DMN_{TA_CONFIG.adx_period}"

    return TAResult(
        pair=pair,
        timeframe=timeframe,
        candle_count=candle_count,
        open=float(df["open"].iloc[-1]),
        close=float(df["close"].iloc[-1]),
        high=float(df["high"].iloc[-1]),
        low=float(df["low"].iloc[-1]),
        volume=float(df["volume"].iloc[-1]),

        ema_fast=_get(ema_fast_col),
        ema_slow=_get(ema_slow_col),

        stoch_k=_get(stoch_k_pattern),
        stoch_d=_get(stoch_d_pattern),
        stoch_k_prev=_get(stoch_k_pattern, row_idx=-2),
        stoch_d_prev=_get(stoch_d_pattern, row_idx=-2),

        macd_line=_get(macd_line_pattern),
        macd_signal=_get(macd_sig_pattern),
        macd_hist=_get(macd_hist_pattern),
        macd_hist_prev=_get(macd_hist_pattern, row_idx=-2),

        bb_upper=_get(bb_upper_pattern),
        bb_mid=_get(bb_mid_pattern),
        bb_lower=_get(bb_lower_pattern),

        atr=_get(atr_pattern),
        volume_ma=_get(vol_ma_pattern),

        # ADX (v1.1)
        adx=_get(adx_pattern),
        adx_plus_di=_get(adx_plus_pattern),
        adx_minus_di=_get(adx_minus_pattern),
    )