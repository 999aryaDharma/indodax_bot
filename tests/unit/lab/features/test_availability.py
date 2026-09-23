"""Availability, point-in-time universe, and warmup leakage tests (FEAT-03)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from indodax_lab.features.context import asof_join_features, point_in_time_market_context
from indodax_lab.features.registry import load_feature_registry


BASE = datetime(2024, 1, 1, tzinfo=UTC)
IDENTITY = "sha256:" + "a" * 64


def test_context_preserves_feature_and_universe_eligibility():
    features = pd.DataFrame({"pair": ["a_idr", "b_idr"], "decision_ts": [BASE] * 2,
        "row_ready_at": [BASE] * 2, "eligible": [True, False],
        "reason_codes": [(), ("MISSING_REQUIRED_FEATURE",)], "log_ret_24_1h": [.1, .9]})
    universe = pd.DataFrame({"pair": ["a_idr", "b_idr"], "available_at": [BASE] * 2,
        "eligible": [True, True], "tier": ["BIG_CAP"] * 2, "universe_snapshot_id": ["u"] * 2})
    result = point_in_time_market_context(features, universe)
    assert result["eligible"].tolist() == [True, False]
    assert result["universe_eligible"].tolist() == [True, True]
    assert result["universe_available_at"].tolist() == [BASE, BASE]
    assert result.loc[0, "tier_momentum_rank_24_1h"] == 1.


@pytest.mark.parametrize("column", ["row_ready_at", "eligible"])
def test_context_requires_feature_evidence(column):
    features = pd.DataFrame({"pair": ["btc_idr"], "decision_ts": [BASE],
        "row_ready_at": [BASE], "eligible": [True]}).drop(columns=column)
    universe = pd.DataFrame({"pair": ["btc_idr"], "available_at": [BASE],
        "eligible": [True], "tier": ["BIG_CAP"], "universe_snapshot_id": ["u"]})
    with pytest.raises(ValueError, match="REQUIRED"):
        point_in_time_market_context(features, universe)


@pytest.mark.parametrize("column", ["is_closed", "available_at", "close_time"])
def test_asof_rejects_missing_closed_evidence(column):
    with pytest.raises(ValueError, match="REQUIRED"):
        asof_join_features(pd.DataFrame({"pair": ["btc_idr"], "decision_ts": [BASE]}),
            _bars().drop(columns=column), "1h", ["close"])


def _minimal_config(path: Path) -> None:
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
        "    lookback_bars: 4\n"
        "    availability: closed_bar\n"
        "    lag_bars: 0\n"
        "    dtype: float64\n"
        "    missing_policy: drop_sample_until_warm\n"
        "    normalization: unitless_ratio\n"
        "    monotonicity: none\n",
        encoding="utf-8",
    )


def _bars(count: int = 5) -> pd.DataFrame:
    rows = []
    for index in range(count):
        open_time = BASE + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1)
        close = 100.0 + index
        rows.append(
            {
                "pair": "btc_idr",
                "interval": "1h",
                "bar_id": f"bar-{index}",
                "open_time": open_time,
                "close_time": close_time,
                "available_at": close_time,
                "is_closed": True,
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "base_volume": 10.0 + index,
                "quote_volume": (10.0 + index) * close,
                "quality_flags": (),
            }
        )
    return pd.DataFrame(rows)


def test_asof_join_uses_only_available_complete_4h_and_daily_bars() -> None:
    """A future or explicitly partial higher-timeframe bar cannot replace the last closed bar."""
    decisions = pd.DataFrame(
        {"pair": ["btc_idr"] * 3, "decision_ts": [BASE + timedelta(hours=h) for h in (4, 7, 8)]}
    )
    decisions.loc[0, "decision_ts"] += timedelta(minutes=5)
    decisions.loc[2, "decision_ts"] += timedelta(minutes=5)
    source_4h = pd.DataFrame(
        [
            {
                "pair": "btc_idr",
                "open_time": BASE,
                "close_time": BASE + timedelta(hours=4),
                "available_at": BASE + timedelta(hours=4, minutes=5),
                "is_closed": True,
                "trend_4h": 0.1,
            },
            {
                "pair": "btc_idr",
                "open_time": BASE + timedelta(hours=4),
                "close_time": BASE + timedelta(hours=8),
                "available_at": BASE + timedelta(hours=6),
                "is_closed": False,
                "trend_4h": 9.9,
            },
            {
                "pair": "btc_idr",
                "open_time": BASE + timedelta(hours=4),
                "close_time": BASE + timedelta(hours=8),
                "available_at": BASE + timedelta(hours=8, minutes=5),
                "is_closed": True,
                "trend_4h": 0.2,
            },
        ]
    )
    joined = asof_join_features(decisions, source_4h, interval="4h", value_columns=("trend_4h",))
    assert joined["trend_4h"].tolist() == [0.1, 0.1, 0.2]
    assert (joined["trend_4h_available_at"] <= joined["decision_ts"]).all()

    daily_decision = pd.DataFrame({"pair": ["btc_idr"], "decision_ts": [BASE + timedelta(days=1)]})
    daily = pd.DataFrame(
        [
            {
                "pair": "btc_idr",
                "open_time": BASE - timedelta(days=1),
                "close_time": BASE,
                "available_at": BASE,
                "is_closed": True,
                "trend_1d": 0.3,
            },
            {
                "pair": "btc_idr",
                "open_time": BASE,
                "close_time": BASE + timedelta(days=1),
                "available_at": BASE + timedelta(hours=12),
                "is_closed": False,
                "trend_1d": 8.8,
            },
        ]
    )
    daily_joined = asof_join_features(daily_decision, daily, interval="1d", value_columns=("trend_1d",))
    assert daily_joined.loc[0, "trend_1d"] == 0.3


def test_point_in_time_rank_and_breadth_ignore_ineligible_and_future_universe_rows() -> None:
    """Today's later eligibility must not rewrite the eligible cross-section at decision time."""
    decision = BASE + timedelta(hours=12)
    features = pd.DataFrame(
        {
            "decision_ts": [decision] * 4,
            "pair": ["a_idr", "b_idr", "c_idr", "d_idr"],
            "log_ret_24_1h": [0.1, 0.2, -0.1, 4.0],
            "rv_24_1h": [0.03, 0.02, 0.05, 9.0],
            "row_ready_at": [decision] * 4,
            "eligible": [True] * 4,
        }
    )
    universe = pd.DataFrame(
        [
            {
                "pair": "a_idr",
                "tier": "SMALL_CAP",
                "eligible": True,
                "listed_at": BASE - timedelta(days=100),
                "available_at": decision - timedelta(hours=2),
                "universe_snapshot_id": "u-old",
            },
            {
                "pair": "b_idr",
                "tier": "SMALL_CAP",
                "eligible": True,
                "listed_at": BASE - timedelta(days=100),
                "available_at": decision - timedelta(hours=2),
                "universe_snapshot_id": "u-old",
            },
            {
                "pair": "c_idr",
                "tier": "BIG_CAP",
                "eligible": True,
                "listed_at": BASE - timedelta(days=100),
                "available_at": decision - timedelta(hours=2),
                "universe_snapshot_id": "u-old",
            },
            {
                "pair": "c_idr",
                "tier": "BIG_CAP",
                "eligible": False,
                "listed_at": BASE - timedelta(days=100),
                "available_at": decision + timedelta(hours=1),
                "universe_snapshot_id": "u-future",
            },
            {
                "pair": "d_idr",
                "tier": "SMALL_CAP",
                "eligible": False,
                "listed_at": BASE - timedelta(days=100),
                "available_at": decision - timedelta(hours=2),
                "universe_snapshot_id": "u-old",
            },
            {
                "pair": "d_idr",
                "tier": "SMALL_CAP",
                "eligible": True,
                "listed_at": BASE - timedelta(days=100),
                "available_at": decision + timedelta(hours=1),
                "universe_snapshot_id": "u-future",
            },
        ]
    )

    result = point_in_time_market_context(features, universe)
    by_pair = result.set_index("pair")

    assert by_pair.loc["a_idr", "tier_momentum_rank_24_1h"] == 0.5
    assert by_pair.loc["b_idr", "tier_momentum_rank_24_1h"] == 1.0
    assert by_pair.loc["c_idr", "tier_momentum_rank_24_1h"] == 1.0
    assert pd.isna(by_pair.loc["d_idr", "tier_momentum_rank_24_1h"])
    assert by_pair.loc["a_idr", "market_breadth_pos_24_1h"] == pytest.approx(2 / 3)
    assert by_pair.loc["a_idr", "market_rv_median_24_1h"] == 0.03
    assert by_pair.loc["c_idr", "universe_snapshot_id"] == "u-old"


