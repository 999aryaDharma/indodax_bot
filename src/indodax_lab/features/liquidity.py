"""Normalized rolling volume and liquidity features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .technical import log_return


def quote_turnover(quote_volume: pd.Series, *, period: int) -> pd.Series:
    """Return log1p rolling quote turnover, leaving scaling to the train fold."""
    volume = pd.Series(quote_volume, index=quote_volume.index, dtype="float64")
    return np.log1p(volume.rolling(period, min_periods=period).sum())


def zero_volume_ratio(base_volume: pd.Series, *, period: int) -> pd.Series:
    """Return the fraction of genuine zero-volume bars in each complete window."""
    volume = pd.Series(base_volume, index=base_volume.index, dtype="float64")
    return volume.eq(0).astype("float64").rolling(period, min_periods=period).mean()


def amihud(close: pd.Series, quote_volume: pd.Series, *, period: int) -> pd.Series:
    """Return rolling abs(log return)/quote volume with zero volume safely masked."""
    volume = pd.Series(quote_volume, index=quote_volume.index, dtype="float64")
    ratio = log_return(close, periods=1).abs().div(volume.mask(volume <= 0))
    return ratio.rolling(period, min_periods=period).mean()


__all__ = ["amihud", "quote_turnover", "zero_volume_ratio"]
