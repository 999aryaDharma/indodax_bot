"""
run_shadow_bot.py — CLI Runner for Live Shadow Paper-Trading Engine

Usage:
  python run_shadow_bot.py --scan               # Single real-time scan & dashboard
  python run_shadow_bot.py --watch              # Continuous live monitor (every 60s)
  python run_shadow_bot.py --status             # View portfolio status & trade history
  python run_shadow_bot.py --reset              # Reset paper trading ledger to Rp 500k
"""

import argparse
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).parent / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from indodax_lab.paper.live_shadow_engine import LiveShadowEngine


def run_single_scan(engine: LiveShadowEngine, pairs: list[str]) -> None:
    """Execute one complete live market scan cycle."""
    print(">>> [1/3] Menghubungi Indodax Public API (Live Tickers & 1h Candles)...")
    live_prices, candle_dfs = engine.fetch_live_market_data(pairs)
    if not live_prices:
        print("[ERROR] Gagal mengambil data harga live dari Indodax. Periksa koneksi internet.")
        return

    print(">>> [2/3] Memeriksa posisi terbuka (Stop Loss, Take Profit, Trailing Stops)...")
    exits_triggered = engine.check_open_positions(live_prices, candle_dfs)

    print(">>> [3/3] Menjalankan Sensory Engine, Sinyal Kuantitatif & Otak AI XGBoost...")
    eval_diagnostics = engine.evaluate_market_scan(live_prices, candle_dfs)

    # Render dashboard
    dashboard_text = engine.format_dashboard(live_prices, eval_diagnostics, exits_triggered)
    print("\n" + dashboard_text)


def run_continuous_watch(engine: LiveShadowEngine, pairs: list[str], interval_sec: int) -> None:
    """Run continuous monitoring loop."""
    print(f"=== MEMULAI CONTINUOUS LIVE SHADOW MONITOR (Polling setiap {interval_sec} detik) ===")
    print("Tekan Ctrl+C kapan saja untuk berhenti dengan aman.\n")
    try:
        iteration = 1
        while True:
            print(f"\n[Cycle #{iteration} — {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}]")
            run_single_scan(engine, pairs)
            print(f"\n[Menunggu {interval_sec} detik sebelum scan berikutnya...]")
            time.sleep(interval_sec)
            iteration += 1
    except KeyboardInterrupt:
        print("\n\n[INFO] Monitor dihentikan oleh user. Seluruh state tersimpan aman di logs/shadow_portfolio_state.sqlite3.")


def main():
    parser = argparse.ArgumentParser(description="Indodax Live Shadow Paper-Trading Bot")
    parser.add_argument("--scan", action="store_true", help="Jalankan satu siklus scan live dan tampilkan dashboard")
    parser.add_argument("--watch", action="store_true", help="Jalankan monitor berkala secara kontinu")
    parser.add_argument("--interval", type=int, default=60, help="Interval polling dalam detik untuk mode --watch (default: 60)")
    parser.add_argument("--status", action="store_true", help="Tampilkan status portofolio dan riwayat trade")
    parser.add_argument("--reset", action="store_true", help="Reset saldo paper trading kembali ke Rp 500.000")
    parser.add_argument("--yes", action="store_true", help="Bypass konfirmasi saat reset")

    args = parser.parse_args()
    engine = LiveShadowEngine()
    active_pairs = ["eth_idr", "btc_idr", "sol_idr"]

    if args.reset:
        if not args.yes:
            confirm = input("Apakah Anda yakin ingin me-reset portofolio paper trading ke Rp 500.000? (y/N): ")
            if confirm.lower() != "y":
                print("Reset dibatalkan.")
                return
        engine.reset_portfolio()
        print("✅ Portofolio paper trading berhasil di-reset ke Rp 500.000 IDR.")
        return

    if args.status:
        live_prices, _ = engine.fetch_live_market_data(active_pairs)
        summary = engine.get_portfolio_summary(live_prices)
        print("\n=== STATUS PORTOFOLIO PAPER TRADING ===")
        for k, v in summary.items():
            print(f"  * {k:<25}: {v}")
        if engine.closed_trades:
            print("\n=== RIWAYAT TRADE TERAKHIR ===")
            for t in engine.closed_trades[-5:]:
                print(f"  * {t.pair.upper()} ({t.strategy_id}) | In: Rp {t.entry_price:,.0f} -> Out: Rp {t.exit_price:,.0f} | Net: Rp {t.net_pnl:+,.0f} | {t.exit_reason}")
        return

    if args.watch:
        run_continuous_watch(engine, active_pairs, args.interval)
    else:
        # Default action is single scan
        run_single_scan(engine, active_pairs)


if __name__ == "__main__":
    main()
