"""
risk_manager.py — ATR-Based Risk Management & Position Sizing

Menerima SignalDecision (dari signal_logic) + WalletBalance (dari indodax_api)
→ menghasilkan TradingPlan siap tampil di Conviction Signal Format.

v1.1 — Parameter risiko kini bergantung pada MarketMode dari SignalDecision:

  MarketMode.BULL  (Sniper / Breakout):
    SL = entry - ATR × 1.5  |  TP = entry + ATR × 2.5  |  RR min 1:2
    Position: 20%–50% saldo IDR  |  Max risk: 2% portfolio

  MarketMode.BEAR  (Bear Bounce):
    SL = entry - ATR × 1.0  |  TP = entry + ATR × 3.0  |  RR min 1:3
    Position: 10%–15% saldo IDR  |  Max risk: 1% portfolio
    (Lebih ketat karena kita melawan tren harian)
"""

import logging
from dataclasses import dataclass
from typing import Optional

from config import BEAR_BOUNCE_CONFIG, RISK_CONFIG
from indodax_api import WalletBalance
from signal_logic import MarketMode, SignalDecision
from ta_processor import TAResult

logger = logging.getLogger(__name__)


# ==============================================================================
# OUTPUT DATA CLASS
# ==============================================================================

@dataclass
class TradingPlan:
    """
    Rencana trading lengkap yang siap ditampilkan di pesan sinyal.
    Semua nilai harga dalam IDR (Rupiah).
    """
    pair: str

    # Harga entry (last price dari candle terkini)
    entry_price: float

    # Stop-Loss & Take-Profit (ATR-based)
    stop_loss: float
    take_profit: float

    # Persentase perubahan dari entry
    sl_pct: float   # Negatif, misal -3.0 berarti -3%
    tp_pct: float   # Positif, misal +7.5 berarti +7.5%

    # Risk/Reward Ratio (TP distance / SL distance)
    risk_reward_ratio: float

    # Position sizing (dalam IDR)
    idr_balance: float       # Saldo IDR tersedia
    position_idr: float      # Jumlah IDR yang direkomendasikan untuk dibeli
    position_pct: float      # Sebagai % dari saldo IDR tersedia
    max_risk_idr: float      # Kerugian maksimum jika SL kena

    # Estimasi jumlah koin yang diterima (position_idr / entry_price)
    estimated_coin: float

    # ATR value yang digunakan (untuk transparency)
    atr_value: float


# ==============================================================================
# PARAMETER RESOLVER
# ==============================================================================

def _get_risk_params(mode: MarketMode) -> dict:
    """
    Mengembalikan parameter risiko yang sesuai untuk mode pasar aktif.

    Ini adalah titik sentral yang memisahkan perilaku bull vs bear bounce.
    Perubahan parameter di masa depan cukup dilakukan di satu tempat ini.
    """
    if mode == MarketMode.BEAR:
        return {
            "max_position_pct": BEAR_BOUNCE_CONFIG.max_position_pct,
            "min_position_pct": BEAR_BOUNCE_CONFIG.min_position_pct,
            "sl_atr_multiplier": BEAR_BOUNCE_CONFIG.sl_atr_multiplier,
            "tp_atr_multiplier": BEAR_BOUNCE_CONFIG.tp_atr_multiplier,
            "min_rr_ratio":      BEAR_BOUNCE_CONFIG.min_rr_ratio,
            "max_risk_pct":      BEAR_BOUNCE_CONFIG.max_risk_pct,
        }
    else:
        # BULL mode: Sniper dan Breakout menggunakan parameter yang sama
        return {
            "max_position_pct": RISK_CONFIG.max_position_pct,
            "min_position_pct": RISK_CONFIG.min_position_pct,
            "sl_atr_multiplier": RISK_CONFIG.sl_atr_multiplier,
            "tp_atr_multiplier": RISK_CONFIG.tp_atr_multiplier,
            "min_rr_ratio":      RISK_CONFIG.min_rr_ratio,
            "max_risk_pct":      RISK_CONFIG.max_risk_pct,
        }


# ==============================================================================
# MAIN CALCULATOR
# ==============================================================================

