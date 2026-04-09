"""
telegram_bot.py — Conviction Signal Formatter & Command Handlers

Tiga tanggung jawab utama:
  1. FORMAT: Mengubah SignalDecision + TradingPlan menjadi Conviction Signal Format
     dengan InlineKeyboard [ ✅ Eksekusi ] dan [ ❌ Skip ].
  2. CALLBACK: Handler untuk tombol inline yang memicu position_tracker.
  3. COMMANDS: Async handler untuk /start, /status, /saldo, /history, /posisi.

Menggunakan python-telegram-bot v20+ (asyncio-based).

v1.1 — Tambahan label strategi di header pesan sinyal:
  [🎯 SNIPER]     → Mean-reversion setup
  [⚡ BREAKOUT]  → Momentum breakout setup
  [⚠️ BEAR BOUNCE] → Counter-trend setup dengan peringatan position size kecil

Callback data convention:
  "exec_{pair}_{signal_sl}_{signal_tp}"  → tombol ✅ Eksekusi
  "skip_{pair}"                          → tombol ❌ Skip
  "paper_{pair}_{entry}_{sl}_{tp}_{pos}_{pct}" → tombol 👻 Paper Trade
"""

import logging
import time
from datetime import datetime
from typing import List, Optional

import pytz
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from config import APP_CONFIG, CREDENTIALS, RISK_CONFIG, SCORING_CONFIG
from indodax_api import MarketContext, WalletBalance, fetch_wallet_balance
from risk_manager import TradingPlan
from signal_cache import get_entry, set_entry
from signal_logic import MarketMode, SignalDecision, SignalStrategy, confirm_signal_sent, get_cooldown_status

logger = logging.getLogger(__name__)

WIB = pytz.timezone(APP_CONFIG.timezone)

# In-memory signal history (5 sinyal terakhir untuk command /history)
_signal_history: List[dict] = []
_MAX_HISTORY = 5


# ==============================================================================
# MARKDOWNV2 HELPER (Escape spesial karakter yang dicek Telegram)
# ==============================================================================

