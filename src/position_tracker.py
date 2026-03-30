"""
position_tracker.py — Active Position State Manager & PnL Engine

Mengelola siklus hidup lengkap sebuah posisi trading:
  Fase A → Cari harga entry asli dari myTrades API (BUY terbaru)
  Fase B → Kalkulasi ulang SL/TP dari harga asli
  Fase C → Monitor harga aktif setiap scan (deteksi TP/SL tercapai)
  Fase D → Konfirmasi SELL dari myTrades → hitung PnL → tutup posisi

State disimpan di in-memory dict (aman karena APScheduler single-process).
Opsional: persist ke SQLite untuk survive restart server.

Prinsip keamanan:
  - TIDAK ADA eksekusi order. Hanya membaca data dan mengirim alert.
  - Semua aksi beli/jual tetap 100% manual oleh pengguna.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pytz

from config import APP_CONFIG, RISK_CONFIG, TRAILING_CONFIG, LOG_DIR
from indodax_api import TradeRecord, fetch_recent_trades, fetch_ticker

logger = logging.getLogger(__name__)
WIB = pytz.timezone(APP_CONFIG.timezone)

# Jendela waktu untuk mencari transaksi BUY/SELL yang relevan setelah tombol ditekan
TRADE_LOOKUP_WINDOW_SECONDS = 1800  # 30 menit (diperpanjang dari 10 untuk toleransi eksekusi manual)
DB_PATH: str = str(LOG_DIR / "positions.db")


# ==============================================================================
# DATA CLASS
# ==============================================================================

@dataclass
class ActivePosition:
    """
    Representasi satu posisi trading yang sedang terbuka/baru ditutup.
    """
    pair: str
    signal_entry_price: float      # Harga entry dari sinyal (teoretis)
    actual_entry_price: float      # Harga beli asli dari myTrades
    actual_coin_amount: float      # Jumlah koin yang benar-benar dibeli
    actual_cost_idr: float         # Total IDR yang benar-benar dikeluarkan

    stop_loss: float               # SL dihitung dari harga asli
    take_profit: float             # TP dihitung dari harga asli
    sl_pct: float
    tp_pct: float
    risk_reward: float

    opened_at: float               # Unix timestamp saat posisi dikonfirmasi
    telegram_message_id: int       # Message ID sinyal asal (untuk edit/reply)

    # Diisi saat posisi ditutup
    closed: bool                   = False
    close_price: Optional[float]   = None
    close_reason: str              = ""    # "TP", "SL", "MANUAL"
    closed_at: Optional[float]     = None
    pnl_idr: Optional[float]       = None
    pnl_pct: Optional[float]       = None

    # Alert flags (mencegah alert duplikat)
    tp_alert_sent: bool            = False
    sl_alert_sent: bool            = False

    # --- Trailing Stop-Loss State ---
    trailing_active: bool          = False   # Apakah trailing sudah diaktifkan
    highest_price: float           = 0.0     # Harga tertinggi yang pernah dicapai
    trailing_sl: Optional[float]   = None    # SL trailing saat ini (override stop_loss)
    last_trail_update_at: float    = 0.0     # Timestamp update trail terakhir


# ==============================================================================
# DATABASE HELPER (SQLite — optional persistence)
# ==============================================================================

def _init_db() -> None:
    """Buat tabel positions jika belum ada."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging untuk konkurensi
        conn.execute("PRAGMA busy_timeout=5000")  # Tunggu 5s jika DB terkunci
        conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                pair TEXT PRIMARY KEY,
                actual_entry_price REAL,
                actual_coin_amount REAL,
                actual_cost_idr REAL,
                stop_loss REAL,
                take_profit REAL,
                sl_pct REAL,
                tp_pct REAL,
                risk_reward REAL,
                opened_at REAL,
                signal_entry_price REAL,
                telegram_message_id INTEGER,
                closed INTEGER DEFAULT 0,
                close_price REAL,
                close_reason TEXT DEFAULT '',
                closed_at REAL,
                pnl_idr REAL,
                pnl_pct REAL,
                trailing_active INTEGER DEFAULT 0,
                highest_price REAL DEFAULT 0,
                trailing_sl REAL,
                last_trail_update_at REAL DEFAULT 0,
                tp_alert_sent INTEGER DEFAULT 0,
                sl_alert_sent INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        logger.debug("Database positions.db siap (WAL mode aktif)")
    except Exception as e:
        logger.warning(f"Gagal init DB: {e} — pakai in-memory only")


