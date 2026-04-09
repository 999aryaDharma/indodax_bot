"""
main.py — Orchestrator & APScheduler Entry Point

v1.1 — Logging verbose di setiap step _process_pair:
  - Jumlah candle aktual per timeframe
  - Waktu proses per pair
  - Penjelasan lengkap setiap rejection
  - Counter stats yang akurat (TA counter fix)
"""

import asyncio
import logging
import signal
import sys
import time as _time
from datetime import datetime
from typing import Dict, Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram.constants import ParseMode

from config import APP_CONFIG, ASSET_WHITELIST, DAILY_TIMEFRAME, PRIMARY_TIMEFRAME, TREND_TIMEFRAME
from indodax_api import (
    MarketContext,
    fetch_market_context,
    fetch_ohlcv,
    fetch_wallet_balance,
    is_pair_already_held,
)
from risk_manager import calculate_trading_plan
from signal_logic import confirm_entry_15m, confirm_signal_sent, evaluate_signal
from ta_processor import calculate
from telegram_bot import (
    build_application,
    format_trailing_activated,
    format_trailing_updated,
    send_signal,
    send_text,
)

logger = logging.getLogger(__name__)
WIB = pytz.timezone(APP_CONFIG.timezone)

_market_context: Optional[MarketContext] = None
_scheduler: Optional[AsyncIOScheduler] = None
_start_time: float = 0.0
_signal_entry_cache: dict = {}


# ==============================================================================
# JOB 1 — SCAN MARKET
# ==============================================================================

async def scan_market() -> None:
    """
    Scan semua pair whitelist dan kirim sinyal jika kondisi terpenuhi.
    """
    global _market_context

    scan_start = datetime.now(WIB)
    logger.info(
        f"{'═'*60}\n"
        f"  🔍 SCAN DIMULAI — {len(ASSET_WHITELIST)} pairs | "
        f"{scan_start.strftime('%H:%M:%S WIB')}\n"
        f"{'═'*60}"
    )

    # Log konteks makro saat ini
    if _market_context:
        logger.info(
            f"  🌡  Market Context: "
            f"F&G={_market_context.fear_greed_value} ({_market_context.fear_greed_label}) | "
            f"BTC Dom={_market_context.btc_dominance_pct:.1f}%"
        )
    else:
        logger.info("  🌡  Market Context: Belum tersedia")

    scan_stats = {
        "total_pairs": len(ASSET_WHITELIST),
        "data_fetched": 0,
        "ta_calculated": 0,
        "signal_worthy": 0,
        "already_held": 0,
        "risk_passed": 0,
        "signals_sent": 0,
        "errors": 0,
        "skipped_cooldown": 0,
        "skipped_daily_gate": 0,
        "skipped_score": 0,
    }

    await _monitor_active_positions()

    for pair in sorted(ASSET_WHITELIST):
        try:
            result = await _process_pair(pair)
            if result:
                for k, v in result.items():
                    if k in scan_stats:
                        scan_stats[k] = scan_stats.get(k, 0) + v
        except Exception as e:
            logger.error(f"[{pair}] Unexpected error saat scan: {e}", exc_info=True)
            scan_stats["errors"] += 1

    # Summary akhir scan
    duration = (datetime.now(WIB) - scan_start).total_seconds()
    logger.info(
        f"{'═'*70}\n"
        f"  ✅ SCAN SELESAI ({duration:.1f}s)\n"
        f"  ├─ Fetch OK      : {scan_stats['data_fetched']:2d}/{scan_stats['total_pairs']}\n"
        f"  ├─ TA calculated : {scan_stats['ta_calculated']:2d}\n"
        f"  ├─ Daily gate    : skip {scan_stats['skipped_daily_gate']:2d} | pass {scan_stats['ta_calculated']-scan_stats['skipped_daily_gate']:2d}\n"
        f"  ├─ Score <80%    : {scan_stats['skipped_score']:2d}\n"
        f"  ├─ Signal ready  : {scan_stats['signal_worthy']:2d}\n"
        f"  ├─ Already held  : {scan_stats['already_held']:2d}\n"
        f"  ├─ Risk passed   : {scan_stats['risk_passed']:2d}\n"
        f"  ├─ 📤 Sent       : {scan_stats['signals_sent']:2d}\n"
        f"  ├─ Cooldown skip : {scan_stats['skipped_cooldown']:2d}\n"
        f"  └─ ❌ Errors     : {scan_stats['errors']:2d}\n"
        f"{'═'*70}"
    )