# Explicit AC mappings for FEAT-03
def test_feat_03_valid_contract() -> None:
    """FEAT-03-AC0: Fitur BTC, rank dan breadth hanya memakai universe dan closed bars yang tersedia saat keputusan."""
    decision_ts = BASE + timedelta(hours=6)
    features = pd.DataFrame(
        {
            "decision_ts": [decision_ts] * 2,
            "pair": ["btc_idr", "eth_idr"],
            "log_ret_24_1h": [0.05, 0.10],
            "rv_24_1h": [0.02, 0.04],
            "row_ready_at": [decision_ts] * 2,
            "eligible": [True] * 2,
        }
    )
    universe = pd.DataFrame(
        [
            {
                "pair": "btc_idr",
                "tier": "BIG_CAP",
                "eligible": True,
                "available_at": decision_ts - timedelta(hours=1),
                "universe_snapshot_id": "u-pit",
            },
            {
                "pair": "eth_idr",
                "tier": "BIG_CAP",
                "eligible": True,
                "available_at": decision_ts - timedelta(hours=1),
                "universe_snapshot_id": "u-pit",
            },
        ]
    )
    res = point_in_time_market_context(features, universe)
    by_pair = res.set_index("pair")
    assert by_pair.loc["btc_idr", "tier_momentum_rank_24_1h"] == 0.5
    assert by_pair.loc["eth_idr", "tier_momentum_rank_24_1h"] == 1.0
    assert by_pair.loc["btc_idr", "market_breadth_pos_24_1h"] == 1.0
    assert by_pair.loc["btc_idr", "market_rv_median_24_1h"] == 0.03


