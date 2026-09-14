"""Deterministic normalized technical indicators with stable internal names."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


def _float_series(values: pd.Series) -> pd.Series:
    return pd.Series(values, index=values.index, dtype="float64")


def _divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.mask(denominator == 0))


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Return Wilder true range, using high-low for the first observation."""
    high, low, close = map(_float_series, (high, low, close))
    previous_close = close.shift(1)
    return pd.concat(
        (high - low, (high - previous_close).abs(), (low - previous_close).abs()), axis=1
    ).max(axis=1)


def wilder_average(values: pd.Series, period: int) -> pd.Series:
    """Use one explicit Wilder/RMA convention for RSI, ATR, and ADX."""
    if period < 1:
        raise ValueError("period must be positive")
    return _float_series(values).ewm(
        alpha=1.0 / period, adjust=False, min_periods=period
    ).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Wilder average true range in raw price units for internal normalization only."""
    return wilder_average(true_range(high, low, close), period)


def ema_ratio(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """Return EMA(fast)/EMA(slow)-1 as a price-unit invariant trend feature."""
    close = _float_series(close)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    return ema_fast.div(ema_slow).sub(1.0)


def ema_slope_atr(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    *,
    ema_period: int,
    slope_bars: int,
    atr_period: int,
) -> pd.Series:
    """Return an EMA change over `slope_bars`, normalized by ATR."""
    close = _float_series(close)
    average = close.ewm(span=ema_period, adjust=False).mean()
    return _divide(average - average.shift(slope_bars), atr(high, low, close, atr_period))


def rsi(close: pd.Series, period: int) -> pd.Series:
    """Return Wilder RSI on a 0..100 scale; flat windows are neutral at 50."""
    close = _float_series(close)
    delta = close.diff()
    average_gain = wilder_average(delta.clip(lower=0), period)
    average_loss = wilder_average(-delta.clip(upper=0), period)
    relative_strength = _divide(average_gain, average_loss)
    result = 100.0 - 100.0 / (1.0 + relative_strength)
    result = result.mask((average_gain == 0) & (average_loss == 0), 50.0)
    return result.mask((average_loss == 0) & (average_gain > 0), 100.0)


def rsi_centered(close: pd.Series, period: int) -> pd.Series:
    """Center and normalize RSI to approximately -1..1."""
    return rsi(close, period).sub(50.0).div(50.0)


def stochrsi(
    close: pd.Series,
    *,
    period: int,
    smooth_k: int,
    smooth_d: int,
) -> pd.DataFrame:
    """Return normalized StochRSI K/D columns in the stable 0..1 range."""
    relative_strength = rsi(close, period)
    rolling_low = relative_strength.rolling(period, min_periods=period).min()
    rolling_high = relative_strength.rolling(period, min_periods=period).max()
    raw = _divide(relative_strength - rolling_low, rolling_high - rolling_low)
    k = raw.rolling(smooth_k, min_periods=smooth_k).mean()
    d = k.rolling(smooth_d, min_periods=smooth_d).mean()
    return pd.DataFrame({"stochrsi_k": k, "stochrsi_d": d}, index=close.index)


def stochrsi_component(
    close: pd.Series,
    *,
    period: int,
    smooth_k: int,
    smooth_d: int,
    component: Literal["k", "d"],
) -> pd.Series:
    """Select one stable StochRSI output for registry-driven execution."""
    return stochrsi(
        close, period=period, smooth_k=smooth_k, smooth_d=smooth_d
    )[f"stochrsi_{component}"]


def macd_hist_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    fast: int,
    slow: int,
    signal: int,
    atr_period: int,
) -> pd.Series:
    """Return MACD histogram divided by ATR, never raw IDR MACD."""
    close = _float_series(close)
    macd = close.ewm(span=fast, adjust=False).mean() - close.ewm(
        span=slow, adjust=False
    ).mean()
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return _divide(macd - signal_line, atr(high, low, close, atr_period))


def adx_di(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int,
) -> pd.DataFrame:
    """Return ADX/100 and (+DI--DI)/100 with stable column names."""
    high, low, close = map(_float_series, (high, low, close))
    upward = high.diff()
    downward = -low.diff()
    plus_dm = upward.where((upward > downward) & (upward > 0), 0.0)
    minus_dm = downward.where((downward > upward) & (downward > 0), 0.0)
    average_range = atr(high, low, close, period)
    plus_di = 100.0 * _divide(wilder_average(plus_dm, period), average_range)
    minus_di = 100.0 * _divide(wilder_average(minus_dm, period), average_range)
    dx = 100.0 * _divide((plus_di - minus_di).abs(), plus_di + minus_di)
    adx = wilder_average(dx, period).div(100.0)
    spread = plus_di.sub(minus_di).div(100.0)
    return pd.DataFrame({"adx": adx, "di_spread": spread}, index=close.index)


def adx_di_component(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int,
    component: Literal["adx", "di_spread"],
) -> pd.Series:
    """Select one normalized ADX family output for registry execution."""
    return adx_di(high, low, close, period=period)[component]


def bollinger_features(
    close: pd.Series,
    *,
    period: int,
    stddev: float,
) -> pd.DataFrame:
    """Return z-position and normalized full Bollinger bandwidth."""
    close = _float_series(close)
    middle = close.rolling(period, min_periods=period).mean()
    deviation = close.rolling(period, min_periods=period).std(ddof=0)
    z_score = _divide(close - middle, deviation)
    width = _divide(2.0 * stddev * deviation, middle)
    return pd.DataFrame({"bb_z": z_score, "bb_width": width}, index=close.index)


def bollinger_component(
    close: pd.Series,
    *,
    period: int,
    stddev: float,
    component: Literal["bb_z", "bb_width"],
) -> pd.Series:
    """Select one stable Bollinger output for registry-driven execution."""
    return bollinger_features(close, period=period, stddev=stddev)[component]


def atr_pct(high: pd.Series, low: pd.Series, close: pd.Series, *, period: int) -> pd.Series:
    """Return ATR divided by close, never raw price-unit ATR."""
    close = _float_series(close)
    return _divide(atr(high, low, close, period), close)


def donchian_position(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int,
) -> pd.Series:
    """Return close position within the rolling Donchian range."""
    rolling_high = _float_series(high).rolling(period, min_periods=period).max()
    rolling_low = _float_series(low).rolling(period, min_periods=period).min()
    return _divide(_float_series(close) - rolling_low, rolling_high - rolling_low)


def volume_zscore(volume: pd.Series, *, period: int) -> pd.Series:
    """Return rolling z-score of log1p(base volume), preserving genuine zeros."""
    logged = np.log1p(_float_series(volume))
    mean = logged.rolling(period, min_periods=period).mean()
    deviation = logged.rolling(period, min_periods=period).std(ddof=0)
    return _divide(logged - mean, deviation)


def vwap_deviation(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    *,
    period: int,
) -> pd.Series:
    """Return close/rolling typical-price VWAP-1."""
    high, low, close, volume = map(_float_series, (high, low, close, volume))
    typical_price = (high + low + close) / 3.0
    numerator = (typical_price * volume).rolling(period, min_periods=period).sum()
    denominator = volume.rolling(period, min_periods=period).sum()
    return _divide(close, _divide(numerator, denominator)).sub(1.0)


def log_return(close: pd.Series, *, periods: int) -> pd.Series:
    """Return logarithmic close return over an explicit bar lag."""
    close = _float_series(close)
    return np.log(_divide(close, close.shift(periods)))


def rolling_distance(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    *,
    period: int,
    side: Literal["high", "low"],
) -> pd.Series:
    """Return close-to-range-edge distance normalized by current close."""
    close = _float_series(close)
    if side == "high":
        edge = _float_series(high).rolling(period, min_periods=period).max()
        return _divide(close - edge, close)
    edge = _float_series(low).rolling(period, min_periods=period).min()
    return _divide(close - edge, close)


def realized_volatility(close: pd.Series, *, period: int) -> pd.Series:
    """Return rolling population standard deviation of one-bar log returns."""
    returns = log_return(close, periods=1)
    return returns.rolling(period, min_periods=period).std(ddof=0)


def downside_volatility(close: pd.Series, *, period: int) -> pd.Series:
    """Return rolling RMS of negative one-bar log returns; positive bars contribute zero."""
    returns = log_return(close, periods=1)
    downside_squared = returns.clip(upper=0).pow(2)
    return downside_squared.rolling(period, min_periods=period).mean().pow(0.5)


def parkinson_volatility(high: pd.Series, low: pd.Series, *, period: int) -> pd.Series:
    """Return rolling Parkinson range volatility without annualization."""
    log_range_squared = np.log(_divide(_float_series(high), _float_series(low))).pow(2)
    return (log_range_squared.rolling(period, min_periods=period).mean() / (4.0 * np.log(2.0))).pow(0.5)


__all__ = [
    "adx_di",
    "adx_di_component",
    "atr",
    "atr_pct",
    "bollinger_component",
    "bollinger_features",
    "donchian_position",
    "downside_volatility",
    "ema_ratio",
    "ema_slope_atr",
    "log_return",
    "macd_hist_atr",
    "parkinson_volatility",
    "realized_volatility",
    "rolling_distance",
    "rsi",
    "rsi_centered",
    "stochrsi",
    "stochrsi_component",
    "true_range",
    "volume_zscore",
    "vwap_deviation",
    "wilder_average",
]