def _save_position(pos: ActivePosition) -> None:
    """Persist posisi ke SQLite dengan semua state termasuk trailing stop."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("""
            INSERT OR REPLACE INTO positions VALUES (
                :pair, :actual_entry_price, :actual_coin_amount, :actual_cost_idr,
                :stop_loss, :take_profit, :sl_pct, :tp_pct, :risk_reward,
                :opened_at, :signal_entry_price, :telegram_message_id,
                :closed, :close_price, :close_reason, :closed_at, :pnl_idr, :pnl_pct,
                :trailing_active, :highest_price, :trailing_sl, :last_trail_update_at,
                :tp_alert_sent, :sl_alert_sent
            )
        """, {
            "pair": pos.pair,
            "actual_entry_price": pos.actual_entry_price,
            "actual_coin_amount": pos.actual_coin_amount,
            "actual_cost_idr": pos.actual_cost_idr,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
            "sl_pct": pos.sl_pct,
            "tp_pct": pos.tp_pct,
            "risk_reward": pos.risk_reward,
            "opened_at": pos.opened_at,
            "signal_entry_price": pos.signal_entry_price,
            "telegram_message_id": pos.telegram_message_id,
            "closed": int(pos.closed),
            "close_price": pos.close_price,
            "close_reason": pos.close_reason,
            "closed_at": pos.closed_at,
            "pnl_idr": pos.pnl_idr,
            "pnl_pct": pos.pnl_pct,
            "trailing_active": int(pos.trailing_active),
            "highest_price": pos.highest_price,
            "trailing_sl": pos.trailing_sl,
            "last_trail_update_at": pos.last_trail_update_at,
            "tp_alert_sent": int(pos.tp_alert_sent),
            "sl_alert_sent": int(pos.sl_alert_sent),
        })
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[{pos.pair}] Gagal simpan ke DB: {e}")


def _load_open_positions() -> Dict[str, ActivePosition]:
    """Load posisi yang belum ditutup dari SQLite saat startup (termasuk trailing state)."""
    positions: Dict[str, ActivePosition] = {}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.execute("PRAGMA busy_timeout=5000")
        rows = conn.execute(
            "SELECT * FROM positions WHERE closed = 0"
        ).fetchall()
        conn.close()
        for row in rows:
            pos = ActivePosition(
                pair=row[0],
                actual_entry_price=row[1],
                actual_coin_amount=row[2],
                actual_cost_idr=row[3],
                stop_loss=row[4],
                take_profit=row[5],
                sl_pct=row[6],
                tp_pct=row[7],
                risk_reward=row[8],
                opened_at=row[9],
                signal_entry_price=row[10],
                telegram_message_id=row[11] or 0,
                trailing_active=bool(row[18]) if len(row) > 18 else False,
                highest_price=row[19] if len(row) > 19 else 0.0,
                trailing_sl=row[20] if len(row) > 20 else None,
                last_trail_update_at=row[21] if len(row) > 21 else 0.0,
                tp_alert_sent=bool(row[22]) if len(row) > 22 else False,
                sl_alert_sent=bool(row[23]) if len(row) > 23 else False,
            )
            positions[pos.pair] = pos
        if positions:
            logger.info(f"📂 {len(positions)} posisi aktif di-load dari database")
            for pair, pos in positions.items():
                if pos.trailing_active:
                    logger.info(
                        f"  ✓ [{pair}] Trailing aktif — SL: {pos.trailing_sl:,.0f} "
                        f"(highest: {pos.highest_price:,.0f})"
                    )
    except Exception as e:
        logger.warning(f"Gagal load posisi dari DB: {e}")
    return positions


# ==============================================================================
# IN-MEMORY STATE
# ==============================================================================

class PositionTracker:
    """
    Singleton manager untuk semua posisi aktif.
    In-memory dict sebagai primary store; SQLite sebagai persistence layer.
    """

    def __init__(self) -> None:
        _init_db()
        # Load posisi yang belum ditutup dari DB saat restart
        self._positions: Dict[str, ActivePosition] = _load_open_positions()

    # ------------------------------------------------------------------
    # FASE A: Open position setelah tombol ✅ ditekan
    # ------------------------------------------------------------------

    def open_position(
        self,
        pair: str,
        signal_entry_price: float,
        signal_sl: float,
        signal_tp: float,
        telegram_message_id: int,
    ) -> Optional[ActivePosition]:
        """
        Fase A: Cari transaksi BUY asli dari myTrades, lalu buka posisi.

        Mencari transaksi BUY dalam 10 menit terakhir. Jika tidak ditemukan,
        menggunakan harga sinyal sebagai fallback dengan peringatan.

        Args:
            pair: Pair ID, e.g. "btc_idr".
            signal_entry_price: Harga entry dari sinyal bot (teoretis).
            signal_sl: Stop-Loss dari trading plan sinyal.
            signal_tp: Take-Profit dari trading plan sinyal.
            telegram_message_id: ID pesan sinyal Telegram untuk reply.

        Returns:
            ActivePosition jika berhasil, None jika gagal total.
        """
        if pair in self._positions and not self._positions[pair].closed:
            logger.warning(f"[{pair}] Posisi sudah aktif, abaikan open baru")
            return self._positions[pair]

        # Cari transaksi BUY asli
        actual_entry, coin_amount, cost_idr = self._find_actual_buy(pair, signal_entry_price)

        # Fase B: Kalkulasi ulang SL/TP dari harga asli
        position = self._calculate_real_plan(
            pair=pair,
            actual_entry=actual_entry,
            coin_amount=coin_amount,
            cost_idr=cost_idr,
            signal_entry=signal_entry_price,
            signal_sl=signal_sl,
            signal_tp=signal_tp,
            message_id=telegram_message_id,
        )

        self._positions[pair] = position
        _save_position(position)

        logger.info(
            f"[{pair}] ✅ Posisi dibuka | "
            f"Entry asli: {actual_entry:,.0f} (sinyal: {signal_entry_price:,.0f}) | "
            f"Coin: {coin_amount:.6f} | "
            f"SL: {position.stop_loss:,.0f} | TP: {position.take_profit:,.0f}"
        )

        return position

    def _find_actual_buy(
        self,
        pair: str,
        signal_price: float,
    ) -> tuple[float, float, float]:
        """
        Cari transaksi BUY dalam window 10 menit terakhir.

        Returns:
            Tuple (entry_price, coin_amount, cost_idr).
            Fallback ke signal_price jika tidak ditemukan.
        """
        trades = fetch_recent_trades(pair, limit=10)
        now = time.time()
        cutoff = now - TRADE_LOOKUP_WINDOW_SECONDS

        # Filter: BUY dalam 10 menit terakhir, urutkan terbaru dulu
        recent_buys = [
            t for t in trades
            if t.trade_type == "buy" and t.timestamp >= cutoff
        ]
        recent_buys.sort(key=lambda t: t.timestamp, reverse=True)

        if recent_buys:
            latest = recent_buys[0]
            cost_idr = latest.price * latest.amount
            logger.info(
                f"[{pair}] Transaksi BUY asli ditemukan: "
                f"Rp {latest.price:,.0f} × {latest.amount:.6f} = Rp {cost_idr:,.0f}"
            )
            return latest.price, latest.amount, cost_idr
        else:
            # Fallback: pakai harga sinyal sebagai estimasi
            # Estimasi jumlah coin dari position_idr yang disarankan (30% saldo)
            logger.warning(
                f"[{pair}] Tidak ada transaksi BUY dalam {TRADE_LOOKUP_WINDOW_SECONDS//60} menit. "
                f"Menggunakan harga sinyal sebagai fallback: {signal_price:,.0f}"
            )
            # Tanpa data asli, kita tidak tahu berapa coin yang dibeli.
            # Gunakan 0 sebagai penanda "tidak diketahui"
            return signal_price, 0.0, 0.0

    def _calculate_real_plan(
        self,
        pair: str,
        actual_entry: float,
        coin_amount: float,
        cost_idr: float,
        signal_entry: float,
        signal_sl: float,
        signal_tp: float,
        message_id: int,
    ) -> ActivePosition:
        """
        Fase B: Hitung ulang SL/TP dari harga entry asli.

        Menggunakan proporsi yang sama dari sinyal original,
        diterapkan ke harga entry yang sebenarnya.
        """
        # Hitung proporsi SL/TP dari sinyal original
        sl_distance_pct = (signal_entry - signal_sl) / signal_entry  # e.g. 0.03 = -3%
        tp_distance_pct = (signal_tp - signal_entry) / signal_entry  # e.g. 0.075 = +7.5%

        # Terapkan ke harga entry asli
        real_sl = actual_entry * (1 - sl_distance_pct)
        real_tp = actual_entry * (1 + tp_distance_pct)
        real_sl_pct = -sl_distance_pct * 100
        real_tp_pct = tp_distance_pct * 100
        rr = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0

        return ActivePosition(
            pair=pair,
            signal_entry_price=signal_entry,
            actual_entry_price=actual_entry,
            actual_coin_amount=coin_amount,
            actual_cost_idr=cost_idr,
            stop_loss=real_sl,
            take_profit=real_tp,
            sl_pct=real_sl_pct,
            tp_pct=real_tp_pct,
            risk_reward=rr,
            opened_at=time.time(),
            telegram_message_id=message_id,
        )

    # ------------------------------------------------------------------
    # FASE C: Monitor posisi aktif
    # ------------------------------------------------------------------

    def monitor_all(self) -> List[dict]:
        """
        Dipanggil oleh scan_market() setiap 5 menit.
        Cek harga terkini untuk semua posisi aktif.

        Returns:
            List event dict yang perlu diproses oleh main.py, contoh:
            [{"type": "TP_HIT", "pair": "btc_idr", "position": ActivePosition}]
        """
        events = []
        open_positions = [p for p in self._positions.values() if not p.closed]

        for pos in open_positions:
            event = self._check_position(pos)
            if event:
                events.append(event)

        return events

    def _check_position(self, pos: ActivePosition) -> Optional[dict]:
        """
        Cek harga terkini vs TP/SL untuk satu posisi.
        Jika trailing aktif, update SL mengikuti harga tertinggi.
        """
        current_price = fetch_ticker(pos.pair)
        if current_price is None:
            logger.debug(f"[{pos.pair}] Skip monitor — gagal fetch ticker")
            return None

        pnl_pct = ((current_price - pos.actual_entry_price) / pos.actual_entry_price) * 100

        # Update highest price
        if current_price > pos.highest_price:
            pos.highest_price = current_price

        # --- Trailing Stop-Loss Logic ---
        trail_event = self._update_trailing(pos, current_price)

        # Tentukan SL yang aktif saat ini
        active_sl = pos.trailing_sl if pos.trailing_active and pos.trailing_sl else pos.stop_loss

        logger.debug(
            f"[{pos.pair}] Monitor | Harga: {current_price:,.0f} | "
            f"PnL: {pnl_pct:+.2f}% | TP: {pos.take_profit:,.0f} | "
            f"SL aktif: {active_sl:,.0f} | Trailing: {pos.trailing_active}"
        )

        # Cek Take Profit
        if current_price >= pos.take_profit and not pos.tp_alert_sent:
            pos.tp_alert_sent = True
            _save_position(pos)
            return {"type": "TP_HIT", "pair": pos.pair, "price": current_price, "position": pos}

        # Cek Stop Loss (trailing atau original)
        if current_price <= active_sl and not pos.sl_alert_sent:
            pos.sl_alert_sent = True
            reason = "TRAILING_SL" if pos.trailing_active else "SL"
            _save_position(pos)
            return {"type": "SL_HIT", "pair": pos.pair, "price": current_price,
                    "position": pos, "reason": reason}

        # Kembalikan trailing event jika SL baru saja diupdate (untuk notifikasi)
        if trail_event:
            _save_position(pos)
            return trail_event

        return None

    def _update_trailing(self, pos: ActivePosition, current_price: float) -> Optional[dict]:
        """
        Update trailing stop-loss berdasarkan harga tertinggi saat ini.

        Returns:
            Event dict jika SL baru saja digeser (untuk notifikasi ke user).
            None jika tidak ada perubahan.
        """
        cfg = TRAILING_CONFIG
        entry = pos.actual_entry_price
        gain_pct = ((current_price - entry) / entry) * 100

        # Cek apakah cukup waktu sejak update terakhir (anti-spam)
        min_interval = cfg.min_update_interval_minutes * 60
        time_since_update = time.time() - pos.last_trail_update_at

        # Aktivasi trailing jika belum aktif dan harga sudah naik cukup
        if not pos.trailing_active and gain_pct >= cfg.activation_pct:
            pos.trailing_active = True
            # SL awal = entry + lock_in_pct (breakeven + buffer kecil)
            initial_trailing_sl = entry * (1 + cfg.lock_in_pct / 100)
            pos.trailing_sl = max(initial_trailing_sl, pos.stop_loss)
            pos.last_trail_update_at = time.time()

            logger.info(
                f"[{pos.pair}] 🔒 Trailing AKTIF! "
                f"Gain: +{gain_pct:.1f}% | SL naik ke {pos.trailing_sl:,.0f} "
                f"(breakeven +{cfg.lock_in_pct}%)"
            )
            return {
                "type": "TRAILING_ACTIVATED",
                "pair": pos.pair,
                "price": current_price,
                "gain_pct": gain_pct,
                "new_sl": pos.trailing_sl,
                "position": pos,
            }

        # Update trailing jika sudah aktif dan interval terpenuhi
        if pos.trailing_active and time_since_update >= min_interval:
            # SL baru = highest_price × (1 - trailing_distance/100)
            candidate_sl = pos.highest_price * (1 - cfg.trailing_distance_pct / 100)

            # SL hanya boleh NAIK, tidak pernah turun (ratchet mechanism)
            if candidate_sl > (pos.trailing_sl or 0):
                old_sl = pos.trailing_sl
                pos.trailing_sl = candidate_sl
                pos.last_trail_update_at = time.time()

                sl_gain_pct = ((pos.trailing_sl - entry) / entry) * 100
                logger.info(
                    f"[{pos.pair}] 📈 Trailing SL digeser: "
                    f"{old_sl:,.0f} → {pos.trailing_sl:,.0f} "
                    f"(+{sl_gain_pct:.1f}% dari entry)"
                )
                return {
                    "type": "TRAILING_UPDATED",
                    "pair": pos.pair,
                    "price": current_price,
                    "gain_pct": gain_pct,
                    "old_sl": old_sl,
                    "new_sl": pos.trailing_sl,
                    "sl_gain_pct": sl_gain_pct,
                    "position": pos,
                }

        return None

    # ------------------------------------------------------------------
    # FASE D: Tutup posisi & hitung PnL
    # ------------------------------------------------------------------

    def close_position(self, pair: str, reason: str = "MANUAL") -> Optional[ActivePosition]:
        """
        Fase D: Konfirmasi penutupan posisi.

        Mencari transaksi SELL terbaru dari myTrades untuk mendapatkan
        harga jual asli. Lalu menghitung PnL final.

        Args:
            pair: Pair yang akan ditutup.
            reason: "TP", "SL", atau "MANUAL".

        Returns:
            ActivePosition yang sudah diupdate dengan data PnL.
        """
        pos = self._positions.get(pair)
        if not pos or pos.closed:
            logger.warning(f"[{pair}] Tidak ada posisi aktif untuk ditutup")
            return None

        # Cari transaksi SELL asli
        close_price = self._find_actual_sell(pair, pos.actual_entry_price)

        # Hitung PnL
        if pos.actual_coin_amount > 0 and close_price:
            revenue_idr = close_price * pos.actual_coin_amount
            pnl_idr = revenue_idr - pos.actual_cost_idr
            pnl_pct = (pnl_idr / pos.actual_cost_idr) * 100 if pos.actual_cost_idr > 0 else 0
        else:
            # Fallback: estimasi dari % perubahan harga
            close_price = close_price or fetch_ticker(pair) or pos.actual_entry_price
            pnl_pct = ((close_price - pos.actual_entry_price) / pos.actual_entry_price) * 100
            pnl_idr = pos.actual_cost_idr * (pnl_pct / 100) if pos.actual_cost_idr > 0 else 0

        pos.closed = True
        pos.close_price = close_price
        pos.close_reason = reason
        pos.closed_at = time.time()
        pos.pnl_idr = pnl_idr
        pos.pnl_pct = pnl_pct

        _save_position(pos)

        emoji = "🟢" if pnl_idr >= 0 else "🔴"
        logger.info(
            f"[{pair}] {emoji} Posisi ditutup ({reason}) | "
            f"Entry: {pos.actual_entry_price:,.0f} → Close: {close_price:,.0f} | "
            f"PnL: {pnl_idr:+,.0f} IDR ({pnl_pct:+.2f}%)"
        )

        return pos

    def _find_actual_sell(self, pair: str, entry_price: float) -> Optional[float]:
        """Cari transaksi SELL dalam 30 menit terakhir."""
        trades = fetch_recent_trades(pair, limit=10)
        now = time.time()
        cutoff = now - TRADE_LOOKUP_WINDOW_SECONDS  # Gunakan window yang sama (30 menit)

        recent_sells = [
            t for t in trades
            if t.trade_type == "sell" and t.timestamp >= cutoff
        ]
        recent_sells.sort(key=lambda t: t.timestamp, reverse=True)

        if recent_sells:
            price = recent_sells[0].price
            logger.info(f"[{pair}] Transaksi SELL asli ditemukan: Rp {price:,.0f}")
            return price

        logger.warning(f"[{pair}] Transaksi SELL tidak ditemukan — estimasi dari ticker")
        return None

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def get_position(self, pair: str) -> Optional[ActivePosition]:
        return self._positions.get(pair)

    def get_all_open(self) -> List[ActivePosition]:
        return [p for p in self._positions.values() if not p.closed]

    def cancel_position(self, pair: str) -> None:
        """Hapus posisi tanpa menghitung PnL (user tekan Skip)."""
        if pair in self._positions:
            del self._positions[pair]
            logger.info(f"[{pair}] Posisi dibatalkan oleh user (Skip)")

    def has_open_position(self, pair: str) -> bool:
        pos = self._positions.get(pair)
        return pos is not None and not pos.closed


# ==============================================================================
# SINGLETON
# ==============================================================================

tracker = PositionTracker()