def test_feat_03_contract_1() -> None:
    """FEAT-03-AC1: Daily atau 4h partial bar dikecualikan."""
    test_asof_join_uses_only_available_complete_4h_and_daily_bars()


def test_feat_03_contract_2() -> None:
    """FEAT-03-AC2: Future listing dan future cap tidak mengubah rank historis."""
    test_point_in_time_rank_and_breadth_ignore_ineligible_and_future_universe_rows()


def test_feat_03_contract_3() -> None:
    """FEAT-03-AC3: Missing BTC history menghasilkan null bukan backfill."""
    # Decisions at T0, T1, T2
    decisions = pd.DataFrame(
        {
            "pair": ["eth_idr"] * 3,
            "decision_ts": [
                BASE,
                BASE + timedelta(hours=1),
                BASE + timedelta(hours=2),
            ],
        }
    )
    # BTC history only starts at T2 (T0 and T1 are missing)
    btc_series = pd.DataFrame(
        [
            {
                "pair": "btc_idr",
                "open_time": BASE + timedelta(hours=1),
                "close_time": BASE + timedelta(hours=2),
                "available_at": BASE + timedelta(hours=2),
                "is_closed": True,
                "btc_ret": 0.02,
            }
        ]
    )
    joined = asof_join_features(
        decisions, btc_series, interval="1h", value_columns=("btc_ret",), join_mode="btc_benchmark"
    )

    # T0 and T1 must be NaN (strictly missing, never backfilled from T2)
    assert pd.isna(joined.loc[0, "btc_ret"])
    assert pd.isna(joined.loc[1, "btc_ret"])
    # T2 is available
    assert joined.loc[2, "btc_ret"] == 0.02


def test_asof_join_never_broadcasts_single_pair_source_to_other_pairs() -> None:
    decisions = pd.DataFrame({"pair": ["eth_idr"], "decision_ts": [BASE + timedelta(hours=2)]})
    source = _bars(1).assign(pair="btc_idr", close=123.0)

    joined = asof_join_features(decisions, source, "1h", ["close"])

    assert pd.isna(joined.loc[0, "close"])


def test_asof_join_filters_each_pair_in_mixed_decision_batch() -> None:
    decisions = pd.DataFrame({
        "pair": ["eth_idr", "btc_idr"],
        "decision_ts": [BASE + timedelta(hours=2)] * 2,
    })
    source = _bars(1).assign(pair="btc_idr", close=123.0)

    joined = asof_join_features(decisions, source, "1h", ["close"])

    assert pd.isna(joined.loc[0, "close"])
    assert joined.loc[1, "close"] == 123.0


