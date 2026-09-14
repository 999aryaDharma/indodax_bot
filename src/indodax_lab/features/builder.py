"""Immutable feature materialization and sample-level causality enforcement (FEAT-04)."""

from __future__ import annotations

import hashlib
import importlib
import inspect
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from indodax_lab.features.context import point_in_time_market_context
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
    raw = f"{pair}:{decision_ts.isoformat()}:{dataset_snapshot_id}:{feature_set_id}:{feature_set_version}"
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
    df_bars = bars.copy()
    if "is_closed" in df_bars.columns:
        df_bars = df_bars[df_bars["is_closed"] == True].copy()

    # Drop any input columns that are forbidden label/future columns
    drop_cols = [c for c in df_bars.columns if _is_forbidden(c)]
    if drop_cols:
        df_bars = df_bars.drop(columns=drop_cols)

    # Normalize timestamps
    df_bars["open_time"] = pd.to_datetime(df_bars["open_time"], utc=True)
    df_bars["close_time"] = pd.to_datetime(df_bars["close_time"], utc=True)
    if "available_at" in df_bars.columns:
        df_bars["available_at"] = pd.to_datetime(df_bars["available_at"], utc=True)
    else:
        df_bars["available_at"] = df_bars["close_time"]

    # Process by pair to enforce causality and isolated warmup
    processed_pairs: list[pd.DataFrame] = []

    for pair, pair_bars in df_bars.groupby("pair", sort=False):
        p_bars = pair_bars.sort_values("close_time").copy().reset_index(drop=True)
        n_rows = len(p_bars)

        feature_values: dict[str, pd.Series] = {}
        warmup_flags: dict[str, list[bool]] = {}

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

            raw_series = func(**kwargs)
            feat_series = pd.Series(raw_series, index=p_bars.index, dtype="float64")

            # Check if source columns have missing values
            valid_src = [col for col in feat.source_columns if col in p_bars.columns]
            if valid_src:
                source_has_na = p_bars[valid_src].isna().any(axis=1)
                feat_series = feat_series.mask(source_has_na, np.nan)

            # Apply warmup mask based on configured lookback_bars
            # Row pos (0-indexed) has pos + 1 available bars in window
            warmup_mask = [((pos + 1) < feat.lookback_bars) for pos in range(n_rows)]
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
            "row_ready_at": p_bars["available_at"],
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
        final_df = point_in_time_market_context(final_df, universe)

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
    ]
    if "universe_snapshot_id" in final_df.columns:
        meta_cols.append("universe_snapshot_id")

    feature_cols = [f.name for f in reg.features]
    final_cols = meta_cols + [c for c in feature_cols if c not in meta_cols]

    return final_df[final_cols]