async def _process_pair(pair: str) -> Optional[dict]:
    """
    Proses satu pair dari fetch sampai (potensial) kirim sinyal.
    Log verbose di setiap step — waktu, jumlah candle, nilai aktual.
    """
    from position_tracker import tracker

    stats = {
        "data_fetched": 0, "ta_calculated": 0,
        "signal_worthy": 0, "already_held": 0,
        "risk_passed": 0, "signals_sent": 0,
        "skipped_cooldown": 0, "skipped_daily_gate": 0,
        "skipped_score": 0,
    }

    pair_start = _time.monotonic()

    # Skip pair yang sudah ada posisi aktif
    if tracker.has_open_position(pair):
        logger.info(f"[{pair}] ⏭️  Posisi aktif sedang dimonitor — skip scan sinyal baru")
        return stats

    loop = asyncio.get_event_loop()

    # --- Step 1: Fetch OHLCV ---
    logger.info(f"[{pair}] 📡 Fetching OHLCV (1H + 4H + 1D)...")
    candles_1h = await loop.run_in_executor(None, fetch_ohlcv, pair, PRIMARY_TIMEFRAME)
    candles_4h = await loop.run_in_executor(None, fetch_ohlcv, pair, TREND_TIMEFRAME)
    candles_1d = await loop.run_in_executor(None, fetch_ohlcv, pair, DAILY_TIMEFRAME)

    c1h = len(candles_1h) if candles_1h else 0
    c4h = len(candles_4h) if candles_4h else 0
    c1d = len(candles_1d) if candles_1d else 0

    if not candles_1h or not candles_4h:
        logger.warning(
            f"[{pair}] ❌ Fetch gagal | 1H: {c1h} | 4H: {c4h} | 1D: {c1d}"
        )
        return stats

    stats["data_fetched"] = 1
    logger.info(
        f"[{pair}] ✅ Fetch OK"
        f" | 1H: {c1h:2d} | 4H: {c4h:2d} | 1D: {c1d if c1d else 0:2d}"
    )

    # --- Step 2: Hitung indikator TA ---
    logger.info(f"[{pair}] 📊 Menghitung indikator TA...")
    ta_1h = calculate(candles_1h, pair, PRIMARY_TIMEFRAME)
    ta_4h = calculate(candles_4h, pair, TREND_TIMEFRAME)
    ta_1d = calculate(candles_1d, pair, DAILY_TIMEFRAME) if candles_1d else None

    if ta_1h is None or ta_4h is None:
        logger.warning(
            f"[{pair}] ❌ Kalkulasi TA gagal — "
            f"1H: {'OK' if ta_1h else 'GAGAL'} | "
            f"4H: {'OK' if ta_4h else 'GAGAL'} "
            f"(kemungkinan candle < 60 atau data corrupt)"
        )
        return stats

    stats["ta_calculated"] = 1
    logger.info(
        f"[{pair}] ✅ TA OK | Daily: {'ready' if ta_1d else 'skip'}"
    )

    # --- Step 3: Evaluasi sinyal ---
    decision = evaluate_signal(
        pair=pair,
        ta_1h=ta_1h,
        ta_4h=ta_4h,
        context=_market_context,
        ta_1d=ta_1d,
    )

    if not decision.should_signal:
        reason = decision.rejection_reason

        # Kategorikan rejection untuk summary stats
        if "Cooldown" in reason:
            stats["skipped_cooldown"] = 1
        elif "Daily Gate" in reason or "Bearish" in reason or "bearish" in reason:
            stats["skipped_daily_gate"] = 1
        else:
            stats["skipped_score"] = 1

        pair_elapsed = _time.monotonic() - pair_start
        logger.info(
            f"[{pair}] ⏭️  No signal ({pair_elapsed:.1f}s) — {reason}"
        )
        return stats

    stats["signal_worthy"] = 1
    logger.info(
        f"[{pair}] 🟢 SIGNAL WORTHY! "
        f"Strategi: {decision.strategy.value} | "
        f"Skor: {decision.score_pct}% | "
        f"Mode: {decision.market_mode.value}"
    )

    # --- Step 3b: Konfirmasi entry timing 15m (lazy fetch) ---
    logger.info(f"[{pair}] ⏱️  Fetching 15m candles untuk konfirmasi entry...")
    candles_15m = await loop.run_in_executor(None, fetch_ohlcv, pair, "15m")
    if candles_15m:
        from config import ENTRY_TIMEFRAME
        ta_15m = calculate(candles_15m, pair, ENTRY_TIMEFRAME)
        if not confirm_entry_15m(ta_15m):
            logger.info(f"[{pair}] ⏭️  15m confirmation FAILED — entry timing buruk, sinyal dibatalkan")
            return stats
        logger.info(f"[{pair}] ✅ 15m confirmation PASSED")
    else:
        logger.warning(f"[{pair}] ⚠️  15m data tidak tersedia — skip konfirmasi, lanjut")

    # --- Step 4: Cek apakah pair sudah dipegang di Indodax ---
    logger.info(f"[{pair}] 🔍 Cek posisi di Indodax (trade history V2)...")
    already_held = await loop.run_in_executor(None, is_pair_already_held, pair)
    if already_held:
        stats["already_held"] = 1
        logger.info(f"[{pair}] ⏭️  Sudah hold posisi di Indodax — sinyal tidak dikirim")
        return stats
    logger.info(f"[{pair}] ✅ Tidak ada posisi aktif di Indodax — lanjut ke sizing")

    # --- Step 5: Fetch saldo real-time ---
    logger.info(f"[{pair}] 💰 Fetching saldo wallet...")
    balance = await loop.run_in_executor(None, fetch_wallet_balance)
    if balance is None:
        logger.warning(f"[{pair}] ❌ Gagal fetch saldo wallet — sinyal dibatalkan")
        return stats
    logger.info(
        f"[{pair}] ✅ Saldo | IDR: Rp {balance.idr_available:,.0f} (total: Rp {balance.idr_total:,.0f})"
    )

    # --- Step 6: Kalkulasi trading plan ---
    logger.info(
        f"[{pair}] 📐 Kalkulasi risk plan "
        f"(mode: {decision.market_mode.value})..."
    )
    plan = calculate_trading_plan(decision, balance)
    if plan is None:
        logger.info(
            f"[{pair}] ⏭️  Trading plan gagal — "
            f"kemungkinan: RR < minimum atau saldo IDR < Rp 50.000"
        )
        return stats

    stats["risk_passed"] = 1
    logger.info(
        f"[{pair}] ✅ Trading Plan\n"
        f"  Entry       → Rp {plan.entry_price:>14,.0f}\n"
        f"  SL (stop)   → Rp {plan.stop_loss:>14,.0f} ({plan.sl_pct:+.2f}%)\n"
        f"  TP (profit) → Rp {plan.take_profit:>14,.0f} ({plan.tp_pct:+.2f}%)\n"
        f"  R/R Ratio   → 1:{plan.risk_reward_ratio:.2f}\n"
        f"  Position    → Rp {plan.position_idr:>14,.0f} ({plan.position_pct:.1f}% saldo)\n"
        f"  Estimasi    → {plan.estimated_coin:.6f} coin\n"
        f"  Max Loss    → Rp {plan.max_risk_idr:>14,.0f} ({plan.max_risk_idr/balance.idr_total*100:.2f}% portfolio)\n"
        f"  ATR (1h)    → {plan.atr_value:,.0f}"
    )

    # --- Step 7: Kirim sinyal ke Telegram ---
    logger.info(f"[{pair}] 📤 Mengirim sinyal ke Telegram...")
    message_id = await send_signal(decision, plan)
    if message_id:
        stats["signals_sent"] = 1
        confirm_signal_sent(pair)
        _signal_entry_cache[pair] = plan.entry_price

        pair_elapsed = _time.monotonic() - pair_start
        logger.info(
            f"[{pair}] 🎉 SINYAL TERKIRIM! "
            f"msg_id={message_id} | "
            f"Total waktu proses: {pair_elapsed:.1f}s"
        )
    else:
        logger.error(f"[{pair}] ❌ Gagal kirim ke Telegram (cek token/chat_id)")

    return stats


