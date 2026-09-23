"""Strict versioned feature-registry contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from indodax_lab.features.registry import load_feature_registry

ROOT = Path(__file__).parents[4]
CANONICAL_CONFIG = ROOT / "configs" / "features" / "tabular_bar_v1.yaml"

EXPECTED_WAVE1_FEATURES = {
    *(f"log_ret_{period}_1h" for period in (1, 3, 6, 12, 24, 72)),
    "dist_high_20_1h",
    "dist_low_20_1h",
    "ema_ratio_20_50_1h",
    "ema20_slope_5_1h",
    "donchian_pos_20_1h",
    "rsi_centered_14_1h",
    "stochrsi_k_14_1h",
    "stochrsi_d_14_1h",
    "macd_hist_atr_1h",
    "adx_14_1h",
    "di_spread_14_1h",
    "atr_pct_14_1h",
    "rv_24_1h",
    "rv_168_1h",
    "downside_vol_24_1h",
    "parkinson_vol_24_1h",
    "bb_z_20_1h",
    "bb_width_20_1h",
    "volume_z_20_1h",
    "quote_turnover_24_1h",
    "zero_volume_ratio_24_1h",
    "amihud_24_1h",
    "vwap_dev_24_1h",
    "btc_log_ret_1_1h",
    "btc_log_ret_24_1h",
    "beta_btc_168_1h",
    "tier_momentum_rank_24_1h",
    "market_breadth_pos_24_1h",
    "market_rv_median_24_1h",
    "hour_sin_utc",
    "hour_cos_utc",
    "dow_sin_utc",
    "dow_cos_utc",
    "log_listing_age_days",
    "bar_completeness_24_1h",
}


def _registry_yaml(*, version: str = "1.0.0", feature_block: str) -> str:
    return (
        "feature_set_id: tabular_bar\n"
        f"version: {version}\n"
        "decision_interval: 1h\n"
        "features:\n"
        f"{feature_block}"
    )


def _ema_feature(*, name: str = "ema_ratio_20_50_1h", lookback: int = 50) -> str:
    return (
        f"  - name: {name}\n"
        "    family: trend\n"
        "    source_columns: [close]\n"
        "    formula: ema(close,20)/ema(close,50)-1\n"
        "    implementation: indodax_lab.features.technical:ema_ratio\n"
        "    params: {fast: 20, slow: 50}\n"
        f"    lookback_bars: {lookback}\n"
        "    availability: closed_bar\n"
        "    lag_bars: 0\n"
        "    dtype: float64\n"
        "    missing_policy: drop_sample_until_warm\n"
        "    normalization: unitless_ratio\n"
        "    monotonicity: none\n"
    )


def test_canonical_registry_contains_exact_wave1_names_and_metadata() -> None:
    """Dropping a contracted feature or metadata field must invalidate the registry."""
    loaded = load_feature_registry(CANONICAL_CONFIG)

    assert loaded.registry.feature_set_id == "tabular_bar"
    assert loaded.registry.version == "1.1.0"
    assert loaded.registry.decision_interval == "1h"
    assert {feature.name for feature in loaded.registry.features} == EXPECTED_WAVE1_FEATURES
    assert loaded.source_id.startswith("sha256:")
    assert all(
        feature.formula
        and feature.implementation
        and feature.source_columns
        and feature.lookback_bars > 0
        and feature.availability
        and feature.dtype == "float64"
        and feature.missing_policy
        and feature.normalization
        for feature in loaded.registry.features
    )


def test_registry_rejects_duplicate_names_bfill_and_insufficient_lookback(
    tmp_path: Path,
) -> None:
    """Unsafe aliases, backward filling, and under-warmed EMA definitions fail closed."""
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        _registry_yaml(feature_block=_ema_feature() + _ema_feature()), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="DUPLICATE_FEATURE_NAME"):
        load_feature_registry(duplicate)

    bfill = tmp_path / "bfill.yaml"
    bfill.write_text(
        _registry_yaml(
            feature_block=_ema_feature().replace(
                "missing_policy: drop_sample_until_warm", "missing_policy: bfill"
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="BFILL_FORBIDDEN"):
        load_feature_registry(bfill)

    too_short = tmp_path / "too-short.yaml"
    too_short.write_text(_registry_yaml(feature_block=_ema_feature(lookback=49)), encoding="utf-8")
    with pytest.raises(ValueError, match="INSUFFICIENT_FEATURE_LOOKBACK"):
        load_feature_registry(too_short)


def test_registry_rejects_timeframe_without_asof_policy(tmp_path: Path) -> None:
    """A 4h feature cannot claim ordinary decision-bar availability."""
    path = tmp_path / "bad-4h.yaml"
    path.write_text(
        _registry_yaml(feature_block=_ema_feature(name="ema_ratio_20_50_4h")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="TIMEFRAME_AVAILABILITY_POLICY_REQUIRED"):
        load_feature_registry(path)


def test_registry_requires_version_bump_when_content_changes(tmp_path: Path) -> None:
    """A prior exact-byte identity makes silent same-version semantic changes impossible."""
    path = tmp_path / "registry.yaml"
    path.write_text(_registry_yaml(feature_block=_ema_feature()), encoding="utf-8")
    previous = load_feature_registry(path)
    path.write_text(
        _registry_yaml(
            feature_block=_ema_feature().replace("unitless_ratio", "train_robust_scale")
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="FEATURE_CONTENT_CHANGED_WITHOUT_VERSION_BUMP"):
        load_feature_registry(path, previous=previous)

    path.write_text(
        _registry_yaml(
            version="1.0.1",
            feature_block=_ema_feature().replace("unitless_ratio", "train_robust_scale"),
        ),
        encoding="utf-8",
    )
    current = load_feature_registry(path, previous=previous)
    assert current.registry.version == "1.0.1"


def test_feat_01_valid_contract() -> None:
    """FEAT-01-AC0: Registry Wave 1 memuat metadata dan identitas versi."""
    test_canonical_registry_contains_exact_wave1_names_and_metadata()


def test_registry_feature_params_cannot_mutate_after_hashing() -> None:
    loaded = load_feature_registry(CANONICAL_CONFIG)
    feature = loaded.registry.feature("ema_ratio_20_50_1h")
    source_id = loaded.source_id

    with pytest.raises(TypeError):
        feature.params["fast"] = 999

    assert feature.params["fast"] == 20
    assert loaded.source_id == source_id
    assert loaded.registry.model_dump(mode="json")["features"][0]["params"]


def test_feat_01_contract_1(tmp_path: Path) -> None:
    """FEAT-01-AC1: Nama duplikat dan bfill ditolak."""
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        _registry_yaml(feature_block=_ema_feature() + _ema_feature()), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="DUPLICATE_FEATURE_NAME"):
        load_feature_registry(duplicate)

    bfill = tmp_path / "bfill.yaml"
    bfill.write_text(
        _registry_yaml(
            feature_block=_ema_feature().replace(
                "missing_policy: drop_sample_until_warm", "missing_policy: bfill"
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="BFILL_FORBIDDEN"):
        load_feature_registry(bfill)


def test_feat_01_contract_2(tmp_path: Path) -> None:
    """FEAT-01-AC2: Lookback kurang dari kebutuhan rumus ditolak."""
    too_short = tmp_path / "too-short.yaml"
    too_short.write_text(_registry_yaml(feature_block=_ema_feature(lookback=49)), encoding="utf-8")
    with pytest.raises(ValueError, match="INSUFFICIENT_FEATURE_LOOKBACK"):
        load_feature_registry(too_short)


def test_feat_01_contract_3(tmp_path: Path) -> None:
    """FEAT-01-AC3: Perubahan konten tanpa version bump ditolak."""
    test_registry_requires_version_bump_when_content_changes(tmp_path)


# ---------------------------------------------------------------------------
# 5m registry tests
# ---------------------------------------------------------------------------

CANONICAL_5M_CONFIG = ROOT / "configs" / "features" / "tabular_bar_5m_v1.yaml"

EXPECTED_5M_FEATURES = {
    "log_ret_1_5m",
    "log_ret_12_5m",
    "log_ret_36_5m",
    "log_ret_144_5m",
    "dist_high_20_5m",
    "dist_low_20_5m",
    "ema_ratio_20_50_5m",
    "ema20_slope_5_5m",
    "donchian_pos_20_5m",
    "rsi_centered_14_5m",
    "stochrsi_k_14_5m",
    "macd_hist_atr_5m",
    "atr_pct_14_5m",
    "rv_288_5m",
    "bb_z_20_5m",
    "volume_z_20_5m",
    "hour_sin_utc",
    "hour_cos_utc",
    "dow_sin_utc",
    "dow_cos_utc",
    "btc_log_ret_1_1h",
}


def test_5m_registry_loads_with_correct_interval_and_feature_count() -> None:
    """Removing 5m from allowed intervals would break scalping feature materialization."""
    loaded = load_feature_registry(CANONICAL_5M_CONFIG)

    assert loaded.registry.feature_set_id == "tabular_bar_5m"
    assert loaded.registry.version == "1.1.0"
    assert loaded.registry.decision_interval == "5m"
    assert {feature.name for feature in loaded.registry.features} == EXPECTED_5M_FEATURES
    assert loaded.source_id.startswith("sha256:")


def test_5m_registry_context_features_use_asof_policy() -> None:
    """1h BTC context features in a 5m registry require as-of policy."""
    loaded = load_feature_registry(CANONICAL_5M_CONFIG)

    context_features = [f for f in loaded.registry.features if f.family == "context"]
    assert context_features, "no context features found"
    for feat in context_features:
        assert feat.availability == "asof_closed_bar", (
            f"context feature {feat.name!r} must use asof_closed_bar in a 5m registry, "
            f"got {feat.availability!r}"
        )


def test_5m_suffix_in_1h_registry_requires_asof_policy(tmp_path: Path) -> None:
    """A feature named with _5m suffix inside a 1h registry must use asof_closed_bar."""
    path = tmp_path / "mixed.yaml"
    path.write_text(
        _registry_yaml(feature_block=_ema_feature(name="ema_ratio_20_50_5m")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="TIMEFRAME_AVAILABILITY_POLICY_REQUIRED"):
        load_feature_registry(path)
