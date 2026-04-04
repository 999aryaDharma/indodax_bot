"""
signal_logic.py — Multi-Layer Signal Evaluation Engine

v1.1 — Dual-Mode + Multi-Strategy + Verbose Logging

Setiap keputusan disertai nilai indikator aktual, jarak dari threshold,
dan skor per-komponen agar log bisa dibaca seperti laporan analisis.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from config import (
    APP_CONFIG, BEAR_BOUNCE_CONFIG, BREAKOUT_CONFIG,
    CONTEXT_CONFIG, SCORING_CONFIG, TA_CONFIG,
)
from indodax_api import MarketContext
from ta_processor import TAResult

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS
# ==============================================================================

class MarketMode(str, Enum):
    BULL  = "BULL_TREND"
    BEAR  = "BEAR_BOUNCE"
    SKIP  = "SKIP"


class SignalStrategy(str, Enum):
    SNIPER      = "SNIPER"
    BREAKOUT    = "BREAKOUT"
    BEAR_BOUNCE = "BEAR_BOUNCE"


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class LayerResult:
    passed: bool
    reason: str


@dataclass
class SignalDecision:
    pair: str
    should_signal: bool
    score: float
    score_pct: int

    market_mode: MarketMode         = MarketMode.BULL
    strategy: SignalStrategy        = SignalStrategy.SNIPER

    layer_trend: LayerResult    = field(default_factory=lambda: LayerResult(False, ""))
    layer_entry: LayerResult    = field(default_factory=lambda: LayerResult(False, ""))
    layer_volume: LayerResult   = field(default_factory=lambda: LayerResult(False, ""))
    layer_scoring: LayerResult  = field(default_factory=lambda: LayerResult(False, ""))

    ta_1h: Optional[TAResult]        = None
    ta_4h: Optional[TAResult]        = None
    context: Optional[MarketContext] = None
    rejection_reason: str            = ""


# ==============================================================================
# COOLDOWN STATE MANAGER
# ==============================================================================

class CooldownManager:
    def __init__(self, cooldown_minutes: int):
        self._cooldown_seconds: int = cooldown_minutes * 60
        self._last_signal_at: Dict[str, float] = {}

    def is_on_cooldown(self, pair: str) -> bool:
        last = self._last_signal_at.get(pair)
        if last is None:
            return False
        return (time.time() - last) < self._cooldown_seconds

    def set_cooldown(self, pair: str) -> None:
        self._last_signal_at[pair] = time.time()
        logger.info(
            f"[{pair}] Cooldown diset — "
            f"terkunci {APP_CONFIG.signal_cooldown_minutes} menit"
        )

    def remaining_minutes(self, pair: str) -> int:
        last = self._last_signal_at.get(pair)
        if last is None:
            return 0
        remaining = max(0, self._cooldown_seconds - (time.time() - last))
        return int(remaining / 60)


_cooldown_mgr = CooldownManager(APP_CONFIG.signal_cooldown_minutes)


# ==============================================================================
# LOGGING HELPERS
# ==============================================================================

def _v(val: Optional[float], dec: int = 2, suffix: str = "") -> str:
    """Format float aman dengan fallback N/A."""
    return f"{val:.{dec}f}{suffix}" if val is not None else "N/A"


def _threshold(val: Optional[float], thr: float, mode: str = "below",
               dec: int = 1) -> str:
    """
    Format nilai + status vs threshold.
    mode='below' → lulus jika val < thr  (untuk oversold, ADX min, dll)
    mode='above' → lulus jika val > thr
    """
    if val is None:
        return f"N/A (perlu {'<' if mode=='below' else '>'}{thr})"
    gap = (thr - val) if mode == "below" else (val - thr)
    ok = gap > 0
    sign = "<" if mode == "below" else ">"
    direction = f"{abs(gap):.{dec}f} {'lagi untuk lolos' if ok else 'lewat threshold'}"
    return f"{val:.{dec}f} ({'✅' if ok else '❌'} perlu {sign}{thr} | {direction})"


def _bb_gap(close: float, bb: Optional[float], label: str) -> str:
    """Jarak persentase harga ke Bollinger Band."""
    if bb is None or bb == 0:
        return f"{label}: N/A"
    pct = ((close - bb) / close) * 100
    if pct > 0:
        return f"{label}: harga {pct:.2f}% DI ATAS ❌"
    else:
        return f"{label}: harga {abs(pct):.2f}% DI BAWAH ✅"


def _vol_ratio(volume: float, vol_ma: Optional[float], thr: float = 1.5) -> str:
    """Rasio volume vs MA dengan status threshold."""
    if vol_ma is None or vol_ma == 0:
        return "Vol/MA: N/A"
    r = volume / vol_ma
    return f"Vol {r:.2f}× MA ({'✅' if r >= thr else '❌'} perlu ≥{thr}×)"


def _log_ta_snapshot(pair: str, ta: TAResult, tf_label: str) -> None:
    """
    Log satu baris padat berisi semua nilai indikator untuk satu timeframe.
    Format: [pair] TF | Close | EMA | StochRSI | MACD | ATR | ADX | BB | Volume | Signals
    """
    # Kumpulkan sinyal aktif untuk ringkasan cepat
    active = []
    if ta.is_ema_bullish:               active.append("EMA↑")
    if ta.is_stochrsi_oversold:         active.append("StochOS")
    if ta.is_stochrsi_crossover_up:     active.append("StochCross↑")
    if ta.is_macd_hist_turning_positive: active.append("MACDcross↑")
    if ta.is_macd_bullish:              active.append("MACD+")
    if ta.is_price_at_lower_bb:         active.append("AtLowerBB")
    if ta.is_price_above_upper_bb:      active.append("AboveUpperBB")
    if ta.is_volume_surge:              active.append("Vol≥1.5×")
    if ta.is_volume_surge_breakout:     active.append("Vol≥2.0×")
    if ta.is_adx_strong:                active.append("ADX>25")
    if ta.is_adx_bullish_direction:     active.append("DMP>DMN")
    signals_str = ", ".join(active) if active else "—"

    logger.info(
        f"[{pair}] {tf_label} │ "
        f"Close={ta.close:>16,.0f} │ "
        f"EMA20={_v(ta.ema_fast,0)} EMA50={_v(ta.ema_slow,0)} "
        f"({'Bull✅' if ta.is_ema_bullish else 'Bear❌'}) │ "
        f"StochRSI K={_v(ta.stoch_k,1)} D={_v(ta.stoch_d,1)} "
        f"(prev K={_v(ta.stoch_k_prev,1)}) │ "
        f"MACDh={_v(ta.macd_hist,6)} (prev={_v(ta.macd_hist_prev,6)}) │ "
        f"ATR={_v(ta.atr,0)} │ "
        f"ADX={_v(ta.adx,1)} +DI={_v(ta.adx_plus_di,1)} -DI={_v(ta.adx_minus_di,1)} │ "
        f"LoBB={_v(ta.bb_lower,0)} HiBB={_v(ta.bb_upper,0)} │ "
        f"{_vol_ratio(ta.volume, ta.volume_ma, 1.5)} │ "
        f"Sinyal: [{signals_str}]"
    )


# ==============================================================================
# DAILY MARKET CLASSIFIER
# ==============================================================================

def classify_daily_mode(ta_1d: TAResult) -> MarketMode:
    """
    Klasifikasi kondisi daily → BULL / BEAR / SKIP.
    Log semua nilai aktual dan jarak ke threshold secara eksplisit.
    """
    pair = ta_1d.pair

    price_above_ema50  = ta_1d.ema_slow is not None and ta_1d.close > ta_1d.ema_slow
    macd_bullish_daily = ta_1d.is_macd_bullish or ta_1d.is_macd_hist_turning_positive
    ema_cross_bullish  = ta_1d.is_ema_bullish
    bull_count = sum([price_above_ema50, macd_bullish_daily, ema_cross_bullish])

    # Kondisi Bear Bounce
    stoch_os = (ta_1d.stoch_k is not None and
                ta_1d.stoch_k < BEAR_BOUNCE_CONFIG.daily_stochrsi_oversold)
    at_lower_bb = ta_1d.is_price_at_lower_bb

    # Build detail strings
    price_ema_str = (
        f"Close={ta_1d.close:,.0f} vs EMA50={ta_1d.ema_slow:,.0f} "
        f"({'✅ di atas' if price_above_ema50 else '❌ di bawah'})"
        if ta_1d.ema_slow else "EMA50=N/A"
    )
    macd_str = (
        f"MACDhist={_v(ta_1d.macd_hist,6)} "
        f"({'✅ positif' if macd_bullish_daily else '❌ negatif'})"
    )
    ema_cross_str = (
        f"EMA20={_v(ta_1d.ema_fast,0)} vs EMA50={_v(ta_1d.ema_slow,0)} "
        f"({'✅ golden' if ema_cross_bullish else '❌ death cross'})"
    )
    stoch_str = _threshold(
        ta_1d.stoch_k, BEAR_BOUNCE_CONFIG.daily_stochrsi_oversold,
        mode="below", dec=1
    )
    bb_gap_str = _bb_gap(ta_1d.close, ta_1d.bb_lower, "Lower BB daily")

    if bull_count >= 1:
        logger.info(
            f"[{pair}] Daily → BULL ✅ ({bull_count}/3)\n"
            f"  ├─ Harga vs EMA50 : {price_ema_str}\n"
            f"  ├─ MACD daily     : {macd_str}\n"
            f"  └─ EMA cross      : {ema_cross_str}"
        )
        return MarketMode.BULL

    if stoch_os and at_lower_bb:
        logger.info(
            f"[{pair}] Daily → BEAR BOUNCE ⚠️\n"
            f"  ├─ Harga vs EMA50 : {price_ema_str}\n"
            f"  ├─ MACD daily     : {macd_str}\n"
            f"  ├─ StochRSI daily : {stoch_str}\n"
            f"  └─ {bb_gap_str}"
        )
        return MarketMode.BEAR

    # SKIP — log detail agar bisa track kemajuan ke gate
    bear_met = sum([stoch_os, at_lower_bb])
    logger.info(
        f"[{pair}] Daily → SKIP ❌ (Bull: {bull_count}/3 | Bear: {bear_met}/2)\n"
        f"  ├─ Harga vs EMA50 : {price_ema_str}\n"
        f"  ├─ MACD daily     : {macd_str}\n"
        f"  ├─ EMA cross      : {ema_cross_str}\n"
        f"  ├─ StochRSI daily : {stoch_str} (perlu < {BEAR_BOUNCE_CONFIG.daily_stochrsi_oversold})\n"
        f"  └─ {bb_gap_str} (perlu menyentuh/di bawah)"
    )
    return MarketMode.SKIP


def _classify_daily_reason(ta_1d: TAResult, mode: MarketMode) -> str:
    if mode == MarketMode.BULL:
        if ta_1d.ema_slow and ta_1d.close > ta_1d.ema_slow and ta_1d.is_ema_bullish:
            return "✅ Daily: Uptrend kuat (harga > EMA50 & golden cross)"
        elif ta_1d.ema_slow and ta_1d.close > ta_1d.ema_slow:
            return "✅ Daily: Harga di atas EMA50"
        else:
            return "✅ Daily: MACD positif / EMA bullish"
    elif mode == MarketMode.BEAR:
        k = f"{ta_1d.stoch_k:.1f}" if ta_1d.stoch_k else "N/A"
        return f"⚠️ Daily: Bearish tapi oversold (StochRSI={k}, di Lower BB)"
    else:
        return "❌ Daily: Bearish — belum cukup oversold untuk bounce"


# ==============================================================================
# SCORING ENGINES
# ==============================================================================

def _calculate_sniper_score(ta_1h: TAResult, ta_4h: TAResult) -> float:
    cfg = SCORING_CONFIG
    score = 0.0
    if ta_4h.is_macd_hist_turning_positive or ta_4h.is_macd_bullish:
        score += cfg.weight_macd_positive
    if ta_1h.is_stochrsi_crossover_up and ta_1h.is_stochrsi_oversold:
        score += cfg.weight_stochrsi_cross
    elif ta_1h.is_stochrsi_oversold:
        score += cfg.weight_stochrsi_cross * 0.5
    if ta_1h.is_price_at_lower_bb:
        score += cfg.weight_lower_bb
    if ta_1h.is_volume_surge:
        score += cfg.weight_volume_surge
    if ta_1h.is_ema_bullish:
        score += cfg.weight_ema_bullish
    return min(score, 1.0)


def _calculate_breakout_score(ta_1h: TAResult, ta_4h: TAResult) -> float:
    if not ta_4h.is_adx_strong:
        return 0.0
    cfg = BREAKOUT_CONFIG
    score = 0.0
    if ta_1h.is_price_above_upper_bb:
        score += cfg.weight_price_above_upper_bb
    if ta_1h.is_volume_surge_breakout:
        score += cfg.weight_volume_surge
    if ta_4h.is_ema_bullish:
        score += cfg.weight_ema_bullish_4h
    if ta_4h.is_adx_bullish_direction:
        score += cfg.weight_dmp_gt_dmn
    return min(score, 1.0)


def _calculate_bear_bounce_score(ta_1h: TAResult, ta_4h: TAResult) -> float:
    score = 0.0
    if ta_1h.is_stochrsi_crossover_up and ta_1h.is_stochrsi_oversold:
        score += 0.40
    elif ta_1h.is_stochrsi_oversold:
        score += 0.20
    if ta_1h.is_volume_surge:
        score += 0.30
    if ta_4h.is_macd_hist_turning_positive:
        score += 0.30
    elif ta_4h.is_macd_bullish:
        score += 0.15
    return min(score, 1.0)


# ==============================================================================
# SCORE BREAKDOWN LOGGERS
# ==============================================================================

def _log_sniper_breakdown(pair: str, ta_1h: TAResult, ta_4h: TAResult,
                          score: float) -> None:
    cfg = SCORING_CONFIG
    thr = int(cfg.min_score_to_signal * 100)

    # MACD 4H
    macd_ok = ta_4h.is_macd_hist_turning_positive or ta_4h.is_macd_bullish
    macd_pts = cfg.weight_macd_positive if macd_ok else 0
    macd_tag = ("baru cross+" if ta_4h.is_macd_hist_turning_positive
                else "positif" if macd_ok else "negatif")

    # StochRSI 1H
    stoch_full = ta_1h.is_stochrsi_crossover_up and ta_1h.is_stochrsi_oversold
    stoch_half = ta_1h.is_stochrsi_oversold and not ta_1h.is_stochrsi_crossover_up
    stoch_pts  = (cfg.weight_stochrsi_cross if stoch_full
                  else cfg.weight_stochrsi_cross * 0.5 if stoch_half else 0)
    stoch_tag  = ("Cross+Oversold" if stoch_full
                  else "Oversold(½poin)" if stoch_half else "Belum oversold")

    # Lower BB
    bb_ok  = ta_1h.is_price_at_lower_bb
    bb_pts = cfg.weight_lower_bb if bb_ok else 0

    # Volume
    vol_ok  = ta_1h.is_volume_surge
    vol_pts = cfg.weight_volume_surge if vol_ok else 0

    # EMA
    ema_ok  = ta_1h.is_ema_bullish
    ema_pts = cfg.weight_ema_bullish if ema_ok else 0

    status = "✅ LOLOS" if score >= cfg.min_score_to_signal else f"❌ BELUM (kurang {thr - int(score*100)}%)"
    logger.info(
        f"[{pair}] SNIPER breakdown → {int(score*100)}% / {thr}% {status}\n"
        f"         • MACD 4H [{macd_tag}]          : +{int(macd_pts*100)}%"
        f"  (hist={_v(ta_4h.macd_hist,6)} prev={_v(ta_4h.macd_hist_prev,6)})\n"
        f"         • StochRSI 1H [{stoch_tag}]   : +{int(stoch_pts*100)}%"
        f"  (K={_v(ta_1h.stoch_k,1)} D={_v(ta_1h.stoch_d,1)}"
        f" prevK={_v(ta_1h.stoch_k_prev,1)})\n"
        f"         • Lower BB 1H                  : +{int(bb_pts*100)}%"
        f"  ({_bb_gap(ta_1h.close, ta_1h.bb_lower, 'LoBB')})\n"
        f"         • Volume 1H                    : +{int(vol_pts*100)}%"
        f"  ({_vol_ratio(ta_1h.volume, ta_1h.volume_ma, 1.5)})\n"
        f"         • EMA 1H                       : +{int(ema_pts*100)}%"
        f"  (EMA20={_v(ta_1h.ema_fast,0)} EMA50={_v(ta_1h.ema_slow,0)})"
    )


def _log_breakout_breakdown(pair: str, ta_1h: TAResult, ta_4h: TAResult,
                             score: float) -> None:
    cfg = BREAKOUT_CONFIG
    thr = int(cfg.min_score_to_signal * 100)

    # ADX hard gate
    adx_gate = ta_4h.is_adx_strong
    if not adx_gate:
        logger.info(
            f"[{pair}] BREAKOUT breakdown → 0% / {thr}% ❌ ADX HARD GATE GAGAL\n"
            f"         • ADX 4H: {_threshold(ta_4h.adx, cfg.adx_threshold, 'above', 1)}"
        )
        return

    bb_ok  = ta_1h.is_price_above_upper_bb
    bb_pts = cfg.weight_price_above_upper_bb if bb_ok else 0
    vol_ok  = ta_1h.is_volume_surge_breakout
    vol_pts = cfg.weight_volume_surge if vol_ok else 0
    ema_ok  = ta_4h.is_ema_bullish
    ema_pts = cfg.weight_ema_bullish_4h if ema_ok else 0
    dmp_ok  = ta_4h.is_adx_bullish_direction
    dmp_pts = cfg.weight_dmp_gt_dmn if dmp_ok else 0

    status = "✅ LOLOS" if score >= cfg.min_score_to_signal else f"❌ BELUM (kurang {thr - int(score*100)}%)"
    logger.info(
        f"[{pair}] BREAKOUT breakdown → {int(score*100)}% / {thr}% {status}\n"
        f"         • ADX 4H [GATE]  : ✅ {_v(ta_4h.adx,1)}"
        f"  +DI={_v(ta_4h.adx_plus_di,1)} -DI={_v(ta_4h.adx_minus_di,1)}\n"
        f"         • Upper BB 1H   : +{int(bb_pts*100)}%"
        f"  ({_bb_gap(ta_1h.close, ta_1h.bb_upper, 'HiBB')})\n"
        f"         • Volume ≥2× 1H : +{int(vol_pts*100)}%"
        f"  ({_vol_ratio(ta_1h.volume, ta_1h.volume_ma, 2.0)})\n"
        f"         • EMA Bull 4H   : +{int(ema_pts*100)}%"
        f"  (EMA20={_v(ta_4h.ema_fast,0)} EMA50={_v(ta_4h.ema_slow,0)})\n"
        f"         • +DI > -DI 4H  : +{int(dmp_pts*100)}%"
        f"  ({'✅' if dmp_ok else '❌'})"
    )


def _log_bear_breakdown(pair: str, ta_1h: TAResult, ta_4h: TAResult,
                        score: float) -> None:
    thr = int(SCORING_CONFIG.min_score_to_signal * 100)

    stoch_full = ta_1h.is_stochrsi_crossover_up and ta_1h.is_stochrsi_oversold
    stoch_half = ta_1h.is_stochrsi_oversold and not ta_1h.is_stochrsi_crossover_up
    stoch_pts  = 0.40 if stoch_full else (0.20 if stoch_half else 0)
    stoch_tag  = ("Cross+Oversold" if stoch_full
                  else "Oversold(½)" if stoch_half else "Belum oversold")

    vol_ok  = ta_1h.is_volume_surge
    vol_pts = 0.30 if vol_ok else 0

    macd_full = ta_4h.is_macd_hist_turning_positive
    macd_half = ta_4h.is_macd_bullish and not macd_full
    macd_pts  = 0.30 if macd_full else (0.15 if macd_half else 0)
    macd_tag  = ("baru cross+(penuh)" if macd_full
                 else "positif(½)" if macd_half else "negatif")

    status = "✅ LOLOS" if score >= SCORING_CONFIG.min_score_to_signal else f"❌ BELUM (kurang {thr - int(score*100)}%)"
    logger.info(
        f"[{pair}] BEAR BOUNCE breakdown → {int(score*100)}% / {thr}% {status}\n"
        f"         • StochRSI 1H [{stoch_tag}] : +{int(stoch_pts*100)}%"
        f"  (K={_v(ta_1h.stoch_k,1)} D={_v(ta_1h.stoch_d,1)}"
        f" prevK={_v(ta_1h.stoch_k_prev,1)})\n"
        f"         • Volume 1H                  : +{int(vol_pts*100)}%"
        f"  ({_vol_ratio(ta_1h.volume, ta_1h.volume_ma, 1.5)})\n"
        f"         • MACD 4H [{macd_tag}]       : +{int(macd_pts*100)}%"
        f"  (hist={_v(ta_4h.macd_hist,6)} prev={_v(ta_4h.macd_hist_prev,6)})"
    )


# ==============================================================================
# CONTEXT ADJUSTMENT
# ==============================================================================

def _apply_context_adjustment(score: float, context: Optional[MarketContext],
                               pair: str, mode: MarketMode) -> float:
    if context is None:
        return score

    cfg = CONTEXT_CONFIG
    adjusted = score
    notes = []

    if context.fear_greed_value <= cfg.extreme_fear_threshold:
        adjusted = min(1.0, adjusted + cfg.score_bonus_extreme_fear)
        notes.append(
            f"F&G={context.fear_greed_value} Extreme Fear "
            f"→ +{int(cfg.score_bonus_extreme_fear*100)}% (contrarian bonus)"
        )
    elif context.fear_greed_value >= cfg.extreme_greed_threshold:
        if mode != MarketMode.BEAR:
            adjusted = max(0.0, adjusted - cfg.score_penalty_extreme_greed)
            notes.append(
                f"F&G={context.fear_greed_value} Extreme Greed "
                f"→ -{int(cfg.score_penalty_extreme_greed*100)}% (risk penalty)"
            )

    if mode == MarketMode.BULL:
        altcoins = {"eth_idr", "sol_idr", "ada_idr", "doge_idr", "xrp_idr"}
        if pair in altcoins and context.btc_dominance_pct > 60.0:
            adjusted *= 0.85
            notes.append(
                f"BTC Dom={context.btc_dominance_pct:.1f}% >60% "
                f"→ ×0.85 penalti altcoin"
            )

    if notes:
        logger.info(
            f"[{pair}] Context adj: {int(score*100)}% → {int(adjusted*100)}% │ "
            + " │ ".join(notes)
        )
    return adjusted


# ==============================================================================
# LAYER BUILDERS
# ==============================================================================

def _build_sniper_layers(ta_1h: TAResult, ta_4h: TAResult) -> tuple:
    price_above_ema = ta_4h.ema_slow is not None and ta_4h.close > ta_4h.ema_slow
    macd_rev = ta_4h.is_macd_hist_turning_positive or ta_4h.is_macd_bullish
    if price_above_ema and macd_rev:
        lt = LayerResult(True,  "✅ Trend 4H: Bullish + MACD positif")
    elif price_above_ema:
        lt = LayerResult(True,  "✅ Trend 4H: Harga di atas EMA50")
    elif macd_rev:
        lt = LayerResult(True,  "✅ MACD 4H: Histogram baru positif")
    else:
        lt = LayerResult(False, "❌ Trend 4H: Belum bullish")

    stoch_ok = ta_1h.is_stochrsi_oversold
    bb_ok    = ta_1h.is_price_at_lower_bb
    k_str    = _v(ta_1h.stoch_k, 1)
    cross    = " + Cross↑" if ta_1h.is_stochrsi_crossover_up else ""
    if stoch_ok and bb_ok:
        le = LayerResult(True,  f"✅ Entry 1H: StochRSI K={k_str}{cross} | Harga di Lower BB")
    elif stoch_ok:
        le = LayerResult(True,  f"⚠️ Entry 1H: StochRSI K={k_str}{cross} (BB belum tersentuh)")
    else:
        le = LayerResult(False, f"❌ Entry 1H: StochRSI K={k_str} / harga di atas Lower BB")

    if ta_1h.is_volume_surge:
        ratio = ta_1h.volume / ta_1h.volume_ma if ta_1h.volume_ma else 0
        lv = LayerResult(True,  f"✅ Volume: {ratio:.1f}× MA (buyer aktif)")
    else:
        ratio = (ta_1h.volume / ta_1h.volume_ma) if ta_1h.volume_ma and ta_1h.volume_ma > 0 else 0
        lv = LayerResult(False, f"❌ Volume: {ratio:.1f}× MA (perlu ≥1.5×)")

    return lt, le, lv


def _build_breakout_layers(ta_1h: TAResult, ta_4h: TAResult) -> tuple:
    adx_str = _v(ta_4h.adx, 1)
    if ta_4h.is_adx_strong and ta_4h.is_adx_bullish_direction:
        lt = LayerResult(True,  f"✅ ADX 4H: {adx_str} kuat & bullish (+DI>-DI)")
    elif ta_4h.is_adx_strong:
        lt = LayerResult(True,  f"✅ ADX 4H: {adx_str} kuat")
    else:
        lt = LayerResult(False, f"❌ ADX 4H: {adx_str} terlalu lemah (perlu >25)")

    ema_str = "EMA bull✅" if ta_4h.is_ema_bullish else "EMA bear❌"
    if ta_1h.is_price_above_upper_bb:
        le = LayerResult(True,  f"✅ Breakout 1H: Harga tembus Upper BB | 4H: {ema_str}")
    else:
        gap = ""
        if ta_1h.bb_upper:
            pct = ((ta_1h.bb_upper - ta_1h.close) / ta_1h.close) * 100
            gap = f" (jarak +{pct:.1f}%)"
        le = LayerResult(False, f"❌ Breakout 1H: Harga belum tembus Upper BB{gap}")

    if ta_1h.is_volume_surge_breakout:
        ratio = ta_1h.volume / ta_1h.volume_ma if ta_1h.volume_ma else 0
        lv = LayerResult(True,  f"✅ Volume: {ratio:.1f}× MA (breakout terkonfirmasi)")
    elif ta_1h.is_volume_surge:
        ratio = ta_1h.volume / ta_1h.volume_ma if ta_1h.volume_ma else 0
        lv = LayerResult(False, f"⚠️ Volume: {ratio:.1f}× MA (perlu ≥2.0× untuk breakout)")
    else:
        ratio = (ta_1h.volume / ta_1h.volume_ma) if ta_1h.volume_ma and ta_1h.volume_ma > 0 else 0
        lv = LayerResult(False, f"❌ Volume: {ratio:.1f}× MA (perlu ≥2.0×)")

    return lt, le, lv


def _build_bear_bounce_layers(ta_1h: TAResult, ta_4h: TAResult) -> tuple:
    if ta_4h.is_macd_hist_turning_positive:
        lt = LayerResult(True,  "✅ MACD 4H: Histogram baru positif (reversal)")
    elif ta_4h.stoch_k is not None and ta_4h.stoch_k < 20:
        lt = LayerResult(True,  f"✅ 4H StochRSI: K={ta_4h.stoch_k:.0f} oversold")
    else:
        lt = LayerResult(False, "⚠️ 4H: Belum ada konfirmasi reversal")

    k_str = _v(ta_1h.stoch_k, 1)
    cross = " + Cross↑" if ta_1h.is_stochrsi_crossover_up else ""
    if ta_1h.is_stochrsi_oversold:
        le = LayerResult(True,  f"✅ Entry 1H: StochRSI K={k_str}{cross} (oversold)")
    else:
        le = LayerResult(False, f"❌ Entry 1H: StochRSI K={k_str} (belum oversold)")

    if ta_1h.is_volume_surge:
        ratio = ta_1h.volume / ta_1h.volume_ma if ta_1h.volume_ma else 0
        lv = LayerResult(True,  f"✅ Volume: {ratio:.1f}× MA (buyer mulai masuk)")
    else:
        ratio = (ta_1h.volume / ta_1h.volume_ma) if ta_1h.volume_ma and ta_1h.volume_ma > 0 else 0
        lv = LayerResult(False, f"❌ Volume: {ratio:.1f}× MA (perlu ≥1.5×)")

    return lt, le, lv


# ==============================================================================
# STRATEGY EVALUATORS
# ==============================================================================

def _try_sniper(pair: str, ta_1h: TAResult, ta_4h: TAResult,
                context: Optional[MarketContext]) -> Optional[SignalDecision]:
    if not ta_1h.is_stochrsi_oversold and not ta_1h.is_price_at_lower_bb:
        logger.debug(
            f"[{pair}] Sniper skip — "
            f"StochRSI K={_v(ta_1h.stoch_k,1)} (perlu <20) "
            f"& harga tidak di Lower BB"
        )
        return None

    lt, le, lv = _build_sniper_layers(ta_1h, ta_4h)

    if not lt.passed:
        logger.info(f"[{pair}] Sniper: Trend 4H gagal → {lt.reason}")
        return None

    raw   = _calculate_sniper_score(ta_1h, ta_4h)
    adj   = _apply_context_adjustment(raw, context, pair, MarketMode.BULL)
    _log_sniper_breakdown(pair, ta_1h, ta_4h, adj)

    passes = adj >= SCORING_CONFIG.min_score_to_signal
    ls = LayerResult(passes, f"{'✅' if passes else '❌'} Sniper: {int(adj*100)}%")
    if not passes:
        return None

    return SignalDecision(
        pair=pair, should_signal=True, score=adj, score_pct=int(adj*100),
        market_mode=MarketMode.BULL, strategy=SignalStrategy.SNIPER,
        layer_trend=lt, layer_entry=le, layer_volume=lv, layer_scoring=ls,
        ta_1h=ta_1h, ta_4h=ta_4h, context=context,
    )


def _try_breakout(pair: str, ta_1h: TAResult, ta_4h: TAResult,
                  context: Optional[MarketContext]) -> Optional[SignalDecision]:
    if not ta_1h.is_price_above_upper_bb:
        if ta_1h.bb_upper:
            gap = ((ta_1h.bb_upper - ta_1h.close) / ta_1h.close) * 100
            logger.debug(
                f"[{pair}] Breakout skip — "
                f"harga {gap:.2f}% di bawah Upper BB"
            )
        return None

    lt, le, lv = _build_breakout_layers(ta_1h, ta_4h)

    raw   = _calculate_breakout_score(ta_1h, ta_4h)
    adj   = _apply_context_adjustment(raw, context, pair, MarketMode.BULL)
    _log_breakout_breakdown(pair, ta_1h, ta_4h, adj)

    passes = adj >= BREAKOUT_CONFIG.min_score_to_signal
    ls = LayerResult(passes, f"{'✅' if passes else '❌'} Breakout: {int(adj*100)}%")
    if not passes:
        return None

    return SignalDecision(
        pair=pair, should_signal=True, score=adj, score_pct=int(adj*100),
        market_mode=MarketMode.BULL, strategy=SignalStrategy.BREAKOUT,
        layer_trend=lt, layer_entry=le, layer_volume=lv, layer_scoring=ls,
        ta_1h=ta_1h, ta_4h=ta_4h, context=context,
    )


def _try_bear_bounce(pair: str, ta_1h: TAResult, ta_4h: TAResult,
                     context: Optional[MarketContext]) -> Optional[SignalDecision]:
    if not ta_1h.is_stochrsi_oversold:
        logger.info(
            f"[{pair}] Bear Bounce skip — "
            f"StochRSI 1H K={_v(ta_1h.stoch_k,1)} belum oversold (<20)"
        )
        return None

    lt, le, lv = _build_bear_bounce_layers(ta_1h, ta_4h)

    raw   = _calculate_bear_bounce_score(ta_1h, ta_4h)
    adj   = _apply_context_adjustment(raw, context, pair, MarketMode.BEAR)
    _log_bear_breakdown(pair, ta_1h, ta_4h, adj)

    passes = adj >= SCORING_CONFIG.min_score_to_signal
    ls = LayerResult(passes, f"{'✅' if passes else '❌'} Bear Bounce: {int(adj*100)}%")
    if not passes:
        return None

    return SignalDecision(
        pair=pair, should_signal=True, score=adj, score_pct=int(adj*100),
        market_mode=MarketMode.BEAR, strategy=SignalStrategy.BEAR_BOUNCE,
        layer_trend=lt, layer_entry=le, layer_volume=lv, layer_scoring=ls,
        ta_1h=ta_1h, ta_4h=ta_4h, context=context,
    )


def _make_rejection(pair, ta_1h, ta_4h, context, reason) -> SignalDecision:
    return SignalDecision(
        pair=pair, should_signal=False, score=0.0, score_pct=0,
        ta_1h=ta_1h, ta_4h=ta_4h, context=context,
        rejection_reason=reason,
    )


# ==============================================================================
# MAIN EVALUATOR
# ==============================================================================

def evaluate_signal(
    pair: str,
    ta_1h: Optional[TAResult],
    ta_4h: Optional[TAResult],
    context: Optional[MarketContext] = None,
    ta_1d: Optional[TAResult] = None,
) -> SignalDecision:
    """
    Evaluasi lengkap satu pair dengan logging verbose di setiap tahap.
    """
    SEP = "─" * 60

    if ta_1h is None or ta_4h is None:
        return _make_rejection(pair, ta_1h, ta_4h, context,
                               "Data TA tidak tersedia")

    if _cooldown_mgr.is_on_cooldown(pair):
        remaining = _cooldown_mgr.remaining_minutes(pair)
        logger.info(f"[{pair}] ⏸️  Cooldown aktif — sisa {remaining} menit")
        return _make_rejection(pair, ta_1h, ta_4h, context,
                               f"Cooldown aktif — sisa {remaining} menit")

    logger.info(f"[{pair}] {SEP}")

    # --- Snapshot semua timeframe ---
    if ta_1d is not None:
        _log_ta_snapshot(pair, ta_1d, "1D")
    _log_ta_snapshot(pair, ta_4h, "4H")
    _log_ta_snapshot(pair, ta_1h, "1H")

    # --- Daily Gate ---
    if ta_1d is not None:
        mode = classify_daily_mode(ta_1d)
        if mode == MarketMode.SKIP:
            logger.info(f"[{pair}] ⏭️  Daily Gate: SKIP → bot diam")
            logger.info(f"[{pair}] {SEP}")
            return _make_rejection(pair, ta_1h, ta_4h, context,
                                   _classify_daily_reason(ta_1d, mode))
    else:
        mode = MarketMode.BULL
        logger.debug(f"[{pair}] Daily tidak tersedia → default BULL")

    # --- Evaluasi strategi ---
    if mode == MarketMode.BULL:
        logger.info(f"[{pair}] 🎯 Evaluasi SNIPER...")
        sniper = _try_sniper(pair, ta_1h, ta_4h, context)

        logger.info(f"[{pair}] ⚡ Evaluasi BREAKOUT...")
        breakout = _try_breakout(pair, ta_1h, ta_4h, context)

        candidates = [d for d in [sniper, breakout] if d is not None]

        if candidates:
            best = max(candidates, key=lambda d: d.score)
            if len(candidates) == 2:
                other = min(candidates, key=lambda d: d.score)
                logger.info(
                    f"[{pair}] 🏆 Dua strategi lolos — "
                    f"{best.strategy.value}({best.score_pct}%) dipilih "
                    f"vs {other.strategy.value}({other.score_pct}%)"
                )
            logger.info(
                f"[{pair}] 🚨 SINYAL VALID! "
                f"{best.strategy.value} | {best.score_pct}%"
            )
            logger.info(f"[{pair}] {SEP}")
            return best

        sniper_raw   = _calculate_sniper_score(ta_1h, ta_4h)
        breakout_raw = _calculate_breakout_score(ta_1h, ta_4h)
        logger.info(
            f"[{pair}] ❌ Tidak ada strategi lolos 80%\n"
            f"         Sniper: {int(sniper_raw*100)}% | "
            f"Breakout: {int(breakout_raw*100)}%"
        )
        logger.info(f"[{pair}] {SEP}")
        return _make_rejection(
            pair, ta_1h, ta_4h, context,
            f"Skor terbaik {int(max(sniper_raw, breakout_raw)*100)}% "
            f"(Sniper:{int(sniper_raw*100)}% | Breakout:{int(breakout_raw*100)}%)"
        )

    else:  # BEAR
        logger.info(f"[{pair}] ⚠️  Evaluasi BEAR BOUNCE...")
        bear = _try_bear_bounce(pair, ta_1h, ta_4h, context)

        if bear is not None:
            logger.info(
                f"[{pair}] 🚨 SINYAL BEAR BOUNCE! {bear.score_pct}% "
                f"⚠️ Ukuran posisi ketat"
            )
            logger.info(f"[{pair}] {SEP}")
            return bear

        bounce_raw = _calculate_bear_bounce_score(ta_1h, ta_4h)
        logger.info(
            f"[{pair}] ❌ Bear Bounce tidak lolos — skor {int(bounce_raw*100)}%"
        )
        logger.info(f"[{pair}] {SEP}")
        return _make_rejection(
            pair, ta_1h, ta_4h, context,
            f"Bear Bounce {int(bounce_raw*100)}% — belum cukup kuat"
        )


# ==============================================================================
# 15m ENTRY CONFIRMATION (Lazy Fetch Gate)
# ==============================================================================

def confirm_entry_15m(ta_15m: 'TAResult') -> bool:
    """
    Konfirmasi entry timing menggunakan timeframe 15m.
    Dipanggil HANYA untuk pair yang sudah lolos scoring 1H (skor >= 65%).

    Logika konfirmasi:
    1. Candle body 15m terakhir tidak terlalu besar (bukan spike candle)
    2. StochRSI 15m belum overbought (tidak kejar harga)

    Args:
        ta_15m: TAResult dari timeframe 15m

    Returns:
        True jika entry timing di 15m masih bagus, False jika sudah telat
    """
    if ta_15m is None:
        logger.warning("confirm_entry_15m: data 15m tidak tersedia, skip konfirmasi")
        return True  # kalau data tidak ada, tidak memblokir sinyal

    # Check 1: Harga tidak sedang spike terlalu jauh (bukan candle raksasa)
    candle_body = abs(ta_15m.close - ta_15m.open)
    # Gunakan ATR sebagai acuan volatilitas normal
    if ta_15m.atr is not None and ta_15m.atr > 0:
        body_to_atr_ratio = candle_body / ta_15m.atr
        if body_to_atr_ratio > 2.0:
            # Candle body > 2x ATR = spike yang tidak wajar, kemungkinan sudah telat
            logger.info(
                f"confirm_entry_15m [{ta_15m.pair}] REJECTED — "
                f"candle body terlalu besar: {candle_body:,.0f} ({body_to_atr_ratio:.1f}x ATR)"
            )
            return False

    # Check 2: StochRSI 15m belum overbought (tidak kejar harga)
    if ta_15m.stoch_k is not None and ta_15m.stoch_k >= 80:
        logger.info(
            f"confirm_entry_15m [{ta_15m.pair}] REJECTED — "
            f"StochRSI 15m sudah overbought: K={ta_15m.stoch_k:.1f}"
        )
        return False

    # Check 3: Pastikan StochRSI tidak sedang turun tajam (bearish divergence di 15m)
    if (ta_15m.stoch_k is not None and ta_15m.stoch_k_prev is not None
            and ta_15m.stoch_k < 50 and ta_15m.stoch_k < ta_15m.stoch_k_prev - 10):
        logger.info(
            f"confirm_entry_15m [{ta_15m.pair}] REJECTED — "
            f"StochRSI 15m sedang turun tajam: K={ta_15m.stoch_k:.1f} (prev={ta_15m.stoch_k_prev:.1f})"
        )
        return False

    logger.info(
        f"confirm_entry_15m [{ta_15m.pair}] PASSED — "
        f"entry timing 15m terkonfirmasi"
    )
    return True


# ==============================================================================
# PUBLIC HELPERS
# ==============================================================================

def confirm_signal_sent(pair: str) -> None:
    _cooldown_mgr.set_cooldown(pair)


def get_cooldown_status() -> Dict[str, int]:
    result = {}
    for pair in _cooldown_mgr._last_signal_at:
        if _cooldown_mgr.is_on_cooldown(pair):
            result[pair] = _cooldown_mgr.remaining_minutes(pair)
    return result