# ==============================================================================
# MONITOR POSISI AKTIF
# ==============================================================================

async def _monitor_active_positions() -> None:
    """Fase C & D: Cek semua posisi aktif (real + paper) terhadap harga terkini."""
    from position_tracker import tracker
    from paper_trader import paper_trader

    loop = asyncio.get_event_loop()

    events = await loop.run_in_executor(None, tracker.monitor_all)
    for event in events:
        pair     = event["pair"]
        price    = event["price"]
        position = event["position"]
        coin     = pair.replace("_idr", "").upper()

        if event["type"] == "TP_HIT":
            msg = (
                f"🎯 *TAKE PROFIT TERCAPAI — {coin}/IDR!*\n\n"
                f"<code>Harga saat ini : Rp {price:,.0f}</code>\n"
                f"<code>Target TP      : Rp {position.take_profit:,.0f}</code>\n"
                f"<code>Entry asli     : Rp {position.actual_entry_price:,.0f}</code>\n\n"
                f"*➡️ Segera jual {coin} di aplikasi Indodax!*\n"
                f"_Bot akan menghitung PnL setelah transaksi jual terdeteksi._"
            )
            await send_text(msg, parse_mode=ParseMode.HTML)
            await _try_close_position(pair, "TP")

        elif event["type"] == "SL_HIT":
            reason_display = "TRAILING SL" if event.get("reason") == "TRAILING_SL" else "STOP LOSS"
            msg = (
                f"🛡️ *{reason_display} TERSENTUH — {coin}/IDR!*\n\n"
                f"<code>Harga saat ini : Rp {price:,.0f}</code>\n"
                f"<code>Batas SL       : Rp {position.stop_loss:,.0f}</code>\n"
                f"<code>Entry asli     : Rp {position.actual_entry_price:,.0f}</code>\n\n"
                f"*⚠️ Segera cut-loss {coin} di Indodax!*"
            )
            await send_text(msg, parse_mode=ParseMode.HTML)
            await _try_close_position(pair, event.get("reason", "SL"))

        elif event["type"] == "TRAILING_ACTIVATED":
            msg = format_trailing_activated(pair, price, event["gain_pct"], event["new_sl"])
            await send_text(msg)

        elif event["type"] == "TRAILING_UPDATED":
            msg = format_trailing_updated(
                pair, price, event["gain_pct"],
                event["old_sl"], event["new_sl"], event["sl_gain_pct"]
            )
            await send_text(msg)

    paper_events = await loop.run_in_executor(None, paper_trader.monitor_all)
    for event in paper_events:
        trade = event["trade"]
        price = event["price"]
        coin  = trade.pair.replace("_idr", "").upper()
        pnl_sign = "+" if trade.pnl_idr >= 0 else ""

        if event["type"] == "PAPER_TP":
            await send_text(
                f"👻 *[SIMULASI] TP Tercapai — {coin}/IDR*\n"
                f"<code>PnL: {pnl_sign}Rp {trade.pnl_idr:,.0f} ({pnl_sign}{trade.pnl_pct:.2f}%)</code>",
                parse_mode=ParseMode.HTML
            )
        elif event["type"] == "PAPER_SL":
            await send_text(
                f"👻 *[SIMULASI] SL Tersentuh — {coin}/IDR*\n"
                f"<code>PnL: Rp {trade.pnl_idr:,.0f} ({trade.pnl_pct:.2f}%)</code>",
                parse_mode=ParseMode.HTML
            )


