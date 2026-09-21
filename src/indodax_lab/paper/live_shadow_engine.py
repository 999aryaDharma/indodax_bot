"""
live_shadow_engine.py — Forward Live Shadow Paper-Trading Engine

Autonomous paper trading engine for Indodax Research Lab:
- Public Indodax live market data ingestion (OHLCV 1h & ticker)
- Multi-asset strategy evaluation (ETH C02, BTC C07, SOL C02)
- M02 XGBoost + Platt Sigmoid probability inference
- Fixed Fractional Risk sizing (1.5% equity, ATR-based lot sizing)
- Exact double-entry Maker accounting (0.1111% buy, 0.3211% sell)
- Trailing ATR stop, time-decay breakeven, Take-Profit management
- Persistent state in logs/shadow_portfolio_state.json
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import xgboost as xgb

logger = logging.getLogger("live_shadow_engine")

# Fee constants (Indodax PRO Maker fees)
MAKER_BUY_FEE_RATE = Decimal("0.001111")   # 0.1111%
MAKER_SELL_FEE_RATE = Decimal("0.003211")  # 0.3211%

FEATURE_COLS = [
    'log_ret_1', 'log_ret_6', 'log_ret_24', 'atr_pct_14',
    'ema_ratio_20_50', 'dist_ema_200', 'bb_z', 'bb_width',
    'rsi_14', 'adx_14', 'vol_z_20'
]


@dataclass
class ShadowPosition:
    position_id: str
    pair: str
    strategy_id: str
    entry_ts: str
    entry_price: float
    qty: float
    cash_debited: float
    buy_fee_paid: float
    stop_loss: float
    take_profit: float
    entry_atr: float
    highest_price: float
    bars_held: int = 0
    time_decay_breakeven: bool = False


@dataclass
class ClosedTrade:
    trade_id: str
    position_id: str
    pair: str
    strategy_id: str
    entry_ts: str
    exit_ts: str
    entry_price: float
    exit_price: float
    qty: float
    cash_debited: float
    cash_credited: float
    buy_fee: float
    sell_fee: float
    gross_pnl: float
    net_pnl: float
    pnl_pct: float
    exit_reason: str
    bars_held: int


class LiveShadowEngine:
    """Manages forward shadow paper trading portfolio and strategy execution."""

    def __init__(
        self,
        state_file: Path = Path("logs/shadow_portfolio_state.json"),
        initial_cash: Decimal = Decimal("500000.00"),
        max_positions: int = 2,
        fixed_risk_pct: float = 0.015,  # 1.5% capital risk
        max_cash_per_trade_pct: float = 0.25,  # 25% max cash allocation
        min_order_idr: Decimal = Decimal("10000.00"),
    ) -> None:
        self.state_file = state_file
        self.initial_cash = initial_cash
        self.max_positions = max_positions
        self.fixed_risk_pct = fixed_risk_pct
        self.max_cash_per_trade_pct = max_cash_per_trade_pct
        self.min_order_idr = min_order_idr

        self.available_cash = initial_cash
        self.open_positions: Dict[str, ShadowPosition] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.audit_log: List[Dict[str, Any]] = []

        # Load models and metadata
        self.models: Dict[str, xgb.Booster] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self._load_models()

        # Load existing state or initialize
        self.load_state()

    def _load_models(self) -> None:
        """Load trained XGBoost boosters and metadata."""
        for p in ["btc", "eth", "sol"]:
            pair_key = f"{p}_idr"
            ubj_path = Path(f"models/artifacts/m02_xgboost_{pair_key}_v2.ubj")
            json_path = Path(f"models/artifacts/m02_xgboost_{pair_key}_v2.json")
            if ubj_path.exists() and json_path.exists():
                booster = xgb.Booster()
                booster.load_model(str(ubj_path))
                self.models[pair_key] = booster
                self.metadata[pair_key] = json.loads(json_path.read_text())

    def load_state(self) -> None:
        """Load portfolio state from JSON file."""
        if not self.state_file.exists():
            self.save_state()
            return

        try:
            data = json.loads(self.state_file.read_text())
            self.available_cash = Decimal(str(data.get("available_cash", self.initial_cash)))
            self.open_positions = {
                pos_id: ShadowPosition(**p_dict)
                for pos_id, p_dict in data.get("open_positions", {}).items()
            }
            self.closed_trades = [
                ClosedTrade(**t_dict) for t_dict in data.get("closed_trades", [])
            ]
            self.audit_log = data.get("audit_log", [])[-50:]  # Keep last 50
        except Exception as e:
            logger.error(f"Failed to load state file: {e}. Keeping current state.")

    def save_state(self) -> None:
        """Persist current state to JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "initial_cash": float(self.initial_cash),
            "available_cash": float(self.available_cash),
            "open_positions": {
                k: asdict(v) for k, v in self.open_positions.items()
            },
            "closed_trades": [asdict(t) for t in self.closed_trades],
            "audit_log": self.audit_log[-50:],
            "last_updated_utc": datetime.now(UTC).isoformat(),
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def reset_portfolio(self) -> None:
        """Reset paper trading portfolio to clean initial state."""
        self.available_cash = self.initial_cash
        self.open_positions = {}
        self.closed_trades = []
        self.audit_log = []
        self.save_state()

    # =========================================================================
    # MARKET DATA FETCHING
    # =========================================================================
    @staticmethod
    def fetch_live_market_data(pairs: List[str]) -> Tuple[Dict[str, float], Dict[str, pd.DataFrame]]:
        """Fetch live ticker and recent 200 1h candles from Indodax public API."""
        tickers = {}
        candle_dfs = {}
        session = requests.Session()

        for pair in pairs:
            # 1. Fetch Ticker
            clean_pair = pair.replace("_", "")
            try:
                t_resp = session.get(f"https://indodax.com/api/ticker/{clean_pair}", timeout=10)
                if t_resp.status_code == 200:
                    t_data = t_resp.json()
                    tickers[pair] = float(t_data["ticker"]["last"])
            except Exception as e:
                logger.warning(f"Failed to fetch ticker for {pair}: {e}")

            # 2. Fetch OHLCV 1h candles
            symbol = pair.replace("_", "").upper()
            now_ts = int(time.time())
            from_ts = now_ts - (200 * 3600)  # 200 hours
            try:
                c_resp = session.get(
                    "https://indodax.com/tradingview/history_v2",
                    params={"symbol": symbol, "tf": "60", "from": from_ts, "to": now_ts},
                    timeout=10,
                )
                if c_resp.status_code == 200:
                    raw_data = c_resp.json()
                    if isinstance(raw_data, list) and len(raw_data) > 0:
                        recs = [{
                            "timestamp": int(c["Time"]),
                            "open": float(c["Open"]),
                            "high": float(c["High"]),
                            "low": float(c["Low"]),
                            "close": float(c["Close"]),
                            "base_volume": float(c["Volume"]),
                        } for c in raw_data]
                        df = pd.DataFrame(recs).sort_values("timestamp").reset_index(drop=True)
                        candle_dfs[pair] = df
            except Exception as e:
                logger.warning(f"Failed to fetch candles for {pair}: {e}")

            time.sleep(0.5)

        return tickers, candle_dfs

    # =========================================================================
    # FEATURE CALCULATION & AI INFERENCE
    # =========================================================================
    @staticmethod
    def compute_features(df: pd.DataFrame) -> pd.DataFrame:
        """Compute technical features on candle DataFrame."""
        high, low, close = df['high'], df['low'], df['close']
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

        df['atr_14'] = tr.rolling(14).mean().fillna(0.0)
        df['ema_200'] = close.ewm(span=200, adjust=False).mean()
        df['ema_20'] = close.ewm(span=20, adjust=False).mean()
        df['ema_50'] = close.ewm(span=50, adjust=False).mean()

        df['log_ret_1'] = np.log(close / close.shift(1)).fillna(0.0)
        df['log_ret_6'] = np.log(close / close.shift(6)).fillna(0.0)
        df['log_ret_24'] = np.log(close / close.shift(24)).fillna(0.0)
        df['atr_pct_14'] = (df['atr_14'] / close).fillna(0.0)

        df['ema_ratio_20_50'] = ((df['ema_20'] / df['ema_50']) - 1.0).fillna(0.0)
        df['dist_ema_200'] = ((close / df['ema_200']) - 1.0).fillna(0.0)

        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std(ddof=1)
        df['bb_z'] = (((close - sma20) / std20)).fillna(0.0)
        df['bb_width'] = (((4 * std20) / sma20)).fillna(0.0)

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        rs = gain.rolling(14).mean() / loss.rolling(14).mean().replace(0, np.nan)
        df['rsi_14'] = (((100 - (100 / (1 + rs))) / 100.0)).fillna(0.5)

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr_14 = tr.rolling(14).sum().replace(0, np.nan)
        plus_di = 100 * pd.Series(plus_dm).rolling(14).sum() / tr_14
        minus_di = 100 * pd.Series(minus_dm).rolling(14).sum() / tr_14
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100).fillna(0.0)
        df['adx_14'] = ((dx.rolling(14).mean() / 100.0)).fillna(0.0)

        vol_mean = df['base_volume'].rolling(20).mean()
        vol_std = df['base_volume'].rolling(20).std(ddof=1)
        df['vol_z_20'] = (((df['base_volume'] - vol_mean) / vol_std)).fillna(0.0)
        return df

    def predict_probability(self, pair: str, features_series: pd.Series) -> float:
        """Standardize features and run Platt-calibrated XGBoost inference."""
        if pair not in self.models or pair not in self.metadata:
            return 0.50

        booster = self.models[pair]
        meta = self.metadata[pair]
        f_means = meta.get("feature_means", {})
        f_stds = meta.get("feature_stds", {})

        scaled_vals = []
        for col in FEATURE_COLS:
            val = float(features_series.get(col, 0.0))
            m = float(f_means.get(col, 0.0))
            s = float(f_stds.get(col, 1.0))
            scaled_vals.append((val - m) / (s if s != 0 else 1.0))

        dmat = xgb.DMatrix(np.array([scaled_vals], dtype=np.float32))
        margin = float(booster.predict(dmat, output_margin=True)[0])

        calib = meta.get("calibration", {})
        a = float(calib.get("a", 1.0))
        b = float(calib.get("b", 0.0))

        prob = 1.0 / (1.0 + math.exp(-(a * margin + b)))
        return prob

    # =========================================================================
    # POSITION MONITORING & EXIT ENGINE
    # =========================================================================
    def check_open_positions(self, live_prices: Dict[str, float]) -> List[ClosedTrade]:
        """Check open positions against live prices for TP, SL, and Trailing Stops."""
        closed_this_cycle = []
        positions_to_delete = []

        now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

        for pos_id, pos in self.open_positions.items():
            curr_px = live_prices.get(pos.pair)
            if curr_px is None:
                continue

            # Update highest price for trailing stop
            pos.highest_price = max(pos.highest_price, curr_px)
            pos.bars_held += 1

            # Trailing stop update (C02 trails 2.0x ATR behind highest price)
            if pos.strategy_id == "C02_EMA_TREND_PULLBACK":
                trailing_sl = pos.highest_price - (2.0 * pos.entry_atr)
                pos.stop_loss = max(pos.stop_loss, trailing_sl)

                # Time-decay breakeven: after 14 bars, if not up 1.0x ATR, move SL to breakeven
                if pos.bars_held >= 14 and pos.highest_price < (pos.entry_price + 1.0 * pos.entry_atr):
                    if not pos.time_decay_breakeven:
                        pos.stop_loss = max(pos.stop_loss, pos.entry_price)
                        pos.time_decay_breakeven = True

            # Exit conditions
            is_tp = curr_px >= pos.take_profit
            is_sl = curr_px <= pos.stop_loss

            if is_tp or is_sl:
                exit_reason = "TAKE_PROFIT" if is_tp else "STOP_LOSS"
                qty_dec = Decimal(str(pos.qty))
                exit_px_dec = Decimal(str(curr_px))
                gross_proceeds = qty_dec * exit_px_dec
                sell_fee = gross_proceeds * MAKER_SELL_FEE_RATE
                net_credit = gross_proceeds - sell_fee

                cash_debited_dec = Decimal(str(pos.cash_debited))
                gross_pnl = float(gross_proceeds - (qty_dec * Decimal(str(pos.entry_price))))
                net_pnl = float(net_credit - cash_debited_dec)
                pnl_pct = (curr_px - pos.entry_price) / pos.entry_price

                # Credit cash back to ledger
                self.available_cash += net_credit

                ct = ClosedTrade(
                    trade_id=f"trade_{int(time.time())}_{pos.pair}",
                    position_id=pos.position_id,
                    pair=pos.pair,
                    strategy_id=pos.strategy_id,
                    entry_ts=pos.entry_ts,
                    exit_ts=now_str,
                    entry_price=pos.entry_price,
                    exit_price=curr_px,
                    qty=pos.qty,
                    cash_debited=pos.cash_debited,
                    cash_credited=float(net_credit),
                    buy_fee=pos.buy_fee_paid,
                    sell_fee=float(sell_fee),
                    gross_pnl=gross_pnl,
                    net_pnl=net_pnl,
                    pnl_pct=pnl_pct,
                    exit_reason=exit_reason,
                    bars_held=pos.bars_held,
                )
                self.closed_trades.append(ct)
                closed_this_cycle.append(ct)
                positions_to_delete.append(pos_id)

        for pid in positions_to_delete:
            del self.open_positions[pid]

        if closed_this_cycle:
            self.save_state()

        return closed_this_cycle

    # =========================================================================
    # SIGNAL EVALUATION & RISK-GOVERNED ENTRY
    # =========================================================================
    def evaluate_market_scan(
        self,
        live_prices: Dict[str, float],
        candle_dfs: Dict[str, pd.DataFrame],
    ) -> List[Dict[str, Any]]:
        """Evaluate technical setups and AI probability filters for new entries."""
        eval_results = []
        now_utc = datetime.now(UTC)
        now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Current total equity for position sizing
        mark_value = Decimal("0.00")
        for pos in self.open_positions.values():
            px = live_prices.get(pos.pair, pos.entry_price)
            mark_value += Decimal(str(pos.qty)) * Decimal(str(px))
        total_equity = self.available_cash + mark_value

        for pair, df in candle_dfs.items():
            if len(df) < 50:
                continue

            df = self.compute_features(df)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            live_px = live_prices.get(pair, float(curr['close']))

            # Diagnostics dictionary
            diag = {
                "timestamp": now_str,
                "pair": pair,
                "live_price": live_px,
                "ema20": float(curr['ema_20']),
                "ema50": float(curr['ema_50']),
                "ema200": float(curr['ema_200']),
                "rsi14": float(curr['rsi_14']),
                "atr14": float(curr['atr_14']),
                "bb_z": float(curr['bb_z']),
                "adx14": float(curr['adx_14']),
                "strategy": "",
                "technical_signal": False,
                "ai_probability": 0.0,
                "threshold": 0.0,
                "action": "SKIP",
                "reason": "",
            }

            # Map strategy and thresholds
            if pair in ["eth_idr", "sol_idr"]:
                strat_id = "C02_EMA_TREND_PULLBACK"
                min_threshold = 0.48 if pair == "sol_idr" else 0.38
                tp_mult = 3.5
                sl_mult = 1.75
            else:  # btc_idr
                strat_id = "C07_MEAN_REVERSION"
                min_threshold = 0.38
                tp_mult = 3.0
                sl_mult = 2.0

            diag["strategy"] = strat_id
            diag["threshold"] = min_threshold

            # Technical signal check
            close_val = live_px
            ema200_val = float(curr['ema_200'])
            atr_val = float(curr['atr_14'])

            if close_val <= ema200_val:
                diag["reason"] = f"BEAR_REGIME: Close Rp {close_val:,.0f} <= EMA200 Rp {ema200_val:,.0f}"
                eval_results.append(diag)
                continue

            tech_signal = False
            if strat_id == "C02_EMA_TREND_PULLBACK":
                f_ema, s_ema = float(curr['ema_20']), float(curr['ema_50'])
                # Uptrend alignment + Pullback touch + Bounce
                if close_val > s_ema and f_ema > s_ema:
                    if float(prev['low']) <= float(prev['ema_20']) and close_val > f_ema:
                        tech_signal = True
                    else:
                        diag["reason"] = "NO_PULLBACK_BOUNCE: Price not bouncing off EMA20"
                else:
                    diag["reason"] = f"EMA_NOT_BULLISH: EMA20 {f_ema:,.0f} vs EMA50 {s_ema:,.0f}"
            elif strat_id == "C07_MEAN_REVERSION":
                bb_z, rsi, adx = float(curr['bb_z']), float(curr['rsi_14']), float(curr['adx_14'])
                if (bb_z <= -1.5) and (rsi <= 0.32) and (adx <= 0.30):
                    tech_signal = True
                else:
                    diag["reason"] = f"NOT_OVERSOLD: BB_Z={bb_z:.2f} (<= -1.5), RSI={rsi:.2f} (<= 0.32), ADX={adx:.2f} (<= 0.30)"

            diag["technical_signal"] = tech_signal

            if not tech_signal:
                eval_results.append(diag)
                continue

            # Run AI Probability Inference
            prob = self.predict_probability(pair, curr)
            diag["ai_probability"] = prob

            if prob < min_threshold:
                diag["action"] = "REJECT_AI_LOW_PROB"
                diag["reason"] = f"AI Probability {prob:.1%} < Threshold {min_threshold:.1%}"
                eval_results.append(diag)
                continue

            # Check Risk Governor Constraints
            if len(self.open_positions) >= self.max_positions:
                diag["action"] = "REJECT_MAX_CAPACITY"
                diag["reason"] = f"Max {self.max_positions} open positions reached"
                eval_results.append(diag)
                continue

            if any(pos.pair == pair for pos in self.open_positions.values()):
                diag["action"] = "REJECT_ALREADY_IN_POSITION"
                diag["reason"] = f"Already holding active position in {pair}"
                eval_results.append(diag)
                continue

            # Position Sizing: 1.5% Risk of Total Equity
            target_risk_idr = total_equity * Decimal(str(self.fixed_risk_pct))
            sl_distance_idr = Decimal(str(sl_mult * atr_val))
            if sl_distance_idr <= 0:
                diag["action"] = "REJECT_INVALID_ATR"
                diag["reason"] = "ATR is zero or negative"
                eval_results.append(diag)
                continue

            # Notional = Risk / (SL_dist / Price)
            sl_dist_ratio = sl_distance_idr / Decimal(str(live_px))
            desired_notional = target_risk_idr / sl_dist_ratio

            # Plafon: Max 25% cash
            max_cash_cap = self.available_cash * Decimal(str(self.max_cash_per_trade_pct))
            allocated_budget = min(desired_notional, max_cash_cap)

            if allocated_budget < self.min_order_idr:
                diag["action"] = "REJECT_BELOW_MIN_NOTIONAL"
                diag["reason"] = f"Budget Rp {allocated_budget:,.0f} < Min order Rp {self.min_order_idr:,.0f}"
                eval_results.append(diag)
                continue

            if allocated_budget > self.available_cash:
                diag["action"] = "REJECT_INSUFFICIENT_CASH"
                diag["reason"] = f"Required Rp {allocated_budget:,.0f} > Available Rp {self.available_cash:,.0f}"
                eval_results.append(diag)
                continue

            # EXECUTE PAPER BUY
            buy_fee = allocated_budget * MAKER_BUY_FEE_RATE
            net_trade_cash = allocated_budget - buy_fee
            qty = float(net_trade_cash / Decimal(str(live_px)))

            sl_price = live_px - (sl_mult * atr_val)
            tp_price = live_px + (tp_mult * atr_val)

            pos_id = f"pos_{int(time.time())}_{pair}"
            new_pos = ShadowPosition(
                position_id=pos_id,
                pair=pair,
                strategy_id=strat_id,
                entry_ts=now_str,
                entry_price=live_px,
                qty=qty,
                cash_debited=float(allocated_budget),
                buy_fee_paid=float(buy_fee),
                stop_loss=sl_price,
                take_profit=tp_price,
                entry_atr=atr_val,
                highest_price=live_px,
                bars_held=0,
            )

            self.available_cash -= allocated_budget
            self.open_positions[pos_id] = new_pos

            diag["action"] = "ENTER_POSITION"
            diag["reason"] = f"EXACT_FILL: Allocated Rp {float(allocated_budget):,.0f} (Qty {qty:.6f}) | TP Rp {tp_price:,.0f} | SL Rp {sl_price:,.0f}"
            eval_results.append(diag)

            self.audit_log.append(diag)
            self.save_state()

        return eval_results

    # =========================================================================
    # PORTFOLIO SUMMARY METRICS
    # =========================================================================
    def get_portfolio_summary(self, live_prices: Dict[str, float]) -> Dict[str, Any]:
        """Compute live equity, unrealized PnL, and win-rate analytics."""
        mark_value = Decimal("0.00")
        unrealized_pnl = 0.0

        for pos in self.open_positions.values():
            curr_px = live_prices.get(pos.pair, pos.entry_price)
            pos_val = Decimal(str(pos.qty)) * Decimal(str(curr_px))
            mark_value += pos_val
            unrealized_pnl += float(pos_val - Decimal(str(pos.cash_debited)))

        total_equity = self.available_cash + mark_value
        capital_growth_pct = float((total_equity - self.initial_cash) / self.initial_cash)

        wins = sum(1 for t in self.closed_trades if t.net_pnl > 0)
        tot_closed = len(self.closed_trades)
        wr = (wins / tot_closed) if tot_closed > 0 else 0.0
        realized_net_pnl = sum(t.net_pnl for t in self.closed_trades)
        total_fees = sum(t.buy_fee + t.sell_fee for t in self.closed_trades) + sum(p.buy_fee_paid for p in self.open_positions.values())

        return {
            "initial_cash": float(self.initial_cash),
            "available_cash": float(self.available_cash),
            "invested_mark_value": float(mark_value),
            "total_equity": float(total_equity),
            "unrealized_pnl": unrealized_pnl,
            "realized_net_pnl": realized_net_pnl,
            "total_fees_paid": total_fees,
            "capital_growth_pct": capital_growth_pct,
            "open_position_count": len(self.open_positions),
            "closed_trades_count": tot_closed,
            "win_rate": wr,
        }

    # =========================================================================
    # EXECUTIVE DASHBOARD FORMATTER
    # =========================================================================
    def format_dashboard(
        self,
        live_prices: Dict[str, float],
        eval_diagnostics: List[Dict[str, Any]],
        exits_triggered: List[ClosedTrade],
    ) -> str:
        """Render a clean CLI status dashboard."""
        now_utc = datetime.now(UTC)
        now_wib = now_utc + timedelta(hours=7)
        summary = self.get_portfolio_summary(live_prices)

        lines = []
        lines.append("=" * 105)
        lines.append(f"  INDODAX RESEARCH LAB — LIVE SHADOW PAPER-TRADING ENGINE")
        lines.append(f"  Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} | WIB: {now_wib.strftime('%Y-%m-%d %H:%M:%S WIB')} | Mode: ZERO-RISK SHADOW")
        lines.append("=" * 105)

        # 1. Market Radar
        lines.append("\n[1] LIVE MARKET RADAR & SENSORY ENGINE:")
        lines.append(f"{'Pair':<9} | {'Live Price':<16} | {'EMA-20':<14} | {'EMA-50':<14} | {'EMA-200':<14} | {'RSI':<5} | {'ATR-14':<10} | {'Regime'}")
        lines.append("-" * 105)
        for diag in eval_diagnostics:
            p = diag['pair'].upper()
            px = diag['live_price']
            e20, e50, e200 = diag['ema20'], diag['ema50'], diag['ema200']
            rsi_val = diag['rsi14'] * 100 if diag['rsi14'] <= 1.0 else diag['rsi14']
            atr = diag['atr14']
            regime = "BULLISH [OK]" if px > e200 else "BEARISH [WAIT]"
            lines.append(f"{p:<9} | Rp {px:>13,.0f} | Rp {e20:>11,.0f} | Rp {e50:>11,.0f} | Rp {e200:>11,.0f} | {rsi_val:>5.1f} | Rp {atr:>8,.0f} | {regime}")

        # 2. Strategy & AI Predictive Brain Matrix
        lines.append("\n[2] STRATEGY SIGNALS & AI BRAIN DECISIONS:")
        lines.append(f"{'Pair':<9} | {'Strategy':<22} | {'Tech Sig':<8} | {'AI Prob':<8} | {'Threshold':<9} | {'Decision':<16} | {'Diagnostics / Reason'}")
        lines.append("-" * 105)
        for diag in eval_diagnostics:
            p = diag['pair'].upper()
            strat = diag['strategy'].replace("_", " ")[:22]
            tsig = "TRIGGER" if diag['technical_signal'] else "IDLE"
            prob = f"{diag['ai_probability']*100:>5.1f}%" if diag['technical_signal'] else "-"
            thresh = f"{diag['threshold']*100:>5.1f}%"
            act = diag['action']
            reason = diag['reason'][:45]
            lines.append(f"{p:<9} | {strat:<22} | {tsig:<8} | {prob:<8} | {thresh:<9} | {act:<16} | {reason}")

        # 3. Position Exits (if any this cycle)
        if exits_triggered:
            lines.append("\n[!] TRADES CLOSED THIS CYCLE:")
            for ct in exits_triggered:
                lines.append(f"  * {ct.pair.upper()} CLOSED via {ct.exit_reason}: Entry Rp {ct.entry_price:,.0f} -> Exit Rp {ct.exit_price:,.0f} | Net PnL: Rp {ct.net_pnl:+,.0f} ({ct.pnl_pct*100:+.2f}%)")

        # 4. Open Positions
        lines.append("\n[3] ACTIVE SHADOW POSITIONS:")
        if not self.open_positions:
            lines.append("  (No active positions. Risk Governor standing by in 100% Cash mode)")
        else:
            lines.append(f"{'Position ID':<22} | {'Pair':<8} | {'Entry Px':<14} | {'Current Px':<14} | {'Stop Loss':<14} | {'Take Profit':<14} | {'Unrealized PnL'}")
            lines.append("-" * 105)
            for pos in self.open_positions.values():
                curr_px = live_prices.get(pos.pair, pos.entry_price)
                unr_pnl = (curr_px - pos.entry_price) * pos.qty
                unr_pct = (curr_px - pos.entry_price) / pos.entry_price
                lines.append(
                    f"{pos.position_id[:22]:<22} | {pos.pair.upper():<8} | Rp {pos.entry_price:>11,.0f} | Rp {curr_px:>11,.0f} | "
                    f"Rp {pos.stop_loss:>11,.0f} | Rp {pos.take_profit:>11,.0f} | Rp {unr_pnl:>+9,.0f} ({unr_pct*100:>+5.2f}%)"
                )

        # 5. Portfolio & Risk Governor Ledger
        lines.append("\n[4] PORTFOLIO LEDGER & RISK CAPACITY:")
        lines.append(f"  * Modal Awal      : Rp {summary['initial_cash']:>12,.0f}")
        lines.append(f"  * Saldo Kas IDR   : Rp {summary['available_cash']:>12,.0f}")
        lines.append(f"  * Nilai Terbuka   : Rp {summary['invested_mark_value']:>12,.0f} (Unrealized PnL: Rp {summary['unrealized_pnl']:>+8,.0f})")
        lines.append(f"  * Total Ekuitas   : Rp {summary['total_equity']:>12,.0f} (Pertumbuhan: {summary['capital_growth_pct']*100:>+5.2f}%)")
        lines.append(f"  * Realized Net PnL: Rp {summary['realized_net_pnl']:>12,.0f} (Total Fee Indodax: Rp {summary['total_fees_paid']:>8,.0f})")
        lines.append(f"  * Kapasitas Slot  : {summary['open_position_count']} / {self.max_positions} Posisi Terpakai")
        lines.append(f"  * Win Rate Record : {summary['win_rate']*100:.1f}% ({summary['closed_trades_count']} trade selesai)")
        lines.append("=" * 105)

        return "\n".join(lines)
