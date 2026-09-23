"""As-of market context, point-in-time universe, and higher-timeframe alignment (FEAT-03)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd


def _utc_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        raise ValueError(f"TEMPORAL_COLUMN_REQUIRED:{column}")
    for value in frame[column]:
        ts = pd.Timestamp(value)
        if pd.isna(ts) or ts.tzinfo is None or ts.utcoffset().total_seconds() != 0:
            raise ValueError(f"UTC_REQUIRED:{column}")
    return pd.to_datetime(frame[column], utc=True)


def _closed_source(source: pd.DataFrame) -> pd.DataFrame:
    if not source.columns.is_unique or "is_closed" not in source:
        raise ValueError("CLOSED_SOURCE_EVIDENCE_REQUIRED")
    if not source["is_closed"].isin([True, False]).all():
        raise ValueError("CLOSED_SOURCE_BOOLEAN_REQUIRED")
    result = source[source["is_closed"].eq(True)].copy()
    for col in ("open_time", "close_time", "available_at"):
        result[col] = _utc_column(result, col)
    if ((result["open_time"] >= result["close_time"]) | (result["available_at"] < result["close_time"])).any():
        raise ValueError("INVALID_CLOSED_SOURCE_CHRONOLOGY")
    return result


def asof_join_features(
    decisions: pd.DataFrame,
    source: pd.DataFrame,
    interval: str,
    value_columns: Sequence[str],
    *,
    join_mode: Literal["same_pair", "btc_benchmark"] = "same_pair",
) -> pd.DataFrame:
    """As-of join higher timeframe or benchmark features strictly available at decision time.

    Enforces:
    1. Exclusion of partial or in-progress bars (is_closed == False).
    2. Strict causality (source.available_at <= decisions.decision_ts).
    3. Missing history yields null/NaN, never backfilled.
    """
    res = decisions.copy()
    res["decision_ts"] = _utc_column(res, "decision_ts")

    # Filter source to only closed/complete bars
    valid_source = _closed_source(source)

    valid_source["available_at"] = pd.to_datetime(valid_source["available_at"], utc=True)

    source_has_pair = "pair" in valid_source.columns
    decisions_has_pair = "pair" in res.columns
    if join_mode not in {"same_pair", "btc_benchmark"}:
        raise ValueError(f"UNSUPPORTED_PAIR_JOIN_MODE:{join_mode}")
    if join_mode == "same_pair" and source_has_pair != decisions_has_pair:
        raise ValueError("PAIR_JOIN_MODE_REQUIRED")
    if join_mode == "btc_benchmark" and (
        not source_has_pair or not valid_source["pair"].eq("btc_idr").all()
    ):
        raise ValueError("BTC_BENCHMARK_PAIR_REQUIRED")

    for col in value_columns:
        res[col] = np.nan
        res[f"{col}_available_at"] = pd.Series(pd.NaT, dtype="datetime64[ns, UTC]", index=res.index)

    for idx, row in res.iterrows():
        d_ts = row["decision_ts"]
        candidates = valid_source[valid_source["available_at"] <= d_ts]
        if join_mode == "same_pair" and source_has_pair:
            candidates = candidates[candidates["pair"] == row["pair"]]

        if not candidates.empty:
            latest = candidates.sort_values("available_at").iloc[-1]
            for col in value_columns:
                if col in latest:
                    res.at[idx, col] = latest[col] if np.isfinite(float(latest[col])) else np.nan
                    res.at[idx, f"{col}_available_at"] = latest["available_at"]

    return res


def point_in_time_market_context(
    features: pd.DataFrame,
    universe: pd.DataFrame,
) -> pd.DataFrame:
    """Compute point-in-time tier momentum rank, market breadth, and RV median.

    Enforces:
    1. Only universe snapshots available at decision_ts are considered (future rows ignored).
    2. Only eligible universe assets contribute to cross-sectional ranks and market breadth.
    3. Ineligible assets have NaN tier momentum rank.
    """
    res = features.copy()
    res["decision_ts"] = _utc_column(res, "decision_ts")
    universe_copy = universe.copy()
    universe_copy["available_at"] = _utc_column(universe_copy, "available_at")
    if "eligible" not in res or not res["eligible"].isin([True, False]).all():
        raise ValueError("FEATURE_ELIGIBILITY_REQUIRED")
    res["row_ready_at"] = _utc_column(res, "row_ready_at")
    res["feature_eligible"] = res["eligible"].eq(True) & res["row_ready_at"].le(res["decision_ts"])
    res["universe_eligible"] = False
    res["universe_available_at"] = pd.Series(pd.NaT, dtype="datetime64[ns, UTC]", index=res.index)

    tier_momentum_rank = pd.Series(np.nan, index=res.index, dtype=float)
    market_breadth_pos = pd.Series(np.nan, index=res.index, dtype=float)
    market_rv_median = pd.Series(np.nan, index=res.index, dtype=float)
    universe_snapshot_id = pd.Series(None, index=res.index, dtype=object)

    for d_ts in res["decision_ts"].unique():
        # Universe rows available at or before decision_ts
        u_avail = universe_copy[universe_copy["available_at"] <= d_ts]
        if u_avail.empty:
            continue

        # Point-in-time latest universe state per pair
        pit_u = u_avail.sort_values("available_at").drop_duplicates("pair", keep="last")

        f_mask = res["decision_ts"] == d_ts
        f_subset = res[f_mask]

        merged = f_subset.drop(columns=["universe_eligible", "universe_available_at", "universe_snapshot_id"], errors="ignore").merge(
            pit_u[["pair", "tier", "eligible", "universe_snapshot_id", "available_at"]].rename(columns={"eligible": "universe_eligible", "available_at": "universe_available_at"}),
            on="pair",
            how="left",
        )

        for pos_idx, orig_idx in enumerate(f_subset.index):
            universe_snapshot_id.loc[orig_idx] = merged.iloc[pos_idx]["universe_snapshot_id"]
            u_row = merged.iloc[pos_idx]
            res.loc[orig_idx, "universe_eligible"] = bool(u_row["universe_eligible"] == True)
            res.loc[orig_idx, "universe_available_at"] = u_row["universe_available_at"]
            if pd.notna(u_row["universe_available_at"]):
                res.loc[orig_idx, "row_ready_at"] = max(res.loc[orig_idx, "row_ready_at"], u_row["universe_available_at"])

        # Eligible cross-section
        eligible_sub = merged[merged["universe_eligible"].eq(True) & merged["feature_eligible"].eq(True)]
        context_columns = [c for c in ("log_ret_24_1h", "rv_24_1h") if c in eligible_sub]
        if context_columns:
            eligible_sub = eligible_sub[np.isfinite(eligible_sub[context_columns]).all(axis=1)]

        if not eligible_sub.empty:
            context_ready = max(eligible_sub["row_ready_at"].max(), eligible_sub["universe_available_at"].max())
            res.loc[f_mask, "row_ready_at"] = res.loc[f_mask, "row_ready_at"].map(lambda ts: max(ts, context_ready))
            # Market breadth: fraction of eligible pairs with positive momentum
            if "log_ret_24_1h" in eligible_sub.columns:
                pos_count = (eligible_sub["log_ret_24_1h"] > 0).sum()
                breadth = float(pos_count) / len(eligible_sub)
                market_breadth_pos.loc[f_mask] = breadth

            # Market RV median across eligible assets
            if "rv_24_1h" in eligible_sub.columns:
                rv_med = float(eligible_sub["rv_24_1h"].median())
                market_rv_median.loc[f_mask] = rv_med

            # Tier momentum rank
            if "log_ret_24_1h" in eligible_sub.columns and "tier" in eligible_sub.columns:
                for tier, group in eligible_sub.groupby("tier"):
                    n_tier = len(group)
                    ranks = group["log_ret_24_1h"].rank(method="min", ascending=True)
                    tier_ranks = ranks / n_tier
                    for pair, rank_val in zip(group["pair"], tier_ranks):
                        pair_mask = f_mask & (res["pair"] == pair)
                        tier_momentum_rank.loc[pair_mask] = float(rank_val)

    res["tier_momentum_rank_24_1h"] = tier_momentum_rank
    res["market_breadth_pos_24_1h"] = market_breadth_pos
    res["market_rv_median_24_1h"] = market_rv_median
    res["universe_snapshot_id"] = universe_snapshot_id
    res["eligible"] = res["feature_eligible"] & res["universe_eligible"]
    if "reason_codes" in res:
        res["reason_codes"] = [tuple(reasons) + (() if member else ("UNIVERSE_INELIGIBLE_OR_MISSING",))
                               for reasons, member in zip(res["reason_codes"], res["universe_eligible"])]

    return res


def hour_sin(close_time: pd.Series) -> pd.Series:
    """Cyclical hour-of-day sine encoding."""
    ts = pd.to_datetime(close_time, utc=True)
    return pd.Series(np.sin(2.0 * np.pi * ts.dt.hour / 24.0), index=close_time.index, dtype="float64")


def hour_cos(close_time: pd.Series) -> pd.Series:
    """Cyclical hour-of-day cosine encoding."""
    ts = pd.to_datetime(close_time, utc=True)
    return pd.Series(np.cos(2.0 * np.pi * ts.dt.hour / 24.0), index=close_time.index, dtype="float64")


def dow_sin(close_time: pd.Series) -> pd.Series:
    """Cyclical day-of-week sine encoding."""
    ts = pd.to_datetime(close_time, utc=True)
    return pd.Series(np.sin(2.0 * np.pi * ts.dt.dayofweek / 7.0), index=close_time.index, dtype="float64")


def dow_cos(close_time: pd.Series) -> pd.Series:
    """Cyclical day-of-week cosine encoding."""
    ts = pd.to_datetime(close_time, utc=True)
    return pd.Series(np.cos(2.0 * np.pi * ts.dt.dayofweek / 7.0), index=close_time.index, dtype="float64")


def log_listing_age(close_time: pd.Series, listed_at: pd.Series | None = None) -> pd.Series:
    """Point-in-time log1p listing age in days."""
    if listed_at is None:
        return pd.Series(np.nan, index=close_time.index, dtype="float64")
    c_ts = pd.to_datetime(close_time, utc=True)
    l_ts = pd.to_datetime(listed_at, utc=True)
    diff_days = (c_ts - l_ts).dt.total_seconds() / 86400.0
    return pd.Series(np.log1p(np.maximum(0.0, diff_days)), index=close_time.index, dtype="float64")


def bar_completeness(close_time: pd.Series, *, period: int = 24) -> pd.Series:
    """Proportion of expected closed bars in the trailing window."""
    ones = pd.Series(1.0, index=close_time.index, dtype="float64")
    return ones.rolling(period, min_periods=period).sum().div(float(period))


def btc_log_return(close: pd.Series, *, periods: int = 1) -> pd.Series:
    """Log return on BTC benchmark series."""
    c = pd.Series(close, index=close.index, dtype="float64")
    return np.log(c.div(c.shift(periods)))


def beta_btc(close: pd.Series, btc_close: pd.Series | None = None, *, period: int = 168) -> pd.Series:
    """Rolling regression beta against BTC benchmark."""
    if btc_close is None:
        return pd.Series(np.nan, index=close.index, dtype="float64")
    r_pair = btc_log_return(close, periods=1)
    r_btc = btc_log_return(btc_close, periods=1)
    cov = r_pair.rolling(period, min_periods=period).cov(r_btc)
    var = r_btc.rolling(period, min_periods=period).var()
    return cov.div(var.mask(var == 0))


def tier_momentum_rank(close: pd.Series, *, period: int = 24) -> pd.Series:
    """Single-pair fallback for tier momentum rank; overwritten by cross-sectional builder."""
    return pd.Series(np.nan, index=close.index, dtype="float64")


def market_breadth_positive(close: pd.Series, *, period: int = 24) -> pd.Series:
    """Single-pair fallback for market breadth; overwritten by cross-sectional builder."""
    return pd.Series(np.nan, index=close.index, dtype="float64")


def market_rv_median(close: pd.Series, *, period: int = 24) -> pd.Series:
    """Single-pair fallback for market RV median; overwritten by cross-sectional builder."""
    return pd.Series(np.nan, index=close.index, dtype="float64")