async def _try_close_position(pair: str, reason: str) -> None:
    from position_tracker import tracker

    await asyncio.sleep(120)  # Tunggu user eksekusi manual

    loop = asyncio.get_event_loop()
    closed = await loop.run_in_executor(None, tracker.close_position, pair, reason)

    if closed and closed.pnl_idr is not None:
        coin = pair.replace("_idr", "").upper()
        pnl_emoji = "🟢" if closed.pnl_idr >= 0 else "🔴"
        pnl_sign  = "+" if closed.pnl_idr >= 0 else ""

        loop = asyncio.get_event_loop()
        balance = await loop.run_in_executor(None, fetch_wallet_balance)
        saldo_str = (
            f"<code>Saldo IDR : Rp {balance.idr_available:,.0f}</code>\n"
            if balance else ""
        )

        msg = (
            f"{pnl_emoji} *Posisi {coin}/IDR Ditutup ({reason})*\n\n"
            f"<code>Entry  : Rp {closed.actual_entry_price:,.0f}</code>\n"
            f"<code>Close  : Rp {closed.close_price:,.0f}</code>\n"
            f"<code>PnL    : {pnl_sign}Rp {closed.pnl_idr:,.0f} "
            f"({pnl_sign}{closed.pnl_pct:.2f}%)</code>\n\n"
            f"{saldo_str}"
            f"_Posisi dihapus dari tracker._"
        )
        await send_text(msg, parse_mode=ParseMode.HTML)
        logger.info(
            f"[{pair}] PnL report: {closed.pnl_idr:+,.0f} IDR "
            f"({closed.pnl_pct:+.2f}%)"
        )