def test_asof_join_requires_explicit_mode_when_only_one_side_has_pair() -> None:
    decisions = pd.DataFrame({"decision_ts": [BASE + timedelta(hours=2)]})
    source = _bars(1).assign(pair="btc_idr", close=123.0)

    with pytest.raises(ValueError, match="PAIR_JOIN_MODE_REQUIRED"):
        asof_join_features(decisions, source, "1h", ["close"])


def test_warmup_rows_stay_null_with_reason_and_never_backfill(tmp_path: Path) -> None:
    """EMA's early numerical seed cannot make a row eligible before registry lookback (FEAT-04)."""
    pytest.importorskip("indodax_lab.features.builder", reason="FEAT-04 builder capability")
    from indodax_lab.features.builder import build_feature_frame

    config = tmp_path / "registry.yaml"
    _minimal_config(config)
    loaded = load_feature_registry(config)

    result = build_feature_frame(
        _bars(), registry=loaded, dataset_snapshot_id=IDENTITY
    )

    assert result["ema_ratio_2_3_1h"].iloc[:3].isna().all()
    assert result["reason_codes"].iloc[:3].tolist() == [
        ("INSUFFICIENT_LOOKBACK",),
        ("INSUFFICIENT_LOOKBACK",),
        ("INSUFFICIENT_LOOKBACK",),
    ]
    assert result["eligible"].tolist() == [False, False, False, True, True]
    assert result["missing_feature_count"].tolist() == [1, 1, 1, 0, 0]
    assert result.loc[3, "row_ready_at"] <= result.loc[3, "decision_ts"]


def test_build_features_cli_dry_run_is_offline_and_non_mutating(tmp_path: Path) -> None:
    """Dry-run builds the real feature frame but must not create its requested output (FEAT-04)."""
    pytest.importorskip("indodax_lab.cli.build_features", reason="FEAT-04 CLI capability")
    from indodax_lab.cli.build_features import main

    config = tmp_path / "registry.yaml"
    bars_path = tmp_path / "bars.csv"
    output = tmp_path / "features.csv"
    _minimal_config(config)
    bars = _bars()
    for column in ("open_time", "close_time", "available_at"):
        bars[column] = bars[column].map(lambda value: value.isoformat())
    bars.to_csv(bars_path, index=False)
    stdout = StringIO()

    result = main(
        [
            "--config", str(config),
            "--bars", str(bars_path),
            "--dataset-snapshot-id", IDENTITY,
            "--output", str(output),
            "--dry-run",
        ],
        stdout=stdout,
    )

    assert result == 0
    assert stdout.getvalue() == "rows=5 eligible=2 dry_run=true\n"
    assert not output.exists()


def test_build_features_cli_persists_parquet_and_companion_manifest(tmp_path: Path) -> None:
    """Non-dry-run build_features creates output file and authoritative companion manifest JSON."""
    import json
    from indodax_lab.cli.build_features import main

    config = tmp_path / "registry.yaml"
    bars_path = tmp_path / "bars.parquet"
    output = tmp_path / "out_features.parquet"
    _minimal_config(config)

    bars = _bars()
    # Intentionally set available_at to future download time (e.g. 2026) to test --historical-availability
    bars["available_at"] = BASE + timedelta(days=365 * 2)
    bars.to_parquet(bars_path, index=False)

    stdout = StringIO()
    result = main(
        [
            "--config", str(config),
            "--bars", str(bars_path),
            "--dataset-snapshot-id", IDENTITY,
            "--output", str(output),
            "--historical-availability",
        ],
        stdout=stdout,
    )

    assert result == 0
    assert output.exists()
    manifest_path = tmp_path / "out_features_manifest.json"
    assert manifest_path.exists()

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["manifest_version"] == "1.0.0"
    assert manifest_data["dataset_snapshot_id"] == IDENTITY
    assert manifest_data["total_rows"] == 5
    assert manifest_data["eligible_rows"] == 2
    assert "output_sha256" in manifest_data
    assert manifest_data["output_file"] == "out_features.parquet"