def _escape_md2(text: str) -> str:
    """
    Escape karakter khusus untuk ParseMode.MARKDOWN_V2 Telegram.
    Telegram v20+ sangat ketat: harus escape _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    if not text:
        return text
    # Karakter yang perlu di-escape untuk MARKDOWN_V2
    escape_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text

def _score_bar(score_pct: int, length: int = 10) -> str:
    """Render progress bar visual untuk skor sinyal. Contoh: ████████░░ 82%"""
    filled = int((score_pct / 100) * length)
    empty = length - filled
    return f"{'█' * filled}{'░' * empty}  {score_pct}%"


# ==============================================================================
# STRATEGY LABEL RESOLVER
# ==============================================================================

def _get_strategy_label(decision: SignalDecision) -> tuple:
    """
    Mengembalikan (header_label, context_description) berdasarkan strategy.

    Returns:
        Tuple (header_line, description_line) untuk ditampilkan di pesan sinyal.
    """
    if decision.strategy == SignalStrategy.SNIPER:
        return (
            "🎯 SNIPER — Beli Diskon",
            "Harga menyentuh zona support, momentum reversal terdeteksi"
        )
    elif decision.strategy == SignalStrategy.BREAKOUT:
        return (
            "⚡ BREAKOUT — Kejar Momentum",
            "Harga menembus resistance, tren kuat dikonfirmasi ADX"
        )
    else:  # BEAR_BOUNCE
        return (
            "⚠️ BEAR BOUNCE — Counter-Trend",
            "Daily bearish tapi oversold ekstrem — position size KECIL, disiplin SL!"
        )


# ==============================================================================
# CONVICTION SIGNAL FORMATTER
# ==============================================================================

def format_signal_message(
    decision: SignalDecision,
    plan: TradingPlan,
) -> str:
    """
    Menghasilkan pesan sinyal dalam Conviction Signal Format.

    v1.1 — Tambahan:
      - Baris label strategi di header (SNIPER / BREAKOUT / BEAR BOUNCE)
      - Peringatan khusus untuk Bear Bounce (position size kecil)
      - Detail ADX untuk Breakout strategy

    Format dirancang untuk menjawab tiga hambatan eksekusi:
      - "Ragu apakah sinyal valid" → bagian KENAPA SINYAL INI VALID
      - "Takut salah pasang SL/TP" → bagian LANGKAH EKSEKUSI DI INDODAX
      - "Tidak tahu cara hitung lot" → bagian SIZING

    Args:
        decision: SignalDecision dengan should_signal=True.
        plan: TradingPlan dari risk_manager.

    Returns:
        String pesan siap kirim dengan Markdown formatting.
    """
    now_wib = datetime.now(WIB).strftime(APP_CONFIG.datetime_format)
    pair_display = plan.pair.replace("_idr", "/IDR").upper()

    # --- Strategy label ---
    strategy_header, strategy_desc = _get_strategy_label(decision)

    # --- Context line ---
    ctx = decision.context
    sentiment_line = ""
    if ctx:
        emoji = "🩸" if ctx.fear_greed_value <= 25 else ("😤" if ctx.fear_greed_value >= 75 else "🌡")
        sentiment_line = f"\n│ {emoji} Sentimen  : F&G {ctx.fear_greed_value} — {ctx.fear_greed_label}"

    # --- TA detail lines ---
    ta_1h = decision.ta_1h
    ta_4h = decision.ta_4h

    # MACD detail
    macd_detail = ""
    if ta_4h and ta_4h.macd_hist is not None:
        macd_detail = f" (hist: {ta_4h.macd_hist:+.4f})"

    # StochRSI detail
    stoch_detail = ""
    if ta_1h and ta_1h.stoch_k is not None and ta_1h.stoch_d is not None:
        stoch_detail = f"K={ta_1h.stoch_k:.0f} → {ta_1h.stoch_d:.0f}"

    # Volume ratio
    vol_ratio = ""
    if ta_1h and ta_1h.volume_ma and ta_1h.volume_ma > 0:
        ratio = ta_1h.volume / ta_1h.volume_ma
        vol_ratio = f"{ratio:.1f}× rata-rata"

    # ADX detail (hanya untuk Breakout)
    adx_detail = ""
    if decision.strategy == SignalStrategy.BREAKOUT and ta_4h and ta_4h.adx:
        adx_detail = f"\n│ 📊 ADX 4H    : {ta_4h.adx:.1f} (tren kuat ✅)"

    # --- Score bar ---
    bar = _score_bar(decision.score_pct)

    # --- Pair name untuk coin estimate ---
    coin_symbol = plan.pair.replace("_idr", "").upper()

    # --- Peringatan khusus Bear Bounce ---
    bear_warning = ""
    if decision.strategy == SignalStrategy.BEAR_BOUNCE:
        bear_warning = (
            f"\n⚠️ *PERINGATAN BEAR BOUNCE:*\n"
            f"`  Tren harian MASIH BEARISH. Ini adalah counter-trend.`\n"
            f"`  Position size dikecilkan otomatis ({plan.position_pct:.0f}% saldo).`\n"
            f"`  Jika SL kena, JANGAN average down — keluar dan tunggu.`\n\n"
        )

    # --- Langkah eksekusi step-by-step ---
    exec_steps = (
        f"  1️⃣ Buka market *{pair_display}*\n"
        f"  2️⃣ Pilih tab *\"Beli\"* → masukkan nominal: *Rp {plan.position_idr:,.0f}*\n"
        f"  3️⃣ Pasang *Stop\\-Loss Limit* di: *Rp {plan.stop_loss:,.0f}*\n"
        f"  4️⃣ Pasang *Take\\-Profit* di: *Rp {plan.take_profit:,.0f}*\n"
        f"  ⚠️ _Jangan ubah sizing — risiko sudah dihitung ketat_"
    )

    # Bangun pesan lengkap
    msg = (
        f"```\n"
        f"╔══════════════════════════════════════╗\n"
        f"  🚨 SINYAL BUY — {pair_display:<10}  ⚡ {decision.score_pct}%\n"
        f"  {strategy_header}\n"
        f"  {now_wib}\n"
        f"╚══════════════════════════════════════╝\n"
        f"```\n\n"
        f"{bear_warning}"
        f"💡 *KENAPA SINYAL INI VALID?*\n"
        f"```\n"
        f"  {decision.layer_trend.reason}\n"
        f"  {decision.layer_entry.reason}\n"
        f"  {decision.layer_volume.reason}"
        f"{adx_detail}"
        f"{sentiment_line}\n"
        f"  📝 {strategy_desc}\n"
        f"```\n\n"
        f"💰 *TRADING PLAN*\n"
        f"```\n"
        f"  Entry      :  Rp {plan.entry_price:>14,.0f}\n"
        f"  Stop-Loss  :  Rp {plan.stop_loss:>14,.0f}  ({plan.sl_pct:.1f}%)\n"
        f"  Take Profit:  Rp {plan.take_profit:>14,.0f}  (+{plan.tp_pct:.1f}%)\n"
        f"  R/R Ratio  :  1 : {plan.risk_reward_ratio:.1f}  ✅\n"
        f"```\n\n"
        f"💼 *SIZING \\(dari saldo aktualmu\\)*\n"
        f"```\n"
        f"  Saldo IDR    :  Rp {plan.idr_balance:>12,.0f}\n"
        f"  Beli         :  Rp {plan.position_idr:>12,.0f}  ({plan.position_pct:.0f}%)\n"
        f"  Est. coin    :  ≈  {plan.estimated_coin:.6f} {coin_symbol}\n"
        f"  Risiko maks  :  Rp {plan.max_risk_idr:>12,.0f}  ({plan.max_risk_idr/plan.idr_balance*100:.1f}% portfolio)\n"
        f"```\n\n"
        f"🛠 *LANGKAH EKSEKUSI DI INDODAX:*\n"
        f"{exec_steps}\n\n"
        f"`⚡ Skor Sinyal : {bar}`\n"
        f"`🔕 Cooldown   : Pair ini terkunci {APP_CONFIG.signal_cooldown_minutes} menit`"
    )

    return msg


# ==============================================================================
# INLINE KEYBOARD BUILDER
# ==============================================================================

def _build_signal_keyboard(plan: TradingPlan) -> InlineKeyboardMarkup:
    """
    Membuat inline keyboard tiga tombol di bawah pesan sinyal.

    Tombol ke-3 (👻 Paper Trade) memungkinkan simulasi tanpa modal nyata.
    Callback data format:
      exec_{pair}_{sl_int}_{tp_int}
      skip_{pair}
      paper_{pair}_{entry_int}_{sl_int}_{tp_int}_{position_idr_int}_{score_pct}
    """
    exec_data  = f"exec_{plan.pair}_{int(plan.stop_loss)}_{int(plan.take_profit)}"
    skip_data  = f"skip_{plan.pair}"
    paper_data = (
        f"paper_{plan.pair}_{int(plan.entry_price)}_"
        f"{int(plan.stop_loss)}_{int(plan.take_profit)}_"
        f"{int(plan.position_idr)}_{plan.position_pct:.0f}"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Saya Eksekusi / Sudah Beli", callback_data=exec_data)],
        [InlineKeyboardButton("👻 Paper Trade (Simulasi)", callback_data=paper_data)],
        [InlineKeyboardButton("❌ Skip Sinyal Ini", callback_data=skip_data)],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==============================================================================
# SEND FUNCTIONS
# ==============================================================================

async def send_signal(decision: SignalDecision, plan: TradingPlan) -> Optional[int]:
    """
    Kirim pesan sinyal ke Telegram dengan InlineKeyboard dua tombol.

    Returns:
        message_id jika berhasil, None jika gagal.
    """
    try:
        bot = Bot(token=CREDENTIALS.telegram_bot_token)
        message = format_signal_message(decision, plan)
        keyboard = _build_signal_keyboard(plan)

        sent = await bot.send_message(
            chat_id=CREDENTIALS.telegram_chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard,
        )

        _add_to_history(decision, plan)
        # Simpan entry price di cache untuk callback_exec
        set_entry(decision.pair, plan.entry_price)
        logger.info(f"[{decision.pair}] ✅ Sinyal dikirim (msg_id: {sent.message_id})")
        return sent.message_id

    except TelegramError as e:
        logger.error(f"[{decision.pair}] Telegram error: {e}")
    except Exception as e:
        logger.error(f"[{decision.pair}] Unexpected error send_signal: {e}", exc_info=True)

    return None


# MarkdownV2 special characters that must be escaped
_MDV2_ESCAPE_CHARS = r'_[]()~`>#+-=|{}.!'


def escape_md_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2 mode.

    Use this for any dynamic text that might contain special chars.
    Example: "Extreme Fear (50)" → "Extreme Fear \\(50\\)"
    """
    for char in _MDV2_ESCAPE_CHARS:
        text = text.replace(char, f'\\{char}')
    return text