# ==============================================================================
# JOB 2 — FETCH CONTEXT
# ==============================================================================

async def fetch_context() -> None:
    global _market_context
    loop = asyncio.get_event_loop()

    try:
        ctx = await loop.run_in_executor(None, fetch_market_context)
        if ctx is not None:
            _market_context = ctx
            logger.info(
                f"🌡  Context updated — "
                f"F&G: {ctx.fear_greed_value} ({ctx.fear_greed_label}) | "
                f"BTC Dom: {ctx.btc_dominance_pct:.1f}%"
            )
    except Exception as e:
        logger.error(f"Error saat fetch context: {e}", exc_info=True)


# ==============================================================================
# JOB 3 — WEEKLY PAPER REPORT
# ==============================================================================

async def _send_weekly_report() -> None:
    from paper_trader import paper_trader

    logger.info("📊 Generating weekly paper trading report...")
    loop = asyncio.get_event_loop()

    try:
        report = await loop.run_in_executor(None, paper_trader.format_weekly_report)
        await send_text(report)
        logger.info("✅ Weekly report dikirim ke Telegram")
    except Exception as e:
        logger.error(f"Gagal kirim weekly report: {e}", exc_info=True)


# ==============================================================================
# JOB 4 — HEALTH CHECK
# ==============================================================================

