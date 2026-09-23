"""Hand-literal golden tests for normalized technical features."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from indodax_lab.features.liquidity import amihud, quote_turnover, zero_volume_ratio
from indodax_lab.features.registry import load_feature_registry
from indodax_lab.features.technical import (
    adx_di,
    atr,
    atr_pct,
    bollinger_features,
    donchian_position,
    ema_ratio,
    ema_slope_atr,
    macd_hist_atr,
    rsi,
    rsi_centered,
    stochrsi,
    volume_zscore,
    vwap_deviation,
    wilder_average,
)

FIXTURE = Path(__file__).parents[3] / "fixtures" / "features" / "golden_ohlcv.csv"
REGISTRY_CONFIG = Path(__file__).parents[4] / "configs" / "features" / "tabular_bar_v1.yaml"


def test_wilder_average_uses_sma_seed_and_exact_warmup_boundary() -> None:
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

    actual = wilder_average(values, period=3)

    assert actual.iloc[:2].isna().all()
    assert actual.iloc[2] == pytest.approx(2.0)
    assert actual.iloc[3] == pytest.approx(8.0 / 3.0)
    assert actual.iloc[4] == pytest.approx(31.0 / 9.0)


def test_rsi_first_valid_and_later_values_use_wilder_sma_seed() -> None:
    close = pd.Series([10.0, 12.0, 11.0, 14.0])

    actual = rsi(close, period=2, seed="sma")

    assert actual.iloc[:2].isna().all()
    assert actual.iloc[2] == pytest.approx(200.0 / 3.0)
    assert actual.iloc[3] == pytest.approx(800.0 / 9.0)


def test_atr_first_valid_and_later_values_use_wilder_sma_seed() -> None:
    high = pd.Series([11.0, 14.0, 17.0, 22.0])
    low = pd.Series([9.0, 10.0, 11.0, 16.0])
    close = pd.Series([10.0, 12.0, 14.0, 20.0])

    actual = atr(high, low, close, period=3, seed="sma")

    assert actual.iloc[:2].isna().all()
    assert actual.iloc[2] == pytest.approx(4.0)
    assert actual.iloc[3] == pytest.approx(16.0 / 3.0)


def test_ema_explicit_first_observation_seed_and_min_periods() -> None:
    close = pd.Series([2.0, 4.0, 8.0])

    actual = ema_ratio(
        close,
        fast=2,
        slow=3,
        seed="first_observation",
        adjust=False,
        min_periods=1,
    )

    assert actual.iloc[0] == pytest.approx(0.0)
    assert actual.iloc[1] == pytest.approx(1.0 / 9.0)
    assert actual.iloc[2] == pytest.approx(17.0 / 99.0)


def test_registry_freezes_indicator_initialization_and_rolling_policies() -> None:
    registry = load_feature_registry(REGISTRY_CONFIG).registry
    features = {feature.name: feature for feature in registry.features}

    assert registry.version == "1.1.0"
    assert features["ema_ratio_20_50_1h"].params == {
        "fast": 20,
        "slow": 50,
        "seed": "first_observation",
        "adjust": False,
        "min_periods": 0,
    }
    assert features["rsi_centered_14_1h"].params["seed"] == "sma"
    assert features["stochrsi_k_14_1h"].params["zero_range_policy"] == "null"
    assert features["bb_z_20_1h"].params["ddof"] == 0


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
        "ema_slope": 0.862780377793843,
        "rsi_centered": 0.8130460851721694,
        "stochrsi_k": 1.0,
        "stochrsi_d": 1.0,
        "macd_hist_atr": 0.19136139935185725,
        "adx": 0.534466656866446,
        "di_spread": 0.17167351238059245,
        "bb_z": 2.25458431148546,
        "bb_width": 0.10241400049518,
        "atr_pct": 0.025393537306624376,
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


def test_feat_02_valid_contract() -> None:
    """FEAT-02-AC0: Indicator outputs and warmup are auditable."""
    bars = _ohlcv()
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    base_vol = bars["base_volume"]
    quote_vol = bars["quote_volume"]

    # Rolling/Wilder indicators have strict warmup periods with NaN
    rsi_c = rsi_centered(close, period=14)
    assert pd.isna(rsi_c.iloc[0])
    assert pd.notna(rsi_c.iloc[-1])
    assert rsi_c.dtype == "float64"

    turnover = quote_turnover(quote_vol, period=24)
    assert pd.isna(turnover.iloc[0])
    assert pd.notna(turnover.iloc[-1])

    zero_ratio = zero_volume_ratio(base_vol, period=24)
    assert pd.isna(zero_ratio.iloc[0])
    assert pd.notna(zero_ratio.iloc[-1])

    amihud_val = amihud(close, quote_vol, period=24)
    assert pd.isna(amihud_val.iloc[0])
    assert pd.notna(amihud_val.iloc[-1])

    donch = donchian_position(high, low, close, period=20)
    assert pd.isna(donch.iloc[0])
    assert pd.notna(donch.iloc[-1])

    # EMA ratio and slope produce valid continuous float64 outputs
    ema = ema_ratio(close, fast=20, slow=50)
    assert pd.notna(ema.iloc[-1])
    assert ema.dtype == "float64"

    slope = ema_slope_atr(close, high, low, ema_period=20, slope_bars=5, atr_period=14)
    assert pd.notna(slope.iloc[-1])
    assert slope.dtype == "float64"


def test_feat_02_contract_1() -> None:
    """FEAT-02-AC1: Golden expected dihitung independen dengan toleransi eksplisit."""
    test_normalized_indicators_match_explicit_golden_values()


def test_feat_02_contract_2() -> None:
    """FEAT-02-AC2: Flat price atau zero-volume tidak menghasilkan infinity."""
    n = 60
    flat_close = pd.Series([100.0] * n)
    flat_high = pd.Series([100.0] * n)
    flat_low = pd.Series([100.0] * n)
    zero_vol = pd.Series([0.0] * n)

    indicators = [
        ema_ratio(flat_close, 20, 50),
        ema_slope_atr(flat_close, flat_high, flat_low, ema_period=20, slope_bars=5, atr_period=14),
        rsi_centered(flat_close, 14),
        macd_hist_atr(flat_high, flat_low, flat_close, fast=12, slow=26, signal=9, atr_period=14),
        atr_pct(flat_high, flat_low, flat_close, period=14),
        donchian_position(flat_high, flat_low, flat_close, period=20),
        volume_zscore(zero_vol, period=20),
        vwap_deviation(flat_high, flat_low, flat_close, zero_vol, period=24),
        quote_turnover(zero_vol, period=24),
        zero_volume_ratio(zero_vol, period=24),
        amihud(flat_close, zero_vol, period=24),
    ]

    for ind in indicators:
        assert not np.isinf(ind).any(), f"Infinite value found in indicator: {ind}"

    stoch = stochrsi(flat_close, period=14, smooth_k=3, smooth_d=3)
    assert not np.isinf(stoch).any().any()

    directional = adx_di(flat_high, flat_low, flat_close, period=14)
    assert not np.isinf(directional).any().any()

    bands = bollinger_features(flat_close, period=20, stddev=2.0)
    assert not np.isinf(bands).any().any()


def test_feat_02_contract_3() -> None:
    """FEAT-02-AC3: Ubah future bar tidak mengubah fitur masa lalu."""
    bars = _ohlcv()
    original_ema = ema_ratio(bars["close"], fast=20, slow=50)
    original_rsi = rsi_centered(bars["close"], period=14)
    original_turnover = quote_turnover(bars["quote_volume"], period=24)

    perturbed = bars.copy()
    perturbed.loc[45:, "close"] *= 3.0
    perturbed.loc[45:, "high"] *= 3.0
    perturbed.loc[45:, "low"] *= 3.0
    perturbed.loc[45:, "quote_volume"] *= 5.0

    perturbed_ema = ema_ratio(perturbed["close"], fast=20, slow=50)
    perturbed_rsi = rsi_centered(perturbed["close"], period=14)
    perturbed_turnover = quote_turnover(perturbed["quote_volume"], period=24)

    pd.testing.assert_series_equal(original_ema.iloc[:45], perturbed_ema.iloc[:45])
    pd.testing.assert_series_equal(original_rsi.iloc[:45], perturbed_rsi.iloc[:45])
    pd.testing.assert_series_equal(original_turnover.iloc[:45], perturbed_turnover.iloc[:45])

