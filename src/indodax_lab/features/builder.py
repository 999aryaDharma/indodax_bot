"""Immutable feature materialization and sample-level causality enforcement (FEAT-04)."""

from __future__ import annotations

import hashlib
import importlib
import inspect
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from indodax_lab.features.context import point_in_time_market_context, _closed_source, asof_join_features
from indodax_lab.features.registry import (
    FeatureDefinition,
    FeatureRegistry,
    LoadedFeatureRegistry,
    MissingPolicy,
)


ALLOWED_MODULES = {
    "indodax_lab.features.technical",
    "indodax_lab.features.liquidity",
    "indodax_lab.features.context",
}

FORBIDDEN_PREFIXES = (
    "net_return",
    "binary_label",
    "future_",
    "label_",
    "exit_",
    "entry_",
)


def _compute_sample_id(
    pair: str,
    decision_ts: pd.Timestamp,
    dataset_snapshot_id: str,
    feature_set_id: str,
    feature_set_version: str,
) -> str:
    """Generate a deterministic content-addressed sample identifier."""
    raw = f"features-v2:{pair}:{decision_ts.isoformat()}:{dataset_snapshot_id}:{feature_set_id}:{feature_set_version}"
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_forbidden(name: str) -> bool:
    """Return True if column name represents a future label or execution outcome."""
    lower = name.lower()
    return any(lower.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def build_feature_frame(
    bars: pd.DataFrame,
    *,
    registry: LoadedFeatureRegistry | FeatureRegistry,
    dataset_snapshot_id: str,
    universe: pd.DataFrame | None = None,
    universe_snapshot_id: str | None = None,
    btc_bars: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Construct an immutable feature frame with exact warmup masks and causality guarantees."""
    if isinstance(registry, LoadedFeatureRegistry):
        reg = registry.registry
    elif isinstance(registry, FeatureRegistry):
        reg = registry
    else:
        raise TypeError("registry must be FeatureRegistry or LoadedFeatureRegistry")

    # Reject any feature definition that references forbidden label/future columns
    for feat in reg.features:
        if _is_forbidden(feat.name):
            raise ValueError(f"FORBIDDEN_FEATURE_NAME:{feat.name}")
        for src_col in feat.source_columns:
            if _is_forbidden(src_col):
                raise ValueError(f"FORBIDDEN_SOURCE_COLUMN:{feat.name}:{src_col}")

    # Work on a copy and sanitize
    df_bars = _closed_source(bars)
    if "pair" not in df_bars or df_bars["pair"].isna().any():
        raise ValueError("PAIR_REQUIRED")

    # Drop any input columns that are forbidden label/future columns
    drop_cols = [c for c in df_bars.columns if _is_forbidden(c)]
    if drop_cols:
        df_bars = df_bars.drop(columns=drop_cols)

    # Normalize timestamps
    df_bars["open_time"] = pd.to_datetime(df_bars["open_time"], utc=True)
    df_bars["close_time"] = pd.to_datetime(df_bars["close_time"], utc=True)
    if "available_at" in df_bars.columns:
        df_bars["available_at"] = pd.to_datetime(df_bars["available_at"], utc=True)

    # Process by pair to enforce causality and isolated warmup
    processed_pairs: list[pd.DataFrame] = []

    for pair, pair_bars in df_bars.groupby("pair", sort=False):
        if not pair_bars["close_time"].is_monotonic_increasing or pair_bars["close_time"].duplicated().any():
            raise ValueError("STRICT_BAR_CHRONOLOGY_REQUIRED")
        p_bars = pair_bars.sort_values("close_time").copy().reset_index(drop=True)
        n_rows = len(p_bars)
        breaks = p_bars["open_time"].ne(p_bars["close_time"].shift())
        if "session_id" in p_bars:
            breaks |= p_bars["session_id"].ne(p_bars["session_id"].shift())
        segments = breaks.cumsum()
        row_ready = p_bars["available_at"].groupby(segments).cummax()

        feature_values: dict[str, pd.Series] = {}
        warmup_flags: dict[str, list[bool]] = {}
        invalid_source = pd.Series(False, index=p_bars.index)

        for feat in reg.features:
            module_name, func_name = feat.implementation.rsplit(":", 1)
            if module_name not in ALLOWED_MODULES:
                raise ValueError(f"DISALLOWED_FEATURE_IMPLEMENTATION:{feat.implementation}")

            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name)

            sig = inspect.signature(func)
            kwargs: dict[str, Any] = dict(feat.params)

            for param_name in sig.parameters:
                if param_name in kwargs:
                    continue
                if param_name in p_bars.columns:
                    kwargs[param_name] = p_bars[param_name]
                elif param_name == "volume" and "base_volume" in p_bars.columns:
                    kwargs[param_name] = p_bars["base_volume"]
                elif param_name == "close" and "close" in p_bars.columns:
                    kwargs[param_name] = p_bars["close"]
                elif param_name == "high" and "high" in p_bars.columns:
                    kwargs[param_name] = p_bars["high"]
                elif param_name == "low" and "low" in p_bars.columns:
                    kwargs[param_name] = p_bars["low"]
                elif param_name == "close_time":
                    kwargs[param_name] = p_bars["close_time"]
                elif param_name == "btc_close" and btc_bars is not None:
                    # Align btc_close if available
                    kwargs[param_name] = None

            benchmark = func_name in {"btc_log_return", "beta_btc"}
            if benchmark:
                if btc_bars is None:
                    kwargs["close" if func_name == "btc_log_return" else "btc_close"] = pd.Series(np.nan, index=p_bars.index)
                else:
                    btc = _closed_source(btc_bars)
                    if "pair" not in btc or not btc["pair"].eq("btc_idr").all():
                        raise ValueError("BTC_BENCHMARK_PAIR_REQUIRED")
                    if not btc["close_time"].is_monotonic_increasing or btc["close_time"].duplicated().any():
                        raise ValueError("BTC_STRICT_CHRONOLOGY_REQUIRED")
                    btc = btc.reset_index(drop=True)
                    btc_segments = btc["open_time"].ne(btc["close_time"].shift()).cumsum()
                    btc["available_at"] = btc["available_at"].groupby(btc_segments).cummax()
                    btc["benchmark"] = pd.to_numeric(btc["close"], errors="coerce")
                    if func_name == "btc_log_return":
                        btc["benchmark"] = btc.groupby(btc_segments)["benchmark"].transform(lambda s: func(s, **feat.params))
                    aligned = asof_join_features(pd.DataFrame({"decision_ts": p_bars["close_time"]}), btc,
                        reg.decision_interval, ["benchmark"], join_mode="btc_benchmark")
                    benchmark_values = aligned["benchmark"]
                    kwargs["close" if func_name == "btc_log_return" else "btc_close"] = benchmark_values
                    row_ready = pd.concat([row_ready, aligned["benchmark_available_at"]], axis=1).max(axis=1)

            # Reset each transform after a source gap or unusable observation.
            usable = pd.Series(True, index=p_bars.index)
            for col in feat.source_columns:
                if col not in p_bars:
                    usable[:] = False
                elif not pd.api.types.is_datetime64_any_dtype(p_bars[col]):
                    finite_source = np.isfinite(pd.to_numeric(p_bars[col], errors="coerce").astype(float))
                    usable &= finite_source
                    invalid_source |= ~finite_source & p_bars[col].notna()
            for key, value in kwargs.items():
                if isinstance(value, pd.Series) and key == "btc_close":
                    usable &= np.isfinite(value)
            run_breaks = breaks | ~usable | ~usable.shift(fill_value=False)
            runs = run_breaks.cumsum()
            feat_series = pd.Series(np.nan, index=p_bars.index, dtype="float64")
            warmup_mask = [True] * n_rows
            for _, indexes in p_bars.loc[usable].groupby(runs).groups.items():
                part_kwargs = {key: value.loc[indexes] if isinstance(value, pd.Series) else value for key, value in kwargs.items()}
                if func_name == "btc_log_return" and btc_bars is not None:
                    calculated = benchmark_values.loc[indexes]
                else:
                    calculated = pd.Series(func(**part_kwargs), index=indexes, dtype="float64")
                calculated = calculated.shift(feat.lag_bars)
                feat_series.loc[indexes] = calculated
                for count, idx in enumerate(indexes, start=1):
                    warmup_mask[idx] = count < feat.lookback_bars + feat.lag_bars
            feat_series = feat_series.where(np.isfinite(feat_series))

            # Check if source columns have missing values
            valid_src = [col for col in feat.source_columns if col in p_bars.columns]
            if valid_src:
                source_has_na = p_bars[valid_src].isna().any(axis=1)
                feat_series = feat_series.mask(source_has_na, np.nan)

            # Apply warmup mask based on configured lookback_bars
            # Row pos (0-indexed) has pos + 1 available bars in window
            for pos, in_warmup in enumerate(warmup_mask):
                if in_warmup:
                    feat_series.iloc[pos] = np.nan

            feature_values[feat.name] = feat_series
            warmup_flags[feat.name] = warmup_mask

        # Build row-level eligibility, missing count, and reason codes
        eligible_list: list[bool] = []
        missing_count_list: list[int] = []
        reasons_list: list[tuple[str, ...]] = []

        for pos in range(n_rows):
            pos_reasons: list[str] = []
            missing_count = 0

            for feat in reg.features:
                val = feature_values[feat.name].iloc[pos]
                is_missing = pd.isna(val)

                if is_missing:
                    if feat.missing_policy == MissingPolicy.DROP_SAMPLE_UNTIL_WARM:
                        missing_count += 1
                        if warmup_flags[feat.name][pos]:
                            if "INSUFFICIENT_LOOKBACK" not in pos_reasons:
                                pos_reasons.append("INSUFFICIENT_LOOKBACK")
                        else:
                            if "MISSING_REQUIRED_FEATURE" not in pos_reasons:
                                pos_reasons.append("MISSING_REQUIRED_FEATURE")

            is_eligible = (missing_count == 0) and (len(pos_reasons) == 0)
            if invalid_source.iloc[pos]:
                pos_reasons.append("INVALID_SOURCE_VALUE")
                is_eligible = False
            if row_ready.iloc[pos] > p_bars.loc[pos, "close_time"]:
                pos_reasons.append("SOURCE_NOT_AVAILABLE")
                is_eligible = False
            eligible_list.append(is_eligible)
            missing_count_list.append(missing_count)
            reasons_list.append(tuple(pos_reasons))

        # Build output columns for pair
        meta_dict: dict[str, Any] = {
            "pair": p_bars["pair"],
            "decision_ts": p_bars["close_time"],
            "decision_interval": reg.decision_interval,
            "feature_set_id": reg.feature_set_id,
            "feature_set_version": reg.version,
            "dataset_snapshot_id": dataset_snapshot_id,
            "row_ready_at": row_ready,
            "temporal_contract_version": "features-v2",
            "readiness_policy": "session_history_max",
            "eligible": eligible_list,
            "missing_feature_count": missing_count_list,
            "reason_codes": reasons_list,
            "quality_flags": [() for _ in range(n_rows)],
        }

        if universe_snapshot_id is not None:
            meta_dict["universe_snapshot_id"] = universe_snapshot_id

        # Compute sample_id
        meta_dict["sample_id"] = [
            _compute_sample_id(
                pair=str(p_bars.loc[pos, "pair"]),
                decision_ts=p_bars.loc[pos, "close_time"],
                dataset_snapshot_id=dataset_snapshot_id,
                feature_set_id=reg.feature_set_id,
                feature_set_version=reg.version,
            )
            for pos in range(n_rows)
        ]

        pair_result = pd.DataFrame(meta_dict)
        for feat in reg.features:
            pair_result[feat.name] = feature_values[feat.name]

        processed_pairs.append(pair_result)

    final_df = pd.concat(processed_pairs, ignore_index=True)

    # If universe provided, enrich cross-sectional metrics
    if universe is not None and not universe.empty:
        context_names = {"tier_momentum_rank_24_1h", "market_breadth_pos_24_1h", "market_rv_median_24_1h"}
        required_local = [f.name for f in reg.features if f.missing_policy == MissingPolicy.DROP_SAMPLE_UNTIL_WARM and f.name not in context_names]
        final_df["eligible"] = (np.isfinite(final_df[required_local]).all(axis=1)
            & final_df["row_ready_at"].le(final_df["decision_ts"])
            & ~final_df["reason_codes"].map(lambda r: "INVALID_SOURCE_VALUE" in r))
        final_df = point_in_time_market_context(final_df, universe)
        required_all = [f.name for f in reg.features if f.missing_policy == MissingPolicy.DROP_SAMPLE_UNTIL_WARM]
        final_df["missing_feature_count"] = (~np.isfinite(final_df[required_all])).sum(axis=1)
        final_df["eligible"] &= final_df["missing_feature_count"].eq(0)
        final_df["reason_codes"] = [tuple(r for r in reasons if r not in {"MISSING_REQUIRED_FEATURE", "INSUFFICIENT_LOOKBACK"})
            + (("MISSING_REQUIRED_FEATURE",) if missing else ())
            for reasons, missing in zip(final_df["reason_codes"], final_df["missing_feature_count"])]

    # Enforce canonical metadata ordering first, then feature definitions
    meta_cols = [
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
        "temporal_contract_version",
        "readiness_policy",
    ]
    if "universe_snapshot_id" in final_df.columns:
        meta_cols.append("universe_snapshot_id")
    for column in ("feature_eligible", "universe_eligible", "universe_available_at"):
        if column in final_df:
            meta_cols.append(column)

    feature_cols = [f.name for f in reg.features]
    final_cols = meta_cols + [c for c in feature_cols if c not in meta_cols]

    return final_df[final_cols]