async def health_check() -> None:
    """
    Health check diperkaya — dikirim setiap 6 jam.

    Berisi:
      - Uptime & konteks makro
      - Status Daily Gate per pair (BULL / BEAR / SKIP + alasan)
      - Posisi aktif (real + paper)
      - Sinyal terakhir yang dikirim
      - Pair yang sedang cooldown
    """
    import time
    from position_tracker import tracker
    from signal_logic import get_cooldown_status, classify_daily_mode
    from telegram_bot import _signal_history

    uptime_hours = (time.time() - _start_time) / 3600
    now_str = datetime.now(WIB).strftime(APP_CONFIG.datetime_format)

    # --- 1. Konteks makro ---
    if _market_context:
        fg = _market_context.fear_greed_value
        fg_label = _market_context.fear_greed_label
        btc_dom = _market_context.btc_dominance_pct
        fg_emoji = "🩸" if fg <= 25 else ("😨" if fg <= 49 else ("😤" if fg >= 75 else "😐"))
        ctx_line = f"{fg_emoji} F&G: {fg} ({fg_label}) | BTC Dom: {btc_dom:.1f}%"
    else:
        ctx_line = "⚠️ Context tidak tersedia"

    # --- 2. Daily Gate status per pair ---
    loop = asyncio.get_event_loop()
    gate_lines = []

    for pair in sorted(ASSET_WHITELIST):
        coin = pair.replace("_idr", "").upper()
        try:
            candles_1d = await loop.run_in_executor(None, fetch_ohlcv, pair, DAILY_TIMEFRAME)
            if not candles_1d:
                gate_lines.append(f"  ⬜ {coin:<5} : NO DATA")
                continue

            ta_1d = calculate(candles_1d, pair, DAILY_TIMEFRAME)
            if ta_1d is None:
                gate_lines.append(f"  ⬜ {coin:<5} : TA GAGAL")
                continue

            mode = classify_daily_mode(ta_1d)

            price_vs_ema = ""
            if ta_1d.ema_slow:
                diff_pct = ((ta_1d.close - ta_1d.ema_slow) / ta_1d.ema_slow) * 100
                price_vs_ema = f"EMA50 {diff_pct:+.1f}%"

            stoch_k = f"StochK={ta_1d.stoch_k:.0f}" if ta_1d.stoch_k is not None else ""

            if mode.value == "BULL_TREND":
                gate_lines.append(f"  🟢 {coin:<5} : BULL    | {price_vs_ema}")
            elif mode.value == "BEAR_BOUNCE":
                gate_lines.append(f"  🟡 {coin:<5} : BOUNCE  | {stoch_k} oversold")
            else:  # SKIP
                bb_gap = ""
                if ta_1d.bb_lower and ta_1d.close > ta_1d.bb_lower:
                    pct = ((ta_1d.close - ta_1d.bb_lower) / ta_1d.close) * 100
                    bb_gap = f" LoBB+{pct:.1f}%"
                gate_lines.append(f"  🔴 {coin:<5} : SKIP    | {price_vs_ema}{bb_gap} {stoch_k}")

        except Exception as e:
            logger.warning(f"[health_check] Gagal cek gate {pair}: {e}")
            gate_lines.append(f"  ⬜ {coin:<5} : ERROR")

    gate_block = "\n".join(gate_lines)

    # --- 3. Posisi aktif ---
    open_positions = tracker.get_all_open()
    if open_positions:
        pos_parts = []
        for pos in open_positions:
            coin = pos.pair.replace("_idr", "").upper()
            current = await loop.run_in_executor(
                None, __import__("indodax_api").fetch_ticker, pos.pair)
            if current:
                pnl = ((current - pos.actual_entry_price) / pos.actual_entry_price) * 100
                trail = " 🔒" if pos.trailing_active else ""
                pos_parts.append(f"  • {coin}: {pnl:+.1f}%{trail}")
            else:
                pos_parts.append(f"  • {coin}: (harga N/A)")
        pos_block = "\n".join(pos_parts)
    else:
        pos_block = "  Tidak ada posisi aktif"

    # Paper trading open count
    try:
        import sqlite3 as _sqlite3
        from config import PAPER_CONFIG as _pc
        conn = _sqlite3.connect(_pc.db_path, timeout=5.0)
        paper_open = conn.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE closed = 0"
        ).fetchone()[0]
        conn.close()
        paper_str = f" | Paper open: {paper_open}"
    except Exception:
        paper_str = ""

    # --- 4. Sinyal terakhir ---
    if _signal_history:
        last = _signal_history[-1]
        from datetime import datetime as _dt
        last_dt = _dt.fromtimestamp(last["sent_at"], tz=WIB).strftime("%d/%m %H:%M")
        last_coin = last["pair"].replace("_idr", "").upper()
        last_signal_str = (
            f"  {last_coin} | {last['strategy']} {last['score_pct']}% | {last_dt}"
        )
    else:
        last_signal_str = "  Belum ada sinyal sejak startup"

    # --- 5. Cooldown ---
    cooldowns = get_cooldown_status()
    if cooldowns:
        cd_parts = [
            f"  {p.replace('_idr','').upper()}: {m}m"
            for p, m in cooldowns.items()
        ]
        cooldown_str = "\n".join(cd_parts)
    else:
        cooldown_str = "  Tidak ada"

    # --- Susun pesan final ---
    msg = (
        f"💚 <b>IBS Health Check</b>\n"
        f"<code>{now_str} | Uptime: {uptime_hours:.1f}j</code>\n"
        f"<code>{ctx_line}</code>\n"
        f"\n"
        f"<b>📊 Daily Gate Status:</b>\n"
        f"<code>{gate_block}</code>\n"
        f"\n"
        f"<b>💼 Posisi Real{paper_str}:</b>\n"
        f"<code>{pos_block}</code>\n"
        f"\n"
        f"<b>📤 Sinyal Terakhir:</b>\n"
        f"<code>{last_signal_str}</code>\n"
        f"\n"
        f"<b>⏸️ Cooldown Aktif:</b>\n"
        f"<code>{cooldown_str}</code>"
    )

    await send_text(msg, parse_mode=ParseMode.HTML)
    logger.info(
        f"Health check dikirim — uptime {uptime_hours:.1f}j | "
        f"Gate: {sum(1 for l in gate_lines if 'BULL' in l)}B "
        f"{sum(1 for l in gate_lines if 'BOUNCE' in l)}Bo "
        f"{sum(1 for l in gate_lines if 'SKIP' in l)}S"
    )


# ==============================================================================
# STARTUP HEALTH CHECK
# ==============================================================================

