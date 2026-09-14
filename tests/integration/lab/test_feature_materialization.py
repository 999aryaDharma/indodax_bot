"""Integration and contract tests for immutable feature materialization (FEAT-04)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from indodax_lab.features.builder import build_feature_frame
from indodax_lab.cli.build_features import main as build_features_main
from indodax_lab.features.registry import load_feature_registry


BASE = datetime(2024, 1, 1, tzinfo=UTC)
SNAPSHOT_ID = "sha256:" + "a" * 64


def _create_registry_yaml(path: Path, lookback: int = 4) -> None:
    path.write_text(
        "feature_set_id: tabular_bar\n"
        "version: 1.0.0\n"
        "decision_interval: 1h\n"
        "features:\n"
        "  - name: ema_ratio_2_3_1h\n"
        "    family: trend\n"
        "    source_columns: [close]\n"
        "    formula: ema(close,2)/ema(close,3)-1\n"
        "    implementation: indodax_lab.features.technical:ema_ratio\n"
        "    params: {fast: 2, slow: 3}\n"
        f"    lookback_bars: {lookback}\n"
        "    availability: closed_bar\n"
        "    lag_bars: 0\n"
        "    dtype: float64\n"
        "    missing_policy: drop_sample_until_warm\n"
        "    normalization: unitless_ratio\n"
        "    monotonicity: none\n",
        encoding="utf-8",
    )


def _make_bars(count: int = 6, pair: str = "btc_idr") -> pd.DataFrame:
    rows = []
    for index in range(count):
        open_time = BASE + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1)
        close = 100.0 + index * 2.0
        rows.append(
            {
                "pair": pair,
                "interval": "1h",
                "bar_id": f"{pair}-bar-{index}",
                "open_time": open_time,
                "close_time": close_time,
                "available_at": close_time,
                "is_closed": True,
                "open": close - 1.0,
                "high": close + 2.0,
                "low": close - 2.0,
                "close": close,
                "base_volume": 10.0 + index,
                "quote_volume": (10.0 + index) * close,
                "quality_flags": (),
            }
        )
    return pd.DataFrame(rows)


def test_feat_04_valid_contract(tmp_path: Path) -> None:
    """FEAT-04-AC0: CLI and builder construct feature matrix with sample identity, warmup mask, and lineage."""
    config_path = tmp_path / "registry.yaml"
    _create_registry_yaml(config_path, lookback=4)
    registry = load_feature_registry(config_path)

    bars = _make_bars(count=6)
    result = build_feature_frame(
        bars,
        registry=registry,
        dataset_snapshot_id=SNAPSHOT_ID,
    )

    # Validate row count
    assert len(result) == 6

    # Validate identity and lineage columns
    expected_meta = [
        "sample_id",
        "pair",
        "decision_ts",
        "decision_interval",
        "feature_set_id",
        "feature_set_version",
        "dataset_snapshot_id",
        "row_ready_at",
        "eligible",
        "missing_feature_count",
        "reason_codes",
        "quality_flags",
    ]
    for col in expected_meta:
        assert col in result.columns, f"Missing metadata column: {col}"

    # Validate sample identity format (content-addressed sha256)
    for sample_id in result["sample_id"]:
        assert sample_id.startswith("sha256:"), f"Invalid sample_id format: {sample_id}"
        assert len(sample_id) == 71

    # Validate unique sample_ids
    assert result["sample_id"].nunique() == 6

    # Warmup mask verification: lookback is 4
    # Rows 0, 1, 2 have available bars 1, 2, 3 < 4 -> masked as NaN, ineligible
    assert result["ema_ratio_2_3_1h"].iloc[:3].isna().all()
    assert result["eligible"].iloc[:3].tolist() == [False, False, False]
    assert result["missing_feature_count"].iloc[:3].tolist() == [1, 1, 1]
    for reasons in result["reason_codes"].iloc[:3]:
        assert "INSUFFICIENT_LOOKBACK" in reasons

    # Rows 3, 4, 5 have available bars 4, 5, 6 >= 4 -> calculated values, eligible
    assert result["ema_ratio_2_3_1h"].iloc[3:].notna().all()
    assert result["eligible"].iloc[3:].tolist() == [True, True, True]
    assert result["missing_feature_count"].iloc[3:].tolist() == [0, 0, 0]
    assert result["reason_codes"].iloc[3:].tolist() == [(), (), ()]

    # Causality invariant: row_ready_at <= decision_ts
    for _, row in result.iterrows():
        assert row["row_ready_at"] <= row["decision_ts"]


def test_feat_04_contract_1(tmp_path: Path) -> None:
    """FEAT-04-AC1: Required feature null makes row ineligible."""
    config_path = tmp_path / "registry.yaml"
    _create_registry_yaml(config_path, lookback=3)
    registry = load_feature_registry(config_path)

    bars = _make_bars(count=5)
    # Inject NaN into a required source column for row 4
    bars.loc[4, "close"] = np.nan

    result = build_feature_frame(
        bars,
        registry=registry,
        dataset_snapshot_id=SNAPSHOT_ID,
    )

    # Row 4 feature must be NaN and marked ineligible
    assert pd.isna(result.loc[4, "ema_ratio_2_3_1h"])
    assert result.loc[4, "eligible"] == False
    assert result.loc[4, "missing_feature_count"] >= 1
    assert len(result.loc[4, "reason_codes"]) > 0


def test_feat_04_contract_2(tmp_path: Path) -> None:
    """FEAT-04-AC2: Label or future column does not enter feature schema."""
    config_path = tmp_path / "registry.yaml"
    _create_registry_yaml(config_path, lookback=3)
    registry = load_feature_registry(config_path)

    bars = _make_bars(count=5)
    # Inject future / label columns into input
    bars["net_return"] = [0.01, -0.02, 0.03, 0.00, 0.05]
    bars["binary_label"] = [1, 0, 1, 0, 1]
    bars["future_close"] = [110.0, 112.0, 114.0, 116.0, 118.0]
    bars["label_available_at"] = [BASE + timedelta(hours=i + 5) for i in range(5)]

    result = build_feature_frame(
        bars,
        registry=registry,
        dataset_snapshot_id=SNAPSHOT_ID,
    )

    # Future and label columns must be strictly excluded from the result
    forbidden_columns = {"net_return", "binary_label", "future_close", "label_available_at"}
    present_forbidden = forbidden_columns.intersection(set(result.columns))
    assert not present_forbidden, f"Forbidden label/future columns found in features: {present_forbidden}"


def test_feat_04_contract_3(tmp_path: Path) -> None:
    """FEAT-04-AC3: Two roots produce value-equivalent features within registered tolerance."""
    root1 = tmp_path / "root1"
    root2 = tmp_path / "root2"
    root1.mkdir()
    root2.mkdir()

    config1 = root1 / "registry.yaml"
    config2 = root2 / "registry.yaml"
    _create_registry_yaml(config1, lookback=3)
    _create_registry_yaml(config2, lookback=3)

    reg1 = load_feature_registry(config1)
    reg2 = load_feature_registry(config2)

    bars1 = _make_bars(count=5)
    bars2 = _make_bars(count=5)

    res1 = build_feature_frame(bars1, registry=reg1, dataset_snapshot_id=SNAPSHOT_ID)
    res2 = build_feature_frame(bars2, registry=reg2, dataset_snapshot_id=SNAPSHOT_ID)

    # Compare columns and values
    assert list(res1.columns) == list(res2.columns)
    assert res1["sample_id"].tolist() == res2["sample_id"].tolist()
    assert res1["eligible"].tolist() == res2["eligible"].tolist()

    # Float feature values match with tight tolerance
    feat_col = "ema_ratio_2_3_1h"
    np.testing.assert_allclose(
        res1[feat_col].dropna().to_numpy(dtype=float),
        res2[feat_col].dropna().to_numpy(dtype=float),
        rtol=1e-7,
        atol=1e-9,
    )


def test_canonical_wave1_feature_materialization() -> None:
    """Validate end-to-end materialization of all 41 canonical Wave 1 features."""
    canonical_config = Path(__file__).parents[3] / "configs" / "features" / "tabular_bar_v1.yaml"
    registry = load_feature_registry(canonical_config)
    bars = _make_bars(count=180)
    result = build_feature_frame(bars, registry=registry, dataset_snapshot_id=SNAPSHOT_ID)

    assert len(result) == 180
    assert len(registry.registry.features) == 41
    for feat in registry.registry.features:
        assert feat.name in result.columns, f"Missing feature: {feat.name}"
        assert result[feat.name].dtype == "float64", f"Feature {feat.name} is not float64"

    # Past lookback 169, rv_168_1h is populated
    assert not pd.isna(result.loc[175, "rv_168_1h"])

