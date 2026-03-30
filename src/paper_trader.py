"""
paper_trader.py — Paper Trading (Ghost Mode) & Win-Rate Analytics

Memungkinkan simulasi trading tanpa modal nyata:
  - Mencatat sinyal seolah-olah dieksekusi
  - Monitor harga vs SL/TP secara paralel dengan real position tracker
  - Kirim Weekly Report setiap Minggu (akurasi, win rate, simulasi profit)

Database: SQLite terpisah dari real positions (logs/paper_trades.db)
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pytz

from config import APP_CONFIG, PAPER_CONFIG
from indodax_api import fetch_ticker

logger = logging.getLogger(__name__)
WIB = pytz.timezone(APP_CONFIG.timezone)


# ==============================================================================
# DATA CLASS
# ==============================================================================

@dataclass
class PaperTrade:
    """Satu record paper trade (simulasi)."""
    id: Optional[int]
    pair: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_idr: float          # Jumlah IDR simulasi yang "dipakai"
    score_pct: int               # Skor sinyal saat masuk

    opened_at: float             # Unix timestamp

    # Diisi saat ditutup
    closed: bool                 = False
    close_price: Optional[float] = None
    close_reason: str            = ""    # "TP", "SL", "EXPIRED"
    closed_at: Optional[float]   = None
    pnl_idr: Optional[float]     = None
    pnl_pct: Optional[float]     = None


# ==============================================================================
# DATABASE
# ==============================================================================

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(PAPER_CONFIG.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    """Inisialisasi tabel paper_trades jika belum ada."""
    try:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                position_idr REAL NOT NULL,
                score_pct INTEGER NOT NULL,
                opened_at REAL NOT NULL,
                closed INTEGER DEFAULT 0,
                close_price REAL,
                close_reason TEXT DEFAULT '',
                closed_at REAL,
                pnl_idr REAL,
                pnl_pct REAL
            )
        """)
        conn.commit()
        conn.close()
        logger.debug("Paper trading DB siap")
    except Exception as e:
        logger.error(f"Gagal init paper trading DB: {e}")


# ==============================================================================
# PAPER TRADER ENGINE
# ==============================================================================