async def send_text(text: str, parse_mode: str = ParseMode.MARKDOWN_V2) -> None:
    """Kirim pesan teks biasa ke Telegram (untuk notifikasi internal)."""
    try:
        bot = Bot(token=CREDENTIALS.telegram_bot_token)
        await bot.send_message(
            chat_id=CREDENTIALS.telegram_chat_id,
            text=text,
            parse_mode=parse_mode,
        )
    except TelegramError as e:
        logger.error(f"Gagal kirim pesan Telegram: {e}")


def _add_to_history(decision: SignalDecision, plan: TradingPlan) -> None:
    """Tambah sinyal ke ring buffer history (maks 5)."""
    _signal_history.append({
        "pair": decision.pair,
        "score_pct": decision.score_pct,
        "strategy": decision.strategy.value,
        "market_mode": decision.market_mode.value,
        "entry": plan.entry_price,
        "sl": plan.stop_loss,
        "tp": plan.take_profit,
        "position_idr": plan.position_idr,
        "sent_at": time.time(),
    })
    if len(_signal_history) > _MAX_HISTORY:
        _signal_history.pop(0)


# ==============================================================================
# TELEGRAM COMMAND HANDLERS
# ==============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk /start"""
    msg = (
        "🤖 *IndoBot Signal \\(IBS\\) v1\\.1*\n\n"
        "Asisten trading kripto untuk Indodax IDR Market\\.\n\n"
        "*Strategi aktif:*\n"
        "  🎯 Sniper — Mean\\-reversion \\(beli diskon\\)\n"
        "  ⚡ Breakout — Momentum \\(kejar tren kuat\\)\n"
        "  ⚠️ Bear Bounce — Counter\\-trend \\(oversold ekstrem\\)\n\n"
        "*Commands yang tersedia:*\n"
        "`/status`  — Status server & scan berikutnya\n"
        "`/saldo`   — Cek saldo IDR aktif\n"
        "`/market`  — Snapshot kondisi TA semua pair\n"
        "`/history` — 5 sinyal terakhir\n"
        "`/posisi`  — Posisi aktif saat ini\n"
        "`/raport`  — Weekly paper trading report\n"
        "`/gate`    — Status Daily Gate semua pair\n\n"
        "_Bot hanya mengirim sinyal\\. Eksekusi tetap manual\\._"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk /status — tampilkan status server dan cooldown state."""
    now_wib = datetime.now(WIB).strftime(APP_CONFIG.datetime_format)
    cooldowns = get_cooldown_status()

    cooldown_str = ""
    if cooldowns:
        cooldown_str = "\n*Pair dalam cooldown:*\n"
        for pair, mins in cooldowns.items():
            cooldown_str += f"  • {pair.upper()}: sisa {mins} menit\n"
    else:
        cooldown_str = "\n_Tidak ada pair dalam cooldown_"

    msg = (
        f"✅ *IBS Status — Online*\n\n"
        f"`Versi    : {APP_CONFIG.app_version}`\n"
        f"`Waktu    : {now_wib}`\n"
        f"`Scan     : setiap {APP_CONFIG.scan_interval_minutes} menit`\n"
        f"`Min skor : {int(SCORING_CONFIG.min_score_to_signal*100)}%`\n"
        f"`Max risk : {int(RISK_CONFIG.max_risk_pct*100)}% per trade (Bull)`\n"
        f"`Bear RR  : 1:3 min, size maks 15%`\n"
        f"{cooldown_str}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk /saldo — fetch dan tampilkan saldo real-time."""
    await update.message.reply_text("⏳ Mengambil data saldo dari Indodax\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    balance: Optional[WalletBalance] = fetch_wallet_balance()
    if balance is None:
        await update.message.reply_text(
            "❌ Gagal mengambil data saldo\\. Cek koneksi atau API key\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    crypto_lines = ""
    if balance.crypto_balances:
        crypto_lines = "\n*Aset kripto:*\n"
        for sym, amt in balance.crypto_balances.items():
            crypto_lines += f"  • {sym.upper()}: {amt:.8f}\n"
    else:
        crypto_lines = "\n_Tidak ada aset kripto yang dipegang_"

    msg = (
        f"💰 *Saldo Dompet Indodax*\n\n"
        f"`IDR Tersedia : Rp {balance.idr_available:>12,.0f}`\n"
        f"`IDR di Order : Rp {balance.idr_on_order:>12,.0f}`\n"
        f"`IDR Total    : Rp {balance.idr_total:>12,.0f}`\n"
        f"{crypto_lines}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk /history — tampilkan 5 sinyal terakhir."""
    if not _signal_history:
        await update.message.reply_text(
            "📭 Belum ada sinyal yang dikirim sejak bot berjalan\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = ["📋 *5 Sinyal Terakhir*\n"]
    for i, rec in enumerate(reversed(_signal_history), 1):
        sent_dt = datetime.fromtimestamp(rec["sent_at"], tz=WIB).strftime("%d/%m %H:%M")
        strategy = _escape_md2(rec.get("strategy", "SNIPER"))
        pair_upper = _escape_md2(rec['pair'].upper())
        lines.append(
            f"*{i}\\. {pair_upper}* \\| {sent_dt} \\| {strategy} \\| Skor: {rec['score_pct']}%\n"
            f"   Entry: {rec['entry']:,.0f} \\| SL: {rec['sl']:,.0f} \\| TP: {rec['tp']:,.0f}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


# ==============================================================================
# CALLBACK QUERY HANDLERS (Tombol Inline Keyboard)
# ==============================================================================

async def callback_exec(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk tombol [ ✅ Saya Eksekusi / Sudah Beli ].

    Parse callback_data → panggil position_tracker.open_position()
    → kirim konfirmasi dengan real trading plan.
    """
    from position_tracker import tracker

    query = update.callback_query
    await query.answer("⏳ Memvalidasi eksekusi...")

    # Parse: "exec_{pair}_{sl_int}_{tp_int}"
    try:
        parts = query.data.split("_")
        pair_parts = parts[1:-2]
        pair = "_".join(pair_parts)
        signal_sl = float(parts[-2])
        signal_tp = float(parts[-1])
        # Ambil entry price dari signal_cache (di-set oleh send_signal setelah kirim ke Telegram)
        signal_entry = get_entry(pair, signal_sl * 1.03)
    except (IndexError, ValueError) as e:
        logger.error(f"Gagal parse callback exec: {query.data} — {e}")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Edit tombol → loading state
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏳ Mencari transaksi di Indodax...", callback_data="noop")
        ]])
    )

    loop = __import__("asyncio").get_event_loop()
    position = await loop.run_in_executor(
        None,
        tracker.open_position,
        pair,
        signal_entry or signal_sl * 1.03,
        signal_sl,
        signal_tp,
        query.message.message_id,
    )

    if position is None:
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Gagal membuka position tracker\\. Cek log server\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Hapus tombol dari pesan sinyal asal
    await query.edit_message_reply_markup(reply_markup=None)

    # Kirim konfirmasi dengan real trading plan
    coin_symbol = pair.replace("_idr", "").upper()
    entry_diff = position.actual_entry_price - position.signal_entry_price

    if entry_diff != 0:
        diff_sign = "+" if entry_diff > 0 else ""
        entry_note = f"(harga asli {diff_sign}Rp {abs(entry_diff):,.0f} dari sinyal)"
    else:
        entry_note = "(sesuai sinyal)"

    if position.actual_coin_amount > 0:
        coin_info = (
            f"`Coin diterima  : {position.actual_coin_amount:.6f} {_escape_md2(coin_symbol)}`\n"
            f"`Total dibayar  : Rp {position.actual_cost_idr:,.0f}`\n"
        )
    else:
        coin_info = "`Coin diterima  : tidak terdeteksi (estimasi)`\n"

    trailing_cfg = __import__('config').TRAILING_CONFIG
    msg = (
        f"✅ *Posisi {_escape_md2(coin_symbol)}/IDR Terkonfirmasi\\!*\n\n"
        f"`Entry asli     : Rp {position.actual_entry_price:,.0f}` {_escape_md2(entry_note)}\n"
        f"{coin_info}"
        f"\n📐 *Real Trading Plan \\(dari harga asli\\):*\n"
        f"`Stop\\-Loss  : Rp {position.stop_loss:,.0f}  ({_escape_md2(f'{position.sl_pct:.1f}%')})`\n"
        f"`Take\\-Profit: Rp {position.take_profit:,.0f}  ({_escape_md2(f'+{position.tp_pct:.1f}%')})`\n"
        f"`R/R Ratio   : 1:{_escape_md2(f'{position.risk_reward:.1f}')}`\n\n"
        f"_🔍 IBS memantau posisi ini setiap "
        f"{APP_CONFIG.scan_interval_minutes} menit\\. "
        f"Trailing stop aktif saat harga naik \\+{trailing_cfg.activation_pct:.0f}%\\._"
    )

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=msg,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info(f"[{pair}] Position tracker aktif via tombol ✅")


async def callback_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk tombol [ ❌ Skip Sinyal Ini ].
    Hapus cooldown pair agar bot bisa kirim sinyal lagi lebih cepat.
    """
    from signal_logic import _cooldown_mgr

    query = update.callback_query
    await query.answer("Skip dicatat.")

    try:
        pair = "_".join(query.data.split("_")[1:])
    except IndexError:
        pair = ""

    await query.edit_message_reply_markup(reply_markup=None)

    if pair:
        _cooldown_mgr._last_signal_at.pop(pair, None)
        pair_display = pair.replace("_idr", "").upper()
        skip_note = f"\n\n_❌ Skip oleh user — cooldown dihapus untuk {pair_display}_"
        try:
            await query.edit_message_text(
                text=query.message.text + skip_note,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception:
            pass
        logger.info(f"[{pair}] Sinyal di-skip, cooldown dihapus")


async def callback_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk tombol loading state (tidak melakukan apa-apa)."""
    await update.callback_query.answer()


async def callback_paper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk tombol Paper Trading — buka simulasi trade."""
    from paper_trader import paper_trader
    
    query = update.callback_query
    await query.answer("⏳ Membuka paper trade simulasi...")

    # Parse: "paper_{pair}_{entry}_{sl}_{tp}_{pos_idr}_{score_pct}"
    try:
        parts = query.data.split("_")
        pair_parts = parts[1:-5]
        pair = "_".join(pair_parts)
        entry = float(parts[-5])
        sl = float(parts[-4])
        tp = float(parts[-3])
        pos_idr = float(parts[-2])
        score_pct = int(parts[-1])
    except (IndexError, ValueError) as e:
        logger.error(f"Gagal parse callback paper: {query.data} — {e}")
        await query.answer("❌ Error parsing paper trade data", show_alert=True)
        return

    # Edit tombol → loading state
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⏳ Membuka simulasi...", callback_data="noop")
        ]])
    )

    loop = __import__("asyncio").get_event_loop()
    try:
        trade_id = await loop.run_in_executor(
            None,
            paper_trader.open_trade,
            pair,
            entry,
            sl,
            tp,
            pos_idr,
            score_pct,
        )
        
        await query.edit_message_reply_markup(reply_markup=None)
        
        coin = pair.replace("_idr", "").upper()
        msg = (
            f"👻 *Paper Trade #{trade_id} Dibuka — {_escape_md2(coin)}/IDR*\n\n"
            f"`Entry    : Rp {entry:,.0f}`\n"
            f"`SL       : Rp {sl:,.0f}`\n"
            f"`TP       : Rp {tp:,.0f}`\n"
            f"`Position : Rp {pos_idr:,.0f}`\n"
            f"`Score    : {score_pct}%`\n\n"
            f"_Monitor posisi simulasi setiap {APP_CONFIG.scan_interval_minutes} menit\\._"
        )
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        
        logger.info(f"[{pair}] 👻 Paper trade #{trade_id} dibuka (Entry: {entry/1000:.0f}k)")
        
    except Exception as e:
        logger.error(f"Gagal buka paper trade: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Gagal membuka simulasi trade\\. Cek log server\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


# ==============================================================================
# COMMAND: /posisi
# ==============================================================================

async def cmd_posisi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk /posisi — tampilkan semua posisi aktif saat ini."""
    from position_tracker import tracker

    open_positions = tracker.get_all_open()

    if not open_positions:
        await update.message.reply_text(
            "📭 Tidak ada posisi aktif saat ini\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    header = f"📊 *{len(open_positions)} Posisi Aktif*\n\n"
    lines = [header]

    for pos in open_positions:
        from indodax_api import fetch_ticker
        current = fetch_ticker(pos.pair)
        pnl_str = ""
        if current:
            pnl_pct = ((current - pos.actual_entry_price) / pos.actual_entry_price) * 100
            emoji = "🟢" if pnl_pct >= 0 else "🔴"
            pnl_str = f"\n   {emoji} PnL saat ini: {pnl_pct:+.2f}%"

        opened_str = datetime.fromtimestamp(pos.opened_at, tz=WIB).strftime("%d/%m %H:%M")
        coin = pos.pair.replace("_idr", "").upper()
        trailing_str = " 🔒 Trailing aktif" if pos.trailing_active else ""

        line = (
            f"*{coin}/IDR* \\| Dibuka: {opened_str}{trailing_str}\n"
            f"   Entry: Rp {pos.actual_entry_price:,.0f}\n"
            f"   SL: Rp {pos.stop_loss:,.0f} \\| TP: Rp {pos.take_profit:,.0f}"
            f"{pnl_str}\n"
        )
        lines.append(line)

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_raport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk /raport — tampilkan weekly paper trading analytics."""
    from paper_trader import paper_trader

    await update.message.reply_text(
        "⏳ Menghitung performa simulasi minggu ini\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    loop = __import__("asyncio").get_event_loop()
    report = await loop.run_in_executor(None, paper_trader.format_weekly_report)

    await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk /gate — tampilkan Daily Gate status semua pair saat ini."""
    from indodax_api import fetch_ohlcv
    from ta_processor import calculate
    from signal_logic import classify_daily_mode
    from config import ASSET_WHITELIST, DAILY_TIMEFRAME
    import asyncio

    await update.message.reply_text(
        "⏳ Mengecek Daily Gate semua pair\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    loop = asyncio.get_event_loop()
    lines = []

    for pair in sorted(ASSET_WHITELIST):
        coin = pair.replace("_idr", "").upper()
        try:
            candles = await loop.run_in_executor(None, fetch_ohlcv, pair, DAILY_TIMEFRAME)
            if not candles:
                lines.append(f"  ⬜ {coin:<5} : NO DATA")
                continue

            ta_1d = calculate(candles, pair, DAILY_TIMEFRAME)
            if ta_1d is None:
                lines.append(f"  ⬜ {coin:<5} : TA GAGAL")
                continue

            mode = classify_daily_mode(ta_1d)

            price_vs_ema = ""
            if ta_1d.ema_slow:
                diff_pct = ((ta_1d.close - ta_1d.ema_slow) / ta_1d.ema_slow) * 100
                price_vs_ema = f"EMA50 {diff_pct:+.1f}%"

            stoch_k = f"StochK={ta_1d.stoch_k:.0f}" if ta_1d.stoch_k is not None else ""

            if mode.value == "BULL_TREND":
                lines.append(f"  🟢 {coin:<5} : BULL    | {price_vs_ema}")
            elif mode.value == "BEAR_BOUNCE":
                lines.append(f"  🟡 {coin:<5} : BOUNCE  | {stoch_k} oversold")
            else:
                bb_gap = ""
                if ta_1d.bb_lower and ta_1d.close > ta_1d.bb_lower:
                    pct = ((ta_1d.close - ta_1d.bb_lower) / ta_1d.close) * 100
                    bb_gap = f" LoBB+{pct:.1f}%"
                lines.append(f"  🔴 {coin:<5} : SKIP    | {price_vs_ema}{bb_gap} {stoch_k}")

        except Exception as e:
            lines.append(f"  ⬜ {coin:<5} : ERROR")
            logger.warning(f"[cmd_gate] {pair}: {e}")

    now_str = datetime.now(WIB).strftime("%d/%m %Y %H:%M WIB")
    bull  = sum(1 for l in lines if "BULL" in l)
    skip  = sum(1 for l in lines if "SKIP" in l)
    bounce = sum(1 for l in lines if "BOUNCE" in l)

    gate_block = "\n".join(lines)
    msg = (
        f"<b>📊 Daily Gate Status</b>\n"
        f"<code>{now_str}</code>\n"
        f"<code>🟢 BULL: {bull}  🟡 BOUNCE: {bounce}  🔴 SKIP: {skip}</code>\n\n"
        f"<code>{gate_block}</code>\n\n"
        f"<i>🟢 sinyal normal | 🟡 counter-trend kecil | 🔴 bot diam</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ==============================================================================
# ALERT FORMATTERS — dipanggil dari main.py
# ==============================================================================

def format_trailing_activated(pair: str, price: float, gain_pct: float, new_sl: float) -> str:
    """Format notifikasi saat trailing stop pertama kali diaktifkan."""
    coin = pair.replace("_idr", "").upper()
    return (
        f"📈 *Trailing Stop Aktif — {coin}/IDR*\n\n"
        f"`Harga saat ini  : Rp {price:,.0f}`\n"
        f"`Kenaikan        : +{gain_pct:.1f}% dari entry`\n"
        f"`SL baru \\(locked\\): Rp {new_sl:,.0f}`\n\n"
        f"_🔒 Profit sudah dikunci\\! SL akan terus mengikuti "
        f"jika harga naik lebih tinggi\\._"
    )


def format_trailing_updated(
    pair: str, price: float, gain_pct: float,
    old_sl: float, new_sl: float, sl_gain_pct: float,
) -> str:
    """Format notifikasi saat SL trailing digeser ke atas."""
    coin = pair.replace("_idr", "").upper()
    return (
        f"🚀 *Trailing SL Digeser — {coin}/IDR*\n\n"
        f"`Harga saat ini  : Rp {price:,.0f}  (+{gain_pct:.1f}%)`\n"
        f"`SL lama         : Rp {old_sl:,.0f}`\n"
        f"`SL baru         : Rp {new_sl:,.0f}  (+{sl_gain_pct:.1f}% dari entry)`\n\n"
        f"_Biarkan profit mengalir\\! SL terus membuntutinya\\._"
    )


def build_application() -> Application:
    """
    Membangun Telegram Application dengan semua handler terdaftar.
    Dipanggil sekali oleh main.py saat startup.
    """
    app = (
        Application.builder()
        .token(CREDENTIALS.telegram_bot_token)
        .build()
    )

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("saldo",   cmd_saldo))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("posisi",  cmd_posisi))
    app.add_handler(CommandHandler("raport",  cmd_raport))
    app.add_handler(CommandHandler("gate",    cmd_gate))

    app.add_handler(CallbackQueryHandler(callback_exec,  pattern=r"^exec_"))
    app.add_handler(CallbackQueryHandler(callback_paper, pattern=r"^paper_"))
    app.add_handler(CallbackQueryHandler(callback_skip,  pattern=r"^skip_"))
    app.add_handler(CallbackQueryHandler(callback_noop,  pattern=r"^noop$"))

    logger.info("✅ Telegram: 6 commands + 4 callback handlers terdaftar")
    return app