"""Hand-literal golden tests for normalized technical features."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from indodax_lab.features.technical import (
    adx_di,
    atr_pct,
    bollinger_features,
    donchian_position,
    ema_ratio,
    ema_slope_atr,
    macd_hist_atr,
    rsi_centered,
    stochrsi,
    volume_zscore,
    vwap_deviation,
)


FIXTURE = Path(__file__).parents[3] / "fixtures" / "features" / "golden_ohlcv.csv"


def _ohlcv() -> pd.DataFrame:
    return pd.read_csv(FIXTURE)


def test_normalized_indicators_match_explicit_golden_values() -> None:
    """Formula/sign/smoothing changes must move at least one hand-recorded terminal value."""
    bars = _ohlcv()
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    volume = bars["base_volume"]

    stoch = stochrsi(close, period=14, smooth_k=3, smooth_d=3)
    directional = adx_di(high, low, close, period=14)
    bands = bollinger_features(close, period=20, stddev=2.0)
    actual = {
        "ema_ratio": ema_ratio(close, fast=20, slow=50).iloc[-1],
        "ema_slope": ema_slope_atr(close, high, low, ema_period=20, slope_bars=5, atr_period=14).iloc[-1],
        "rsi_centered": rsi_centered(close, period=14).iloc[-1],
        "stochrsi_k": stoch["stochrsi_k"].iloc[-1],
        "stochrsi_d": stoch["stochrsi_d"].iloc[-1],
        "macd_hist_atr": macd_hist_atr(high, low, close, fast=12, slow=26, signal=9, atr_period=14).iloc[-1],
        "adx": directional["adx"].iloc[-1],
        "di_spread": directional["di_spread"].iloc[-1],
        "bb_z": bands["bb_z"].iloc[-1],
        "bb_width": bands["bb_width"].iloc[-1],
        "atr_pct": atr_pct(high, low, close, period=14).iloc[-1],
        "donchian_pos": donchian_position(high, low, close, period=20).iloc[-1],
        "volume_z": volume_zscore(volume, period=20).iloc[-1],
        "vwap_dev": vwap_deviation(high, low, close, volume, period=24).iloc[-1],
    }
    expected = {
        "ema_ratio": 0.0398445922836319,
        "ema_slope": 0.862591964023765,
        "rsi_centered": 0.813888558810225,
        "stochrsi_k": 1.0,
        "stochrsi_d": 1.0,
        "macd_hist_atr": 0.191319609895783,
        "adx": 0.528311473180984,
        "di_spread": 0.171204404357557,
        "bb_z": 2.25458431148546,
        "bb_width": 0.10241400049518,
        "atr_pct": 0.0253990839524304,
        "donchian_pos": 0.895793355290317,
        "volume_z": 1.86207715601609,
        "vwap_dev": 0.0580494331388117,
    }
    tolerances = {
        "ema_ratio": 1e-12,
        "ema_slope": 1e-12,
        "rsi_centered": 1e-12,
        "stochrsi_k": 1e-12,
        "stochrsi_d": 1e-12,
        "macd_hist_atr": 1e-12,
        "adx": 1e-12,
        "di_spread": 1e-12,
        "bb_z": 1e-12,
        "bb_width": 1e-12,
        "atr_pct": 1e-12,
        "donchian_pos": 1e-12,
        "volume_z": 1e-12,
        "vwap_dev": 1e-12,
    }

    for name, wanted in expected.items():
        assert actual[name] == pytest.approx(wanted, abs=tolerances[name], rel=0.0), name


def test_price_rescaling_does_not_change_cross_asset_normalized_indicators() -> None:
    """Multiplying the price unit must not leak raw IDR MACD/ATR into model features."""
    bars = _ohlcv()
    scaled = bars.copy()
    scaled[["open", "high", "low", "close"]] *= 1_000.0

    original = {
        "ema": ema_ratio(bars.close, fast=20, slow=50),
        "slope": ema_slope_atr(bars.close, bars.high, bars.low, ema_period=20, slope_bars=5, atr_period=14),
        "macd": macd_hist_atr(bars.high, bars.low, bars.close, fast=12, slow=26, signal=9, atr_period=14),
        "atr": atr_pct(bars.high, bars.low, bars.close, period=14),
        "vwap": vwap_deviation(bars.high, bars.low, bars.close, bars.base_volume, period=24),
    }
    rescaled = {
        "ema": ema_ratio(scaled.close, fast=20, slow=50),
        "slope": ema_slope_atr(scaled.close, scaled.high, scaled.low, ema_period=20, slope_bars=5, atr_period=14),
        "macd": macd_hist_atr(scaled.high, scaled.low, scaled.close, fast=12, slow=26, signal=9, atr_period=14),
        "atr": atr_pct(scaled.high, scaled.low, scaled.close, period=14),
        "vwap": vwap_deviation(scaled.high, scaled.low, scaled.close, scaled.base_volume, period=24),
    }

    for name in original:
        pd.testing.assert_series_equal(original[name], rescaled[name], check_names=False, atol=1e-12, rtol=1e-12)