async def _startup_check() -> bool:
    logger.info("🚀 Menjalankan startup health check...")
    all_ok = True

    try:
        from telegram import Bot
        bot = Bot(token=__import__("config").CREDENTIALS.telegram_bot_token)
        me = await bot.get_me()
        logger.info(f"✅ Telegram OK — Bot: @{me.username}")
    except Exception as e:
        logger.critical(f"❌ Telegram gagal: {e}")
        all_ok = False

    try:
        loop = asyncio.get_event_loop()
        candles = await loop.run_in_executor(None, fetch_ohlcv, "btc_idr", "1h")
        if candles:
            logger.info(f"✅ Indodax Public API OK — {len(candles)} candles BTC/1H")
        else:
            logger.warning("⚠️  Indodax Public API: response kosong")
    except Exception as e:
        logger.error(f"❌ Indodax Public API error: {e}")
        all_ok = False

    try:
        loop = asyncio.get_event_loop()
        balance = await loop.run_in_executor(None, fetch_wallet_balance)
        if balance:
            logger.info(
                f"✅ Indodax Private API OK — "
                f"IDR: Rp {balance.idr_available:,.0f}"
            )
        else:
            logger.warning("⚠️  Indodax Private API: response None")
    except Exception as e:
        logger.error(f"❌ Indodax Private API error: {e}")

    return all_ok


# ==============================================================================
# GRACEFUL SHUTDOWN
# ==============================================================================

def _handle_shutdown(sig_num: int, frame) -> None:
    sig_name = signal.Signals(sig_num).name
    logger.info(f"📛 Sinyal {sig_name} — graceful shutdown...")
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    sys.exit(0)


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

async def main() -> None:
    global _scheduler, _start_time
    import time
    _start_time = time.time()

    logger.info("=" * 60)
    logger.info(f"  {APP_CONFIG.app_name} v{APP_CONFIG.app_version} — Starting Up")
    logger.info("=" * 60)

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    ok = await _startup_check()
    if not ok:
        logger.critical("Startup check gagal. Bot dihentikan.")
        sys.exit(1)

    await fetch_context()

    _scheduler = AsyncIOScheduler(timezone=APP_CONFIG.timezone)

    _scheduler.add_job(
        scan_market,
        trigger=IntervalTrigger(minutes=APP_CONFIG.scan_interval_minutes),
        id="scan_market",
        name="Market Scanner",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.add_job(
        fetch_context,
        trigger=IntervalTrigger(hours=APP_CONFIG.context_fetch_interval_hours),
        id="fetch_context",
        name="Context Fetcher",
        replace_existing=True,
    )

    _scheduler.add_job(
        health_check,
        trigger=IntervalTrigger(hours=APP_CONFIG.health_check_interval_hours),
        id="health_check",
        name="Health Check",
        replace_existing=True,
    )

    from apscheduler.triggers.cron import CronTrigger
    from config import PAPER_CONFIG

    _scheduler.add_job(
        _send_weekly_report,
        trigger=CronTrigger(
            day_of_week=PAPER_CONFIG.weekly_report_day,
            hour=PAPER_CONFIG.weekly_report_hour,
            minute=0,
            timezone=APP_CONFIG.timezone,
        ),
        id="weekly_report",
        name="Weekly Paper Report",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"✅ APScheduler aktif — "
        f"Scan: {APP_CONFIG.scan_interval_minutes}m | "
        f"Context: {APP_CONFIG.context_fetch_interval_hours}h | "
        f"Health: {APP_CONFIG.health_check_interval_hours}h | "
        f"Weekly Report: Minggu {PAPER_CONFIG.weekly_report_hour}:00 WIB"
    )

    await send_text(
        f"🟢 *{APP_CONFIG.app_name} v{APP_CONFIG.app_version} Online*\n"
        f"<code>Memantau {len(ASSET_WHITELIST)} pair setiap "
        f"{APP_CONFIG.scan_interval_minutes} menit</code>\n"
        f"<code>Strategi: Sniper | Breakout | Bear Bounce</code>",
        parse_mode=ParseMode.HTML
    )

    tg_app = build_application()
    await tg_app.initialize()
    await tg_app.start()

    logger.info("🤖 Telegram bot polling dimulai — bot siap menerima command")

    async with tg_app:
        await tg_app.updater.start_polling(drop_pending_updates=True)
        try:
            while True:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Keep-alive loop dihentikan")
        finally:
            await tg_app.updater.stop()
            await tg_app.stop()

    if _scheduler and _scheduler.running:
        _scheduler.shutdown()

    logger.info("👋 IBS shutdown selesai")


if __name__ == "__main__":
    asyncio.run(main())