class PaperTrader:
    """Engine untuk paper trading dan analytics."""

    def __init__(self) -> None:
        _init_db()

    # ------------------------------------------------------------------
    # OPEN & CLOSE
    # ------------------------------------------------------------------

    def open_trade(
        self,
        pair: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_idr: float,
        score_pct: int,
    ) -> int:
        """
        Buka paper trade baru. Mengembalikan ID trade.
        Fee sudah diperhitungkan dari position_idr.
        """
        # Kurangi fee dari position simulasi
        effective_idr = position_idr * (1 - PAPER_CONFIG.trading_fee_pct)

        try:
            conn = _get_conn()
            cursor = conn.execute("""
                INSERT INTO paper_trades
                (pair, entry_price, stop_loss, take_profit, position_idr,
                 score_pct, opened_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pair, entry_price, stop_loss, take_profit, effective_idr,
                  score_pct, time.time()))
            trade_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(
                f"[PAPER] [{pair}] Trade #{trade_id} dibuka | "
                f"Entry: {entry_price:,.0f} | SL: {stop_loss:,.0f} | "
                f"TP: {take_profit:,.0f} | Simulasi: Rp {effective_idr:,.0f}"
            )
            return trade_id
        except Exception as e:
            logger.error(f"[PAPER] Gagal buka trade: {e}")
            return -1

    def close_trade(self, trade_id: int, close_price: float, reason: str) -> Optional[PaperTrade]:
        """Tutup paper trade dan hitung PnL simulasi."""
        try:
            conn = _get_conn()
            row = conn.execute(
                "SELECT * FROM paper_trades WHERE id = ?", (trade_id,)
            ).fetchone()

            if not row or row["closed"]:
                conn.close()
                return None

            entry = row["entry_price"]
            position = row["position_idr"]
            fee = PAPER_CONFIG.trading_fee_pct

            # Revenue setelah fee jual
            revenue = (close_price / entry) * position * (1 - fee)
            pnl_idr = revenue - position
            pnl_pct = (pnl_idr / position) * 100

            conn.execute("""
                UPDATE paper_trades
                SET closed=1, close_price=?, close_reason=?,
                    closed_at=?, pnl_idr=?, pnl_pct=?
                WHERE id=?
            """, (close_price, reason, time.time(), pnl_idr, pnl_pct, trade_id))
            conn.commit()
            conn.close()

            emoji = "🟢" if pnl_idr >= 0 else "🔴"
            logger.info(
                f"[PAPER] Trade #{trade_id} ditutup ({reason}) | "
                f"{emoji} PnL: {pnl_idr:+,.0f} IDR ({pnl_pct:+.2f}%)"
            )

            return PaperTrade(
                id=trade_id,
                pair=row["pair"],
                entry_price=entry,
                stop_loss=row["stop_loss"],
                take_profit=row["take_profit"],
                position_idr=position,
                score_pct=row["score_pct"],
                opened_at=row["opened_at"],
                closed=True,
                close_price=close_price,
                close_reason=reason,
                pnl_idr=pnl_idr,
                pnl_pct=pnl_pct,
            )
        except Exception as e:
            logger.error(f"[PAPER] Gagal tutup trade #{trade_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # MONITOR
    # ------------------------------------------------------------------

    def monitor_all(self) -> List[dict]:
        """
        Cek semua paper trade aktif vs harga terkini.
        Dipanggil setiap scan oleh main.py (sama seperti position_tracker).
        """
        events = []
        try:
            conn = _get_conn()
            rows = conn.execute(
                "SELECT * FROM paper_trades WHERE closed = 0"
            ).fetchall()
            conn.close()

            for row in rows:
                event = self._check_trade(dict(row))
                if event:
                    events.append(event)
        except Exception as e:
            logger.error(f"[PAPER] Monitor error: {e}")
        return events

    def _check_trade(self, row: dict) -> Optional[dict]:
        """Cek satu paper trade terhadap harga terkini."""
        pair = row["pair"]
        current = fetch_ticker(pair)
        if current is None:
            return None

        pnl_pct = ((current - row["entry_price"]) / row["entry_price"]) * 100

        if current >= row["take_profit"]:
            closed = self.close_trade(row["id"], current, "TP")
            if closed:
                return {"type": "PAPER_TP", "trade": closed, "price": current}

        elif current <= row["stop_loss"]:
            closed = self.close_trade(row["id"], current, "SL")
            if closed:
                return {"type": "PAPER_SL", "trade": closed, "price": current}

        return None

    # ------------------------------------------------------------------
    # ANALYTICS ENGINE
    # ------------------------------------------------------------------

    def get_weekly_stats(self) -> dict:
        """
        Hitung statistik performa paper trading untuk 7 hari terakhir.

        Returns dict dengan semua metrik untuk weekly report.
        """
        cutoff = time.time() - (7 * 24 * 3600)

        try:
            conn = _get_conn()
            rows = conn.execute("""
                SELECT * FROM paper_trades
                WHERE opened_at >= ? AND closed = 1
                ORDER BY opened_at ASC
            """, (cutoff,)).fetchall()

            # Total sinyal dikirim (termasuk yang belum ditutup)
            total_signals = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE opened_at >= ?", (cutoff,)
            ).fetchone()[0]

            open_count = conn.execute(
                "SELECT COUNT(*) FROM paper_trades WHERE opened_at >= ? AND closed = 0", (cutoff,)
            ).fetchone()[0]

            conn.close()
        except Exception as e:
            logger.error(f"[PAPER] Gagal hitung weekly stats: {e}")
            return {}

        closed = [dict(r) for r in rows]
        if not closed:
            return {
                "total_signals": total_signals,
                "closed": 0,
                "open": open_count,
                "wins": 0, "losses": 0,
                "win_rate": 0.0,
                "total_pnl_idr": 0.0,
                "avg_pnl_pct": 0.0,
                "best_trade": None,
                "worst_trade": None,
                "by_pair": {},
            }

        wins   = [t for t in closed if t["pnl_idr"] >= 0]
        losses = [t for t in closed if t["pnl_idr"] < 0]
        win_rate = (len(wins) / len(closed)) * 100 if closed else 0
        total_pnl = sum(t["pnl_idr"] for t in closed)
        avg_pnl_pct = sum(t["pnl_pct"] for t in closed) / len(closed)

        best  = max(closed, key=lambda t: t["pnl_idr"])
        worst = min(closed, key=lambda t: t["pnl_idr"])

        # Breakdown per pair
        by_pair: Dict[str, dict] = {}
        for t in closed:
            p = t["pair"]
            if p not in by_pair:
                by_pair[p] = {"count": 0, "wins": 0, "pnl": 0.0}
            by_pair[p]["count"] += 1
            by_pair[p]["pnl"] += t["pnl_idr"]
            if t["pnl_idr"] >= 0:
                by_pair[p]["wins"] += 1

        return {
            "total_signals": total_signals,
            "closed": len(closed),
            "open": open_count,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl_idr": total_pnl,
            "avg_pnl_pct": avg_pnl_pct,
            "best_trade": best,
            "worst_trade": worst,
            "by_pair": by_pair,
        }

    def format_weekly_report(self) -> str:
        """Format weekly report sebagai string Markdown untuk Telegram."""
        stats = self.get_weekly_stats()
        if not stats:
            return "❌ Gagal mengambil data weekly report\\."

        if stats["closed"] == 0:
            return (
                "📊 *Weekly Paper Trading Report*\n\n"
                f"`Periode  : 7 hari terakhir`\n"
                f"`Sinyal   : {stats['total_signals']} dikirim`\n"
                f"`Masih open: {stats['open']} trade`\n\n"
                "_Belum ada trade yang selesai minggu ini\\._"
            )

        week_str = datetime.now(WIB).strftime("%d %b %Y")
        win_emoji = "🟢" if stats["win_rate"] >= 60 else ("🟡" if stats["win_rate"] >= 40 else "🔴")
        pnl_emoji = "🟢" if stats["total_pnl_idr"] >= 0 else "🔴"
        pnl_sign = "+" if stats["total_pnl_idr"] >= 0 else ""

        # Breakdown per pair
        pair_lines = ""
        for pair, data in sorted(stats["by_pair"].items(), key=lambda x: x[1]["pnl"], reverse=True):
            coin = pair.replace("_idr", "").upper()
            pair_pnl_sign = "+" if data["pnl"] >= 0 else ""
            pair_lines += (
                f"  {coin}: {data['wins']}/{data['count']} menang "
                f"| {pair_pnl_sign}Rp {data['pnl']:,.0f}\n"
            )

        best = stats["best_trade"]
        worst = stats["worst_trade"]
        best_str = (
            f"`  🏆 Best  : {best['pair'].upper()} {best['pnl_pct']:+.1f}% "
            f"(+Rp {best['pnl_idr']:,.0f})`"
            if best else ""
        )
        worst_str = (
            f"`  💀 Worst : {worst['pair'].upper()} {worst['pnl_pct']:+.1f}% "
            f"(Rp {worst['pnl_idr']:,.0f})`"
            if worst else ""
        )

        report = (
            f"📊 *Weekly Paper Trading Report*\n"
            f"`{week_str}`\n\n"
            f"```\n"
            f"  Sinyal dikirim  : {stats['total_signals']}\n"
            f"  Trade selesai   : {stats['closed']}\n"
            f"  Masih open      : {stats['open']}\n"
            f"  ─────────────────────────────\n"
            f"  Menang (TP)     : {stats['wins']} trade\n"
            f"  Kalah  (SL)     : {stats['losses']} trade\n"
            f"  Win Rate        : {win_emoji} {stats['win_rate']:.1f}%\n"
            f"  ─────────────────────────────\n"
            f"  Simulasi PnL    : {pnl_emoji} {pnl_sign}Rp {stats['total_pnl_idr']:,.0f}\n"
            f"  Rata-rata/trade : {stats['avg_pnl_pct']:+.2f}%\n"
            f"```\n\n"
            f"*Breakdown per Pair:*\n"
            f"`{pair_lines.strip()}`\n\n"
            f"{best_str}\n"
            f"{worst_str}\n\n"
            f"_Ini adalah simulasi\\. Modal nyata tidak terpengaruh\\._"
        )

        return report


# ==============================================================================
# SINGLETON
# ==============================================================================

paper_trader = PaperTrader()