def calculate_trading_plan(
    decision: SignalDecision,
    balance: WalletBalance,
) -> Optional[TradingPlan]:
    """
    Menghitung trading plan lengkap dari sinyal yang sudah valid.

    Parameter SL/TP/position sizing secara otomatis disesuaikan berdasarkan
    decision.market_mode — Bull Trend menggunakan parameter normal,
    Bear Bounce menggunakan parameter yang lebih konservatif.

    Args:
        decision: SignalDecision dengan should_signal=True dan ta_1h tersedia.
        balance: WalletBalance dari Indodax Private API.

    Returns:
        TradingPlan siap pakai, atau None jika kalkulasi gagal
        (misalnya RR < minimum atau saldo tidak cukup).
    """
    ta: Optional[TAResult] = decision.ta_1h
    if ta is None:
        logger.error(f"[{decision.pair}] TAResult 1H tidak ada di SignalDecision")
        return None

    if ta.atr is None or ta.atr <= 0:
        logger.warning(f"[{decision.pair}] ATR tidak valid: {ta.atr}")
        return None

    # --- Saldo validation ---
    if balance.idr_available < RISK_CONFIG.min_idr_balance:
        logger.warning(
            f"[{decision.pair}] Saldo IDR Rp {balance.idr_available:,.0f} "
            f"di bawah minimum Rp {RISK_CONFIG.min_idr_balance:,.0f}"
        )
        return None

    # --- Ambil parameter sesuai mode ---
    params = _get_risk_params(decision.market_mode)

    mode_label = decision.market_mode.value
    logger.debug(
        f"[{decision.pair}] Mode: {mode_label} | "
        f"SL×{params['sl_atr_multiplier']} TP×{params['tp_atr_multiplier']} "
        f"RR≥1:{params['min_rr_ratio']} | "
        f"Position: {int(params['min_position_pct']*100)}%–{int(params['max_position_pct']*100)}%"
    )

    entry = ta.close
    atr = ta.atr

    # --- SL & TP Calculation (ATR-based, mode-dependent) ---
    stop_loss = entry - (atr * params["sl_atr_multiplier"])
    take_profit = entry + (atr * params["tp_atr_multiplier"])

    sl_distance = entry - stop_loss
    tp_distance = take_profit - entry

    if sl_distance <= 0:
        logger.warning(f"[{decision.pair}] SL distance tidak valid: {sl_distance}")
        return None

    sl_pct = -(sl_distance / entry) * 100
    tp_pct = (tp_distance / entry) * 100
    rr_ratio = tp_distance / sl_distance

    # --- Risk/Reward validation (threshold berbeda per mode) ---
    if rr_ratio < params["min_rr_ratio"]:
        logger.info(
            f"[{decision.pair}] RR {rr_ratio:.2f} di bawah minimum "
            f"{params['min_rr_ratio']} untuk {mode_label} → sinyal diabaikan"
        )
        return None

    # --- Position Sizing ---
    total_portfolio = balance.idr_total
    max_risk_idr = total_portfolio * params["max_risk_pct"]

    sl_pct_decimal = abs(sl_pct) / 100
    if sl_pct_decimal <= 0:
        return None

    # Position = risiko yang bisa ditoleransi / persentase SL
    position_from_risk = max_risk_idr / sl_pct_decimal

    # Batasi antara min%–max% dari saldo IDR yang tersedia (mode-dependent)
    min_position = balance.idr_available * params["min_position_pct"]
    max_position = balance.idr_available * params["max_position_pct"]

    position_idr = max(min_position, min(position_from_risk, max_position))

    # Recalculate actual risk based on final position
    actual_risk_idr = position_idr * sl_pct_decimal
    position_pct = (position_idr / balance.idr_available) * 100

    # Estimasi jumlah koin
    estimated_coin = position_idr / entry if entry > 0 else 0

    plan = TradingPlan(
        pair=decision.pair,
        entry_price=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        sl_pct=sl_pct,
        tp_pct=tp_pct,
        risk_reward_ratio=rr_ratio,
        idr_balance=balance.idr_available,
        position_idr=position_idr,
        position_pct=position_pct,
        max_risk_idr=actual_risk_idr,
        estimated_coin=estimated_coin,
        atr_value=atr,
    )

    logger.info(
        f"[{decision.pair}] Trading Plan ✅ [{mode_label}/{decision.strategy.value}] | "
        f"Entry: {entry:,.0f} | SL: {stop_loss:,.0f} ({sl_pct:.1f}%) | "
        f"TP: {take_profit:,.0f} ({tp_pct:.1f}%) | "
        f"RR: 1:{rr_ratio:.1f} | "
        f"Beli: Rp {position_idr:,.0f} ({position_pct:.0f}%) | "
        f"Risiko: Rp {actual_risk_idr:,.0f}"
    )

    return plan